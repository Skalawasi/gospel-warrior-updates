#!/usr/bin/env python3
"""Self-contained app service; launched only by the native Mac application."""
from __future__ import annotations

import argparse
import hashlib
import gzip
import json
import os
import shutil
import signal
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path


def merge_bundled_archive(website: Path, data_directory: Path, updater, *, seeded=False) -> int:
    """Carry an expanded offline bundle into an older saved library once."""
    manifest = updater.read_json(website.parent / "build-manifest.json", {})
    expected = manifest.get("archiveSHA256")
    if not expected:
        return 0
    marker = data_directory / "bundled-archive-applied.json"
    if updater.read_json(marker, {}).get("archiveSHA256") == expected:
        return 0
    if not seeded:
        digest = hashlib.sha256()
        with updater.CONTENT_PATH.open("rb") as archive:
            for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                digest.update(chunk)
        seeded = digest.hexdigest() == expected
    if seeded:
        updater.atomic_json(marker, {"archiveSHA256": expected})
        return 0
    data = updater.load_archive()
    with gzip.open(website / "content.json.gz", "rt", encoding="utf-8") as handle:
        bundled = json.load(handle)
    known_ids = {str(post["id"]) for post in data["posts"]}
    known_texts = {updater.study_body_hash(post["text"], post["title"]) for post in data["posts"]}
    added = []
    for post in bundled["posts"]:
        if str(post["id"]) in known_ids or updater.reader_excludes(post["id"], post["title"]):
            continue
        digest = updater.study_body_hash(post["text"], post["title"])
        if digest in known_texts:
            continue
        added.append(post)
        known_ids.add(str(post["id"]))
        known_texts.add(digest)
    if added:
        print(f"Adding {len(added):,} bundled studies to the saved library…", flush=True)
        data["posts"].extend(added)
        data["posts"].sort(key=lambda post: (int(bool(post.get("pinned"))), int(post.get("timestamp") or 0)), reverse=True)
        data.setdefault("archive", {})["lastBundledArchiveMerge"] = updater.now_iso()
        updater.save_archive(data, compresslevel=6)
        summary = updater.archive_summary(data["posts"])
        updater.write_status(currentTotal=summary["total"], totalWords=summary["words"], subjects=summary["subjects"], structuredMetadata=summary["structuredMetadata"])
    updater.atomic_json(marker, {"archiveSHA256": expected})
    return len(added)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--website", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--ready", type=Path, required=True)
    parser.add_argument("--parent", type=int, required=True)
    parser.add_argument("--port", type=int, default=18743)
    parser.add_argument("--no-scheduler", action="store_true")
    parser.add_argument("--skip-bundle-merge", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--verification-fixture", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()

    def stop_during_startup(_signum, _frame):
        # Exit through Python's finally blocks if the app is closed mid-migration.
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop_during_startup)
    signal.signal(signal.SIGINT, stop_during_startup)
    args.data.mkdir(parents=True, exist_ok=True)
    (args.data / "assets").mkdir(exist_ok=True)
    os.environ["GW_ARCHIVE_DIR"] = str(args.data)
    sys.path.insert(0, str(args.website))

    # Seed once: updates and saved archive data survive app replacements.
    seeded_archive = False
    for name in ("content.json.gz", "update-config.json", "update-status.json"):
        destination = args.data / name
        if not destination.exists():
            temporary = destination.with_suffix(destination.suffix + ".seed")
            shutil.copy2(args.website / name, temporary)
            temporary.replace(destination)
            if name == "content.json.gz":
                seeded_archive = True

    import update_server as service

    # Do not decompress and scan millions of words on every launch. The bundle
    # is already curated, and each importer write records its policy stamp.
    stamp = service.updater.reader_policy_stamp()
    applied = service.updater.read_json(args.data / "reader-policy-applied.json", {})
    known_clean = seeded_archive or stamp == applied
    if not known_clean:
        manifest = service.updater.read_json(args.website.parent / "build-manifest.json", {})
        expected = manifest.get("archiveSHA256")
        if expected:
            digest = hashlib.sha256()
            with service.updater.CONTENT_PATH.open("rb") as archive:
                for chunk in iter(lambda: archive.read(1024 * 1024), b""):
                    digest.update(chunk)
            known_clean = digest.hexdigest() == expected
    if not known_clean:
        service.updater.curate_reader_archive()
    service.updater.mark_reader_policy()
    service.updater.ensure_defaults()
    if not args.skip_bundle_merge:
        merge_bundled_archive(args.website, args.data, service.updater, seeded=seeded_archive)
    if args.verification_fixture:
        if not args.no_scheduler:
            parser.error("Verification fixtures require the scheduler to be disabled.")
        # Used only by isolated native integration tests. This exercises the
        # real check API, atomic archive replacement, and refresh notifications
        # without depending on the public source or changing a user's library.
        import copy
        import time
        fixture = json.loads(args.verification_fixture.read_text())
        fixture_index = 0

        def verification_update():
            nonlocal fixture_index
            data = service.updater.load_archive()
            service.updater.write_status(state="checking", running=True, error=None, message="Checking for Bible studies…")
            time.sleep(0.15)
            title = fixture["titles"][fixture_index]
            fixture_index += 1
            now = datetime.now(timezone.utc)
            post = copy.deepcopy(data["posts"][0])
            post.update(id=f"verification-study-{fixture_index}", title=title, text=title + "\n\n" + post["text"], pinned=False, timestamp=int(now.timestamp()), date=now.isoformat())
            data["posts"].insert(0, post)
            data["archive"]["publicRecordsRecovered"] = len(data["posts"])
            service.updater.save_archive(data, compresslevel=1)
            recent = [{"id": post["id"], "title": title, "date": post["date"], "subject": post["subject"]}]
            service.updater.write_status(state="current", running=False, message="A new Bible study was collected.", lastCheck=now.isoformat(), lastSuccess=now.isoformat(), currentTotal=len(data["posts"]), addedLastRun=1, recentAdded=recent, error=None)
            return {"added": 1}

        service.updater.run_update = verification_update
    # An interrupted import must not leave the app showing "running" forever.
    status = service.updater.read_json(service.updater.STATUS_PATH, {})
    if status.get("running"):
        status.update(running=False, state="ready", message="Ready to check for new studies.")
        service.updater.atomic_json(service.updater.STATUS_PATH, status)
    service.scheduler_state["serverStarted"] = service.iso(datetime.now(timezone.utc))
    service.scheduler_state["schedulerEnabled"] = not args.no_scheduler
    try:
        server = service.LocalThreadingHTTPServer(("127.0.0.1", args.port), service.Handler)
    except OSError:
        # Coexist with the existing website or another local application.
        server = service.LocalThreadingHTTPServer(("127.0.0.1", 0), service.Handler)

    stopping = threading.Event()

    def stop(_signum=None, _frame=None):
        if not stopping.is_set():
            stopping.set()
            service.stop_event.set()
            threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)

    def watch_parent():
        while not stopping.wait(2):
            if os.getppid() != args.parent:
                stop()
                return

    threading.Thread(target=watch_parent, daemon=True, name="app-lifetime").start()
    if not args.no_scheduler:
        threading.Thread(target=service.scheduler_loop, daemon=True, name="archive-scheduler").start()
    url = f"http://127.0.0.1:{server.server_port}"
    service.updater.atomic_json(args.ready, {"url": url, "pid": os.getpid()})
    print(f"Gospel Warrior app service: {url}", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    finally:
        service.stop_event.set()
        server.server_close()
        args.ready.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
