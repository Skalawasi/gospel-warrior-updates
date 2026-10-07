"""Real bundled-model checks: offline inference, EOS, formatting and no truncation."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'gospel-warrior-study'))
import local_translator
import study_translations


class TokenPartitionTests(unittest.TestCase):
    def test_long_source_is_partitioned_without_dropping_any_tokens(self):
        tokens = ['▁word', 'piece'] * 500
        groups = list(local_translator.token_groups(tokens))
        self.assertEqual([token for group in groups for token in group], tokens)
        self.assertTrue(all(len(group) <= 240 for group in groups))


@unittest.skipUnless(importlib.util.find_spec('ctranslate2') and local_translator.available('mg'), 'Run with the bundled Python runtime for model inference')
class LocalModelTests(unittest.TestCase):
    def test_french_and_malagasy_translate_without_network_and_preserve_original_scripts(self):
        source = 'The grace of God brings salvation.\n\nThe original word is λόγος.\nאֱלֹהִים\n\nhttps://example.com/study'
        with patch('requests.Session.get', side_effect=AssertionError('Translation must work offline')):
            for language in ('fr', 'mg'):
                result = local_translator.translate(source, language)
                self.assertNotIn('The grace of God brings salvation.', result)
                self.assertIn('Dieu' if language == 'fr' else 'Andriamanitra', result)
                self.assertIn('λόγος', result)
                self.assertIn('אֱלֹהִים', result)
                self.assertIn('https://example.com/study', result)
                self.assertEqual(result.count('\n'), source.count('\n'))
                self.assertLess(len(result), 1000, 'Source EOS prevents runaway repetition')

    def test_complete_study_is_saved_with_local_provider_and_no_online_requests(self):
        post = {'id': 'offline-model-test', 'title': 'A study of faith', 'subtitle': '', 'text': 'A study of faith\n\nGod gives us wisdom.\n\nLet us walk in love.'}
        key = study_translations.source_key(post, 'fr')
        with tempfile.TemporaryDirectory() as directory, patch('requests.Session.get', side_effect=AssertionError('No internet')):
            path = Path(directory) / f'{key}.json'
            study_translations._translate(post, 'fr', key, path)
            result = json.loads(path.read_text())
            self.assertEqual(result['state'], 'ready')
            self.assertEqual(result['provider'], local_translator.PROVIDER)
            self.assertIn('Dieu', result['study']['text'])
            self.assertNotIn('God gives us wisdom.', result['study']['text'])
            study_translations._jobs.pop(key)


if __name__ == '__main__':
    unittest.main(verbosity=2)
