#!/usr/bin/env python3
"""Write the status file used by a static public update source.

The desktop/macOS update server computes its status through API endpoints. A
GitHub raw-content repository has no server process, so Android reads this
document instead. The archive digest is stable until content.json.gz changes,
which lets the app detect a new archive without downloading the 27 MB file on
every status poll.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
CONTENT_PATH = HERE / "content.json.gz"
STATUS_PATH = HERE / "update-status.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def main() -> None:
    if not CONTENT_PATH.is_file():
        raise SystemExit(f"Missing archive: {CONTENT_PATH}")

    status = {}
    if STATUS_PATH.is_file():
        try:
            status = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            status = {}

    digest = hashlib.sha256(CONTENT_PATH.read_bytes()).hexdigest()
    status.update(
        {
            # Android can poll this file and download content, but a static
            # repository cannot accept POST /api/update/check or settings.
            "apiAvailable": True,
            "staticOnly": True,
            "schedulerEnabled": True,
            "automaticChecksEnabled": True,
            "autoRefresh": True,
            "nextCheck": None,
            "contentRevision": f"sha256-{digest}",
            "statusGeneratedAt": now_iso(),
        }
    )
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
