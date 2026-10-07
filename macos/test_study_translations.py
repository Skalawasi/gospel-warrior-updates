"""Translation completeness, source invalidation and offline-cache checks."""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'gospel-warrior-study'))
import study_translations as translations


class TranslationTests(unittest.TestCase):
    def setUp(self):
        patcher = patch.object(translations.local_translator, 'available', return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_chunks_preserve_every_character_even_in_long_paragraphs(self):
        text = ('First paragraph.\n\n' + 'Tenin’Andriamanitra ' * 300 + '\n\nLast paragraph.\n')
        parts = list(translations.chunks(text, 1200))
        self.assertEqual(''.join(parts), text)
        self.assertTrue(all(len(part) <= 1200 for part in parts))

    def test_source_changes_invalidate_translation(self):
        post = {'id': 'test', 'title': 'Grace', 'text': 'Original study'}
        key = translations.source_key(post, 'fr')
        self.assertNotEqual(key, translations.source_key({**post, 'text': 'Updated teaching'}, 'fr'))
        self.assertNotEqual(key, translations.source_key(post, 'mg'))

    def test_complete_offline_translation_is_used_without_network(self):
        post = {'id': 'test', 'title': 'Grace', 'text': 'Original study'}
        key = translations.source_key(post, 'mg')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'translations').mkdir()
            payload = {'state': 'ready', 'sourceKey': key, 'study': {'title': 'Fahasoavana', 'text': 'Fianarana'}}
            (root / 'translations' / f'{key}.json').write_text(json.dumps(payload))
            with patch.object(translations, '_translate') as worker:
                self.assertEqual(translations.translation_status(post, 'mg', root), payload)
                worker.assert_not_called()

    def test_chunk_boundaries_survive_service_whitespace_trimming(self):
        session = Mock()
        session.get.return_value.json.return_value = [[['Texte traduit', 'source']]]
        text = 'First paragraph.\n\n'
        self.assertEqual(translations.translate_text(text, 'fr', session, time.monotonic() + 10), 'Texte traduit\n\n')

    def test_unsupported_language_is_rejected(self):
        with self.assertRaises(ValueError):
            translations.translation_status({'id': 'test'}, '../unsafe', Path('/tmp'))

    def test_failed_translation_never_saves_a_partial_version(self):
        post = {'id': 'failed', 'title': 'Grace', 'subtitle': 'Study', 'text': 'A complete study'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'translations/result.json'
            with patch.object(translations, 'translate_text', side_effect=['La grâce', OSError('offline')]):
                translations._translate(post, 'fr', 'failed-key', path)
            self.assertFalse(path.exists())
            self.assertEqual(translations._jobs.pop('failed-key')['state'], 'error')

    def test_ready_translation_saves_all_fields_atomically(self):
        post = {'id': 'complete', 'title': 'Grace', 'subtitle': 'Study', 'text': 'A complete study'}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'translations/result.json'
            with patch.object(translations, 'translate_text', side_effect=['Fahasoavana', 'Fianarana', 'Ny fianarana manontolo']):
                translations._translate(post, 'mg', 'complete-key', path)
            payload = json.loads(path.read_text())
            self.assertEqual(payload['study']['text'], 'Ny fianarana manontolo')
            self.assertEqual(payload['study']['title'], 'Fahasoavana')
            self.assertFalse(path.with_suffix('.tmp').exists())
            translations._jobs.pop('complete-key')

    def test_rate_limit_falls_back_to_another_google_host(self):
        import requests
        limited = Mock(status_code=429)
        error = requests.HTTPError('limited', response=limited)
        result = Mock()
        result.json.return_value = [[['La grâce', 'Grace']]]
        session = Mock()
        session.get.side_effect = [error, result]
        with patch.object(translations.time, 'sleep'):
            self.assertEqual(translations.translate_text('Grace', 'fr', session, time.monotonic() + 10), 'La grâce')
        self.assertEqual([call.args[0] for call in session.get.call_args_list], list(translations.ENDPOINTS))

    def test_interrupted_study_resumes_cached_chunks_without_retranslating(self):
        import requests
        text = 'A' * 2800 + 'B' * 10
        first = Mock()
        first.json.return_value = [[['Première partie', 'A']]]
        error = requests.HTTPError('limited', response=Mock(status_code=429))
        session = Mock()
        session.get.side_effect = [first, error, error]
        with tempfile.TemporaryDirectory() as directory, patch.object(translations.time, 'sleep'):
            root = Path(directory)
            with self.assertRaises(requests.HTTPError):
                translations.translate_text(text, 'fr', session, time.monotonic() + 10, root)
            resumed = Mock()
            resumed.json.return_value = [[['Deuxième partie', 'B']]]
            retry = Mock()
            retry.get.return_value = resumed
            self.assertEqual(translations.translate_text(text, 'fr', retry, time.monotonic() + 10, root), 'Première partieDeuxième partie')
            retry.get.assert_called_once()
            self.assertEqual(retry.get.call_args.kwargs['params']['q'], 'B' * 10)


if __name__ == '__main__':
    unittest.main(verbosity=2)
