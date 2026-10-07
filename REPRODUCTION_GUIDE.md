# Gospel Warrior Website — Reproduction Guide

This guide covers two meanings of “reproduce”:

1. **Exact project restoration (recommended):** copy the retained `gospel-warrior-study` folder, install three Python dependencies, validate, and serve it.
2. **Rebuild only from current Facebook public pages:** not fully reproducible from zero. The 3,796-study archive is a curated seed assembled over historical public sources. Facebook may not expose the same old material later, and the exact initial harvesting commands were not retained. To reproduce the final result, preserve/copy `content.json.gz` and `assets/`.

No Facebook password, private cookie, API token, database server, Node.js, package bundler, or administrator privileges are required.

## 1. Prerequisites

### Required to read the site

- A current Chrome, Edge, Firefox, or Safari release with the browser `DecompressionStream` API.
- An HTTP server. Do not open `index.html` through `file://`, because browser fetch security normally blocks loading `content.json.gz`.

### Required for updates and validation

- Python 3.10 or later is recommended.
- `pip` and Python virtual-environment support.
- Internet access to Facebook's logged-out public pages.
- Approximately 120 MB free disk space for the current project plus temporary update files. More headroom is recommended.

The session's observed environment used Python 3.13.14, requests 2.33.0, Beautiful Soup 4.15.0, and Pillow 12.3.0. The project declares compatible ranges instead of pinning those exact versions.

## 2. Obtain the project files

Copy the complete retained directory to the target computer. For example:

```text
gospel-warrior-study/
```

The exact source location/distribution URL is **not recorded** and the folder is not a Git repository, so no `git clone` command can be provided honestly.

The minimum exact-restore set is:

```text
index.html
styles.css
app.js
study.html
study-styles.css
study-app.js
content.json.gz
assets/                 (entire directory)
updater.py
update_server.py
validate_archive.py
requirements.txt
update-config.json
update-status.json
presentations/            (five generated Old Testament study decks)
```

Recommended operational/documentation files:

```text
start-auto-update.sh
start-auto-update.bat
update-log.jsonl
README.md
AUTO_UPDATE.md
APPLY_AUTO_UPDATE.txt
EXECUTION_REPORT.md
COMMAND_HISTORY.md
TOOLS_AND_SKILLS.md
REPRODUCTION_GUIDE.md
```

Do not omit or rename individual assets: every archived post has an `imageLocal` reference validated against this directory.

## 3. Verify the copied baseline

Open a terminal in the copied project root.

### macOS/Linux

```bash
cd /path/to/gospel-warrior-study
sha256sum content.json.gz index.html app.js study.html study-app.js updater.py update_server.py validate_archive.py requirements.txt
```

### Windows PowerShell

```powershell
cd C:\path\to\gospel-warrior-study
Get-FileHash content.json.gz,index.html,app.js,study.html,study-app.js,updater.py,update_server.py,validate_archive.py,requirements.txt -Algorithm SHA256
```

Expected baseline hashes recorded before these reports were generated:

```text
a843109e6a29c81023481004d08924cbc0ca92ef76bbd37d98920a9ef16b2723  content.json.gz
34326f252f462032f40abff1c09e0255da4475050a335d8424f86ea59320c6d2  index.html
61b46dde25bbaa6510ae55306b8cc2017a71d98c893a96c9edd97d980cc59aba  app.js
d53fcf7fb0764a3dc0402fddda5cb9a91eddabea205aee5a87b89811852dc9e6  study.html
c22997b9ae1fccc912cb5292431a23521dee5cb7f1dcab19fb706eb5bca6aacc  study-app.js
e5fd17b084649d817c83ff7028ed67e3620f6fd25fcd12e1dcbc38b40d3c7949  updater.py
387e3a953d8ade6984b010ce45d39dcff8ab8ec9bab5af837654f516d768036a  update_server.py
38f2cc9fb8b81f0927435777dffd3c2128df268cfb1ffeafaca02d2bbaa40223  validate_archive.py
9ec451f76bdbaa20c15240034310904eec10ff4728382ed2a95afc6b9209ae78  requirements.txt
```

