#!/usr/bin/env python3
"""Static web server plus automatic Gospel Warrior archive scheduler."""
from __future__ import annotations

import argparse
import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import updater
import study_translations
import translation_library

HERE = Path(__file__).resolve().parent
update_lock = threading.Lock()
stop_event = threading.Event()
scheduler_wakeup = threading.Event()
scheduler_state = {"nextCheck": None, "serverStarted": None, "schedulerEnabled": True}
_study_lookup_lock = threading.Lock()
_study_lookup_revision = None
_study_lookup = {}
_translation_library = None
_translation_library_lock = threading.Lock()


def find_study(study_id):
    global _study_lookup_revision, _study_lookup
    with _study_lookup_lock:
        revision = archive_revision()
        if revision != _study_lookup_revision:
            _study_lookup = {str(post["id"]): post for post in updater.load_archive()["posts"]}
            _study_lookup_revision = revision
        return _study_lookup.get(str(study_id))


def all_studies():
    find_study(None)
    policy = updater.reader_policy()
    return sorted((post for post in _study_lookup.values() if not updater.reader_excludes(post['id'], post['title'], policy)), key=lambda post: post.get('timestamp', 0), reverse=True)


def get_translation_library():
    global _translation_library
    with _translation_library_lock:
        if _translation_library is None:
            _translation_library = translation_library.TranslationLibrary(updater.HERE, all_studies, archive_revision)
        return _translation_library


def iso(value: datetime | None) -> str | None:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z") if value else None


def read_config() -> dict:
    return {**updater.DEFAULT_CONFIG, **updater.read_json(updater.CONFIG_PATH, {})}


def save_config(changes: dict) -> dict:
    current = read_config()
    previous_enabled = current.get("enabled", True)
    previous_interval = current.get("intervalMinutes", 15)
    if "enabled" in changes:
        current["enabled"] = bool(changes["enabled"])
    if "intervalMinutes" in changes:
        current["intervalMinutes"] = max(5, min(1440, int(changes["intervalMinutes"])))
    if "autoRefresh" in changes:
        current["autoRefresh"] = bool(changes["autoRefresh"])
    updater.atomic_json(updater.CONFIG_PATH, current)
    status = updater.read_json(updater.STATUS_PATH, {})
    status["intervalMinutes"] = current["intervalMinutes"]
    status["schedulerEnabled"] = current["enabled"]
    updater.atomic_json(updater.STATUS_PATH, status)
    if not current["enabled"]:
        scheduler_state["nextCheck"] = None
    elif not previous_enabled or previous_interval != current["intervalMinutes"]:
        delay = timedelta(seconds=3) if not previous_enabled else timedelta(minutes=current["intervalMinutes"])
        scheduler_state["nextCheck"] = iso(datetime.now(timezone.utc) + delay)
    scheduler_wakeup.set()
    return current


def archive_revision(stat=None) -> str | None:
    try:
        stat = stat or updater.CONTENT_PATH.stat()
        return f"{stat.st_mtime_ns}-{stat.st_size}"
    except FileNotFoundError:
        return None


def status_payload() -> dict:
    status = updater.read_json(updater.STATUS_PATH, {})
    config = read_config()
    status.update({
        "apiAvailable": True,
        "schedulerEnabled": bool(config.get("enabled", True)) and bool(scheduler_state.get("schedulerEnabled", True)),
        "automaticChecksEnabled": bool(config.get("enabled", True)),
        "autoRefresh": bool(config.get("autoRefresh", True)),
        "intervalMinutes": int(config.get("intervalMinutes", 15)),
        "nextCheck": scheduler_state.get("nextCheck"),
        "serverStarted": scheduler_state.get("serverStarted"),
        "updateInProgress": update_lock.locked() or bool(status.get("running")),
        "contentRevision": archive_revision(),
    })
    return status


def update_job(reason: str = "manual") -> None:
    try:
        updater.append_log({"event": "trigger", "reason": reason, "at": updater.now_iso()})
        updater.run_update()
    except Exception as exc:
        print(f"[updater] {type(exc).__name__}: {exc}", flush=True)
    finally:
        update_lock.release()
        scheduler_wakeup.set()


def start_update(reason: str = "manual") -> bool:
    # Reserve the job before spawning its thread, so simultaneous manual and
    # scheduled requests cannot both report that they started an import.
    if not update_lock.acquire(blocking=False):
        return False
    config = read_config()
    if config.get("enabled", True) and scheduler_state.get("schedulerEnabled", True):
        scheduler_state["nextCheck"] = iso(datetime.now(timezone.utc) + timedelta(minutes=int(config.get("intervalMinutes", 15))))
    try:
        threading.Thread(target=update_job, args=(reason,), daemon=True, name="archive-update").start()
    except Exception:
        update_lock.release()
        raise
    return True


def scheduler_tick(now: datetime | None = None) -> float:
    """One scheduling decision, using wall time to catch up after Mac sleep."""
    now = now or datetime.now(timezone.utc)
    config = read_config()
    if not config.get("enabled", True) or not scheduler_state.get("schedulerEnabled", True):
        scheduler_state["nextCheck"] = None
        return 5
    interval = max(5, min(1440, int(config.get("intervalMinutes", 15))))
    due = scheduler_state.get("nextCheck")
    next_run = datetime.fromisoformat(due.replace("Z", "+00:00")) if due else now + timedelta(seconds=3)
    if now >= next_run:
        if start_update("scheduled"):
            next_run = now + timedelta(minutes=interval)
        else:
            # A slow import is still running. Do not queue duplicate checks.
            return 5
    scheduler_state["nextCheck"] = iso(next_run)
    return max(0.2, min(5, (next_run - now).total_seconds()))


