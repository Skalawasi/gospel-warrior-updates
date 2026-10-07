"""Canonical completeness and verse-specific original-language checks."""
import gzip
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / 'gospel-warrior-study/assets/bible'


def read(file):
    with gzip.open(DATA / file, 'rt', encoding='utf-8') as stream:
        return json.load(stream)


def verse_text(verse):
    return ''.join(token[0] for token in verse['tokens'])


class BibleDataTests(unittest.TestCase):
    def test_complete_canon_and_every_link_resolves(self):
        index = json.loads((DATA / 'index.json').read_text())
        lexicon = read('lexicon.json.gz')
        self.assertEqual(len(index['books']), 66)
        total = 0
        for metadata in index['books']:
            book = read(metadata['file'])
            self.assertEqual(len(book['chapters']), metadata['chapters'])
            for chapter in book['chapters']:
                self.assertEqual([verse['number'] for verse in chapter], list(range(1, len(chapter) + 1)))
                for verse in chapter:
                    self.assertTrue(verse_text(verse).strip())
                    for _, codes, _ in verse['tokens']:
                        for code in codes:
                            self.assertIn(code, lexicon)
                total += len(chapter)
        self.assertEqual(total, 31102)

    def test_known_passages_and_correct_hebrew_greek_lemmas(self):
        genesis = read('01.json.gz')['chapters'][0][0]
        self.assertEqual(verse_text(genesis), 'In the beginning God created the heaven and the earth.')
        self.assertIn(['God', ['H430'], False], genesis['tokens'])
        john = read('43.json.gz')['chapters'][0][0]
        self.assertIn('In the beginning was the Word', verse_text(john))
        self.assertTrue(any('Word' in text and 'G3056' in codes for text, codes, _ in john['tokens']))
        lexicon = read('lexicon.json.gz')
        self.assertEqual(lexicon['G3056']['lemma'], 'λόγος')
        self.assertEqual(lexicon['H430']['lemma'], 'אֱלֹהִים')
        self.assertIn('God', lexicon['H430']['meaning'])
        self.assertEqual(len(read('19.json.gz')['chapters'][118]), 176)
        self.assertIn('The grace of our Lord Jesus Christ', verse_text(read('66.json.gz')['chapters'][21][20]))

    def test_published_malagasy_canon_and_source_numbering(self):
        index = json.loads((DATA / 'mg/index.json').read_text())
        kjv = json.loads((DATA / 'index.json').read_text())
        self.assertEqual(len(index['books']), 66)
        self.assertEqual([book['englishName'] for book in index['books']], [book['name'] for book in kjv['books']])
        total, placeholders = 0, 0
        for metadata in index['books']:
            book = read(metadata['file'])
            self.assertEqual(len(book['chapters']), metadata['chapters'])
            for chapter in book['chapters']:
                self.assertEqual([verse['number'] for verse in chapter], list(range(1, len(chapter) + 1)))
                for verse in chapter:
                    if verse.get('textUnavailable'):
                        self.assertEqual(verse['text'], '')
                        placeholders += 1
                    else:
                        self.assertTrue(verse['text'].strip())
                        self.assertNotIn('<title', verse['text'])
                    total += 1
        self.assertEqual(total, 31172)
        self.assertEqual(placeholders, 72)
        self.assertEqual(len(index['textlessSourceSlots']), placeholders)
        self.assertIn('Andriamanitra nahary ny lanitra sy ny tany', read('mg/01.json.gz')['chapters'][0][0]['text'])
        self.assertIn('Andriamanitra', read('mg/43.json.gz')['chapters'][2][15]['text'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
