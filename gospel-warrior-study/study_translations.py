"""Complete, source-versioned study translations, cached in the app data folder."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import threading
import time
from pathlib import Path

import requests
import local_translator

LANGUAGES = {"fr", "mg"}
PROVIDER = "Google Translate (machine translation)"
_lock = threading.Lock()
_jobs: dict[str, dict] = {}
_request_lock = threading.Lock()
_last_request = 0.0
ENDPOINTS = ('https://translate.google.com/translate_a/single', 'https://translate.googleapis.com/translate_a/single')


def store_connection(directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(directory / 'translations.sqlite3', timeout=30)
    connection.execute('CREATE TABLE IF NOT EXISTS chunks (key TEXT PRIMARY KEY, translated TEXT NOT NULL)')
    connection.execute('CREATE TABLE IF NOT EXISTS catalog (source_key TEXT PRIMARY KEY, study_id TEXT NOT NULL, language TEXT NOT NULL, title TEXT NOT NULL, subtitle TEXT NOT NULL, excerpt TEXT NOT NULL, updated INTEGER NOT NULL)')
    connection.commit()
    return connection


def register_translation(post: dict, payload: dict, directory: Path):
    study = payload['study']
    blocks = [block.strip() for block in re.split(r'\n\s*\n', study['text']) if block.strip()]
    excerpt = next((block for block in blocks if block not in {study['title'], study.get('subtitle', '')} and len(block) > 60), study['text'])[:185]
    with store_connection(directory) as connection:
        connection.execute('INSERT OR REPLACE INTO catalog VALUES (?, ?, ?, ?, ?, ?, ?)',
                           (payload['sourceKey'], str(post['id']), payload['language'], study['title'], study.get('subtitle', ''), excerpt, time.time_ns()))
    connection.close()


def source_key(post: dict, language: str) -> str:
    source = json.dumps([str(post["id"]), post["title"], post.get("subtitle", ""), post["text"], language, 1], ensure_ascii=False)
    return hashlib.sha256(source.encode()).hexdigest()


def chunks(text: str, limit: int = 2800):
    """Keep every source character and split preferentially between paragraphs."""
    while len(text) > limit:
        end = text.rfind("\n\n", 0, limit - 1)
        if end < limit // 3:
            end = text.rfind(" ", 0, limit)
        end = end + (2 if text[end:end + 2] == "\n\n" else 1) if end > 0 else limit
        yield text[:end]
        text = text[end:]
    if text:
        yield text


def translate_text(text: str, language: str, session, deadline: float, directory: Path | None = None, progress=None) -> str:
    translated = []
    for chunk in chunks(text):
        if not chunk.strip():
            translated.append(chunk)
            continue
        if time.monotonic() >= deadline:
            raise TimeoutError("Translation took too long. Please retry.")
        local = local_translator.available(language)
        cache_key = hashlib.sha256((('local-opus-v1:' if local else '') + language + '\0' + chunk.strip()).encode()).hexdigest()
        result = None
        if directory is not None:
            with store_connection(directory) as connection:
                row = connection.execute('SELECT translated FROM chunks WHERE key = ?', (cache_key,)).fetchone()
                if row:
                    result = row[0]
            connection.close()
        if result is None and local:
            result = local_translator.translate(chunk.strip(), language)
            if directory is not None:
                with store_connection(directory) as connection:
                    connection.execute('INSERT OR REPLACE INTO chunks VALUES (?, ?)', (cache_key, result))
                connection.close()
        if result is None:
            last_error = None
            for endpoint in ENDPOINTS:
                try:
                    # Pace requests from both the foreground reader and background
                    # library worker; fail over when one provider host is busy.
                    global _last_request
                    with _request_lock:
                        delay = max(0, .8 - (time.monotonic() - _last_request))
                        if delay:
                            time.sleep(delay)
                        _last_request = time.monotonic()
                    response = session.get(endpoint, params={
                        'client': 'gtx', 'sl': 'en', 'tl': language, 'dt': 't', 'q': chunk.strip(),
                    }, timeout=25)
                    response.raise_for_status()
                    data = response.json()
                    result = ''.join(part[0] for part in data[0] if part and isinstance(part[0], str))
                    if not result.strip():
                        raise ValueError('The translation service returned empty text.')
                    break
                except (requests.RequestException, ValueError, TypeError, IndexError) as error:
                    last_error = error
            if result is None or not result.strip():
                raise last_error or ValueError('No translation returned')
            if directory is not None:
                with store_connection(directory) as connection:
                    connection.execute('INSERT OR REPLACE INTO chunks VALUES (?, ?)', (cache_key, result))
                connection.close()
        # Keep paragraph/chunk boundaries even if the service trims whitespace.
        prefix = re.match(r"^\s*", chunk)[0]
        suffix = re.search(r"\s*$", chunk)[0]
        translated.append(prefix + result.strip() + suffix)
        if progress:
            progress()
    return "".join(translated)


def _translate(post: dict, language: str, key: str, path: Path):
    try:
        deadline = time.monotonic() + 840
        fields = ('title', 'subtitle', 'text')
        total = sum(sum(bool(chunk.strip()) for chunk in chunks(post.get(field) or '')) for field in fields)
        completed = 0

        def progress():
            nonlocal completed
            completed += 1
            with _lock:
                _jobs[key] = {'state': 'pending', 'language': language, 'completedChunks': completed, 'totalChunks': total}

        with requests.Session() as session:
            study = {field: translate_text(post.get(field) or '', language, session, deadline, path.parent, progress) for field in fields}
        payload = {"state": "ready", "language": language, "sourceKey": key, "provider": local_translator.PROVIDER if local_translator.available(language) else PROVIDER, "study": study}
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        temporary.replace(path)
        register_translation(post, payload, path.parent)
    except Exception as error:
        status = getattr(getattr(error, 'response', None), 'status_code', None)
        print(f'[translations] {language} study {post["id"]}: {type(error).__name__}' + (f' (HTTP {status})' if status else ''), flush=True)
        payload = {'state': 'error', 'language': language, 'retryable': True,
                   'error': 'Translation service is busy. Saved progress will resume on retry.' if status == 429 else 'Translation interrupted. Saved progress will resume when the connection is available.'}
    with _lock:
        _jobs[key] = payload


def translation_status(post: dict, language: str, data_directory: Path, *, retry=False) -> dict:
    if language not in LANGUAGES:
        raise ValueError("Choose French (fr) or Malagasy (mg).")
    key = source_key(post, language)
    path = data_directory / "translations" / f"{key}.json"
    with _lock:
        if path.is_file():
            try:
                cached = json.loads(path.read_text(encoding="utf-8"))
                if cached.get("sourceKey") == key and cached.get("state") == "ready" and cached.get("study", {}).get("text"):
                    return cached
            except (ValueError, OSError):
                pass
        if key in _jobs and not (retry and _jobs[key]["state"] == "error"):
            return _jobs[key]
        if sum(job["state"] == "pending" for job in _jobs.values()) >= 2:
            return {"state": "busy", "language": language}
        # Bound memory; complete results remain available on disk.
        if len(_jobs) >= 200:
            for old in list(_jobs):
                if _jobs[old]["state"] != "pending":
                    del _jobs[old]
        _jobs[key] = {"state": "pending", "language": language}
        threading.Thread(target=_translate, args=(dict(post), language, key, path), daemon=True, name="study-translation").start()
        return _jobs[key]
