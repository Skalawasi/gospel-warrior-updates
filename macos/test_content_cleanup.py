"""Regression checks for promotional cleanup without losing Bible teaching."""
from __future__ import annotations

import copy
import gzip
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gospel-warrior-study"))
import updater


class ContentCleanupTests(unittest.TestCase):
    def test_actual_archive_promotion_variants_are_removed(self):
        invitations = (
            "You can become a monthly subscriber.",
            "Prayerfully consider becoming a subscriber.",
            "Subscribers also receive 50% off our products as our thank-you, including books, T-shirts, mugs, journals, and more.",
            "The Gospel Warrior Library contains thousands of FREE Christian ebooks, devotionals, and discipleship resources.",
            "Gospel Warrior also maintains a growing library containing thousands of FREE Christian ebooks.",
            "And explore the Gospel Warrior Library, where thousands of FREE Christian ebooks are available.",
            "Share it to your Facebook profile.",
            "Follow the ministry.",
            "Follow for daily truth that challenges, heals, and realigns your heart with Jesus.",
            "Tag somebody who needs it.",
            "Comment.",
            "Because one shared article can reach a struggling believer.",
            "If you want to support the mission and go deeper:",
            "Support what feeds your spirit.",
            "@followers @highlight",
            "Gospel Warrior also continues building a library containing thousands of FREE Christian ebooks.",
            "Tell your testimony in the comments. Somebody reading beneath this article may need it.",
            "Share Gospel Warrior articles to your Facebook profile.",
            "Let the comments beneath this article become more than reactions.",
            "Tag because sometimes one name beneath one article becomes a doorway to a conversation.",
            "Support because you freely believe this work is worth helping continue and expand.",
            "👍 LIKE & FOLLOW MY PAGE FOR EXCLUSIVE TEACHINGS TO BE A TRUE GOSPEL WARRIOR!",
            "👍 LIKE & FOLLOW BROTHER JOHN’S PAGE FOR MORE!",
            "💡 Follow Brother John for More Powerful Teachings!",
            "https://www.facebook.com/profile.php?id=61572888282375",
            "Follow for deeper biblical truth that cuts through confusion.",
            "• SHARE this with someone who feels like they’re not enough",
            "• COMMENT: “Grace over performance” if this hit you",
            "• SAVE this—you’ll need the reminder",
            "👕 Discounts on Gospel Warrior apparel",
            "💵 Price: FREE",
            "#GospelWarrior #GospelWarriorLibrary #BibleStudy",
        )
        opening = "Jesus calls us to love our neighbours."
        closing = "Follow Christ, pray faithfully, and serve those in need."
        for invitation in invitations:
            with self.subTest(invitation=invitation):
                cleaned, removed = updater.clean_social_calls(f"{opening}\n\n{invitation}\n\n{closing}")
                self.assertEqual(cleaned, f"{opening}\n\n{closing}")
                self.assertGreater(removed, 0)

    def test_biblical_actions_and_ordinary_product_mentions_remain_verbatim(self):
        teaching = (
            'Jesus said, “Follow me.”\n\n'
            "Share the Gospel and support your neighbours in their suffering.\n\n"
            "The early church shared bread and cared for the poor.\n\n"
            "There are verses we put on coffee mugs, T-shirts, and the walls of our homes.\n\n"
            "Salvation cannot be subscribed to.\n\n"
            "Read John 3:16 and pray for understanding."
        )
        self.assertEqual(updater.clean_social_calls(teaching), (teaching, 0))

    def test_plain_newlines_do_not_cause_scripture_to_be_removed(self):
        text = 'John 3:16 — God so loved the world.\nSubscribe today.\nFollow Christ in love.'
        cleaned, _ = updater.clean_social_calls(text)
        self.assertEqual(cleaned, 'John 3:16 — God so loved the world.\nFollow Christ in love.')

    def test_multiblock_ebook_offer_and_comment_reply_are_removed(self):
        text = (
            "Prayer is a daily act of trust in God.\n\n"
            "🔥 THIS BOOK WILL HELP YOU:\n\n"
            "• Build a prayer habit\n• Develop trust in God\n\n"
            "✅ Access to this FREE premium ebook\n\n"
            "✅ Early access to future releases\n\n"
            "🎁 PLUS AS A THANK YOU...\n\n"
            "• Christian Books\n\n• T-Shirts\n\n• Coffee Mugs\n\n"
            "⚡ CALL TO ACTION\n\n"
            "Unlock your FREE copy of:\n\n📖 HOW TO BECOME A PRAYER WARRIOR\n\n"
            'Comment:\n\n“AMEN”\n\n'
            "Christ remains the source of our hope."
        )
        cleaned, _ = updater.clean_social_calls(text)
        self.assertEqual(cleaned, "Prayer is a daily act of trust in God.\n\nChrist remains the source of our hope.")

    def test_cleanup_is_idempotent(self):
        text = "Trust God.\n\nYou can become a monthly subscriber.\n\nThe discount is a thank-you.\n\nFollow Christ."
        cleaned, _ = updater.clean_social_calls(text)
        self.assertEqual(cleaned, "Trust God.\n\nFollow Christ.")
        self.assertEqual(updater.clean_social_calls(cleaned), (cleaned, 0))

    def test_partial_multiline_cleanup_normalizes_remaining_block_once(self):
        text = "Trust Jesus.\n\nSubscribe now.\n and keep reading Scripture.\n\nFollow Christ."
        cleaned, _ = updater.clean_social_calls(text)
        self.assertEqual(cleaned, "Trust Jesus.\n\nand keep reading Scripture.\n\nFollow Christ.")
        self.assertEqual(updater.clean_social_calls(cleaned), (cleaned, 0))

    def test_future_import_is_cleaned_before_metadata_and_deduplication(self):
        raw = {
            "id": "new-study", "timestamp": 1791200000,
            "url": "https://www.facebook.com/iamGospelWarrior/posts/new-study",
            "image": "https://example.org/study.jpg",
            "text": "A study of faith in Jesus\n\n" + "Jesus teaches us to love our neighbours. " * 60
                    + "\n\nYou can become a monthly subscriber.\n\nThe Gospel Warrior Library is waiting for you.",
        }
        with patch.object(updater, "download_image", return_value=("assets/study.jpg", "image/jpeg")):
            post, info = updater.make_post(None, raw, set(), set())
        self.assertEqual(info["result"], "added")
        self.assertNotIn("subscriber", post["text"])
        self.assertNotIn("Gospel Warrior Library", post["text"])
        self.assertEqual(post["duplicateGroup"], updater.body_hash(post["text"]))
        self.assertEqual(post["sourceUrl"], raw["url"])

    def test_changed_body_cannot_reuse_an_older_cleanup_stamp(self):
        post = {
            "id": "changed-study", "title": "Trust Christ", "subtitle": "Trust Christ.",
            "text": "Trust Christ.", "subject": "Faith, Grace & Salvation",
        }
        data = {"posts": [post], "archive": {}}
        updater.apply_reader_policy(data)
        self.assertFalse(updater.archive_posts_need_cleanup(data))
        post["text"] += "\n\nYou can become a monthly subscriber."
        self.assertTrue(updater.archive_posts_need_cleanup(data))
        updater.apply_reader_policy(data)
        self.assertEqual(post["text"], "Trust Christ.")
        self.assertFalse(updater.archive_posts_need_cleanup(data))

    def test_existing_saved_archive_is_migrated_without_changing_identity(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".macos-build") as temporary:
            directory = Path(temporary)
            (directory / "assets").mkdir()
            (directory / "assets/study.jpg").write_bytes(b"study illustration")
            archive = directory / "content.json.gz"
            original = {
                "id": "saved-study", "title": "A Bible study on prayer", "subtitle": "Subscribe now.",
                "text": "A Bible study on prayer\n\nJesus teaches us to pray.\n\nYou can become a monthly subscriber.\n\nFollow Christ.",
                "timestamp": 1791200000, "date": "2026-10-05", "subject": "Prayer & Spiritual Life",
                "url": "https://example.org/original", "imageLocal": "assets/study.jpg",
            }
            data = {"archive": {"socialCallsRemoved": True}, "posts": [copy.deepcopy(original)]}
            with gzip.open(archive, "wt", encoding="utf-8") as handle:
                json.dump(data, handle)
            with patch.object(updater, "HERE", directory), patch.object(updater, "CONTENT_PATH", archive), patch.object(updater, "STATUS_PATH", directory / "update-status.json"):
                updater.curate_reader_archive()
                with gzip.open(archive, "rt", encoding="utf-8") as handle:
                    migrated = json.load(handle)
                self.assertEqual(migrated["archive"]["socialCallsCleanupVersion"], updater.SOCIAL_CALLS_CLEANUP_VERSION)
                post = migrated["posts"][0]
                for key in ("id", "title", "date", "timestamp", "url", "imageLocal"):
                    self.assertEqual(post[key], original[key])
                self.assertEqual(post["text"], "A Bible study on prayer\n\nJesus teaches us to pray.\n\nFollow Christ.")
                self.assertEqual(post["subtitle"], "Jesus teaches us to pray.")
                self.assertEqual(post["duplicateGroup"], updater.body_hash(post["text"]))
                self.assertEqual(json.loads((directory / "reader-policy-applied.json").read_text()), updater.reader_policy_stamp())
                before = archive.stat().st_mtime_ns
                updater.curate_reader_archive()
                self.assertEqual(archive.stat().st_mtime_ns, before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
