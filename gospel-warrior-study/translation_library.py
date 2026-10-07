"""Resumable full-library translation with honest full-text coverage counts."""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import study_translations as translations
import local_translator


class TranslationLibrary:
    def __init__(self, directory: Path, get_posts, get_revision, *, start=True):
        self.directory = directory
        self.get_posts = get_posts
        self.get_revision = get_revision
        self.config_path = directory / 'translation-library.json'
        try:
            self.enabled = json.loads(self.config_path.read_text()).get('enabled', True)
        except (OSError, ValueError):
            self.enabled = True
        self.lock = threading.RLock()
        self.wakeup = threading.Event()
        self.stopping = threading.Event()
        self.posts = []
        self.queue = []
        self.keys = {'fr': set(), 'mg': set()}
        self.revision = None
        self.current = None
        self.error = None
        self.next_retry = None
        self.loading = True
        self.thread = threading.Thread(target=self.run, daemon=True, name='translation-library')
        if start:
            self.thread.start()

    def reload(self):
        revision = self.get_revision()
        if revision == self.revision:
            return
        posts = list(self.get_posts())
        queue = [(post, code, translations.source_key(post, code)) for post in posts for code in ('fr', 'mg')]
        keys = {code: {key for _, language, key in queue if language == code} for code in ('fr', 'mg')}
        with self.lock:
            self.posts, self.queue, self.keys, self.revision = posts, queue, keys, revision
            self.loading = False

    def rows(self):
        with translations.store_connection(self.directory / 'translations') as connection:
            rows = connection.execute('SELECT source_key, study_id, language, title, subtitle, excerpt, updated FROM catalog').fetchall()
        connection.close()
        with self.lock:
            return [row for row in rows if row[0] in self.keys.get(row[2], set())]

    def status(self):
        rows = self.rows()
        ready = {code: sum(row[2] == code for row in rows) for code in ('fr', 'mg')}
        with self.lock:
            current = dict(self.current) if self.current else None
            if current:
                with translations._lock:
                    job = translations._jobs.get(current['sourceKey'], {})
                    current.update({key: job[key] for key in ('completedChunks', 'totalChunks') if key in job})
            total = len(self.posts)
            return {'enabled': self.enabled, 'state': 'loading' if self.loading else 'paused' if not self.enabled else 'waiting' if self.next_retry else 'complete' if total and all(count == total for count in ready.values()) else 'preparing',
                    'total': total, 'ready': ready, 'current': current, 'error': self.error, 'nextRetry': self.next_retry,
                    'catalogRevision': f'{self.revision}:{max((row[6] for row in rows), default=0)}',
                    'engine': 'local' if all(local_translator.available(code) for code in ('fr', 'mg')) else 'online'}

    def catalog(self, code):
        if code not in ('fr', 'mg'):
            raise ValueError('Choose French or Malagasy')
        return {'language': code, 'entries': [{'id': row[1], 'sourceKey': row[0], 'title': row[3], 'subtitle': row[4], 'excerpt': row[5]} for row in self.rows() if row[2] == code]}

    def configure(self, enabled):
        if not isinstance(enabled, bool):
            raise ValueError('enabled must be true or false')
        with self.lock:
            self.enabled = enabled
            self.directory.mkdir(parents=True, exist_ok=True)
            temporary = self.config_path.with_suffix('.tmp')
            temporary.write_text(json.dumps({'enabled': enabled}), encoding='utf-8')
            temporary.replace(self.config_path)
        self.wakeup.set()
        return self.status()

    def wait(self, seconds):
        self.wakeup.wait(seconds)
        self.wakeup.clear()

    def close(self):
        self.stopping.set()
        self.wakeup.set()

    def run(self):
        failures = 0
        while not self.stopping.is_set():
            try:
                self.reload()
                if not self.enabled:
                    self.wait(10)
                    continue
                ready = {row[0] for row in self.rows()}
                item = next((item for item in self.queue if item[2] not in ready), None)
                if item is None:
                    with self.lock:
                        self.current, self.error, self.next_retry = None, None, None
                    self.wait(30)
                    continue
                post, code, key = item
                with self.lock:
                    self.current = {'id': str(post['id']), 'title': post['title'], 'language': code, 'sourceKey': key}
                    self.error = None
                    self.next_retry = None
                result = translations.translation_status(post, code, self.directory, retry=True)
                while result['state'] in ('pending', 'busy') and not self.stopping.is_set():
                    self.wait(1)
                    result = translations.translation_status(post, code, self.directory)
                if self.stopping.is_set():
                    return
                if result['state'] == 'ready':
                    # Also repairs catalog metadata for older cached JSON versions.
                    translations.register_translation(post, result, self.directory / 'translations')
                    failures = 0
                    with self.lock:
                        self.current = None
                    continue
                failures += 1
                delay = min(300, 30 * 2 ** min(failures - 1, 4))
                with self.lock:
                    self.error = result.get('error', 'Translation temporarily unavailable.')
                    self.next_retry = time.time() + delay
                self.wait(delay)
            except Exception as error:
                print(f'[translation-library] {type(error).__name__}', flush=True)
                with self.lock:
                    self.error = 'Preparing translations will resume when the local library is available.'
                    self.next_retry = time.time() + 30
                self.wait(30)