def scheduler_loop() -> None:
    while not stop_event.is_set():
        delay = scheduler_tick()
        scheduler_wakeup.wait(delay)
        scheduler_wakeup.clear()


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".gz": "application/gzip", ".json": "application/json; charset=utf-8"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(HERE), **kwargs)

    def log_message(self, fmt, *args):
        print("[web] " + fmt % args, flush=True)

    def end_headers(self):
        path = urlparse(self.path).path
        if path.endswith(("content.json.gz", "update-status.json", ".js", ".html")) or path.startswith("/api/"):
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        # Android builds may be served from a different local HTTPS origin.
        # Keep the existing same-origin website behavior while allowing the
        # mobile reader to fetch the archive and status endpoint.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Expose-Headers", "X-Archive-Revision")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        super().end_headers()

    def send_head(self):
        if urlparse(self.path).path.endswith(".json.gz"):
            try:
                archive = open(self.translate_path(self.path), "rb")
            except OSError:
                self.send_error(HTTPStatus.NOT_FOUND, "The study archive is unavailable")
                return None
            # The revision belongs to the opened file, not a newer file that an
            # atomic import could replace while this response is being sent.
            stat = os.fstat(archive.fileno())
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Encoding", "gzip")
            self.send_header("Content-Length", str(stat.st_size))
            self.send_header("Last-Modified", self.date_time_string(stat.st_mtime))
            if urlparse(self.path).path == "/content.json.gz":
                self.send_header("X-Archive-Revision", archive_revision(stat))
            self.end_headers()
            return archive
        return super().send_head()

    def translate_path(self, path):
        bundled = Path(super().translate_path(path))
        relative = bundled.relative_to(HERE)
        if relative.as_posix() in {"content.json.gz", "update-status.json", "update-config.json"} or relative.parts[:1] == ("assets",):
            writable = updater.HERE / relative
            if writable.is_file():
                return str(writable)
        return str(bundled)

    def send_json(self, data, status=HTTPStatus.OK):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", "0") or 0)
        if length > 100_000:
            raise ValueError("Request body is too large")
        return json.loads(self.rfile.read(length) or b"{}")

    def do_GET(self):
        path = urlparse(self.path).path
        if path == '/api/studies/translations/status':
            return self.send_json(get_translation_library().status())
        if path == '/api/studies/translations/catalog':
            try:
                language = parse_qs(urlparse(self.path).query).get('language', [''])[0]
                return self.send_json(get_translation_library().catalog(language))
            except ValueError as error:
                return self.send_json({'error': str(error)}, HTTPStatus.BAD_REQUEST)
        if path == "/api/update/status":
            return self.send_json(status_payload())
        if path == "/api/health":
            return self.send_json({"ok": True, "service": "Gospel Warrior automatic update server", "time": updater.now_iso()})
        return super().do_GET()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        path = urlparse(self.path).path
        if path == '/api/studies/translations/settings':
            try:
                body = self.read_json_body()
                return self.send_json(get_translation_library().configure(body.get('enabled')))
            except (ValueError, TypeError, AttributeError):
                return self.send_json({'error': 'Invalid translation settings'}, HTTPStatus.BAD_REQUEST)
        if path == "/api/studies/translation":
            try:
                body = self.read_json_body()
                post = find_study(body.get("id"))
                if not post or updater.reader_excludes(post["id"], post["title"]):
                    return self.send_json({"error": "Study not found"}, HTTPStatus.NOT_FOUND)
                payload = study_translations.translation_status(post, body.get("language"), updater.HERE, retry=body.get("retry") is True)
                return self.send_json(payload)
            except (ValueError, TypeError, AttributeError):
                return self.send_json({"error": "Invalid translation request"}, HTTPStatus.BAD_REQUEST)
        if path == "/api/update/check":
            started = start_update("manual")
            return self.send_json({"ok": True, "started": started, "message": "Update started." if started else "An update is already running."}, HTTPStatus.ACCEPTED)
        if path == "/api/update/settings":
            try:
                config = save_config(self.read_json_body())
                return self.send_json({"ok": True, "config": config, "status": status_payload()})
            except Exception as exc:
                return self.send_json({"ok": False, "error": str(exc)}, HTTPStatus.BAD_REQUEST)
        return self.send_json({"ok": False, "error": "Unknown endpoint"}, HTTPStatus.NOT_FOUND)


class LocalThreadingHTTPServer(ThreadingHTTPServer):
    """Bind without a reverse-DNS lookup.

    Some macOS/network configurations block `socket.getfqdn()` for a long
    time during `TCPServer.server_bind()`. The local reading server does not
    need a canonical hostname, so keep its bind path deterministic.
    """

    def server_bind(self):
        self.socket.bind(self.server_address)
        self.server_address = self.socket.getsockname()
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the archive and keep it synchronized with new public studies.")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind (use 0.0.0.0 for network/preview access)")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-scheduler", action="store_true", help="Serve files without scheduled public checks")
    args = parser.parse_args()
    updater.ensure_defaults()
    scheduler_state["serverStarted"] = updater.now_iso()
    scheduler_state["schedulerEnabled"] = not args.no_scheduler
    if not args.no_scheduler:
        threading.Thread(target=scheduler_loop, daemon=True, name="update-scheduler").start()
    server = LocalThreadingHTTPServer((args.host, args.port), Handler)
    print(f"Gospel Warrior: http://{args.host}:{server.server_port}", flush=True)
    print("Automatic public checks: " + ("disabled" if args.no_scheduler else f"every {read_config()['intervalMinutes']} minutes"), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.server_close()


if __name__ == "__main__":
    main()
