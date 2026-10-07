# Automatic updates

The website now includes an **Automatic Updates** section and a small local update service.

## Start the live archive

### Windows

Double-click `start-auto-update.bat`.

### macOS or Linux

```bash
chmod +x start-auto-update.sh
./start-auto-update.sh
```

Then open <http://127.0.0.1:8000>.

The first launch installs three Python packages (`requests`, `beautifulsoup4`, and `Pillow`). The server checks the logged-out public profile every **15 minutes** by default. It never asks for or stores Facebook passwords, private cookies, or access tokens.

## What an update does

1. Reads the newest frontier of the public Gospel Warrior album.
2. Continues paging until it reaches a post already in the archive.
3. Fetches the complete body and matching image of each new public study.
4. Optimizes each newly imported image as a maximum 960-pixel progressive JPEG to control archive growth.
5. Removes promotional/social-media calls to subscribe, share, comment, tag, or follow while retaining the study wording.
6. Rejects duplicates by normalized full title and complete-body hash.
7. Atomically rebuilds `content.json.gz` and updates `update-status.json`.
8. The open webpage detects the larger archive and refreshes automatically.

## Controls on the webpage

Open the **Updates** profile tab to:

- see the last successful check and next scheduled check;
- run **Check now**;
- turn scheduled checks on or off;
- choose a 15-, 30-, 60-, or 180-minute schedule;
- enable or disable automatic browser refresh;
- view titles added during the most recent check.

## Static-host mode

If the folder is served with `python -m http.server`, the webpage can still watch `update-status.json` and refresh when another scheduled process updates the files, but the **Check now** button and server schedule controls require `update_server.py`.

For a hosted production site, run `python updater.py --once` from cron, Task Scheduler, GitHub Actions, or another scheduler, then deploy the changed `content.json.gz`, `update-status.json`, and new files in `assets/`.

Run `python validate_archive.py` at any time to verify unique IDs, titles and complete bodies, local-image existence, current totals, and recent-import CTA cleanup.

## Public-access limits

The updater uses only logged-out public Facebook pages. Facebook can change or temporarily rate-limit those pages. When that happens, the updater keeps the current archive unchanged, records the error, and retries at the next scheduled check. Private, deleted, friends-only, or members-only posts cannot be imported without a lawful public source.
