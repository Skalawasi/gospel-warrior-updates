# Gospel Warrior — bundled software

The app uses Apple's AppKit and WebKit frameworks supplied by macOS. It includes
the original Gospel Warrior study website, its locally archived study content,
and the following runtime components:

- **CPython 3.12.15**, Python Software Foundation License, distributed through
  Astral's python-build-standalone release `20261003`. The bundled runtime includes
  Python's `LICENSE.txt` and its dependency license directory.
  <https://github.com/astral-sh/python-build-standalone>
- **Requests**, Apache License 2.0. <https://requests.readthedocs.io/>
- **Beautiful Soup**, MIT License. <https://www.crummy.com/software/BeautifulSoup/>
- **Pillow**, MIT-CMU License. <https://python-pillow.org/>
- Their runtime dependencies, including certifi, charset-normalizer, idna,
  urllib3, soupsieve, and typing_extensions. Their license files are retained
  in the corresponding `*.dist-info` directories in the bundled Python runtime.

Exact installed package versions and the runtime download checksum are recorded
in `Contents/Resources/build-manifest.json`. The cross-and-open-Bible app icon is
generated locally by `macos/make_icon.py`.

## Bible texts and dictionaries

The app includes the complete KJV/OSIS Bible with Strong’s number associations
and the published public-domain Baiboly Malagasy (1865), from CrossWire via
Scrollmapper. It also includes Open Scriptures’ Hebrew (2010) and Greek (2009)
Strong’s JSON dictionaries, distributed under the source CC-BY-SA terms. The
derived lexicon retains those terms. Full source credits, licenses, changes,
pinned source URLs, and reproduction instructions are bundled at
`website/assets/bible/SOURCES.md` and in the Bible index manifests.

French and Malagasy study versions use bundled Helsinki-NLP OPUS-MT models
(Apache-2.0), CTranslate2 (MIT), SentencePiece (Apache-2.0), and NumPy
(BSD-3-Clause). They are labelled as machine translations. Model cards, pinned
source URLs, SHA-256 checksums and attribution are bundled under
`website/assets/translation-models/`. Runtime package licenses are retained.
Earlier saved Google Translate versions remain readable.
