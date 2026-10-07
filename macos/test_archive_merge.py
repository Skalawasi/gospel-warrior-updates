"""Checks for lossless Arena adaptation, real-text deduplication, and images."""
from __future__ import annotations

import copy
import io
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "macos"))
import merge_arena_archive as merge


class ArchiveMergeTests(unittest.TestCase):
    def study(self, pid, title, teaching):
        return {"id": pid, "title": title, "text": title + "\n\n" + teaching}

    def test_shared_headline_does_not_discard_a_different_study(self):
        base = [self.study("1", "Trust in God", "Genesis teaches us about Abraham’s journey.")]
        candidate = self.study("2", "Trust in God", "The Psalms teach us to pray through our grief.")
        outcomes = {}
        self.assertEqual(merge.merge_records(base, [candidate], outcomes), [candidate])
        self.assertEqual(outcomes["2"]["result"], "imported")

    def test_repeated_teaching_with_different_headline_is_deduplicated(self):
        base = [self.study("1", "Trust in God", 'Jesus said, “Follow me.” God gives us hope.')]
        candidate = self.study("2", "Faith and hope", 'Jesus said, "Follow me." God gives us hope.')
        original = copy.deepcopy(base)
        outcomes = {}
        self.assertEqual(merge.merge_records(base, [candidate], outcomes), [])
        self.assertEqual(outcomes["2"], {"result": "duplicate-text", "retainedId": "1"})
        self.assertEqual(base, original)

    def test_existing_id_keeps_the_current_record(self):
        base = [self.study("1", "Trust in God", "The current study text.")]
        outcomes = {}
        self.assertEqual(merge.merge_records(base, [self.study("1", "Replacement", "Different text.")], outcomes), [])
        self.assertEqual(base[0]["text"], "Trust in God\n\nThe current study text.")

    def test_future_updater_accepts_a_short_biblical_devotional(self):
        raw = {
            "id": "123", "timestamp": 1679356800, "url": "https://example.org/original",
            "image": "https://example.org/study.jpg",
            "text": "Trust in God\n\n" + "Jesus teaches us to love our neighbours. " * 12,
        }
        with patch.object(merge.updater, "download_image", return_value=("assets/study.jpg", "image/jpeg")):
            post, info = merge.updater.make_post(None, raw, {"trust in god"}, set())
        self.assertEqual(info["result"], "added")
        self.assertLess(merge.updater.word_count(post["text"]), 350)

    def test_future_updater_rejects_renamed_full_text_repetition(self):
        teaching = "Jesus teaches us to love our neighbours. " * 12
        original = "Trust in God\n\n" + teaching
        raw = {
            "id": "123", "timestamp": 1679356800, "url": "https://example.org/original",
            "image": "https://example.org/study.jpg", "text": "Faith and hope\n\n" + teaching,
        }
        known = {merge.updater.study_body_hash(original, "Trust in God")}
        with patch.object(merge.updater, "download_image") as download:
            post, info = merge.updater.make_post(None, raw, set(), known)
        self.assertIsNone(post)
        self.assertEqual(info["result"], "duplicate-body")
        download.assert_not_called()

    def test_short_study_retains_source_words_and_richer_character_metadata(self):
        record = {"id": "123", "title": "The God who sees", "date": "2023-03-21", "createdTs": 1679356800}
        teaching = "Hagar discovered that God saw her in the wilderness. Read Genesis 16:13 and trust His mercy."
        body = {
            "id": "123", "title": record["title"], "content": record["title"] + "\n\n" + teaching
                + "\n\nYou can become a monthly subscriber.\n\nThe Gospel Warrior Library is waiting for you.",
            "sourceUrl": "https://www.facebook.com/iamGospelWarrior/posts/123",
            "biblicalCharacters": ["Hagar"], "topics": ["Women of the Bible"],
            "bibleBooks": ["Genesis"], "bibleReferences": ["Genesis 16:13", "2 Corinthians 9:7"],
            "readingMinutes": 100,
        }
        post, removed = merge.convert_study(record, body)
        self.assertEqual(post["text"], record["title"] + "\n\n" + teaching)
        self.assertIn("Hagar", post["biblicalCharacters"])
        self.assertIn("Women of the Bible", post["topics"])
        self.assertIn("Genesis 16:13", post["bibleReferences"])
        self.assertNotIn("2 Corinthians 9:7", post["bibleReferences"])
        self.assertEqual(post["testament"], "Old Testament")
        self.assertEqual(post["readingMinutes"], 1)
        self.assertEqual(post["timestamp"], record["createdTs"])
        self.assertGreater(removed, 0)

    def test_available_zip_image_is_copied_and_referenced_offline(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".macos-build") as temporary:
            website = Path(temporary)
            (website / "assets").mkdir()
            image = io.BytesIO()
            Image.new("RGB", (8, 8), "green").save(image, "WEBP")
            package = io.BytesIO()
            member = merge.IMAGE_PREFIX + "321.webp"
            with zipfile.ZipFile(package, "w") as archive:
                archive.writestr(member, image.getvalue())
            package.seek(0)
            post = {"id": "123", "media": [{"id": "321", "url": "https://example.org/original"}]}
            report = {"copiedImages": 0, "downloadedImages": 0, "imageFallbacks": []}
            with zipfile.ZipFile(package) as archive, patch.object(merge, "WEBSITE", website):
                merge.attach_image(post, archive, {member}, report)
            self.assertEqual(post["imageLocal"], "assets/arena-321.webp")
            self.assertEqual((website / post["imageLocal"]).read_bytes(), image.getvalue())
            self.assertEqual(post["originalMedia"][0]["local"], post["imageLocal"])
            self.assertEqual(report["copiedImages"], 1)

    def test_missing_body_recovery_uses_the_requested_public_post(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".macos-build") as temporary:
            directory = Path(temporary)
            text = "Daily Devotional #28\n\n" + "Jesus teaches us to love God and our neighbours. " * 20
            payload = {"post_id": "123", "message": {"text": text}, "url": "https://www.facebook.com/iamGospelWarrior/posts/123", "creation_time": 1679356800}
            response = Mock(text='<script type="application/json">' + json.dumps(payload) + '</script>')
            response.raise_for_status.return_value = None
            record = {"id": "123", "title": "Daily Devotional #28", "date": "2023-03-21", "createdTs": 1679356800, "media": []}
            with patch.object(merge.requests, "get", return_value=response) as get:
                pid, body, error = merge.recover_body(record, directory)
                self.assertEqual(pid, "123")
                self.assertEqual(body["content"], text)
                self.assertIsNone(error)
                self.assertEqual(get.call_args.args[0], "https://m.facebook.com/iamGospelWarrior/posts/123")
                merge.recover_body(record, directory)
                self.assertEqual(get.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
