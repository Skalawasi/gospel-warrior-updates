#!/usr/bin/env python3
"""Build the Intel macOS application and drag-to-install disk image."""
from __future__ import annotations

import argparse
import ast
import gzip
import hashlib
import json
import plistlib
import shutil
import struct
import subprocess
import sys
import tarfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "macos"
WEBSITE = ROOT / "gospel-warrior-study"
CACHE = ROOT / ".macos-build"
DIST = ROOT / "dist"
APP = DIST / "Gospel Warrior.app"
RUNTIME_NAME = "cpython-3.12.15+20261003-x86_64-apple-darwin-install_only_stripped.tar.gz"
RUNTIME_URL = "https://github.com/astral-sh/python-build-standalone/releases/download/20261003/" + RUNTIME_NAME.replace("+", "%2B")
RUNTIME_SHA256 = "562c30864ece2cb1d3e0ad66a1acd498611a47e5a10ce81b99158bef1ccbd355"


def run(*arguments, **kwargs):
    print("Running:", " ".join(map(str, arguments)), flush=True)
    return subprocess.run(list(map(str, arguments)), check=True, **kwargs)


def macho_versions(path: Path):
    """Inspect deployment versions without relying on the build machine's OS."""
    data = path.read_bytes()
    slices = [data]
    if data[:4] in (b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
        wide = data[:4] == b"\xca\xfe\xba\xbf"
        count = struct.unpack_from(">I", data, 4)[0]
        slices = []
        for index in range(count):
            offset = 8 + index * (32 if wide else 20)
            cpu = struct.unpack_from(">I", data, offset)[0]
            start, length = struct.unpack_from(">QQ" if wide else ">II", data, offset + 8)
            if cpu == 0x01000007:
                slices.append(data[start:start + length])
        if not slices:
            raise RuntimeError(f"No Intel slice in {path}")
    versions = []
    for binary in slices:
        if binary[:4] != b"\xcf\xfa\xed\xfe":
            continue
        cpu, _subtype, _type, commands = struct.unpack_from("<IIII", binary, 4)
        if cpu != 0x01000007:
            raise RuntimeError(f"Non-Intel binary: {path}")
        offset = 32
        for _ in range(commands):
            command, length = struct.unpack_from("<II", binary, offset)
            if command in (0x24, 0x32):
                version = struct.unpack_from("<I", binary, offset + (12 if command == 0x32 else 8))[0]
                versions.append((version >> 16, (version >> 8) & 255, version & 255))
            offset += length
    return versions


def binary_paths(directory: Path):
    for path in directory.rglob("*"):
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            magic = stream.read(4)
        if magic in (b"\xcf\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"):
            yield path


def prepare_runtime():
    archive = CACHE / RUNTIME_NAME
    if not archive.exists():
        partial = archive.with_suffix(".download")
        run("curl", "--fail", "--location", "--retry", "3", "--output", partial, RUNTIME_URL)
        partial.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != RUNTIME_SHA256:
        raise RuntimeError("The Python runtime download did not match its pinned SHA-256.")
    runtime = CACHE / "python"
    marker = CACHE / "runtime-ready.json"
    requirements_hash = hashlib.sha256((SOURCE / "requirements.txt").read_bytes()).hexdigest()
    metadata = json.loads(marker.read_text()) if marker.exists() else {}
    fresh = not runtime.exists() or metadata.get("pythonSHA256") != digest
    if fresh:
        if runtime.exists():
            shutil.rmtree(runtime)
        with tarfile.open(archive) as package:
            package.extractall(CACHE, filter="data")
    if fresh or metadata.get("requirementsSHA256") != requirements_hash:
        python = runtime / "bin/python3"
        run(python, "-I", "-m", "pip", "install", "--only-binary=:all:", "--disable-pip-version-check", "-r", SOURCE / "requirements.txt")
        frozen = run(python, "-I", "-m", "pip", "freeze", capture_output=True, text=True).stdout
        marker.write_text(json.dumps({"pythonSHA256": digest, "requirementsSHA256": requirements_hash, "packages": frozen.splitlines()}, indent=2))
    return runtime, json.loads(marker.read_text())


def package_disk_image(staging):
    token = uuid.uuid4().hex
    raw = CACHE / f'Gospel-Warrior-{token}-raw.dmg'
    image = CACHE / f'Gospel-Warrior-{token}.dmg'
    try:
        # DiscRecording's HFS writer avoids filesystem-helper stalls seen with
        # hdiutil create -srcfolder on large model-bearing app bundles.
        run('hdiutil', 'makehybrid', '-hfs', '-hfs-volume-name', 'Gospel Warrior', '-o', raw, staging)
        run('hdiutil', 'convert', raw, '-format', 'UDZO', '-imagekey', 'zlib-level=1', '-o', image)
        run('hdiutil', 'verify', image)
        image.replace(DIST / 'Gospel Warrior-Intel.dmg')
    finally:
        raw.unlink(missing_ok=True)
        image.unlink(missing_ok=True)


def prepare_disk_staging():
    staging = CACHE / 'disk-image'
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()
    shutil.copytree(APP, staging / APP.name, symlinks=True)
    (staging / 'Applications').symlink_to('/Applications', target_is_directory=True)
    shutil.copy2(SOURCE / 'INSTALL.md', staging / 'Read Me.md')
    return staging


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-dmg", action="store_true", help="Only build the application bundle")
    parser.add_argument('--package-only', action='store_true', help='Package the already built and staged application')
    args = parser.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("Build this application on a Mac with Xcode Command Line Tools.")
    CACHE.mkdir(exist_ok=True)
    DIST.mkdir(exist_ok=True)
    if args.package_only:
        run('codesign', '--verify', '--strict', APP)
        package_disk_image(prepare_disk_staging())
        return
    runtime, dependencies = prepare_runtime()
    if APP.exists():
        # Only the generated application is replaced. User data lives elsewhere.
        shutil.rmtree(APP)
    contents = APP / "Contents"
    resources = contents / "Resources"
    executable = contents / "MacOS/GospelWarrior"
    executable.parent.mkdir(parents=True)
    resources.mkdir()
    shutil.copy2(SOURCE / "Info.plist", contents / "Info.plist")
    run("xcrun", "clang", "-arch", "x86_64", "-mmacosx-version-min=11.0", "-fobjc-arc", "-O2", "-Wall", "-Wextra", "-Wno-unused-parameter", "-framework", "Cocoa", "-framework", "WebKit", SOURCE / "GospelWarrior.m", "-o", executable)

    shutil.copytree(runtime, resources / "python", symlinks=True)
    # These development tools are unnecessary for running the bundled service.
    for relative in ("include", "share", "lib/python3.12/test", "lib/python3.12/idlelib", "lib/python3.12/ensurepip", "lib/python3.12/config-3.12-darwin"):
        path = resources / "python" / relative
        if path.exists():
            shutil.rmtree(path)
    for path in (resources / "python").rglob("__pycache__"):
        shutil.rmtree(path)
    bundled_site = resources / "website"
    bundled_site.mkdir()
    if not (WEBSITE / "assets/bible/index.json").is_file() or not (WEBSITE / "assets/bible/mg/index.json").is_file():
        raise RuntimeError("Run macos/import_kjv.py and macos/import_malagasy_bible.py before packaging.")
    for name in ("study.html", "study-app.js", "study-languages.js", "study-copy.js", "study-notebook.js", "kjv-bible.js", "study-styles.css", "study_translations.py", "translation_library.py", "local_translator.py", "content.json.gz", "content-policy.json", "updater.py", "update_server.py", "update-config.json"):
        shutil.copy2(WEBSITE / name, bundled_site / name)
    policy = json.loads((WEBSITE / "content-policy.json").read_text())
    omitted_images = {Path(value).name for value in policy.get("excludedImages", [])}
    shutil.copytree(WEBSITE / "assets", bundled_site / "assets", ignore=shutil.ignore_patterns(".DS_Store", *omitted_images))
    for language in ('fr', 'mg'):
        if not (bundled_site / 'assets/translation-models' / language / 'model.bin').is_file():
            raise RuntimeError('Run macos/import_translation_models.py before packaging.')
    # Start each installation with truthful idle status, not the builder's log.
    with gzip.open(bundled_site / "content.json.gz", "rt", encoding="utf-8") as stream:
        data = json.load(stream)
    posts = data["posts"]
    excluded_ids = {str(value) for value in policy.get("excludedPostIds", [])}
    if any(str(post["id"]) in excluded_ids for post in posts):
        raise RuntimeError("Apply updater.py --curate-reader before packaging the study archive.")
    cleanup_version = next(node.value.value for node in ast.parse((WEBSITE / "updater.py").read_text()).body if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == "SOCIAL_CALLS_CLEANUP_VERSION" for target in node.targets))
    if data.get("archive", {}).get("socialCallsCleanupVersion") != cleanup_version or any(post.get("socialCallsCleanupVersion") != cleanup_version or not post.get("socialCallsCleanupHash") for post in posts):
        raise RuntimeError("Apply updater.py --clean-archive before packaging the study archive.")
    status = {
        "state": "ready", "running": False, "currentTotal": len(posts),
        "message": "The offline library is ready. New public studies are checked while the app is open.",
        "lastCheck": None, "lastSuccess": None, "addedLastRun": 0, "recentAdded": [], "error": None,
    }
    (bundled_site / "update-status.json").write_text(json.dumps(status, indent=2))
    for name in ("desktop_server.py", "selftest.js"):
        shutil.copy2(SOURCE / name, resources / name)
    shutil.copy2(SOURCE / "THIRD_PARTY_NOTICES.md", resources / "THIRD_PARTY_NOTICES.md")
    python = runtime / "bin/python3"
    certificates = run(python, "-I", "-c", "import certifi; print(certifi.where())", capture_output=True, text=True).stdout.strip()
    shutil.copy2(certificates, resources / "certificates.pem")
    iconset = CACHE / "GospelWarrior.iconset"
    run(python, "-I", SOURCE / "make_icon.py", iconset)
    run("iconutil", "--convert", "icns", "--output", resources / "GospelWarrior.icns", iconset)

    binaries = list(binary_paths(contents))
    deployment = []
    for binary in binaries:
        versions = macho_versions(binary)
        if not versions:
            raise RuntimeError(f"Cannot verify the minimum macOS version of {binary}")
        if max(versions) > (11, 0, 0):
            raise RuntimeError(f"{binary} requires macOS {max(versions)}, beyond Big Sur")
        deployment.append({"path": str(binary.relative_to(APP)), "minimumMacOS": ".".join(map(str, max(versions)))})
    manifest = {
        "name": "Gospel Warrior", "version": plistlib.loads((SOURCE / "Info.plist").read_bytes())["CFBundleShortVersionString"], "architecture": "x86_64", "minimumMacOS": "11.0",
        "studies": len(posts), "topics": len({topic for post in posts for topic in post.get("topics", [])}),
        "bibleBooks": len({book for post in posts for book in post.get("bibleBooks", [])}),
        "characters": len({character for post in posts for character in post.get("biblicalCharacters", [])}),
        "archiveSHA256": hashlib.sha256((bundled_site / "content.json.gz").read_bytes()).hexdigest(),
        "runtime": dependencies, "binaryDeploymentTargets": deployment,
    }
    (resources / "build-manifest.json").write_text(json.dumps(manifest, indent=2))
    shutil.copy2(resources / "build-manifest.json", DIST / "build-manifest.json")
    # Sign nested Mach-O files before sealing the top-level application bundle.
    for binary in binaries:
        subprocess.run(["codesign", "--force", "--sign", "-", str(binary)], check=True, capture_output=True)
    run("codesign", "--force", "--sign", "-", APP)
    run("codesign", "--verify", "--strict", APP)
    run("plutil", "-lint", contents / "Info.plist")
    shutil.copy2(SOURCE / "INSTALL.md", DIST / "INSTALL.md")
    if not args.no_dmg:
        package_disk_image(prepare_disk_staging())
    print(f"Built {APP}\nIncluded {len(posts):,} studies. Minimum macOS: 11.0 (Intel).", flush=True)


if __name__ == "__main__":
    main()
