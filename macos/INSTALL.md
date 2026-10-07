# Install Gospel Warrior on your Mac

## Installation

1. Double-click **Gospel Warrior-Intel.dmg**.
2. Drag **Gospel Warrior** onto the **Applications** folder in that window.
3. Open **Applications → Gospel Warrior**.
4. To keep it in your Dock, right-click its Dock icon and select
   **Options → Keep in Dock**.

You can also launch the supplied **Gospel Warrior.app** directly.
No separate Python installation, browser setup, or Terminal window is required.

## Compatibility

- Intel Mac, including the late-2013 MacBook Pro.
- **macOS Big Sur 11.0 or later**. Big Sur is the last macOS version Apple
  officially supports on the late-2013 MacBook Pro.
- Uses macOS's built-in WebKit instead of including another browser engine.
- Contains the complete packaged study archive and local images for offline reading.
- New study checks require an internet connection and available public source pages.

## Reading and updates

Version 2 introduces an app-style workspace with a forest-green sidebar, warm
parchment surfaces, and a quiet reading room:

- **Study desk** — the latest study, continue reading, and Scripture shortcuts.
- **Study library** — search, sorting, compact lists or study cards.
- **Saved studies**, **Bible index**, **Study topics**, and **Timeline**.
- **Library updates** — live check/import status, last check, and next-check countdown.
- **Settings** — separate Reading, Library, and Updates tabs.

The personal 52nd-birthday announcement and portraits remain excluded.
Version 2.1.1 also removes social-media calls to action, subscription invitations,
external Gospel Warrior Library promotions, and merchandise/discount offers from
study text and previews. Existing saved archives are cleaned on upgrade, and the
same cleanup applies to future imports.

Version **2.2** includes **8,859 studies**, approximately **11.7 million words**,
and material indexed across **all 66 Bible books**. The Arena collection has been
merged with existing studies, including 58 recovered full texts that were listed
in its newer index. Shorter Bible devotionals are included alongside long-form
studies. Different texts can share a headline; duplicate detection compares the
complete teaching text.

Replacing an older app also merges newly bundled studies into its saved library,
preserving existing IDs, later online imports, bookmarks, and reading settings.
This runs once per changed bundled archive.

## Study tools and Bible versions — version 2.3

Open a study and choose **English**, **Français**, or **Malagasy**. French and
Malagasy studies are machine translations generated locally using bundled OPUS-MT
models. Translation needs no internet or service account; completed translations
are saved in your app data and available offline. Switching languages remembers your
choice and does not alter the original English archive.

**Version 2.3.2:** the **Study language** selector is also visible above the entire
library. **Translation progress** shows how many complete French and Malagasy
studies are ready offline. Both versions of every study are prepared automatically
in the background. The full library contains millions of words, so this is a
long-running job: keep the app open. Translation runs locally, without internet
access or request limits. You can pause or resume
preparation. Completed sections survive interruptions and app relaunches; opening
a pending study prioritizes its translation. Translated titles/previews appear as
complete versions become ready. Pending entries are clearly labelled.

The local engine replaces reliance on the online translation service that was
rejecting automated requests. Existing saved translations remain available.

- **Select all text** selects the study’s title and reading text.
- **Copy study** copies the complete current-language study to the clipboard.
- Select a passage, then press **Highlight** or **Underline**. Markings save
  automatically and remain attached to that language’s wording.
- **Bookmark passage** saves selected text, or the current visible passage when
  nothing is selected. In **Notes & bookmarks**, click an entry to return to it.
- **Notes & bookmarks** opens the study notebook. Notes save automatically and
  are shared across the study’s three languages. Entries can be removed from the
  notebook. The existing **Save study** control bookmarks the entire study in
  **Saved studies**.

Choose **Bible · KJV & Malagasy** in the sidebar to read either complete offline
Bible. **English · KJV** includes 31,102 verses and verse-specific Strong’s
Hebrew/Aramaic and Greek dictionaries. Hover, click, or keyboard-focus a word to
see its lemma, transliteration, meaning, and KJV renderings. Dictionary meanings
are shown in English. Use **Escape** to dismiss a word popup.

