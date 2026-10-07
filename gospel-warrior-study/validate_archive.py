#!/usr/bin/env python3
"""Run integrity checks on the live Gospel Warrior archive."""
from __future__ import annotations
import json
import gzip
from collections import Counter
import updater

with gzip.open(updater.CONTENT_PATH, "rt", encoding="utf-8") as handle:
    data = json.load(handle)
unique = updater.validate_archive_data(data)
posts = data["posts"]
words = sum(updater.word_count(post.get("text", "")) for post in posts)
subjects = Counter(post.get("subject") for post in posts)
residuals = [post["id"] for post in posts if updater.clean_social_calls(post.get("text", ""))[0] != post.get("text", "") or any(updater.is_cta_block(post.get(field, "")) for field in ("title", "subtitle"))]
if residuals:
    raise SystemExit(f"Whole-archive CTA validation failed for {len(residuals)} posts: {residuals[:10]}")
if updater.archive_posts_need_cleanup(data):
    raise SystemExit("Archive contains missing or outdated per-study promotional-cleanup stamps.")
metadata_fields = ("bibleReferences", "bibleBooks", "biblicalCharacters", "topics", "testament", "gospelCategory", "sourceUrl", "originalDate", "duplicateGroup")
missing_metadata = [post["id"] for post in posts if any(field not in post for field in metadata_fields)]
if missing_metadata:
    raise SystemExit(f"Structured metadata validation failed for {len(missing_metadata)} posts: {missing_metadata[:10]}")
latest = max(posts, key=lambda post: int(post.get("timestamp") or 0))
report = {
    "ok": True,
    **unique,
    "words": words,
    "subjects": len(subjects),
    "missingImages": 0,
    "promotionalCtaResiduals": 0,
    "socialCallsCleanupVersion": data.get("archive", {}).get("socialCallsCleanupVersion"),
    "structuredMetadata": len(posts) - len(missing_metadata),
    "latest": {"id": latest["id"], "title": latest["title"], "date": latest["date"]},
    "automaticUpdate": data.get("archive", {}).get("automaticUpdateEnabled", False),
}
print(json.dumps(report, indent=2, ensure_ascii=False))
