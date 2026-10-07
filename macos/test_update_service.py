"""Deterministic checks for 15-minute scheduling, wake-up, and job exclusion."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gospel-warrior-study"))
import update_server as service


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        service.scheduler_state.update(nextCheck=None, schedulerEnabled=True)
        service.update_lock = threading.Lock()
        self.config = {"enabled": True, "intervalMinutes": 15, "autoRefresh": True}
        self.config_patch = patch.object(service, "read_config", side_effect=lambda: dict(self.config))
        self.config_patch.start()
        self.addCleanup(self.config_patch.stop)
        self.now = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)

    def test_startup_then_every_fifteen_minutes(self):
        with patch.object(service, "start_update", return_value=True) as start:
            service.scheduler_tick(self.now)
            self.assertEqual(service.scheduler_state["nextCheck"], service.iso(self.now + timedelta(seconds=3)))
            service.scheduler_tick(self.now + timedelta(seconds=2))
            start.assert_not_called()
            first_check = self.now + timedelta(seconds=3)
            service.scheduler_tick(first_check)
            self.assertEqual(start.call_count, 1)
            self.assertEqual(service.scheduler_state["nextCheck"], service.iso(first_check + timedelta(minutes=15)))
            service.scheduler_tick(first_check + timedelta(minutes=14, seconds=59))
            self.assertEqual(start.call_count, 1)
            service.scheduler_tick(first_check + timedelta(minutes=15))
            self.assertEqual(start.call_count, 2)

    def test_mac_wake_runs_one_overdue_check(self):
        service.scheduler_state["nextCheck"] = service.iso(self.now + timedelta(minutes=15))
        wake_time = self.now + timedelta(hours=3)
        with patch.object(service, "start_update", return_value=True) as start:
            service.scheduler_tick(wake_time)
            start.assert_called_once_with("scheduled")
            self.assertEqual(service.scheduler_state["nextCheck"], service.iso(wake_time + timedelta(minutes=15)))

    def test_pause_clears_schedule(self):
        self.config["enabled"] = False
        with patch.object(service, "start_update") as start:
            service.scheduler_tick(self.now)
            self.assertIsNone(service.scheduler_state["nextCheck"])
            start.assert_not_called()

    def test_slow_import_does_not_queue_another_job(self):
        service.scheduler_state["nextCheck"] = service.iso(self.now)
        with patch.object(service, "start_update", return_value=False) as start:
            self.assertEqual(service.scheduler_tick(self.now), 5)
            start.assert_called_once()
            self.assertEqual(service.scheduler_state["nextCheck"], service.iso(self.now))

    def test_simultaneous_manual_and_scheduled_checks_share_one_job(self):
        entered, release = threading.Event(), threading.Event()

        def import_studies():
            entered.set()
            release.wait(3)

        with patch.object(service.updater, "append_log"), patch.object(service.updater, "run_update", side_effect=import_studies) as update:
            try:
                self.assertTrue(service.start_update("manual"))
                self.assertTrue(entered.wait(2))
                self.assertFalse(service.start_update("scheduled"))
            finally:
                release.set()
                deadline = time.monotonic() + 3
                while service.update_lock.locked() and time.monotonic() < deadline:
                    time.sleep(0.01)
            self.assertFalse(service.update_lock.locked())
            self.assertEqual(update.call_count, 1)


class ConfigurationTests(unittest.TestCase):
    def test_archive_writes_record_a_current_reader_policy_stamp(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".macos-build") as directory:
            directory = Path(directory)
            (directory / "assets").mkdir()
            (directory / "assets/study.jpg").write_bytes(b"local image")
            archive = directory / "content.json.gz"
            data = {"posts": [{"id": "prayer-test", "title": "A Bible study on prayer", "text": "A reflection on prayer and Scripture.", "imageLocal": "assets/study.jpg"}]}
            with patch.object(service.updater, "HERE", directory), patch.object(service.updater, "CONTENT_PATH", archive):
                service.updater.save_archive(data, compresslevel=1)
                recorded = json.loads((directory / "reader-policy-applied.json").read_text())
                self.assertEqual(recorded, service.updater.reader_policy_stamp())
                archive.write_bytes(b"an older archive was restored")
                self.assertNotEqual(recorded, service.updater.reader_policy_stamp())

    def test_auto_refresh_and_schedule_settings_persist(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".macos-build") as directory:
            directory = Path(directory)
            config = directory / "config.json"
            status = directory / "status.json"
            archive = directory / "content.json.gz"
            config.write_text(json.dumps({"enabled": False, "intervalMinutes": 30, "autoRefresh": False}))
            status.write_text("{}")
            archive.write_bytes(b"archive-generation-one")
            with patch.object(service.updater, "CONFIG_PATH", config), patch.object(service.updater, "STATUS_PATH", status), patch.object(service.updater, "CONTENT_PATH", archive):
                service.scheduler_state.update(nextCheck=None, schedulerEnabled=True)
                saved = service.save_config({"enabled": True, "intervalMinutes": 15, "autoRefresh": True})
                self.assertTrue(saved["enabled"] and saved["autoRefresh"])
                self.assertEqual(json.loads(config.read_text())["intervalMinutes"], 15)
                payload = service.status_payload()
                self.assertTrue(payload["autoRefresh"] and payload["schedulerEnabled"])
                self.assertIsNotNone(payload["nextCheck"])
                first_revision = payload["contentRevision"]
                archive.write_bytes(b"archive-generation-two-is-different")
                self.assertNotEqual(service.status_payload()["contentRevision"], first_revision)
                service.save_config({"enabled": False, "autoRefresh": False})
                payload = service.status_payload()
                self.assertFalse(payload["schedulerEnabled"] or payload["autoRefresh"])
                self.assertIsNone(payload["nextCheck"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