**Malagasy · 1865** is the published public-domain **Baiboly Malagasy (1865)**,
with all 66 books and Malagasy book-navigation labels. The switch retains your
selected passage where the verse number exists in both editions. Source verse
numbering is preserved, including explicitly labelled empty numbering slots.
Choose **Open this passage in KJV** for original-language word study.

Enter a reference such as **John 3:16**, **Jaona 3:16**, or **Salamo 23** to open a
passage. Scripture-reference buttons in a study also open the Bible reader.

Notes, highlights, underlines, saved studies, Bible version, and reading location
persist across app relaunches. Translations are stored under the app’s
`library/translations/` directory; notebook entries are included in
`preferences.json`. Replacing the app preserves these files.

## Appearance choices — version 2.1

Open **Settings → Reading** to combine **Light**, **Sepia**, or **Dark** skins with
one of six colour palettes:

- Forest & Gold
- Terracotta
- Midnight Blue
- Royal Plum
- Olive & Honey
- Ocean Teal

There are **18 combinations**. **Warm evening preset** selects **Terracotta +
Dark**, with warm charcoal surfaces, cream text, and soft coral accents. Changes
apply immediately throughout the app, including its native Mac window appearance,
and remain selected after relaunches and automatic content refreshes.

The reading room also has quick **Light / Sepia / Dark** buttons. The dark-mode
shortcut returns to your previous light or sepia choice. **Restore Forest & Light**
resets the colour palette and skin. Reading size, bookmarks, and update controls
are independent of appearance choices.

Useful keyboard shortcuts:

| Shortcut | Action |
| --- | --- |
| ⌘K | Search studies |
| ⌘, | Open settings |
| ⌘R | Refresh content in place |
| ⇧⌘R | Check online for new studies |
| ⌘D | Toggle dark reading mode |
| ⌘Q | Quit the app |
| ⌘1–⌘5 | Navigate the workspace |

## Automatic updates — enabled by default

The app checks shortly after launch, then **every 15 minutes while open**.
**Automatic content refresh is on by default**: newly collected Bible studies
appear without restarting the app or manually refreshing a webpage.

Refresh happens in place, preserving your open study, reading position, selected
text, search, filters, sorting, and saved studies. The app also remembers your
reading progress so you can continue from the study desk.

Open **Settings → Updates** to control automatic checks and automatic refresh.
Open **Library updates** in the sidebar, or **Navigate → Library Updates**, to see
the next-check countdown, last check, progress, and recently collected studies.
**Check now** performs an immediate manual check.

After Mac sleep, an overdue check runs when the computer resumes. If the public
source cannot be reached, the offline library remains available and the next
scheduled check retries. Reading the bundled archive needs no internet access.
External study links open in your default browser.

Saved studies and reading settings are stored in the app, independently of your
Safari/Chrome bookmarks for the original website.

## Your app data

Archive updates and preferences are stored in:

```text
~/Library/Application Support/Gospel Warrior/
```

Choose **File → Show App Data in Finder** to open this folder. Replacing the app
preserves this data. The application stops its own local service when you quit.
It can run alongside the original website server on port 8000.

## Local build

This is a locally built, ad-hoc-signed application. It is not an App Store release
or an Apple-notarized download. If another Mac blocks a transferred copy, use
**System Settings → Privacy & Security → Open Anyway** after attempting to open
it. On Big Sur, you can also right-click the app and choose **Open**.

To rebuild from this project on a Mac with Xcode Command Line Tools and Python 3.12+:

```bash
python3 macos/build.py
python3 macos/verify_app.py
```

The build downloads a checksum-pinned Intel Python runtime and bundles its
dependencies. Every bundled Mach-O binary is checked for a deployment target
no newer than macOS 11.0 before the app is packaged.
