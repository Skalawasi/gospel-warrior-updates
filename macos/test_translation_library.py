"""Coverage counts must refer to complete, current-source study versions."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'gospel-warrior-study'))
from translation_library import TranslationLibrary
import study_translations as translations


class TranslationLibraryTests(unittest.TestCase):
    def test_catalog_counts_only_current_complete_translations(self):
        post = {'id': 'test', 'title': 'Grace', 'subtitle': '', 'text': 'Original complete study'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = TranslationLibrary(root, lambda: [post], lambda: 'revision-1', start=False)
            library.reload()
            self.assertEqual(library.status()['ready'], {'fr': 0, 'mg': 0})
            payload = {'sourceKey': translations.source_key(post, 'fr'), 'language': 'fr', 'study': {'title': 'La grâce', 'text': 'Une étude complète.'}}
            translations.register_translation(post, payload, root / 'translations')
            self.assertEqual(library.status()['ready'], {'fr': 1, 'mg': 0})
            self.assertEqual(library.catalog('fr')['entries'][0]['title'], 'La grâce')
            post['text'] = 'An updated teaching'
            library.get_revision = lambda: 'revision-2'
            library.reload()
            self.assertEqual(library.status()['ready']['fr'], 0)
            self.assertEqual(library.catalog('fr')['entries'], [])

    def test_pause_and_resume_persist_after_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            library = TranslationLibrary(root, lambda: [], lambda: 'revision', start=False)
            library.reload()
            self.assertEqual(library.configure(False)['state'], 'paused')
            reopened = TranslationLibrary(root, lambda: [], lambda: 'revision', start=False)
            self.assertFalse(reopened.enabled)
            reopened.configure(True)
            self.assertTrue(json.loads((root / 'translation-library.json').read_text())['enabled'])

    def test_all_studies_are_queued_in_both_languages(self):
        posts = [{'id': str(i), 'title': f'Study {i}', 'text': f'Teaching {i}'} for i in range(3)]
        with tempfile.TemporaryDirectory() as directory:
            library = TranslationLibrary(Path(directory), lambda: posts, lambda: 'revision', start=False)
            library.reload()
            self.assertEqual(len(library.queue), 6)
            self.assertEqual(library.status()['total'], 3)
            self.assertEqual([language for _, language, _ in library.queue], ['fr', 'mg'] * 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
