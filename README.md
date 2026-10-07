# Gospel Warrior Study

The finished website lives in [`gospel-warrior-study/study.html`](gospel-warrior-study/study.html). The root `index.html` redirects there so the workspace opens the focused Bible-study library.

## Install the Mac app

Open **`dist/Gospel Warrior-Intel.dmg`**, drag **Gospel Warrior** into
**Applications**, and launch it from Applications or the Dock.

The standalone app is built for **Intel Macs running macOS Big Sur 11 or later**,
including the late-2013 MacBook Pro. It includes the complete archive for offline
reading and runs its own bundled update service. No Terminal window or separate
Python installation is required.

**Version 2.0** uses a sidebar-based Study Companion interface, a quiet reading
room, dedicated settings, and a live Updates screen. It checks for new Bible
studies **every 15 minutes while open** and **automatically refreshes content in
place**, preserving your current reading session.

**Version 2.1** adds three reading skins and six colour palettes, including a
warm **Terracotta + Dark** preset. Choose them in **Settings → Reading**; appearance
choices persist across app relaunches and automatic content refreshes.

**Version 2.1.1** removes social-media invitations, monthly-subscriber offers,
Gospel Warrior Library promotions, and product/discount advertising from study
text. Existing saved archives are cleaned on upgrade, and future imports use the
same rules while retaining study IDs, bookmarks, and appearance preferences.

**Version 2.2** expands the offline library to **8,859 studies** by merging the
Arena AI archive with the existing collection and recovering 58 index-only full
texts from their public source posts. It includes approximately **11.7 million
words** and studies across **all 66 Bible books**. Distinct studies sharing a
headline are retained; duplicate checks compare the complete teaching text.
Shorter biblical devotionals are also included in future update checks.

On upgrade, newly bundled studies merge into an older saved library while
existing study IDs, newer collected studies, bookmarks, and settings are retained.

See [`macos/INSTALL.md`](macos/INSTALL.md) for installation, keyboard shortcuts,
data storage, and build instructions. The native application source and packaging
tools are in `macos/`.

## Install the Android app

The Android package is a native WebView shell around the same responsive Study
Companion. It includes the complete English study archive, offline KJV and
Malagasy Bibles, Strong’s word lookup, saved studies, notes, bookmarks, and
reading preferences.

Install the ready-to-use debug APK from
[`dist/Gospel Warrior-debug.apk`](dist/Gospel%20Warrior-debug.apk). On an Android
device, allow installation from the file manager when prompted, then open the
APK to install **Gospel Warrior**.

To rebuild it on a machine with Android SDK and Java 17 or later:

```bash
cd android
./gradlew assembleDebug
```

The build automatically packages the current website and archive while leaving
the desktop-only translation model bundle out of the Android package. The APK
is written to `android/app/build/outputs/apk/debug/app-debug.apk` and supports
Android 5.0/API 21 and newer.

### Enable daily Android study updates

The existing updater can also serve Android clients. Host the `gospel-warrior-study`
directory and keep its update server running at a public HTTPS URL. Then build
the APK with that URL:

```bash
cd android
./gradlew assembleDebug -PupdateBaseUrl=https://studies.example.com
```

The Android app checks the server while open, detects a changed archive
revision, downloads the latest study archive, and keeps local saved studies,
notes, bookmarks, and reading progress. Without `-PupdateBaseUrl`, the app uses
only its bundled offline archive. The URL can also be entered later in
**Settings → Updates → Android update source**, and the latest downloaded
archive is cached for offline reading.

### Share one automatically updated APK

For friends to use the APK without access to this Mac, use the included
`.github/workflows/publish-study-updates.yml`. Put the project in a **public**
GitHub repository; GitHub Actions runs the updater hourly and commits the
changed archive and study images. The Android client reads the public raw
source, so no Mac-hosted server is required:

```text
https://raw.githubusercontent.com/GITHUB_NAME/REPOSITORY/main/gospel-warrior-study
```

Build the distributable APK with that address compiled in:

```bash
cd android
./gradlew assembleDebug -PupdateBaseUrl=https://raw.githubusercontent.com/GITHUB_NAME/REPOSITORY/main/gospel-warrior-study
```

Give friends that APK. They install it normally; while the app is open and
connected to the internet, it checks the public status document and downloads
new study content automatically. Their saved studies, notes, bookmarks, and
reading progress remain on each device.

## Study tools and Bible reader — version 2.3

**Version 2.3.2** includes local OPUS-MT translation models, a persistent **Study
language** selector above the library, and background preparation of **all studies
in both French and Malagasy**. Translation runs on the Mac without an online
service or rate limit. **Translation progress** shows complete-study coverage and
the current job. Translated titles and previews appear as full versions finish;
pending entries remain labelled.

The full collection is a long-running translation job, not an already-translated
bundle. Keep the app open; translation itself needs no internet. Completed text sections are cached
in SQLite, so interruptions and app relaunches resume existing work. Full completed
studies are stored as source-versioned JSON. Reading a pending study prioritizes
its version while the background queue continues; preparation can be paused.

- **English / Français / Malagasy** switch in each study and above the library.
  French and Malagasy studies are machine-translated locally using bundled
  OPUS-MT models and cached. Reading a pending study prioritizes it.
  Local translation needs the app service with Python 3.12 and the model dependencies.
- **Select all text** and **Copy study**, including the selected language’s title
  and complete study text. ⌘A / Ctrl+A selects the study while reading.
- **Notes & bookmarks**: automatically saved notes, selected-text highlighting,
  underlining, and passage bookmarks. Notes belong to the study; text markings
  belong to the specific language version. Bookmarks can return to a passage.
- **Bible · KJV & Malagasy** in the sidebar: complete offline **King James Bible**
  and published **Baiboly Malagasy (1865)**. The version switch retains the selected
  book, chapter, and verse where that numbering exists in the other edition.
- Hover, click, or keyboard-focus KJV words for verse-specific **Strong’s Hebrew /
  Aramaic and Greek** lemmas, transliterations, meanings, and KJV renderings.
  Study Scripture-reference buttons open the Bible reader at that passage.

Notes and text markings are saved on this device and survive app replacement.
Bible source credits and reproducible import instructions are in
[`assets/bible/SOURCES.md`](gospel-warrior-study/assets/bible/SOURCES.md).
Translation model credits and reproduction instructions are in
[`assets/translation-models/SOURCES.md`](gospel-warrior-study/assets/translation-models/SOURCES.md).

## Start the full website

```bash
cd gospel-warrior-study
python3 -m pip install -r requirements.txt
python3 update_server.py --host 127.0.0.1 --port 8000
```

Open <http://127.0.0.1:8000>.

For a static reading-only preview:

```bash
cd gospel-warrior-study
python3 -m http.server 8000
```

The full project includes the study archive, archive map, year timeline, search, topic filters, Bible Study Reader, local images, automatic archive updates, duplicate detection, archive validation, and the reproduction documentation requested in `EXECUTION_REPORT.md`.