A mismatch is expected after a legitimate update or intentional source edit. In particular, `content.json.gz` changes whenever studies are added.

## 4. Create an isolated Python environment

The following are **recommended reproduction commands**, not claims about the original historical setup.

### macOS/Linux

From the project root:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Windows Command Prompt

```bat
py -3 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Successful installation should provide:

- requests 2.x
- beautifulsoup4 4.x
- Pillow 10.x, 11.x, or 12.x

No `sudo`, administrator shell, API key, or account login is needed. Package installation requires internet access unless packages are already cached.

Check versions:

```bash
python -c "import sys,requests,bs4,PIL; print(sys.version); print('requests',requests.__version__); print('beautifulsoup4',bs4.__version__); print('Pillow',PIL.__version__)"
```

## 5. Validate before serving

Run in the project root with the virtual environment active:

```bash
python validate_archive.py
```

For the recorded baseline, expected important fields are:

```json
{
  "ok": true,
  "posts": 3796,
  "ids": 3796,
  "titles": 3796,
  "bodies": 3796,
  "words": 7189381,
  "subjects": 17,
  "missingImages": 0,
  "recentImportCtaResiduals": 0,
  "structuredMetadata": 3796,
  "automaticUpdate": true
}
```

If Facebook updates have already run, totals may be higher. The invariant expectations are `ok: true`, equal post/ID/title/body counts, `missingImages: 0`, `structuredMetadata` equal to the post count, and `recentImportCtaResiduals: 0`.

If metadata rules change, rebuild the searchable fields locally without contacting Facebook:

```bash
python updater.py --enrich-metadata
```

Optional Python syntax check:

```bash
python -m py_compile updater.py update_server.py validate_archive.py
```

This creates `__pycache__`, which is safe and regenerable. Remove it if conserving workspace size:

### macOS/Linux

```bash
rm -rf __pycache__
find . -name '*.pyc' -delete
```

### Windows PowerShell

```powershell
Remove-Item -Recurse -Force __pycache__ -ErrorAction SilentlyContinue
Get-ChildItem -Recurse -Filter *.pyc | Remove-Item -Force
```

## 6. Start the full website with automatic updates

### Direct command (all platforms)

Run in the project root:

```bash
python update_server.py --host 127.0.0.1 --port 8000
```

Expected startup text:

```text
Gospel Warrior: http://127.0.0.1:8000
Automatic public checks: every 15 minutes
```

Open <http://127.0.0.1:8000>.

The server schedules a public check a few seconds after startup and then uses `update-config.json` (15 minutes by default). Stop it with **Ctrl+C**.

### Included launchers

macOS/Linux:

```bash
chmod +x start-auto-update.sh
./start-auto-update.sh
```

Windows: double-click `start-auto-update.bat`, or run:

```bat
start-auto-update.bat
```

The launchers install requirements into the currently selected Python environment, then start the server. A virtual environment is recommended so they do not modify global Python packages.

### Serve without scheduled checks

```bash
python update_server.py --host 127.0.0.1 --port 8000 --no-scheduler
```

This preserves the API and manual controls but prevents background scheduling.

## 7. Static-only viewing

If updates/API controls are not needed:

```bash
python -m http.server 8000 --bind 127.0.0.1
```

Then open <http://127.0.0.1:8000>.

In static mode:

- Timeline, readers, local search, photos, bookmarks, and title index work.
- The webpage reads `update-status.json` as a fallback.
- Manual **Check now** and scheduler settings are unavailable because those require `update_server.py`.

## 8. Run an update manually

Back up the project first if desired, then run:

```bash
python updater.py --once
```

The command requires public internet access but no login. A successful no-change run resembles:

```json
{
  "pagesScanned": 1,
  "discovered": 0,
  "added": 0,
  "after": {
    "total": 3796,
    "words": 7189381,
    "subjects": 17
  }
}
```

A successful change run reports discovered/added counts and details. It may modify:

- `content.json.gz`
- `assets/archive-<id>.jpg`
- `update-status.json`
- `update-log.jsonl`

Run validation immediately afterward:

```bash
python validate_archive.py
```

To regenerate only the structured index fields from the retained study text, without a network request:

```bash
python updater.py --enrich-metadata
```

This updates Bible references, books, biblical characters, topics, testament, Gospel categories, source fields, and duplicate hashes without rewriting the original study wording.

To rerun the social-action cleanup on the retained text, use:

```bash
python updater.py --clean-archive
```

The cleanup removes recognized comment, share, tag, follow, subscribe, save, and support blocks while preserving the surrounding study wording. Validate immediately afterward.

The updater writes the gzip archive to a temporary file, validates it, and only then atomically replaces the live archive. On a source/network failure it records an error and leaves the existing archive unchanged.

## 9. Configure updates

Edit `update-config.json` only while the server is stopped, or use the website's **Updates** tab while it is running.

Current defaults:

```json
{
  "enabled": true,
  "intervalMinutes": 15,
  "maxFrontierPages": 16,
  "requestDelaySeconds": 0.45,
  "source": "https://www.facebook.com/iamGospelWarrior",
  "albumId": "111666608844421"
}
```

Safe meanings:

- `enabled`: enable/disable background checks.
- `intervalMinutes`: server clamps this between 5 and 1,440 minutes.
- `maxFrontierPages`: importer clamps this between 1 and 40 pages.
- `requestDelaySeconds`: importer enforces at least 0.2 seconds between pagination calls.

Do not insert credentials, private cookies, or access tokens. They are neither required nor supported.

## 10. Verify HTTP and API behavior

With `update_server.py` running, open a second terminal in any directory and run:

```bash
python - <<'PY'
from urllib.request import urlopen
import json
urls = [
    'http://127.0.0.1:8000/',
    'http://127.0.0.1:8000/api/health',
    'http://127.0.0.1:8000/api/update/status',
    'http://127.0.0.1:8000/content.json.gz',
]
for url in urls:
    with urlopen(url, timeout=15) as response:
        print(response.status, response.headers.get('Content-Type'), url)
        if url.endswith('/status'):
            status = json.load(response)
            print('studies:', status['currentTotal'], 'state:', status['state'])
