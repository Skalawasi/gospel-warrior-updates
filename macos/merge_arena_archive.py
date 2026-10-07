#!/usr/bin/env python3
"""Merge Arena's study archive into the existing Mac/website library.

Reads only study JSON and image data from the supplied ZIP. Existing installed
study IDs are retained. Title matches do not discard differently worded studies;
full-text repetitions are resolved to their retained study ID in the report.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
WEBSITE = ROOT / "gospel-warrior-study"
INSTALLED = Path.home() / "Library/Application Support/Gospel Warrior/library"
sys.path.insert(0, str(WEBSITE))
import updater

PREFIX = "gospel-warrior-library/data/studies/"
IMAGE_PREFIX = "gospel-warrior-library/data/img/"


def read_gzip(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def ordered_union(*groups):
    return list(dict.fromkeys(value for group in groups for value in group if value))


def compact(value):
    return re.sub(r"\s+", "", value.casefold()).replace("–", "-").replace("—", "-")


def convert_study(record, body):
    """Adapt Arena's schema without replacing or summarizing the source text."""
    text, removed = updater.clean_social_calls(body["content"])
    if not text or not re.search(r"\w", text):
        return None, removed
    title = body.get("title") or record.get("title") or updater.title_and_subtitle(text)[0]
    if updater.is_cta_block(title):
        title = updater.title_and_subtitle(text)[0]
    if not updater.normalize_title(title):
        return None, removed
    original_date = body.get("originalDate") or record.get("date")
    timestamp = int(body.get("createdTs") or record.get("createdTs") or 0)
    if not timestamp and original_date:
        timestamp = int(datetime.fromisoformat(original_date).replace(tzinfo=timezone.utc).timestamp())
    if not timestamp:
        raise ValueError(f"Study {record['id']} has no source date")
    url = body.get("sourceUrl") or f"{updater.PROFILE_URL}/posts/{record['id']}"
    media = copy.deepcopy(body.get("originalMedia") or [])
    if not media:
        media = [{"type": "photo", **value} for value in record.get("media", [])]
    for item in media:
        item["url"] = item.get("sourceUrl") or item.get("uri") or item.get("url") or (
            f"https://lookaside.fbsbx.com/lookaside/crawler/media/?media_id={item['id']}" if item.get("id") else None
        )
    post = {
        "id": str(record["id"]), "title": title,
        "subtitle": updater.title_and_subtitle(text)[1], "text": text,
        "url": url, "timestamp": timestamp,
        "date": datetime.fromtimestamp(timestamp, timezone.utc).isoformat(),
        "author": "John Domino Sanchez Asis", "mediaType": "photo",
        "image": media[0].get("url") if media else None,
        "media": media, "reactions": 0, "comments": 0, "shares": 0,
        "pinned": False, "with": None,
        "subject": updater.classify_subject(title, text),
        "contentSource": body.get("contentSource", "post text"),
        "dateApproximate": bool(body.get("dateApproximate", record.get("dateApproximate", False))),
        "dateSource": body.get("dateSource"),
        "arenaOriginalDate": original_date,
        "arenaDuplicateGroup": body.get("duplicateGroup") or record.get("duplicateGroup"),
        "importedFrom": "Arena AI Gospel Warrior archive",
        "socialCallsCleanupVersion": updater.SOCIAL_CALLS_CLEANUP_VERSION,
        "socialCallsCleanupHash": updater.body_hash(text),
        "wordCount": updater.word_count(text),
        "readingMinutes": max(1, round(updater.word_count(text) / 235)),
    }
    updater.enrich_post(post)
    # Retain the richer supplied character/topic index. Scripture references
    # from a removed promotional paragraph must not remain as study tags.
    full_text = f"{title}\n{text}"
    compact_text = compact(full_text)
    references = [value for value in body.get("bibleReferences", record.get("bibleReferences", [])) if compact(value) in compact_text]
    post["bibleReferences"] = ordered_union(post["bibleReferences"], references)
    books = body.get("bibleBooks", record.get("bibleBooks", []))
    supported_books = [book for book in books if re.search(r"\b" + re.escape(book) + r"\b", full_text, re.I) or any(ref.startswith(book + " ") for ref in post["bibleReferences"])]
    post["bibleBooks"] = ordered_union(post["bibleBooks"], supported_books)
    characters = body.get("biblicalCharacters", record.get("biblicalCharacters", []))
    post["biblicalCharacters"] = ordered_union(post["biblicalCharacters"], [name for name in characters if re.search(r"\b" + re.escape(name) + r"\b", full_text, re.I)])
    post["topics"] = ordered_union(post["topics"], body.get("topics", record.get("topics", [])), body.get("extraTopics", record.get("extraTopics", [])))
    post["gospelCategory"] = ordered_union(post["gospelCategory"], body.get("gospelCategory", record.get("gospelCategory", [])))
    testaments = {testament for book, testament, _ in updater.BIBLE_BOOK_RULES if book in post["bibleBooks"]}
    if testaments:
        post["testament"] = "Both Testaments" if len(testaments) > 1 else next(iter(testaments))
    return post, removed


