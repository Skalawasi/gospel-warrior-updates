# Gospel Warrior Android app

This directory contains the Android wrapper for the existing Gospel Warrior
Study Companion website. It serves the complete offline reader from the APK in
a native WebView, including the study archive, KJV, Malagasy Bible, Strong's
dictionary, saved studies, notes, and reading preferences.

## Build

From this directory, run:

```bash
./gradlew assembleDebug
```

That creates an offline-only Android build. To enable live study updates, host
the existing `update_server.py` behind a public HTTPS URL and pass that URL at
build time:

```bash
./gradlew assembleDebug -PupdateBaseUrl=https://studies.example.com
```

The Android app then checks `/api/update/status` while it is open, downloads a
new `content.json.gz` when the archive revision changes, and uses the same
server for images that were not bundled in the installed APK. The server must
remain online and its scheduler must keep running the existing updater. The
server now includes CORS headers for the Android reader.

The URL can also be entered or changed inside **Settings → Updates → Android
update source**. It is stored on the device and the latest downloaded archive is
cached for offline reading.

The debug APK is written to:

```text
app/build/outputs/apk/debug/app-debug.apk
```

The Gradle build generates the website payload from `../gospel-warrior-study/`
on every build. The translation model bundle and desktop/server files are
intentionally omitted: translation preparation depends on the Mac Python
service, while the Android app provides the complete offline English and Bible
reading experience.

Without `-PupdateBaseUrl` or a URL entered in the app, the app remains fully
offline and keeps the bundled archive as its source of truth.

## Public free hosting for friends

The repository includes a GitHub Actions workflow at
`../.github/workflows/publish-study-updates.yml`. It runs the existing public
Facebook importer hourly on GitHub's servers, writes a static status document,
and publishes changed archive files. Your Mac does not need to be online.

Create a **public** GitHub repository, upload the project files that are not
ignored by the root `.gitignore`, and enable GitHub Actions. The update source
for the APK is the HTTPS raw-content URL:

```text
https://raw.githubusercontent.com/GITHUB_NAME/REPOSITORY/main/gospel-warrior-study
```

The raw-content source provides the CORS response required by the Android
WebView. Build the APK once with that URL:

```bash
./gradlew assembleDebug -PupdateBaseUrl=https://raw.githubusercontent.com/GITHUB_NAME/REPOSITORY/main/gospel-warrior-study
```

Friends then install that APK normally. Whenever they open it with internet
access, it polls the public status document, downloads a changed archive, and
keeps the newest studies available offline. The public repository contains
the archive and study images; do not place secrets, passwords, or private
tokens in it.