PY
```

Expected: HTTP 200 for every URL; status should report at least 3,796 studies for the recorded baseline and normally `state: current` when no check is running.

## 11. Manual browser verification

Open both:

- <http://127.0.0.1:8000/>
- <http://127.0.0.1:8000/study.html>

Checklist:

- [ ] Profile/timeline page loads without a console error.
- [ ] The total displays 3,796 or a later valid count.
- [ ] Search finds words in titles and bodies.
- [ ] Subject filters change the result set.
- [ ] **Load more posts** adds cards.
- [ ] **Title Index** lists studies and can open one in Focus mode.
- [ ] Focus reader shows full text and local image; previous/next navigation works.
- [ ] Photos and Reels tabs render.
- [ ] Saving a study persists after refresh in the same browser.
- [ ] Study Reader loads cards and can open a full article.
- [ ] Updates tab reports API availability when using `update_server.py`.
- [ ] `python validate_archive.py` still passes after any update.

No automated browser test was recorded, so these are manual checks rather than claimed historical passes.

## 12. Deployment

### Static hosting

Deploy the entire project folder (or at minimum the browser files, `content.json.gz`, `update-status.json`, and complete `assets/`) to any host that:

- serves `.gz` as a downloadable binary (`application/gzip` is ideal),
- permits relative file requests,
- does not rewrite image requests to HTML,
- supports files totaling about 92 MB.

No front-end build command exists. Upload files as-is.

For updates in static hosting, run this elsewhere on a schedule:

```bash
cd /path/to/gospel-warrior-study
. .venv/bin/activate
python updater.py --once
python validate_archive.py
```

Then deploy changed `content.json.gz`, `update-status.json`, `update-log.jsonl` if desired, and new/changed assets.

### Long-running Python deployment

Run:

```bash
python update_server.py --host 127.0.0.1 --port 8000
```

Place a real reverse proxy/TLS/auth policy in front if exposing it publicly. The local server is intentionally simple and the POST update/settings endpoints do not authenticate users. Do not bind it directly to the public internet without appropriate network controls.

A systemd, Docker, Windows Service, or cloud-platform configuration was not created or tested in this task, so exact production service commands are **not recorded**.

## 13. Rebuilding from a blank directory

The application shell can be recreated by copying the source files, but the exact historical dataset cannot be reliably regenerated from Facebook alone. The updater is incremental and expects a non-empty valid `content.json.gz` seed.

To recreate the exact final project on another computer:

1. Copy the final `content.json.gz`.
2. Copy all 3,825 image assets.
3. Copy HTML/CSS/JS/Python/config files.
4. Install requirements.
5. Run validation.
6. Start the server.

Without steps 1–2, the archive's September 2017–October 2026 historical coverage and exact curation cannot be guaranteed. Facebook may no longer expose old posts, and initial harvesting commands are not available.

## 14. Troubleshooting

### `ModuleNotFoundError: requests`, `bs4`, or `PIL`

**Cause:** dependencies are not installed in the active Python environment.

**Verified remedy:**

```bash
python -m pip install -r requirements.txt
```

Confirm that your shell is using the intended virtual environment.

### The page is blank or reports that the archive cannot be loaded

**Likely causes:** opened with `file://`, old browser without `DecompressionStream`, wrong working directory, or host serving `content.json.gz` incorrectly.

