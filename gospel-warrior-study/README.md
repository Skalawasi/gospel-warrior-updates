# Gospel Warrior Facebook-Style Reading Archive

A responsive, self-contained profile and reading archive built from the public content at [facebook.com/iamGospelWarrior](https://www.facebook.com/iamGospelWarrior).

## Current Study Companion archive — version 2.2

The current reading interface is `study.html`, also packaged as the standalone
Intel Mac app. The merged archive contains **8,859 studies**, approximately **11.7 million words**,
and indexed material for **all 66 Bible books**. It adds 5,005 entries from the
Arena collection, including 58 full texts recovered from their public posts.
Social calls to action, subscription/library advertising, discount offers,
promotional page links, and hashtag footers are removed from the reading text.
Distinct studies with matching headlines are preserved; repeated complete
teaching text is deduplicated.

The older profile-clone description below records the original delivery.

## Final website

`index.html` is the primary delivery. It recreates the public profile experience with:

- Cover image, profile image, follower information, tabs, intro, work, location, relationship, and profile history
- A Facebook-style post timeline
- 3,796 unique, complete publicly accessible studies, including 174 newly imported studies from September 29 through October 3, 2026
- 7,189,381 message-focused words preserved for reading after removing 3,146 social-action blocks
- Public devotional coverage now reaches back to September 2017 through the profile’s named historical albums
- Repeated complete teaching texts are deduplicated; distinct studies may share a title
- Social-media calls to comment, share, tag, follow, subscribe, support, react, or save removed from the displayed study text while the remaining original wording is retained
- 17 study subjects with subject filtering, full-text search, and continuous Focus Reader navigation
- Structured index metadata for Bible references, Bible books, biblical characters, topics, testament, and Gospel categories
- Complete Bible Study Index with date/A–Z/Z–A sorting, Old/New Testament shelves, individual book and character navigation, matching-term highlighting, and paginated rendering
- Dedicated Jesus & Gospels, biblical-character, Bible-book, and chronological timeline exploration
- Reading-first optimized local images for every archived post
- Compressed archive loading keeps the very large text collection practical in a browser
- Every post image stored locally
- Expandable full post text and a distraction-free Focus reader
- A complete Title Index table listing every post, introduction, topic, date, and reading time
- Search and sorting in the Title Index, with one-click jumps into the selected full post
- Search across all archived post text
- Topic shortcuts, saved studies, and comfortable reading mode
- About, Reels, and Photos views
- Five premium Old Testament PowerPoint reading decks in `presentations/`
- Six public Reel thumbnails linking to the original videos
- Responsive desktop, tablet, and mobile layouts

## Bible Study Reader

`study.html` preserves the separate editorial Bible Study Library. It provides guided paths, cards, search, bookmarks, adjustable reading size, and reading progress.

## Automatic updates

The Facebook-style profile now includes a dedicated **Updates** tab, a live status card, recently imported titles, schedule controls, manual **Check now**, and automatic webpage refresh when a larger archive is detected.

For the full automatic mode, run:

```bash
python -m pip install -r requirements.txt
python update_server.py --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000`. The default schedule checks the logged-out public profile every 15 minutes. Windows users can double-click `start-auto-update.bat`; macOS/Linux users can run `./start-auto-update.sh`. See `AUTO_UPDATE.md` for deployment and scheduler details.

Each incremental update:

- scans newest public-album pages until it reaches a known post;
- fetches the complete public body, original permalink, and image;
- optimizes newly imported images to a maximum 960-pixel progressive JPEG so frequent updates remain deployable within the workspace size budget;
- removes social/promotional CTA blocks while retaining the study wording;
- removes monthly-subscriber invitations, Gospel Warrior Library advertisements,
  product discounts, merchandise offers, and standalone share/comment/tag reminders;
- rejects duplicates by normalized full title and complete-body hash;
- validates and atomically replaces `content.json.gz`;
- updates `update-status.json`, allowing open webpages to refresh automatically.

The updater uses public logged-out access only and never asks for passwords, private cookies, or access tokens. If Facebook temporarily rate-limits or changes its public pages, the current archive remains unchanged and the scheduler retries later.

## Static viewing

The website can still be viewed without the update API:

```bash
python -m http.server 8000 --bind 0.0.0.0
```

In this mode the webpage can detect files refreshed by an external cron job, but its schedule controls and **Check now** button are unavailable.

## Main files

- `index.html` — Facebook-style profile clone
- `styles.css` — clone layout and responsive styling
- `app.js` — timeline, tabs, search, Focus reader, and interactions
- `study.html` — editorial Bible Study Reader
- `study-styles.css` and `study-app.js` — Study Reader styling and behavior
- `content.json.gz` — compressed public profile metadata and complete post text (loaded automatically by the site)
- `updater.py` — one-shot incremental public-profile importer
- `update_server.py` — website server, update API, and background scheduler
- `validate_archive.py` — integrity, duplicate, image, and whole-archive CTA checks
- `presentations/` — five randomly selected Old Testament study decks and their selection manifest
- `update-status.json` and `update-config.json` — live status and schedule configuration
- `AUTO_UPDATE.md` — setup, controls, hosting, and public-access limitations
- `assets/` — all archived images and Reel thumbnails

The static reader uses no external frameworks, CDNs, fonts, or browser-side build step. It uses standard browser `fetch`, `DecompressionStream`, and `localStorage` APIs. Automatic importing is server-side and depends on Facebook continuing to expose the source posts publicly.

The archive metadata can be backfilled without a network request after importer-rule changes:

```bash
python3 updater.py --enrich-metadata
```

The display cleanup can also be rerun locally after CTA rules change:

```bash
python3 updater.py --clean-archive
```

The supplied Gospel Warrior group URL currently redirects anonymous requests to Facebook login, so no group-only post was imported without public access. Future group imports use normalized-title and complete-body deduplication so a study already preserved from the profile will not be copied twice. Historical or group posts that Facebook does not expose anonymously require a Facebook export or direct public post URLs.
