#!/usr/bin/env python3
"""Integration checks for the packaged service and real native WebKit app."""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def wait_ready(path, process):
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        if path.exists():
            return json.loads(path.read_text())
        if process.poll() is not None:
            raise RuntimeError("The bundled service stopped during startup")
        time.sleep(0.1)
    raise TimeoutError("The bundled service did not start")


def assert_process_stopped(pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.1)
    raise AssertionError(f"The app left a service process running: {pid}")


def verify_update_flow(args, resources, binary, manifest, output):
    """Focused refresh regression checks using a small real-study fixture.

    Full archive loading/filtering is covered by phases 1–2. This isolates the
    update behavior so testing need not repeatedly rewrite the entire corpus.
    """
    reports = []
    with tempfile.TemporaryDirectory(prefix="gospel-update-flow-", dir=ROOT / ".macos-build") as temporary:
        work = Path(temporary)
        profile = work / "profile"
        library = profile / "library"
        library.mkdir(parents=True)
        (library / 'translation-library.json').write_text(json.dumps({'enabled': False}))
        with gzip.open(resources / "website/content.json.gz", "rt", encoding="utf-8") as archive:
            data = json.load(archive)
        data["posts"] = data["posts"][:24]
        data["archive"]["publicRecordsRecovered"] = len(data["posts"])
        with gzip.open(library / "content.json.gz", "wt", encoding="utf-8", compresslevel=1) as archive:
            archive.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
        initial_count = len(data["posts"])
        preferences = {"gw-saved": json.dumps([data["posts"][1]["id"]]), "gw-sort-order": "az", "gw-font-size": "20", "gw-reading-dark": "true"}
        (profile / "preferences.json").write_text(json.dumps(preferences))
        del data
        fixture = work / "fixture.json"
        fixture.write_text(json.dumps({"titles": ["A NEW BIBLE STUDY ON PRAYER — INTEGRATION CHECK", "A NEW BIBLE STUDY ON FAITH — INTEGRATION CHECK"]}))
        phases = (8, 9) if args.reader_only else (5, 6, 3, 7) if args.appearance_only else (3, 4)
        for phase in phases:
            report_path = output / f"native-phase-{phase}.json"
            report_path.unlink(missing_ok=True)
            command = [str(binary), "--self-test", str(report_path), "--profile-dir", str(profile), "--test-phase", str(phase), "--disable-decompression", "--no-scheduler", "--port", "0"]
            if phase == 3:
                command.extend(["--verification-fixture", str(fixture)])
            with (output / f"native-phase-{phase}.log").open("w") as log:
                subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
            shutil.copy2(profile / "app-service.log", output / f"native-phase-{phase}-service.log")
            report = json.loads(report_path.read_text())
            assert report["ok"], report
            assert report["studies"] == initial_count + (2 if phase in (3, 4, 7) else 0)
            if args.appearance_only:
                assert report["windowAppearance"] == "NSAppearanceNameDarkAqua", report["windowAppearance"]
            assert_process_stopped(report["servicePID"])
            reports.append(report)
            print(f"Native phase {phase}: {len(report['checks'])} checks passed", flush=True)
    subprocess.run(["codesign", "--verify", "--strict", str(args.app)], check=True)
    subprocess.run(["hdiutil", "verify", str(ROOT / "dist/Gospel Warrior-Intel.dmg")], check=True)
    summary = "reader-feature-summary.json" if args.reader_only else "appearance-summary.json" if args.appearance_only else "update-flow-summary.json"
    (output / summary).write_text(json.dumps({"ok": True, "version": manifest["version"], "packagedStudies": manifest["studies"], "focusedUpdateVerification": True, "reports": reports}, indent=2))
    print("Study languages, notes, markings, KJV dictionary, Malagasy Bible, and native persistence passed." if args.reader_only else "Appearance persistence, automatic refresh, and reading continuity passed." if args.appearance_only else "Automatic refresh, reading continuity, and update settings passed.", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app", type=Path, default=ROOT / "dist/Gospel Warrior.app")
    parser.add_argument("--updates-only", action="store_true", help="Run focused native update/refresh regression checks")
    parser.add_argument("--appearance-only", action="store_true", help="Verify all skin/colour combinations, relaunch persistence, and content refresh")
    parser.add_argument("--reader-only", action="store_true", help="Verify study languages, notebook, and both Bible versions in native WebKit")
    args = parser.parse_args()
    resources = args.app / "Contents/Resources"
    python = resources / "python/bin/python3"
    binary = args.app / "Contents/MacOS/GospelWarrior"
    website = resources / "website"
    manifest = json.loads((resources / "build-manifest.json").read_text())
    reports = []
    output = ROOT / "dist/verification"
    output.mkdir(parents=True, exist_ok=True)
    if args.updates_only or args.appearance_only or args.reader_only:
        verify_update_flow(args, resources, binary, manifest, output)
        return
    subprocess.run([str(python), "-I", "-B", str(ROOT / "macos/test_update_service.py")], check=True)
    with tempfile.TemporaryDirectory(prefix="gospel-warrior-verify-", dir=ROOT / ".macos-build") as temporary:
        work = Path(temporary)
        ready = work / "ready.json"
        library = work / "library"
        environment = {**os.environ, "SSL_CERT_FILE": str(resources / "certificates.pem"), "REQUESTS_CA_BUNDLE": str(resources / "certificates.pem")}
        command = [str(python), "-I", "-B", "-u", str(resources / "desktop_server.py"), "--website", str(website), "--data", str(library), "--ready", str(ready), "--parent", str(os.getpid()), "--port", "0", "--no-scheduler"]
        with (output / "service-test.log").open("w") as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=environment)
            try:
                service = wait_ready(ready, process)
                url = service["url"]
                with urllib.request.urlopen(url + "/study.html", timeout=20) as response:
                    html = response.read().decode()
                    assert response.status == 200 and 'id="settingsPanel"' in html
                with urllib.request.urlopen(url + "/content.json.gz", timeout=20) as response:
                    assert response.headers.get("Content-Encoding") == "gzip"
                    assert response.headers.get("X-Archive-Revision")
                    archive = json.loads(gzip.decompress(response.read()))
                    assert len(archive["posts"]) == manifest["studies"]
                    assert not any(str(post["id"]) == "28949692034615161" for post in archive["posts"])
                for omitted in ("archive-28949692034615161.webp", "profile.jpg", "cover.jpg"):
                    assert not (website / "assets" / omitted).exists(), omitted
                for post in archive["posts"]:
                    assert (website / post["imageLocal"]).is_file(), post["id"]
                with urllib.request.urlopen(url + "/" + archive["posts"][0]["imageLocal"], timeout=20) as response:
                    assert response.status == 200 and len(response.read()) > 0
                with urllib.request.urlopen(url + "/api/update/status", timeout=20) as response:
                    status = json.load(response)
                    assert status["apiAvailable"] and not status["schedulerEnabled"]
                    assert status["autoRefresh"] and status["intervalMinutes"] == 15 and status["contentRevision"]
                # Imported assets are served from the writable data directory.
                (library / "assets/desktop-verification.txt").write_text("writable asset")
                with urllib.request.urlopen(url + "/assets/desktop-verification.txt", timeout=20) as response:
                    assert response.read() == b"writable asset"
                # The updater must validate seeded studies against bundled images.
                validation = subprocess.run([str(python), "-I", "-B", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import updater; print(updater.validate_archive_data(updater.load_archive()))", str(website)], env={**environment, "GW_ARCHIVE_DIR": str(library)}, check=True, capture_output=True, text=True)
                print(validation.stdout.strip())
                exclusion = subprocess.run([str(python), "-I", "-B", "-c", "import sys; sys.path.insert(0, sys.argv[1]); import updater; post, info = updater.make_post(None, {'id': '28949692034615161', 'text': 'ON MY 52ND BIRTHDAY, I AM GIVING GOD THE ONLY GIFT I CAN NEVER TAKE BACK'}, set(), set()); assert post is None and info['result'] == 'excluded-from-study-reader'; print('Birthday reimport rejected before downloading any image')", str(website)], check=True, capture_output=True, text=True)
                print(exclusion.stdout.strip())
                reports.append({"ok": True, "name": "Packaged service", "studies": manifest["studies"], "checks": ["HTTP gzip on older Safari", "All local images present", "Writable archive and imported image routing", "Update API", "Full archive deduplication validation", "Birthday post and personal portrait assets removed", "Birthday reimport blocked"]})
            finally:
                process.terminate()
                process.wait(timeout=10)
                assert not ready.exists(), "Service readiness file was not cleaned up"

        # Test the actual Cocoa/WKWebView app, not only its static assets.
        profile = work / "native-profile"
        fixture = work / "update-fixture.json"
        fixture.write_text(json.dumps({"titles": ["A NEW BIBLE STUDY ON PRAYER — INTEGRATION CHECK", "A NEW BIBLE STUDY ON FAITH — INTEGRATION CHECK"]}))
        for phase in (1, 2, 3, 4):
            if phase == 2:
                # Simulate an existing installation restoring an older archive.
                existing_path = profile / "library/content.json.gz"
                with gzip.open(existing_path, "rt", encoding="utf-8") as stream:
                    older = json.load(stream)
                birthday = copy.deepcopy(older["posts"][0])
                birthday.update(id="28949692034615161", title="ON MY 52ND BIRTHDAY, I AM GIVING GOD THE ONLY GIFT I CAN NEVER TAKE BACK")
                older["posts"].insert(0, birthday)
                with gzip.open(existing_path, "wt", encoding="utf-8", compresslevel=1) as stream:
                    stream.write(json.dumps(older, ensure_ascii=False, separators=(",", ":")))
            reservation = socket.socket()
            reservation.bind(("127.0.0.1", 0))
            reservation.listen()
            port = 0 if phase == 1 else reservation.getsockname()[1]
            report_path = output / f"native-phase-{phase}.json"
            report_path.unlink(missing_ok=True)
            command = [str(binary), "--self-test", str(report_path), "--profile-dir", str(profile), "--test-phase", str(phase), "--disable-decompression", "--no-scheduler", "--port", str(port)]
            if phase == 3:
                command.extend(["--verification-fixture", str(fixture)])
            try:
                with (output / f"native-phase-{phase}.log").open("w") as log:
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=300, check=True)
                report = json.loads(report_path.read_text())
                shutil.copy2(profile / "app-service.log", output / f"native-phase-{phase}-service.log")
                assert report["ok"], report
                assert report["studies"] == manifest["studies"] + (2 if phase >= 3 else 0)
                assert int(report["url"].split(":")[-1]) != reservation.getsockname()[1]
                assert_process_stopped(report["servicePID"])
                reports.append(report)
                print(f"Native phase {phase}: {len(report['checks'])} checks passed")
            finally:
                reservation.close()
    subprocess.run(["codesign", "--verify", "--strict", str(args.app)], check=True)
    subprocess.run(["hdiutil", "verify", str(ROOT / "dist/Gospel Warrior-Intel.dmg")], check=True)
    (output / "summary.json").write_text(json.dumps({"ok": True, "minimumMacOS": manifest["minimumMacOS"], "architecture": manifest["architecture"], "reports": reports}, indent=2))
    print(f"All checks passed. Reports and app screenshots: {output}")


if __name__ == "__main__":
    main()
