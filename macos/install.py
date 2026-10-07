#!/usr/bin/env python3
"""Install a verified local build, retaining a backup of the previous app."""
from __future__ import annotations

import argparse
import plistlib
import shutil
import subprocess
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--destination', type=Path, default=Path('/Applications/Gospel Warrior.app'))
    parser.add_argument('--open', action='store_true')
    args = parser.parse_args()
    source = ROOT / 'dist/Gospel Warrior.app'
    destination = args.destination
    source_info = plistlib.loads((source / 'Contents/Info.plist').read_bytes())
    if destination.parent != Path('/Applications') or destination.suffix != '.app':
        parser.error('The destination must be a Gospel Warrior application in /Applications.')
    if destination.exists():
        old_info = plistlib.loads((destination / 'Contents/Info.plist').read_bytes())
        if old_info.get('CFBundleIdentifier') != source_info['CFBundleIdentifier']:
            parser.error('The destination is a different application.')
    else:
        old_info = {}
    subprocess.run(['codesign', '--verify', '--strict', str(source)], check=True)
    staging = destination.parent / f'.GospelWarrior-install-{uuid.uuid4().hex}.app'
    backup = None
    try:
        shutil.copytree(source, staging, symlinks=True)
        subprocess.run(['codesign', '--verify', '--strict', str(staging)], check=True)
        subprocess.run(['osascript', '-e', 'if application id "org.gospelwarrior.study" is running then tell application id "org.gospelwarrior.study" to quit'], check=True)
        if destination.exists():
            backups = ROOT / '.macos-build/installed-backups'
            backups.mkdir(parents=True, exist_ok=True)
            backup = backups / f'{destination.stem}-{old_info.get("CFBundleShortVersionString", "previous")}-{uuid.uuid4().hex[:8]}.app'
            shutil.move(str(destination), backup)
            print(f'Previous app backed up at {backup}', flush=True)
        try:
            staging.rename(destination)
        except Exception:
            if backup and not destination.exists():
                shutil.move(str(backup), destination)
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    print(f'Installed Gospel Warrior {source_info["CFBundleShortVersionString"]} at {destination}', flush=True)
    if args.open:
        subprocess.run(['open', '-n', str(destination)], check=True)


if __name__ == '__main__':
    main()