**Safe solutions:**

```bash
cd /path/to/gospel-warrior-study
python -m http.server 8000 --bind 127.0.0.1
```

Then use a current browser at `http://127.0.0.1:8000`.

### HTTP 404 for status

The correct endpoint is:

```text
/api/update/status
```

`/api/status` was tried during development and correctly returned 404.

### Port 8000 is already in use

Choose another port:

```bash
python update_server.py --host 127.0.0.1 --port 8080
```

Then open `http://127.0.0.1:8080`.

### Facebook returns 403 or “public album grid”/token errors

**Observed behavior:** generic direct-page retrieval returned HTTP 403, while the updater's public album route succeeded.

**Verified safe behavior:** the updater records the error and retains the existing archive. Do not provide passwords or scrape private sessions.

Try again later. If repeated runs fail, Facebook may have changed public HTML/GraphQL structures; `initial_album_page`, `query_album_page`, or the public query document ID may require code maintenance.

### Group content is missing

The supplied group redirected logged-out requests to Facebook login. This is a known limitation, not an updater defect. Only use a lawful public export or direct public links; never insert private credentials into this project.

### Validation reports duplicate title/body

Do not hand-edit around the error. Restore the last known-good `content.json.gz`, inspect the candidate post, and preserve the normalized-title/body-hash rule. The updater itself checks duplicates before addition.

### Validation reports missing images

Inspect the referenced `imageLocal` path in `content.json.gz` and ensure the complete `assets` directory was copied/deployed. Re-running the updater will not necessarily redownload an image for a post already in the archive.

### Workspace grows over 128 MB

Current updater imports already apply 960-pixel progressive JPEG optimization. Measure with:

```bash
du -sh . assets
```

Do not delete random referenced images. Run validation to ensure every archived local path exists. Old WebP assets are already compact; further historical recompression was not required or tested.

### Updates run concurrently

The built-in server uses a process-local lock. Avoid running `python updater.py --once` manually while `update_server.py` is actively updating. Wait until status no longer reports `running`/`updateInProgress`.

### Server says current but Facebook visibly has a newer post

Possible reasons include public album indexing delay, a post outside the monitored album, regional/logged-out availability, a duplicate title, or a post that does not meet the long-form Bible-study filter. Check `update-log.jsonl` and the public permalink. “Current” means current to the monitored logged-out album frontier.

## 15. Final reproduction success criteria

A reproduction is successful when:

1. `python validate_archive.py` exits with code 0 and reports `ok: true`.
2. Browser pages load through HTTP.
3. Archive totals are 3,796 or a later valid count.
4. Search, filters, full reading, local images, and bookmarks work.
5. `/api/update/status` returns HTTP 200 under `update_server.py`.
6. A no-change updater run exits successfully without corrupting/decreasing the archive.
7. Project size remains within the intended storage budget.
