# Tools, Skills, Dependencies, and Workflows

This inventory includes only tools/services supported by conversation evidence. Where the historical record is incomplete, it says so rather than inferring usage.

## 1. AI execution environment

### Arena.ai Agent Mode

- **Purpose:** agentic assistant environment used to inspect, edit, execute, validate, and present workspace deliverables.
- **Configuration:** sandboxed workspace rooted at `/home/user`; persisted files under that root; long-running preview processes proxied from ports bound to `0.0.0.0`.
- **Interaction:** orchestrated workspace tools, shell commands, public web access, and background preview serving.
- **Required to reproduce?** No. A person can follow [REPRODUCTION_GUIDE.md](REPRODUCTION_GUIDE.md) with Python and a browser.
- **Cost/limits:** platform-dependent; may be subject to account/tool usage and workspace-size limits. The relevant workspace cap in this session was approximately 128 MB.
- **Model:** the specific underlying model was not exposed in the task record and is therefore **not recorded**. Arena.ai Agent Mode may route work across different model providers; no particular provider/model is claimed here.

Hidden system instructions and confidential internal reasoning are not user-authorized project artifacts and are not reproduced. User-visible task instructions and reusable reconstructed prompts appear in [EXECUTION_REPORT.md](EXECUTION_REPORT.md#7-reusable-prompts-and-instructions).

## 2. Arena workspace tools actually used

### `functions.read_file`

- **Purpose:** read source, configuration, logs, status, and documentation from the workspace.
- **Why selected:** preserves exact file contents without shell parsing and supports large-file line ranges.
- **Configuration:** file path plus line offset/limit.
- **Interaction:** informed edits, tests, architecture documentation, and this report.
- **Required to reproduce?** No; any editor or `cat`/`sed` can substitute.
- **Cost/limits:** Arena platform limits; no external paid API known.

### `functions.write_file`

- **Purpose:** create or overwrite complete files.
- **Used for:** implementation/configuration files in historical work and the four final report files.
- **Configuration:** workspace path and full content.
- **Interaction:** paired with validation commands and `read_file` inspection.
- **Required to reproduce?** No; any editor works.

### `functions.edit_file`

- **Purpose:** fuzzy search-and-replace editing of existing files.
- **Used for final site:** update totals in HTML/README, add Pillow and image optimization, and correct documentation/status text.
- **Interaction:** changes were followed by syntax/archive/optimizer verification.
- **Required to reproduce?** No.

### `functions.bash`

- **Purpose:** execute one-shot shell/Python/Node commands in the sandbox.
- **Used for:** updater runs, validation, measurements, image optimization, HTTP checks, package/test/build commands in the deleted IPTV branch, and report evidence gathering.
- **Configuration:** command, working directory, timeout.
- **Interaction:** produced outputs recorded in [COMMAND_HISTORY.md](COMMAND_HISTORY.md).
- **Required to reproduce?** A terminal is required for the documented Python workflow, but not Arena's specific wrapper.
- **Privileges:** all recorded commands ran without `sudo`/administrator rights.

### `functions.fetch_page`

- **Purpose:** retrieve a web page as parsed Markdown.
- **Use/result:** attempted to retrieve `https://web.facebook.com/iamGospelWarrior`; Facebook returned HTTP 403.
- **Why selected:** quick public-page inspection without browser automation.
- **Required to reproduce?** No; the project updater uses Python requests and public album routes.
- **Cost/limits:** Arena/web access limits and remote-site rate/access limits.

### `functions.web_search`

- **Purpose:** search current public web results.
- **Use/result:** searched for recent Gospel Warrior Facebook content; returned no results.
- **Required to reproduce?** No.
- **Cost/limits:** search-service and Arena usage limits may apply.

### `functions.start_process`

- **Purpose:** run a long-lived background preview.
- **Use:** launched `python3 update_server.py --host 0.0.0.0 --port 8000` as “Gospel Warrior Bible Study.”
- **Interaction:** exposed the site through Arena's live preview and allowed local HTTP/API validation.
- **Current status:** a later process lookup returned `not_found`, so it is not claimed to still be running.
- **Required to reproduce?** No; run the same Python command in a normal terminal.

### `functions.get_process_output`

- **Purpose:** inspect liveness/logs of a process launched with `start_process`.
- **Use/result:** later lookup reported that the previous preview process was no longer found.
- **Required to reproduce?** No.

### `functions.ask_user`

- **Purpose:** present a structured clarification question.
- **Use:** asked which project should remain before destructive cleanup; the question was skipped, and the user later explicitly instructed deletion of IPTVnator.
- **Required to reproduce?** No.

### `multi_tool_use.parallel`

- **Purpose:** execute independent reads/checks concurrently.
- **Use:** parallelized file inspection, tests, lint/typecheck, and validation commands.
- **Required to reproduce?** No; commands can be run sequentially.

### Connected-app / GitHub connector attempt

- **Evidence:** preserved session record says GitHub connected-app tooling was checked during the deleted IPTV task and was unsupported; public downloads/checkouts were used instead.
- **Final project dependency:** none.
- **Credentials:** no GitHub token was stored or requested.

No evidence shows that an MCP server, voice-generation tool, speech tool, or proprietary browser automation plugin was used for the final Gospel Warrior update. They are not claimed.

## 3. Final application technologies

### HTML5

- **Purpose:** semantic structure for profile, timeline, title index, update center, study library, dialogs/readers, forms, and navigation.
- **Files:** `index.html`, `study.html`.
- **Why selected:** deploys statically with no build tool or framework.
- **Required:** yes.
- **Cost:** free/open web standard.

### CSS3

- **Purpose:** responsive Facebook-inspired profile layout and book-like study-reader presentation.
- **Files:** `styles.css`, `study-styles.css`.
- **Required:** yes for intended design; content remains present without it.
- **Cost:** free/open web standard.

### Vanilla JavaScript

- **Purpose:** gzip archive loading, rendering, search, filters, title index, focus/article readers, photo/reel displays, bookmarks, reading progress, update polling, and API controls.
- **Files:** `app.js`, `study-app.js`.
- **Browser APIs used:** Fetch, Streams, `DecompressionStream('gzip')`, DOM events, History API, `localStorage`, `Intl.DateTimeFormat`, `Intl.NumberFormat`.
- **Why selected:** no framework/build dependency and works from any HTTP static server in current browsers.
- **Required:** yes for interactive rendering.
- **Cost:** free/open standards.

### Python standard library

- **Observed version:** Python 3.13.14 in the execution environment.
- **Modules used:** `argparse`, `base64`, `copy`, `gzip`, `hashlib`, `io`, `json`, `os`, `re`, `tempfile`, `threading`, `time`, `collections`, `datetime`, `http.server`, `pathlib`, `urllib.parse`.
- **Purpose:** archive processing, atomic writes, validation, HTTP server/API, scheduler, and test/inspection scripts.
- **Required:** Python 3 is required for updates/server, but not for hosting already-generated static files.
- **Cost:** Python is free/open source.

### requests

- **Declared range:** `>=2.31,<3`; observed 2.33.0.
- **Purpose:** HTTP sessions, Facebook public-page/GraphQL/story/image requests, timeouts, and status handling.
- **Why selected:** reliable session-based HTTP client.
- **Configuration:** public crawler-style User-Agent, English accept-language, 90-second timeouts, no cookies/tokens supplied by the user.
- **Required:** yes for `updater.py`.
- **License/cost:** open source/free; remote services may rate-limit requests.

### Beautiful Soup 4 (`beautifulsoup4`)

- **Declared range:** `>=4.12,<5`; observed 4.15.0.
- **Purpose:** parse Facebook HTML and extract embedded `application/json` script payloads.
- **Required:** yes for `updater.py`.
- **License/cost:** open source/free.

### Pillow

- **Declared range:** `>=10,<13`; observed 12.3.0.
- **Purpose:** EXIF orientation, resizing new images to at most 960×960, alpha-to-white conversion, progressive JPEG output at quality 72.
- **Why selected:** reduce repeated update growth and satisfy the 128 MB workspace cap while preserving visual content.
- **Required:** yes for current `updater.py` and image optimizer tests.
- **License/cost:** open source/free.

## 4. External services and public integrations

### Facebook public profile

- **URL:** `https://www.facebook.com/iamGospelWarrior` (user supplied `web.facebook.com`; updater normalizes to `www.facebook.com`).
- **Purpose:** source of publicly exposed studies, metadata, permalinks, and images.
- **Access model:** logged-out public routes only. No password, private cookie, or access token.
- **Cost:** public access is ordinarily free, but subject to Facebook terms, page changes, throttling, regional behavior, and availability.
- **Required:** required only to fetch future updates; not required to read the local archive.

### Facebook public legacy album / GraphQL route

- **Album ID:** `111666608844421`.
- **GraphQL endpoint:** `https://www.facebook.com/api/graphql/`.
- **Purpose:** enumerate the newest media frontier and page until a known post boundary.
- **Configuration:** public page tokens extracted at runtime; fixed public query document identifier currently stored in `updater.py`.
- **Limits:** undocumented endpoint structure may change; public requests can be blocked/rate-limited.

### Facebook lookaside/image hosts

- **Purpose:** retrieve public post/profile/cover imagery.
- **Required:** only for updates; all current display assets are stored locally.

### Supplied Facebook group

- **URL:** `https://www.facebook.com/groups/1904819580346256`.
- **Result:** anonymous access redirected to login, so no group-only content was imported.
- **Required:** not used by the final updater due public-access limitation.

### GitHub / BtbN / FFmpeg (deleted branch only)

Public GitHub release/source downloads were used in the deleted IPTV task to inspect IPTVnator v0.24.0 and verify FFmpeg archives. They are not dependencies of Gospel Warrior Study.

## 5. Custom automation workflows

### Incremental archive update workflow

Implemented in `updater.py`:

1. Validate seed/current archive.
2. Scan new public album pages.
3. Stop at a known post boundary.
4. Fetch full story body and metadata.
5. Remove known CTA/promotion blocks.
6. Require long-form/Bible signals.
7. Deduplicate title/body.
8. optimize and store local image.
9. update profile/archive metadata.
10. validate and atomically replace gzip archive.
11. update status and append audit log.

This workflow is required for future automatic updates.

### Update server/scheduler workflow

Implemented in `update_server.py`:

- Serves static files.
- Checks shortly after startup and then on a configurable interval.
- Serializes updates with a lock.
- Exposes status, health, manual check, and schedule settings APIs.
- Adds no-cache and basic security headers.

Required only for interactive update controls and built-in scheduling.

### Archive validation workflow

Implemented in `validate_archive.py`:

- Requires non-empty posts.
- Ensures unique IDs, normalized titles, and body hashes.
- Verifies every local image path.
- Counts words and subjects.
- Checks recent imports for principal prohibited CTA phrases.

Strongly recommended after every update/deployment.

### Image budget workflow

Implemented inside `download_image` plus one historical batch migration:

- EXIF transpose.
- Thumbnail at maximum 960×960.
- Transparent images composited over white.
- RGB progressive JPEG, quality 72, optimized.
- Temporary file and atomic replacement.

Required to keep future growth manageable.

## 6. Project-specific agent instructions and skills

- The final Gospel Warrior project has no `AGENTS.md`, `.codex/skills`, `.claude/skills`, or equivalent custom agent instruction directory.
- A deleted IPTVnator repository had `AGENTS.md` and architecture contracts, and those were consulted for that branch. The user ordered that branch deleted; those files are unavailable and irrelevant to final reproduction.
- No reusable external “skill” package can be verified for the Gospel Warrior build.
- Reusable user-authorized prompts are documented in [EXECUTION_REPORT.md](EXECUTION_REPORT.md#7-reusable-prompts-and-instructions).

## 7. What is and is not required to reproduce

| Component | Exact restore/read | Future updates | Development/report recreation |
| --- | ---: | ---: | ---: |
| Final project folder, including archive/assets | Required | Required as seed | Required |
| Current browser with gzip `DecompressionStream` | Required | Required to view | Recommended |
| Python 3 | Not if statically hosted | Required | Required for validation |
| requests | No | Required | Required for updater tests |
| beautifulsoup4 | No | Required | Required for updater tests |
| Pillow | No | Required | Required for optimizer tests |
| Facebook public availability | No | Required | No for offline validation |
| Arena.ai | No | No | No |
| Credentials/API key | No | No | No |
| Node/npm/front-end build system | No | No | No |
| SQL database | No | No | No |