def recover_body(record, directory):
    """Recover a missing body from its matching, logged-out public post."""
    pid = str(record["id"])
    cache = directory / f"{pid}.json"
    if cache.exists():
        return pid, json.loads(cache.read_text()), None
    errors = []
    for host in ("m.facebook.com", "www.facebook.com"):
        try:
            response = requests.get(f"https://{host}/iamGospelWarrior/posts/{pid}", headers=updater.HEADERS, timeout=35)
            response.raise_for_status()
            story = updater.story_from_html(response.text, pid)
            media = [{"type": "photo", "id": value.get("id"), "sourceUrl": story.get("image")} for value in record.get("media", [])]
            body = {
                "id": pid, "title": updater.title_and_subtitle(story["text"])[0],
                "content": story["text"], "createdTs": story.get("timestamp") or record.get("createdTs"),
                "originalDate": record.get("date"), "sourceUrl": story.get("url") or f"{updater.PROFILE_URL}/posts/{pid}",
                "originalMedia": media, "contentSource": "post text",
                "dateApproximate": record.get("dateApproximate", False),
                "dateSource": "public post recovery",
                **{key: record.get(key, []) for key in ("bibleReferences", "bibleBooks", "biblicalCharacters", "topics", "extraTopics", "gospelCategory")},
            }
            updater.atomic_json(cache, body)
            return pid, body, None
        except Exception as exc:
            errors.append(f"{host}: {str(exc)[:180]}")
    return pid, None, "; ".join(errors)


def attach_image(post, archive, members, report):
    for media in post["media"]:
        mid = str(media.get("id") or "")
        member = IMAGE_PREFIX + mid + ".webp"
        if re.fullmatch(r"\d+", mid) and member in members:
            local = f"assets/arena-{mid}.webp"
            target = WEBSITE / local
            if not target.exists():
                target.write_bytes(archive.read(member))
                report["copiedImages"] += 1
            media["local"] = local
            post["imageLocal"] = local
            post["originalMedia"] = copy.deepcopy(post["media"])
            return
    # New index-only records were published after the ZIP's thumbnail snapshot.
    if post.get("image"):
        try:
            with requests.Session() as session:
                local, _ = updater.download_image(session, post["image"], post["id"])
            post["imageLocal"] = local
            if post["media"]:
                post["media"][0]["local"] = local
            post["originalMedia"] = copy.deepcopy(post["media"])
            report["downloadedImages"] += 1
            return
        except Exception as exc:
            report["imageFallbacks"].append({"id": post["id"], "error": str(exc)[:200]})
    post["imageLocal"] = "assets/study-emblem.svg"


