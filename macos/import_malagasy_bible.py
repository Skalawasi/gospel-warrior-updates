#!/usr/bin/env python3
"""Bundle the published public-domain Baiboly Malagasy (1865)."""
import hashlib
import json
import re

import requests

from import_kjv import BIBLE_COMMIT, OUTPUT, parse_verse, write_gzip

SOURCE = f'https://raw.githubusercontent.com/scrollmapper/bible_databases/{BIBLE_COMMIT}/sources/mg/Mg1865/Mg1865-osis.json'
SOURCE_HASH = '5b83b262c8ef7d32be7eeedea6d0d4d89be4e30f'
BOOK_NAMES = [
    'Genesisy', 'Eksodosy', 'Levitikosy', 'Nomery', 'Deoteronomia', 'Josoa', 'Mpitsara', 'Rota',
    '1 Samoela', '2 Samoela', '1 Mpanjaka', '2 Mpanjaka', '1 Tantara', '2 Tantara', 'Ezra', 'Nehemia', 'Estera', 'Joba',
    'Salamo', 'Ohabolana', 'Mpitoriteny', 'Tononkiran’i Solomona', 'Isaia', 'Jeremia', 'Fitomaniana', 'Ezekiela', 'Daniela',
    'Hosea', 'Joela', 'Amosa', 'Obadia', 'Jona', 'Mika', 'Nahoma', 'Habakoka', 'Zefania', 'Hagay', 'Zakaria', 'Malakia',
    'Matio', 'Marka', 'Lioka', 'Jaona', 'Asan’ny Apostoly', 'Romana', '1 Korintiana', '2 Korintiana', 'Galatiana', 'Efesiana',
    'Filipiana', 'Kolosiana', '1 Tesaloniana', '2 Tesaloniana', '1 Timoty', '2 Timoty', 'Titosy', 'Filemona', 'Hebreo',
    'Jakoba', '1 Petera', '2 Petera', '1 Jaona', '2 Jaona', '3 Jaona', 'Joda', 'Apokalypsy',
]


def main():
    response = requests.get(SOURCE, timeout=180)
    response.raise_for_status()
    raw = response.content
    if hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest() != SOURCE_HASH:
        raise ValueError('Malagasy Bible source checksum failed')
    source = response.json()
    if len(source['books']) != 66:
        raise ValueError('The Malagasy Bible must have all 66 books')
    output = OUTPUT / 'mg'
    output.mkdir(parents=True, exist_ok=True)
    books, total, empty = [], 0, []
    for number, book in enumerate(source['books'], 1):
        chapters = []
        for chapter in book['chapters']:
            verses = []
            for verse in chapter['verses']:
                text = ''.join(token[0] for token in parse_verse(verse['text'])).strip()
                if not text:
                    empty.append(verse['name'])
                verses.append({'number': verse['verse'], 'text': text, **({'textUnavailable': True} if not text else {})})
                total += 1
            chapters.append(verses)
        name = BOOK_NAMES[number - 1]
        english = re.sub(r'^(III|II|I) ', lambda match: {'I': '1', 'II': '2', 'III': '3'}[match[1]] + ' ', book['name'])
        if english == 'Revelation of John':
            english = 'Revelation'
        file = f'mg/{number:02}.json.gz'
        write_gzip(OUTPUT / file, {'name': name, 'chapters': chapters})
        books.append({'name': name, 'englishName': english, 'file': file, 'chapters': len(chapters), 'verses': [len(chapter) for chapter in chapters]})
    manifest = {'version': 1, 'translation': 'Baiboly Malagasy (1865)', 'language': 'mg', 'license': 'Public Domain', 'verseCount': total, 'textlessSourceSlots': empty,
                'books': books, 'source': {'url': SOURCE, 'gitBlobSHA1': SOURCE_HASH},
                'attribution': 'Baiboly Malagasy (1865), CrossWire via Scrollmapper. Public domain. Book navigation labels localized; editorial headings/notes omitted; verse wording retained.'}
    (output / 'index.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'Bundled Baiboly Malagasy (1865): {len(books)} books and {total:,} verses.')
    print(f'Source numbering placeholders without text: {len(empty)}')


if __name__ == '__main__':
    main()
