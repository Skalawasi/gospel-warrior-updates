"""Expanded bundled archives merge into older saved libraries on upgrade."""
import gzip
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "macos"))
sys.path.insert(0, str(ROOT / "gospel-warrior-study"))
import desktop_server
import updater


class BundleUpgradeTests(unittest.TestCase):
    def test_upgrade_retains_existing_and_newer_studies_then_runs_only_once(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".macos-build") as temporary:
            directory = Path(temporary)
            website = directory / "website"
            data_dir = directory / "library"
            (website / "assets").mkdir(parents=True)
            data_dir.mkdir()
            (website / "assets/study.jpg").write_bytes(b"study illustration")
            def post(pid, text):
                return {"id": pid, "title": "Trust in God", "text": text, "imageLocal": "assets/study.jpg", "subject": "Faith, Grace & Salvation", "timestamp": 1791200000}
            current = {"posts": [post("existing", "The current wording about faith in Jesus."), post("newer", "A newer study about the Psalms.")]}
            bundle = {"posts": [post("existing", "An older wording about faith."), post("historical", "A recovered historical study about Genesis.")]}
            with gzip.open(website / "content.json.gz", "wt", encoding="utf-8") as handle:
                json.dump(bundle, handle)
            revision = hashlib.sha256((website / "content.json.gz").read_bytes()).hexdigest()
            (directory / "build-manifest.json").write_text(json.dumps({"archiveSHA256": revision}))
            with patch.object(updater, "HERE", data_dir), patch.object(updater, "CONTENT_PATH", data_dir / "content.json.gz"), patch.object(updater, "STATUS_PATH", data_dir / "update-status.json"), patch.object(updater, "__file__", str(website / "updater.py")):
                updater.save_archive(current, compresslevel=1)
                self.assertEqual(desktop_server.merge_bundled_archive(website, data_dir, updater), 1)
                data = updater.load_archive()
                self.assertEqual({p["id"] for p in data["posts"]}, {"existing", "newer", "historical"})
                self.assertEqual(next(p["text"] for p in data["posts"] if p["id"] == "existing"), "The current wording about faith in Jesus.")
                before = updater.CONTENT_PATH.stat().st_mtime_ns
                self.assertEqual(desktop_server.merge_bundled_archive(website, data_dir, updater), 0)
                self.assertEqual(updater.CONTENT_PATH.stat().st_mtime_ns, before)
                self.assertEqual(json.loads((data_dir / "bundled-archive-applied.json").read_text())["archiveSHA256"], revision)

    def test_fresh_seed_is_stamped_without_rewriting_the_archive(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".macos-build") as temporary:
            directory = Path(temporary)
            website = directory / "website"
            data_dir = directory / "library"
            website.mkdir()
            data_dir.mkdir()
            (directory / "build-manifest.json").write_text(json.dumps({"archiveSHA256": "fresh-bundle-revision"}))
            with patch.object(updater, "load_archive") as load:
                self.assertEqual(desktop_server.merge_bundled_archive(website, data_dir, updater, seeded=True), 0)
                load.assert_not_called()
            self.assertTrue((data_dir / "bundled-archive-applied.json").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