def merge_records(base, candidates, outcomes):
    ids = {str(post["id"]): post for post in base}
    bodies = {updater.study_body_hash(post["text"], post["title"]): post["id"] for post in base}
    added = []
    for post in candidates:
        pid = post["id"]
        if pid in ids:
            outcomes[pid] = {"result": "already-present", "retainedId": pid}
            continue
        digest = updater.study_body_hash(post["text"], post["title"])
        if digest in bodies:
            outcomes[pid] = {"result": "duplicate-text", "retainedId": bodies[digest]}
            continue
        ids[pid] = post
        bodies[digest] = pid
        added.append(post)
        outcomes[pid] = {"result": "imported", "retainedId": pid}
    return added


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--work", type=Path, default=ROOT / ".macos-build/arena-merge")
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    recovery = args.work / "recovered"
    recovery.mkdir(exist_ok=True)
    for label, path in (("source", WEBSITE / "content.json.gz"), ("installed", INSTALLED / "content.json.gz")):
        backup = args.work / f"before-{label}.json.gz"
        if path.exists() and not backup.exists():
            shutil.copy2(path, backup)
    preferences = INSTALLED.parent / "preferences.json"
    if preferences.exists() and not (args.work / "preferences-before.json").exists():
        shutil.copy2(preferences, args.work / "preferences-before.json")
    data = read_gzip(WEBSITE / "content.json.gz")
    source_posts = data["posts"]
    installed_posts = read_gzip(INSTALLED / "content.json.gz")["posts"] if (INSTALLED / "content.json.gz").exists() else []
    # Prefer current installed records for shared IDs and preserve every saved ID.
    base_map = {str(post["id"]): post for post in source_posts}
    base_map.update({str(post["id"]): post for post in installed_posts})
    base = list(base_map.values())
    for post in base:
        local = post.get("imageLocal")
        if local and not (WEBSITE / local).exists():
            for origin in (INSTALLED, Path("/Applications/Gospel Warrior.app/Contents/Resources/website")):
                if (origin / local).is_file():
                    shutil.copy2(origin / local, WEBSITE / local)
                    break
    report = {
        "archive": args.archive.name, "archiveSHA256": hashlib.sha256(args.archive.read_bytes()).hexdigest(),
        "started": updater.now_iso(), "baseStudies": len(base),
        "copiedImages": 0, "downloadedImages": 0, "imageFallbacks": [],
        "recoveredBodies": [], "unavailableBodies": [], "removedPromotionalBlocks": 0,
        "outcomes": {},
    }
    with zipfile.ZipFile(args.archive) as archive:
        members = set(archive.namelist())
        index = json.loads(gzip.decompress(archive.read(PREFIX + "index.json.gz")))
        content = json.loads(gzip.decompress(archive.read(PREFIX + "content/content.json.gz")))
        report.update(arenaIndexedEntries=len(index), arenaFullTexts=len(content))
        records = {str(record["id"]): record for record in index}
        for pid, body in content.items():
            records.setdefault(str(pid), {"id": str(pid), "title": body.get("title"), "date": body.get("originalDate"), "createdTs": body.get("createdTs")})
        if any(not re.fullmatch(r"[A-Za-z0-9_-]+", pid) for pid in records):
            raise ValueError("Archive contains an invalid study ID")
        missing = [record for pid, record in records.items() if pid not in content and pid not in base_map and not updater.reader_excludes(pid, record.get("title", ""))]
        print(f"Comparing {len(records):,} Arena entries with {len(base):,} current studies; recovering {len(missing)} missing bodies.", flush=True)
        with ThreadPoolExecutor(max_workers=3) as pool:
            jobs = [pool.submit(recover_body, record, recovery) for record in missing]
            for job in as_completed(jobs):
                pid, body, error = job.result()
                if body:
                    content[pid] = body
                    report["recoveredBodies"].append(pid)
                else:
                    report["unavailableBodies"].append({"id": pid, "title": records[pid].get("title"), "error": error})
                print(f"Recovered {len(report['recoveredBodies'])}/{len(missing)} bodies; unavailable {len(report['unavailableBodies'])}.", flush=True)
        candidates = []
        for number, (pid, record) in enumerate(records.items(), 1):
            if updater.reader_excludes(pid, record.get("title", "")):
                report["outcomes"][pid] = {"result": "reader-exclusion"}
                continue
            if pid in base_map:
                report["outcomes"][pid] = {"result": "already-present", "retainedId": pid}
                continue
            body = content.get(pid)
            if not body:
                report["outcomes"][pid] = {"result": "body-unavailable"}
                continue
            post, removed = convert_study(record, body)
            report["removedPromotionalBlocks"] += removed
            if post:
                candidates.append(post)
            else:
                report["outcomes"][pid] = {"result": "empty-after-promotional-cleanup"}
            if number % 250 == 0:
                print(f"Processed {number:,}/{len(records):,} index entries; prepared {len(candidates):,} studies.", flush=True)
        added = merge_records(base, candidates, report["outcomes"])
        print(f"Adding {len(added):,} distinct studies and their images.", flush=True)
        for number, post in enumerate(added, 1):
            attach_image(post, archive, members, report)
            if number % 500 == 0:
                print(f"Installed images for {number:,}/{len(added):,} added studies.", flush=True)
    data["posts"] = sorted(base + added, key=lambda post: (int(bool(post.get("pinned"))), int(post.get("timestamp") or 0)), reverse=True)
    data.setdefault("archive", {}).update(
        deduplication="Unique post IDs and complete teaching text; distinct studies may share a headline",
        lastArchiveMerge=updater.now_iso(), archiveMergeSource=args.archive.name,
    )
    updater.save_archive(data, compresslevel=6)
    summary = updater.archive_summary(data["posts"])
    outcomes = Counter(value["result"] for value in report["outcomes"].values())
    report.update(completed=updater.now_iso(), addedStudies=len(added), finalStudies=len(data["posts"]), outcomesSummary=dict(outcomes), **summary)
    updater.atomic_json(args.work / "report.json", report)
    updater.write_status(currentTotal=summary["total"], totalWords=summary["words"], subjects=summary["subjects"], structuredMetadata=summary["structuredMetadata"], running=False)
    print(json.dumps({key: value for key, value in report.items() if key not in ("outcomes", "recoveredBodies", "unavailableBodies", "imageFallbacks")}, indent=2), flush=True)
    if report["unavailableBodies"]:
        print("Some indexed bodies could not be recovered; see the detailed report.", flush=True)


if __name__ == "__main__":
    main()
