#!/usr/bin/env python3
"""Build the bundled KJV/Strong's reader from pinned, attributed source data."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / 'gospel-warrior-study/assets/bible'
BIBLE_COMMIT = 'e1b254cef86d0e65b1a5d1a94b8b112d0f296a2c'
STRONGS_COMMIT = '0acd2f251c2d35ff8db2dece4e0593979d3ac223'
SOURCES = {
    'bible': (f'https://raw.githubusercontent.com/scrollmapper/bible_databases/{BIBLE_COMMIT}/sources/en/KJV/KJV-osis.json', '260707635cf5dd0d717cec02e1e730f72c3fe579'),
    'hebrew': (f'https://raw.githubusercontent.com/openscriptures/strongs/{STRONGS_COMMIT}/hebrew/strongs-hebrew-dictionary.js', 'b5b7cd2799981b0bcf96a93541236187b2c85fcf'),
    'greek': (f'https://raw.githubusercontent.com/openscriptures/strongs/{STRONGS_COMMIT}/greek/strongs-greek-dictionary.js', '0bebdeeec31f93b42ec591909da3f18626a684a8'),
}


def download(name):
    url, expected = SOURCES[name]
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    raw = response.content
    actual = hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()
    if actual != expected:
        raise ValueError(f'Pinned source checksum failed: {name}')
    return raw.decode('utf-8-sig')


class VerseParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tokens = []
        self.words = []
        self.added = 0
        self.ignored = 0

    def handle_starttag(self, tag, attrs):
        if tag in {'note', 'title'}:
            self.ignored += 1
        if self.ignored:
            return
        if tag == 'w':
            lemma = dict(attrs).get('lemma', '')
            self.words.append([letter + str(int(number)) for letter, number in re.findall(r'strong:([HG])(\d+)', lemma)])
        if tag == 'transchange':
            self.added += 1

    def handle_endtag(self, tag):
        if tag in {'note', 'title'}:
            self.ignored = max(0, self.ignored - 1)
            return
        if self.ignored:
            return
        if tag == 'w' and self.words:
            self.words.pop()
        if tag == 'transchange':
            self.added = max(0, self.added - 1)

    def handle_startendtag(self, tag, attrs):
        # OSIS milestones/paragraph markers are layout, not verse wording.
        pass

    def handle_data(self, text):
        if self.ignored or not text:
            return
        codes = self.words[-1] if self.words else []
        token = [text, codes, bool(self.added)]
        if self.tokens and self.tokens[-1][1:] == token[1:]:
            self.tokens[-1][0] += text
        else:
            self.tokens.append(token)


def parse_verse(text):
    parser = VerseParser()
    parser.feed(text)
    parser.close()
    return parser.tokens


def parse_dictionary(source):
    # Extract JSON as data; do not execute downloaded JavaScript.
    start = source.index('{', source.index('var strongs'))
    data, _ = json.JSONDecoder().raw_decode(source[start:])
    return {code: {
        'lemma': entry.get('lemma', ''),
        'transliteration': entry.get('xlit') or entry.get('translit', ''),
        'pronunciation': entry.get('pron', ''),
        'meaning': entry.get('strongs_def', '').strip(),
        'derivation': entry.get('derivation', ''),
        'kjv': entry.get('kjv_def', ''),
    } for code, entry in data.items()}


def write_gzip(path, data):
    raw = json.dumps(data, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    path.write_bytes(gzip.compress(raw, mtime=0))


def main():
    bible = json.loads(download('bible'))
    lexicon = {**parse_dictionary(download('hebrew')), **parse_dictionary(download('greek'))}
    OUTPUT.mkdir(parents=True, exist_ok=True)
    books = []
    verse_total = 0
    code_total = 0
    missing = set()
    for number, book in enumerate(bible['books'], 1):
        name = re.sub(r'^(III|II|I) ', lambda match: {'I': '1', 'II': '2', 'III': '3'}[match[1]] + ' ', book['name'])
        if name == 'Revelation of John':
            name = 'Revelation'
        chapters = []
        for chapter in book['chapters']:
            verses = []
            for verse in chapter['verses']:
                tokens = parse_verse(verse['text'])
                if not ''.join(token[0] for token in tokens).strip():
                    raise ValueError(f'Empty verse: {verse["name"]}')
                verses.append({'number': verse['verse'], 'tokens': tokens})
                verse_total += 1
                for _, codes, _ in tokens:
                    code_total += len(codes)
                    missing.update(code for code in codes if code not in lexicon)
            chapters.append(verses)
        file = f'{number:02}.json.gz'
        write_gzip(OUTPUT / file, {'name': name, 'chapters': chapters})
        books.append({'name': name, 'file': file, 'chapters': len(chapters), 'verses': [len(chapter) for chapter in chapters]})
    if len(books) != 66 or verse_total != 31102:
        raise ValueError(f'Incomplete Bible: {len(books)} books, {verse_total} verses')
    write_gzip(OUTPUT / 'lexicon.json.gz', lexicon)
    manifest = {
        'version': 1, 'translation': 'King James Version', 'books': books,
        'verseCount': verse_total, 'strongsLinks': code_total, 'dictionaryEntries': len(lexicon),
        'unavailableDictionaryCodes': sorted(missing),
        'sources': {name: {'url': url, 'gitBlobSHA1': sha} for name, (url, sha) in SOURCES.items()},
        'attribution': 'KJV/OSIS: CrossWire Bible Society via Scrollmapper. Strong’s Hebrew and Greek JSON dictionaries: Open Scriptures (2009/2010), CC-BY-SA; source credits and licenses in SOURCES.md.',
    }
    (OUTPUT / 'index.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Bundled {len(books)} books, {verse_total:,} verses, {code_total:,} verse-specific Strong’s links and {len(lexicon):,} dictionary entries.')
    print(f'Unavailable dictionary codes: {sorted(missing)}')


if __name__ == '__main__':
    main()
