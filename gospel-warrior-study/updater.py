#!/usr/bin/env python3
"""Incremental public-profile updater for the Gospel Warrior study archive.

The updater reads the newest public photo-album frontier, fetches complete public
post pages, removes only promotional/social CTA blocks, deduplicates by full
normalized title and body hash, downloads the matching image, and atomically
rebuilds content.json.gz.

It intentionally uses logged-out public Facebook routes. It does not accept,
store, or request passwords, cookies, or access tokens.
"""
from __future__ import annotations

import argparse
import base64
import copy
import gzip
import hashlib
import io
import json
import os
import re
import tempfile
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageOps

# The Mac app keeps mutable archive data outside its signed application bundle.
# Website/command-line use continues to use this script's directory by default.
HERE = Path(os.environ.get("GW_ARCHIVE_DIR", Path(__file__).resolve().parent)).resolve()
CONTENT_PATH = HERE / "content.json.gz"
STATUS_PATH = HERE / "update-status.json"
CONFIG_PATH = HERE / "update-config.json"
LOG_PATH = HERE / "update-log.jsonl"
ASSETS = HERE / "assets"

PROFILE_URL = "https://www.facebook.com/iamGospelWarrior"
ALBUM_ID = "111666608844421"
ALBUM_URL = f"https://www.facebook.com/media/set/?set=a.{ALBUM_ID}&type=3"
PROFILE_ID = "100000032478992"
GRAPHQL_URL = "https://www.facebook.com/api/graphql/"
ALBUM_DOC_ID = "34407011978913359"
USER_AGENT = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"
HEADERS = {"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"}
# Include shorter Bible devotionals as well as long-form studies.
MIN_STUDY_WORDS = 50
MAX_FRONTIER_PAGES = 16  # initial 8 + up to 800 older items per run
SOCIAL_CALLS_CLEANUP_VERSION = 4

DEFAULT_CONFIG = {
    "enabled": True,
    "intervalMinutes": 15,
    "autoRefresh": True,
    "maxFrontierPages": 16,
    "requestDelaySeconds": 0.45,
    "source": PROFILE_URL,
    "albumId": ALBUM_ID,
}

SOCIAL_URL_RE = re.compile(
    r"facebook\.com/(?:profile\.php\?id=\d+|iamGospelWarrior(?:/(?:subscribenow|support)|/?(?:\s|$))|groups/\d+)|"
    r"(?:paypal|patreon|buymeacoffee|ko-fi)\.", re.I
)
CTA_DIRECT_RE = re.compile(
    r"\b(?:subscribe\s+(?:here|now|today)|become\s+(?:a\s+)?subscriber|"
    r"support\s+(?:the\s+)?gospel\s+warrior|consider\s+(?:supporting|subscribing|helping\s+us)|"
    r"press(?:es|ed)?\s+share|click\s+(?:share|subscribe|follow)|"
    r"share\s+this\s+(?:article|post|message)|tag\s+(?:a|someone|your)|"
    r"follow\s+(?:us|this\s+page)|turn\s+on\s+notifications|"
    r"comment\s+(?:amen|below)|type\s+amen|drop\s+(?:an?\s+)?amen|"
    r"send\s+stars|monthly\s+subscription|subscriber(?:s)?\s+(?:receive|get)|"
    r"50%\s+discount\s+on\s+gospel\s+warrior|gospel\s+warrior\s+products)\b", re.I
)
CTA_PROMO_RE = re.compile(
    r"\b(?:as\s+a\s+thank[- ]you\s+for\s+that\s+support|"
    r"helps?\s+us\s+continue\s+(?:creating|publishing|sharing)|"
    r"if\s+this\s+ministry\s+has\s+fed\s+you|"
    r"one\s+believer\s+presses\s+share|"
    r"exclusive\s+content|support\s+our\s+mission)\b", re.I
)
SOCIAL_ACTION_RE = re.compile(
    r"\b(?:comment\s+(?:[“\"']|below\b|your\b|if\b|to\b|because\b|amen\b)|"
    r"leave\s+[^\n]{0,100}\bcomments?\b|tag\s+(?:a|someone|somebody|your|the)\b|"
    r"(?:share|save)\s+(?:(?:this|these|the|my|our|an?|Christian|gospel\s+warrior)\s+)?(?:articles?|posts?|messages?|stud(?:y|ies))\b|"
    r"share\s+it\b|share\s+(?:this|these)\s+(?:to|on)\b|"
    r"share\s+(?:Christian|biblical)\s+posts?\b|"
    r"(?:one|a|your)\s+share\b|(?:a|one|every|each|your)\s+shared\s+(?:article|post)\b|"
    r"(?:posts?|articles?)\s+you\s+[^\n]{0,60}\bshare\b|your\s+(?:share|comment|follow)\b|"
    r"share\b[^\n]{0,120}\b(?:Facebook|profile|(?:the|our|this)\s+page)\b|"
    r"the\s+share\s+(?:that|which|you)\b|"
    r"(?:tell|share|leave|write|put|drop)\b[^\n]{0,160}\b(?:in|below|under|beneath)\s+(?:the\s+)?comments?\b|"
    r"let\s+the\s+comments?\s+(?:beneath|underneath|below)\b|one\s+(?:honest\s+)?comment\b|"
    r"press(?:es|ed)?\s+share\b|click\s+share\b|"
    r"follow\s+(?:gospel\s+warrior|(?:this|the|our|Christian)\s+(?:pages?|accounts?|ministry)|me\s+for)\b|"
    r"follow\s+for\s+(?:daily|more)\b|and\s+a\s+follow\s+keeps\b|"
    r"join\s+(?:the|our|this)\s+(?:community|page|group)\b|"
    r"invite\s+[^\n]{0,100}\b(?:follow|page|group)\b|"
    r"(?:like|react|save|share)\s+(?:this|the)\s+post\b|"
    r"turn\s+on\s+notifications\b)|^\W*(?:(?:and|so)\s+)?tag\b|@(?:followers|highlight|everyone)\b", re.I
)
SUBSCRIPTION_RE = re.compile(r"\b(?:subscrib(?:e|ing|ers?)|subscriptions?)\b", re.I)
LIBRARY_PROMO_RE = re.compile(
    r"\bgospel\s+warrior(?:['’]s)?\s+(?:(?:growing|free|Christian)\s+)*(?:library|products?|store|shop)\b|"
    r"\bgospel\s+warrior\b[^\n]{0,100}\blibrary\b|"
    r"\b(?:visit|explore|browse|join|access|unlock)\s+(?:(?:the|our|growing)\s+)*library\b",
    re.I
)
SUPPORT_PROMO_RE = re.compile(
    r"\b(?:support(?:ing)?\s+(?:the\s+|this\s+|our\s+|that\s+|a\s+)?"
    r"(?:gospel\s+warrior|(?:Christian\s+)?ministry|mission|work|page|financially|us\b)|"
    r"financially\s+support\b|(?:your|monthly)\s+(?:financial\s+)?support\b|"
    r"support\s+what\s+feeds\s+your\s+spirit\b|"
    r"(?:help|support|stand\s+with|stand\s+behind)\s+[^\n]{0,80}\bgospel\s+warrior\b|"
    r"(?:you['’]re|you\s+are)\s+invited\s+to\s+join\s+us\b|"
    r"donate\s+(?:now|here|today|to\s+us)\b)|"
    r"^\W*(?:(?:and|so)\s+)?support\s+(?:because|freely)\b", re.I
)
OFFER_PROMO_RE = re.compile(
    r"\b(?:\d+\s*%\s*(?:off|discount)|discount\s+(?:on|for|is\s+(?:simply|a\s+thank))|"
    r"(?:unlock|download|claim|grab|get|receive|access)\s+(?:(?:your|this|the|our|a|to)\s+)*"
    r"(?:(?:free|premium|Christian|growing|collection|of)\s+)*(?:copy|ebooks?|growth\s+resources)|"
    r"(?:early|exclusive|members?[- ]only)\s+access|"
    r"(?:available|access)\s+[^\n]{0,50}\b(?:ebooks?|library)\b|"
    r"(?:our|paid|faith[- ]based)\s+(?:products|merchandise)|"
    r"more\s+than\s+merchandise|bigger\s+than\s+merchandise)\b", re.I
)
PROMO_HEADING_RE = re.compile(
    r"^\W*(?:call\s+to\s+action|(?:this\s+is\s+)?more\s+than\s+an?\s+e?book|"
    r"this\s+e?book\s+(?:will|can)\s+help\s+you|"
    r"(?:plus\s+)?as\s+a\s+thank[- ]you|"
    r"(?:subscriber|subscription|membership)\s+(?:benefits|perks))\b", re.I
)
STANDALONE_SOCIAL_RE = re.compile(
    r"^\W*(?:comment|share|save|like|follow(?:\s+me)?|subscribe|tag|react|repost)\W*$", re.I
)
PRODUCT_LIST_RE = re.compile(
    r"^\W*(?:(?:Christian|faith[- ]based|devotional|prayer|coffee)\s+)*"
    r"(?:books|t[- ]shirts|mugs|journals|resources|merchandise)(?:\W*|\s+and\s+more\W*)$", re.I
)
PROMO_CONTINUATION_RE = re.compile(
    r"^(?:(?:and|but)\s+)?(?:"
    r"(?:the|this|that|your)\s+(?:discount|merchandise|monthly\s+support)\b|"
    r"(?:it|this|that)\s+(?:helps?|allows?|enables?)\s+us\b|"
    r"(?:the\s+)?(?:deepest|real)\s+reason\s+to\s+stay\s+connected\b|"
    r"it\s+(?:cannot|does\s+not|is\s+discipleship)[.!]*$|"
    r"(?:and\s+)?more\s+as\s+the\s+gospel\s+warrior\b|"
    r"because\s+(?:some\s+ministry|you['’]ll\s+need\s+this\s+reminder)\b|"
    r"some\s+happens\b|and\s+sometimes\s+it\s+happens\b)", re.I
)
OLDER_SOCIAL_PROMO_RE = re.compile(
    r"\bfollow\s+(?:(?:my|our)\s+page|brother\s+john(?:['’]s)?\s+(?:(?:official\s+)?page|for\b)|"
    r"(?:the\s+)?gospel\s+warrior\s+page)\b|"
    r"^\W*(?:and\s+)?follow\s+for\b|"
    r"^\W*comment\s*:|\bshare\s+this(?:\s*[—–:]|\s+(?:with|if|so|because)\b)|"
    r"^\W*save\s+(?:this|it)(?:\s*[—–:]|\s+(?:for|so|because|post|study|article|message)\b|[.!]\s*$)|\bdiscounts\s+on\b|"
    r"^\W*price\s*:\s*(?:free|\d)|\bgospelwarriorlibrary\b", re.I
)
BIBLE_SIGNAL_RE = re.compile(
    r"\b(?:Bible|Scripture|Jesus|Christ|Gospel|God|LORD|YHWH|Genesis|Exodus|"
    r"Leviticus|Numbers|Deuteronomy|Joshua|Judges|Samuel|Kings|Chronicles|"
    r"Psalms?|Proverbs|Isaiah|Jeremiah|Ezekiel|Daniel|Hosea|Joel|Amos|"
    r"Obadiah|Jonah|Micah|Nahum|Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|"
    r"Matthew|Mark|Luke|John|Acts|Romans|Corinthians|Galatians|Ephesians|"
    r"Philippians|Colossians|Thessalonians|Timothy|Titus|Philemon|Hebrews|"
    r"James|Peter|Jude|Revelation|verse|chapter|Hebrew|Greek)\b", re.I
)

# These rules power the structured Bible Study Index. They deliberately use
# only words present in a title/body; no book, character, topic, or Gospel
# category is assigned from a generated summary.
BIBLE_BOOK_RULES: tuple[tuple[str, str, re.Pattern[str]], ...] = (
    ("Genesis", "Old Testament", re.compile(r"\bgenesis\b", re.I)),
    ("Exodus", "Old Testament", re.compile(r"\bexodus\b", re.I)),
    ("Leviticus", "Old Testament", re.compile(r"\bleviticus\b", re.I)),
    ("Numbers", "Old Testament", re.compile(r"\bnumbers\b", re.I)),
    ("Deuteronomy", "Old Testament", re.compile(r"\bdeuteronomy\b", re.I)),
    ("Joshua", "Old Testament", re.compile(r"\bjoshua\b", re.I)),
    ("Judges", "Old Testament", re.compile(r"\bjudges?\b", re.I)),
    ("Ruth", "Old Testament", re.compile(r"\bruth\b", re.I)),
    ("1 Samuel", "Old Testament", re.compile(r"\b(?:1|first)\s+samuel\b", re.I)),
    ("2 Samuel", "Old Testament", re.compile(r"\b(?:2|second)\s+samuel\b", re.I)),
    ("1 Kings", "Old Testament", re.compile(r"\b(?:1|first)\s+kings?\b", re.I)),
    ("2 Kings", "Old Testament", re.compile(r"\b(?:2|second)\s+kings?\b", re.I)),
    ("1 Chronicles", "Old Testament", re.compile(r"\b(?:1|first)\s+chronicles?\b", re.I)),
    ("2 Chronicles", "Old Testament", re.compile(r"\b(?:2|second)\s+chronicles?\b", re.I)),
    ("Ezra", "Old Testament", re.compile(r"\bezra\b", re.I)),
    ("Nehemiah", "Old Testament", re.compile(r"\bnehemiah\b", re.I)),
    ("Esther", "Old Testament", re.compile(r"\besther\b", re.I)),
    ("Job", "Old Testament", re.compile(r"\bjob\b", re.I)),
    ("Psalms", "Old Testament", re.compile(r"\bpsalms?\b", re.I)),
    ("Proverbs", "Old Testament", re.compile(r"\bproverbs?\b", re.I)),
    ("Ecclesiastes", "Old Testament", re.compile(r"\becclesiastes\b", re.I)),
    ("Song of Solomon", "Old Testament", re.compile(r"\bsong\s+of\s+(?:songs?|solomon)\b", re.I)),
    ("Isaiah", "Old Testament", re.compile(r"\bisaiah\b", re.I)),
    ("Jeremiah", "Old Testament", re.compile(r"\bjeremiah\b", re.I)),
    ("Lamentations", "Old Testament", re.compile(r"\blamentations\b", re.I)),
    ("Ezekiel", "Old Testament", re.compile(r"\bezekiel\b", re.I)),
    ("Daniel", "Old Testament", re.compile(r"\bdaniel\b", re.I)),
    ("Hosea", "Old Testament", re.compile(r"\bhosea\b", re.I)),
    ("Joel", "Old Testament", re.compile(r"\bjoel\b", re.I)),
    ("Amos", "Old Testament", re.compile(r"\bamos\b", re.I)),
    ("Obadiah", "Old Testament", re.compile(r"\bobadiah\b", re.I)),
    ("Jonah", "Old Testament", re.compile(r"\bjonah\b", re.I)),
    ("Micah", "Old Testament", re.compile(r"\bmicah\b", re.I)),
    ("Nahum", "Old Testament", re.compile(r"\bnahum\b", re.I)),
    ("Habakkuk", "Old Testament", re.compile(r"\bhabakkuk\b", re.I)),
    ("Zephaniah", "Old Testament", re.compile(r"\bzephaniah\b", re.I)),
    ("Haggai", "Old Testament", re.compile(r"\bhaggai\b", re.I)),
    ("Zechariah", "Old Testament", re.compile(r"\bzechariah\b", re.I)),
    ("Malachi", "Old Testament", re.compile(r"\bmalachi\b", re.I)),
    ("Matthew", "New Testament", re.compile(r"\bmatthew\b", re.I)),
    ("Mark", "New Testament", re.compile(r"\bmark\b", re.I)),
    ("Luke", "New Testament", re.compile(r"\bluke\b", re.I)),
    ("John", "New Testament", re.compile(r"\bjohn\b", re.I)),
    ("Acts", "New Testament", re.compile(r"\bacts?\b", re.I)),
    ("Romans", "New Testament", re.compile(r"\bromans?\b", re.I)),
    ("1 Corinthians", "New Testament", re.compile(r"\b(?:1|first)\s+corinthians?\b", re.I)),
    ("2 Corinthians", "New Testament", re.compile(r"\b(?:2|second)\s+corinthians?\b", re.I)),
    ("Galatians", "New Testament", re.compile(r"\bgalatians?\b", re.I)),
    ("Ephesians", "New Testament", re.compile(r"\bephesians?\b", re.I)),
    ("Philippians", "New Testament", re.compile(r"\bphilippians?\b", re.I)),
    ("Colossians", "New Testament", re.compile(r"\bcolossians?\b", re.I)),
    ("1 Thessalonians", "New Testament", re.compile(r"\b(?:1|first)\s+thessalonians?\b", re.I)),
    ("2 Thessalonians", "New Testament", re.compile(r"\b(?:2|second)\s+thessalonians?\b", re.I)),
    ("1 Timothy", "New Testament", re.compile(r"\b(?:1|first)\s+timothy\b", re.I)),
    ("2 Timothy", "New Testament", re.compile(r"\b(?:2|second)\s+timothy\b", re.I)),
    ("Titus", "New Testament", re.compile(r"\btitus\b", re.I)),
    ("Philemon", "New Testament", re.compile(r"\bphilemon\b", re.I)),
    ("Hebrews", "New Testament", re.compile(r"\bhebrews?\b", re.I)),
    ("James", "New Testament", re.compile(r"\bjames\b", re.I)),
    ("1 Peter", "New Testament", re.compile(r"\b(?:1|first)\s+peter\b", re.I)),
    ("2 Peter", "New Testament", re.compile(r"\b(?:2|second)\s+peter\b", re.I)),
    ("1 John", "New Testament", re.compile(r"\b(?:1|first)\s+john\b", re.I)),
    ("2 John", "New Testament", re.compile(r"\b(?:2|second)\s+john\b", re.I)),
    ("3 John", "New Testament", re.compile(r"\b(?:3|third)\s+john\b", re.I)),
    ("Jude", "New Testament", re.compile(r"\bjude\b", re.I)),
    ("Revelation", "New Testament", re.compile(r"\brevelation\b", re.I)),
)

BIBLICAL_CHARACTER_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Adam", re.compile(r"\badam\b", re.I)), ("Eve", re.compile(r"\beve\b", re.I)),
    ("Noah", re.compile(r"\bnoah\b", re.I)), ("Abraham", re.compile(r"\babraham\b", re.I)),
    ("Sarah", re.compile(r"\bsarah\b", re.I)), ("Isaac", re.compile(r"\bisaac\b", re.I)),
    ("Ishmael", re.compile(r"\bishmael\b", re.I)), ("Jacob", re.compile(r"\bjacob\b", re.I)),
    ("Joseph", re.compile(r"\bjoseph\b", re.I)), ("Moses", re.compile(r"\bmoses\b", re.I)),
    ("Joshua", re.compile(r"\bjoshua\b", re.I)), ("David", re.compile(r"\bdavid\b", re.I)),
    ("Solomon", re.compile(r"\bsolomon\b", re.I)), ("Elijah", re.compile(r"\belijah\b", re.I)),
    ("Elisha", re.compile(r"\belisha\b", re.I)), ("Isaiah", re.compile(r"\bisaiah\b", re.I)),
    ("Jeremiah", re.compile(r"\bjeremiah\b", re.I)), ("Daniel", re.compile(r"\bdaniel\b", re.I)),
    ("Mary", re.compile(r"\bmary\b", re.I)), ("Jesus", re.compile(r"\bjesus\b", re.I)),
    ("Peter", re.compile(r"\bpeter\b", re.I)), ("Paul", re.compile(r"\bpaul\b", re.I)),
    ("John", re.compile(r"\bjohn\b", re.I)), ("James", re.compile(r"\bjames\b", re.I)),
    ("Martha", re.compile(r"\bmartha\b", re.I)), ("Lazarus", re.compile(r"\blazarus\b", re.I)),
    ("Pilate", re.compile(r"\bpilate\b", re.I)), ("Barnabas", re.compile(r"\bbarnabas\b", re.I)),
)

_BOOK_SCAN_ALIASES = {
    "first samuel": "1 Samuel", "second samuel": "2 Samuel", "first kings": "1 Kings", "second kings": "2 Kings",
    "first chronicles": "1 Chronicles", "second chronicles": "2 Chronicles", "first corinthians": "1 Corinthians",
    "second corinthians": "2 Corinthians", "first thessalonians": "1 Thessalonians", "second thessalonians": "2 Thessalonians",
    "first timothy": "1 Timothy", "second timothy": "2 Timothy", "first peter": "1 Peter", "second peter": "2 Peter",
    "first john": "1 John", "second john": "2 John", "third john": "3 John", "song of songs": "Song of Solomon",
    "song of song": "Song of Solomon",
}
_BOOK_SCAN_TERMS = sorted({label for label, _testament, _pattern in BIBLE_BOOK_RULES} | set(_BOOK_SCAN_ALIASES), key=len, reverse=True)
BOOK_SCAN_RE = re.compile(r"\b(?:" + "|".join(re.escape(term) for term in _BOOK_SCAN_TERMS) + r")\b", re.I)
CHARACTER_SCAN_RE = re.compile(r"\b(?:" + "|".join(re.escape(name) for name, _pattern in BIBLICAL_CHARACTER_RULES) + r")\b", re.I)

TOPIC_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Jesus & Gospels", re.compile(r"\b(?:jesus|christ|messiah|gospel|parable|miracle|disciples?|kingdom of god|resurrection|calvary|cross)\b", re.I)),
    ("Genesis & Patriarchs", re.compile(r"\b(?:genesis|adam|eve|abraham|sarah|isaac|ishmael|jacob|joseph|noah|eden)\b", re.I)),
    ("Kings & Prophets", re.compile(r"\b(?:joshua|judges|samuel|kings|chronicles|david|solomon|elijah|elisha|isaiah|jeremiah|ezekiel|daniel|prophet)\b", re.I)),
    ("Torah & Covenant", re.compile(r"\b(?:exodus|leviticus|numbers|deuteronomy|moses|sinai|torah|covenant|tabernacle|sabbath)\b", re.I)),
    ("Acts & Early Church", re.compile(r"\b(?:acts|apostle|paul|peter|stephen|barnabas|silas|early church)\b", re.I)),
    ("Prayer & Spiritual Life", re.compile(r"\b(?:pray|prayer|fasting|devotion|spiritual discipline|worship)\w*", re.I)),
    ("Faith, Grace & Salvation", re.compile(r"\b(?:faith|grace|salvation|saved|justify|justification|redemption|forgiven)\w*", re.I)),
    ("Marriage & Relationships", re.compile(r"\b(?:marriage|married|husband|wife|wedding|divorce|bride|relationship|love)\w*", re.I)),
    ("Sexuality & Purity", re.compile(r"\b(?:sex|sexual|semen|menstru|adulter|porn|lust|purity|seduct|desire|circumcision)\w*", re.I)),
    ("Revelation & Eternity", re.compile(r"\b(?:revelation|rapture|tribulation|antichrist|second coming|eternity|hell|new jerusalem)\w*", re.I)),
    ("Wisdom, Psalms & Worship", re.compile(r"\b(?:psalm|proverb|ecclesiastes|song of songs|wisdom|worship)\w*", re.I)),
    ("Spiritual Warfare", re.compile(r"\b(?:demon|satan|devil|spiritual warfare|deliverance|temptation)\w*", re.I)),
    ("Church & Ministry", re.compile(r"\b(?:church|pastor|preach|ministry|minister|elder|deacon)\w*", re.I)),
    ("Family & Parenting", re.compile(r"\b(?:parent|mother|father|son|daughter|child|children|family|sibling)\w*", re.I)),
    ("Healing & Encouragement", re.compile(r"\b(?:healing|grief|grieving|anxiety|depression|encourag|comfort|brokenhearted|suffering)\w*", re.I)),
    ("Money & Stewardship", re.compile(r"\b(?:money|wealth|giving|tithe|offering|steward|debt|finance|rich)\w*", re.I)),
)

GOSPEL_CATEGORY_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("Jesus", re.compile(r"\bjesus\b", re.I)), ("Teachings", re.compile(r"\b(?:teach|sermon|command|parable|kingdom of god)\w*", re.I)),
    ("Miracles", re.compile(r"\bmiracle\w*|healed|healing|raised the dead", re.I)), ("Parables", re.compile(r"\bparable\w*", re.I)),
    ("Death & Resurrection", re.compile(r"\b(?:cross|crucifixion|calvary|resurrection|empty tomb|rose again)\b", re.I)),
    ("Disciples & Ministry", re.compile(r"\b(?:disciples?|apostles?|ministry|mission)\w*", re.I)),
    ("Kingdom of God", re.compile(r"\bkingdom of (?:god|heaven)\b", re.I)), ("Salvation, Faith & Grace", re.compile(r"\b(?:salvation|faith|grace|saved)\w*", re.I)),
)

REFERENCE_RE = re.compile(
    r"\b(?P<book>(?:1|2|3|first|second|third)?\s*(?:Samuel|Kings|Chronicles|Corinthians|Thessalonians|Timothy|Peter|John)"
    r"|Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes|"
    r"Song\s+of\s+(?:Songs?|Solomon)|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|"
    r"Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|Matthew|Mark|Luke|Acts|Romans|Galatians|Ephesians|Philippians|Colossians|"
    r"Hebrews|James|Titus|Philemon|Jude|Revelation)\s+(?P<chapter>\d+(?::\d+(?:[-–]\d+)?)?)\b", re.I
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(default)


def atomic_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def reader_policy() -> dict[str, Any]:
    return read_json(Path(__file__).resolve().parent / "content-policy.json", {})


def reader_policy_stamp() -> dict[str, Any]:
    policy = Path(__file__).resolve().parent / "content-policy.json"
    stat = CONTENT_PATH.stat()
    return {"policySHA256": hashlib.sha256(policy.read_bytes() if policy.exists() else b"{}").hexdigest(), "socialCallsCleanupVersion": SOCIAL_CALLS_CLEANUP_VERSION, "archiveMtimeNs": stat.st_mtime_ns, "archiveSize": stat.st_size}


def mark_reader_policy() -> None:
    atomic_json(HERE / "reader-policy-applied.json", reader_policy_stamp())


def reader_excludes(post_id: Any, title: str = "", policy: dict[str, Any] | None = None) -> bool:
    policy = reader_policy() if policy is None else policy
    return str(post_id) in {str(value) for value in policy.get("excludedPostIds", [])} or (
        bool(title) and normalize_title(title) in {normalize_title(value) for value in policy.get("excludedTitles", [])}
    )


def apply_reader_policy(data: dict[str, Any], *, clean_promotions: bool = True) -> list[dict[str, Any]]:
    posts = data.get("posts") or []
    policy = reader_policy()
    removed, retained = [], []
    for post in posts:
        (removed if reader_excludes(post.get("id"), post.get("title", ""), policy) else retained).append(post)
    data["posts"] = retained
    archive = data.setdefault("archive", {})
    archive["publicRecordsRecovered"] = len(data["posts"])
    archive["readerFocus"] = "Bible study"
    archive["readerExcludedPostIds"] = policy.get("excludedPostIds", [])
    if clean_promotions and archive_posts_need_cleanup(data):
        clean_archive_posts(data)
    return removed


def load_archive() -> dict[str, Any]:
    with gzip.open(CONTENT_PATH, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    apply_reader_policy(data)
    return data


def curate_reader_archive() -> dict[str, Any]:
    """Apply requested reader exclusions to the saved archive, without network IO."""
    with gzip.open(CONTENT_PATH, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    previous_archive = copy.deepcopy(data.get("archive", {}))
    needs_cleanup = archive_posts_need_cleanup(data)
    removed = apply_reader_policy(data)
    if removed or needs_cleanup or previous_archive != data.get("archive"):
        # Curation can run during app startup on an older Intel Mac. Level six
        # avoids the long CPU-bound level-nine recompression on large archives.
        save_archive(data, compresslevel=6)
    summary = archive_summary(data["posts"])
    status = read_json(STATUS_PATH, {})
    status["recentAdded"] = [post for post in status.get("recentAdded", []) if not reader_excludes(post.get("id"), post.get("title", ""))]
    status.update(currentTotal=summary["total"], totalWords=summary["words"], subjects=summary["subjects"], structuredMetadata=summary["structuredMetadata"])
    atomic_json(STATUS_PATH, status)
    return {"removed": [{"id": post["id"], "title": post["title"]} for post in removed], **summary}


def validate_archive_data(data: dict[str, Any]) -> dict[str, int]:
    posts = data.get("posts")
    if not isinstance(posts, list) or not posts:
        raise RuntimeError("Archive has no posts")
    ids: set[str] = set()
    titles: set[str] = set()
    bodies: set[str] = set()
    missing_images: list[str] = []
    for post in posts:
        pid = str(post.get("id") or "")
        title = normalize_title(post.get("title", ""))
        digest = body_hash(post.get("text", ""))
        if not pid or pid in ids:
            raise RuntimeError(f"Duplicate or empty post id: {pid}")
        if not title:
            raise RuntimeError(f"Empty normalized title: {post.get('title', '')[:120]}")
        if digest in bodies:
            raise RuntimeError(f"Duplicate complete body: {pid}")
        ids.add(pid); titles.add(title); bodies.add(digest)
        local = post.get("imageLocal")
        bundled_image = Path(__file__).resolve().parent / (local or "")
        if not local or not ((HERE / local).is_file() or bundled_image.is_file()):
            missing_images.append(pid)
    if missing_images:
        raise RuntimeError(f"Archive references {len(missing_images)} missing local images")
    return {"posts": len(posts), "ids": len(ids), "titles": len(titles), "bodies": len(bodies)}


def save_archive(data: dict[str, Any], compresslevel: int = 9) -> None:
    apply_reader_policy(data)
    validate_archive_data(data)
    fd, tmp = tempfile.mkstemp(prefix="content.", suffix=".json.gz", dir=HERE)
    os.close(fd)
    try:
        with open(tmp, "wb") as raw:
            with gzip.GzipFile(filename="content.json", mode="wb", fileobj=raw, compresslevel=compresslevel, mtime=0) as zipped:
                # Stream JSON to avoid constructing several archive-sized
                # Unicode/UTF-8 copies during a background update on Intel Macs.
                with io.TextIOWrapper(zipped, encoding="utf-8") as text:
                    json.dump(data, text, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        # Check the complete gzip stream/CRC without parsing another in-memory
        # copy. Archive identity and image integrity were validated above.
        with gzip.open(tmp, "rb") as check:
            for _ in iter(lambda: check.read(1024 * 1024), b""):
                pass
        os.replace(tmp, CONTENT_PATH)
        mark_reader_policy()
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_status(**updates: Any) -> dict[str, Any]:
    status = read_json(STATUS_PATH, {})
    status.update(updates)
    status.setdefault("source", PROFILE_URL)
    status.setdefault("intervalMinutes", read_json(CONFIG_PATH, DEFAULT_CONFIG).get("intervalMinutes", 15))
    atomic_json(STATUS_PATH, status)
    return status


def append_log(entry: dict[str, Any]) -> None:
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def rx(text: str, pattern: str) -> str:
    match = re.search(pattern, text)
    return match.group(1) if match else ""


def walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def script_payloads(html: str) -> Iterable[Any]:
    soup = BeautifulSoup(html, "html.parser")
    for script in soup.find_all("script", attrs={"type": "application/json"}):
        try:
            yield json.loads(script.string or script.get_text())
        except Exception:
            continue


def decode_story_id(encoded: str | None) -> str | None:
    if not encoded:
        return None
    try:
        raw = base64.b64decode(encoded + "===").decode("utf-8", errors="ignore")
        numbers = re.findall(r"\d{10,}", raw)
        return numbers[-1] if numbers else None
    except Exception:
        return None


def edge_record(edge: dict[str, Any]) -> dict[str, Any] | None:
    node = edge.get("node") or {}
    story = node.get("creation_story") or {}
    post_id = decode_story_id(story.get("id"))
    photo_id = str(node.get("id") or "")
    if not post_id or not photo_id:
        return None
    image = (node.get("image") or {}).get("uri") or f"https://lookaside.fbsbx.com/lookaside/crawler/media/?media_id={photo_id}"
    return {"post_id": post_id, "photo_id": photo_id, "image": image}


def initial_album_page(session: requests.Session) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    response = session.get(ALBUM_URL, headers=HEADERS, timeout=90)
    response.raise_for_status()
    html = response.text
    grids = []
    for payload in script_payloads(html):
        for obj in walk_json(payload):
            if str(obj.get("id")) == ALBUM_ID and isinstance(obj.get("grid_media"), dict):
                grid = obj["grid_media"]
                if isinstance(grid.get("edges"), list):
                    grids.append(grid)
    if not grids:
        raise RuntimeError("Facebook did not expose the public album grid")
    grid = max(grids, key=lambda item: len(item.get("edges") or []))
    records = [record for edge in grid.get("edges", []) if (record := edge_record(edge))]
    tokens = {
        "lsd": rx(html, r'\["LSD",\[\],\{"token":"([^"]+)'),
        "hsi": rx(html, r'"hsi":"([^"]+)'),
        "rev": rx(html, r'"client_revision":(\d+)'),
        "spin": rx(html, r'"__spin_t":(\d+)'),
    }
    if not all(tokens.values()):
        raise RuntimeError("Facebook public-page query tokens were not available")
    return html, records, {"tokens": tokens, "page_info": grid.get("page_info") or {}}


def query_album_page(session: requests.Session, cursor: str, tokens: dict[str, str], request_no: int) -> dict[str, Any]:
    variables = {"count": 50, "cursor": cursor, "id": ALBUM_ID, "scale": 1}
    form = {
        "av": "0", "__user": "0", "__a": "1", "__req": str(request_no),
        "dpr": "1", "__ccg": "EXCELLENT", "__rev": tokens["rev"], "__hsi": tokens["hsi"],
        "__comet_req": "15", "lsd": tokens["lsd"], "__spin_r": tokens["rev"],
        "__spin_b": "trunk", "__spin_t": tokens["spin"],
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "ProfileCometLegacyAlbumGridViewPaginationQuery",
        "variables": json.dumps(variables, separators=(",", ":")),
        "server_timestamps": "true", "doc_id": ALBUM_DOC_ID,
    }
    response = session.post(
        GRAPHQL_URL,
        headers={**HEADERS, "content-type": "application/x-www-form-urlencoded", "x-fb-lsd": tokens["lsd"], "origin": "https://www.facebook.com", "referer": ALBUM_URL},
        data=form, timeout=90,
    )
    response.raise_for_status()
    payload = json.loads(response.text.splitlines()[0])
    grid = (((payload.get("data") or {}).get("node") or {}).get("grid_media"))
    if not isinstance(grid, dict) or not isinstance(grid.get("edges"), list):
        message = (payload.get("errors") or [{}])[0].get("message", "album pagination returned no grid")
        raise RuntimeError(message)
    return grid


def scan_frontier(session: requests.Session, known_ids: set[str], config: dict[str, Any]) -> tuple[list[dict[str, Any]], int, bool]:
    _, first, meta = initial_album_page(session)
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    pages = 1

    def add(records: list[dict[str, Any]]) -> bool:
        found_known = False
        for record in records:
            pid = record["post_id"]
            if pid in known_ids:
                found_known = True
            elif pid not in seen:
                collected.append(record)
                seen.add(pid)
        return found_known

    found_known = add(first)
    page_info = meta["page_info"]
    cursor = page_info.get("end_cursor")
    has_next = bool(page_info.get("has_next_page"))
    max_pages = max(1, min(40, int(config.get("maxFrontierPages", MAX_FRONTIER_PAGES))))
    delay = max(0.2, float(config.get("requestDelaySeconds", 0.45)))
    while not found_known and has_next and cursor and pages < max_pages:
        time.sleep(delay)
        grid = query_album_page(session, cursor, meta["tokens"], pages + 1)
        pages += 1
        records = [record for edge in grid.get("edges", []) if (record := edge_record(edge))]
        found_known = add(records)
        page_info = grid.get("page_info") or {}
        cursor = page_info.get("end_cursor")
        has_next = bool(page_info.get("has_next_page"))
    boundary_complete = found_known or not has_next
    return collected, pages, boundary_complete


def story_from_html(html: str, target_id: str) -> dict[str, Any]:
    objects: list[dict[str, Any]] = []
    all_objects: list[dict[str, Any]] = []
    for payload in script_payloads(html):
        for obj in walk_json(payload):
            all_objects.append(obj)
            message = obj.get("message")
            text = message.get("text") if isinstance(message, dict) else message if isinstance(message, str) else None
            if str(obj.get("post_id") or "") == target_id and isinstance(text, str) and len(text) > 200:
                objects.append(obj)
    if not objects:
        raise RuntimeError("Complete public story body was not exposed")
    story = max(objects, key=lambda obj: len((obj.get("message") or {}).get("text", "")) if isinstance(obj.get("message"), dict) else len(str(obj.get("message") or "")))
    message = story.get("message")
    text = message.get("text") if isinstance(message, dict) else str(message)

    permalink = story.get("url") or story.get("permalink_url") or story.get("wwwURL")
    if not permalink:
        for obj in objects:
            for key in ("url", "permalink_url", "wwwURL", "comet_permalink_url"):
                value = obj.get(key)
                if isinstance(value, str) and "facebook.com" in value and "/posts/" in value:
                    permalink = value
                    break
            if permalink:
                break
    timestamp = 0
    image = None
    photo_id = None
    for obj in all_objects:
        if not timestamp and isinstance(obj.get("creation_time"), (int, float)):
            # Prefer a node containing the target story id or its content tree.
            encoded = json.dumps(obj, ensure_ascii=False)[:250000]
            if target_id in encoded:
                timestamp = int(obj["creation_time"])
        media = obj.get("photo_image")
        if not image and isinstance(media, dict) and isinstance(media.get("uri"), str):
            image = media["uri"]
            photo_id = str(obj.get("id") or "") or None
    return {"text": text, "url": permalink, "timestamp": timestamp, "image": image, "photo_id": photo_id}


def fetch_story(session: requests.Session, record: dict[str, Any]) -> dict[str, Any]:
    post_id = record["post_id"]
    url = f"https://www.facebook.com/{PROFILE_ID}/posts/{post_id}/"
    response = session.get(url, headers=HEADERS, timeout=100)
    response.raise_for_status()
    result = story_from_html(response.text, post_id)
    result["id"] = post_id
    result["url"] = result.get("url") or f"https://www.facebook.com/iamGospelWarrior/posts/{post_id}"
    result["image"] = result.get("image") or record.get("image")
    result["photo_id"] = result.get("photo_id") or record.get("photo_id")
    return result


def normalize_title(title: str) -> str:
    return re.sub(r"[\W_]+", " ", unicodedata.normalize("NFKC", title).casefold()).strip()


def body_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text).strip().casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def study_body_hash(text: str, title: str) -> str:
    """Identify repeated teaching, ignoring its headline and typography."""
    lines = text.strip().splitlines()
    if lines and normalize_title(lines[0]) == normalize_title(title):
        remainder = "\n".join(lines[1:]).strip()
        if remainder:
            text = remainder
    normalized = re.sub(r"[\W_]+", " ", unicodedata.normalize("NFKC", text).casefold()).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def is_cta_block(block: str) -> bool:
    stripped = block.strip()
    if not stripped:
        return False
    if re.fullmatch(r"(?:[#@][^\s]+\s*)+", stripped):
        return True
    # Most of the archive is ordinary Scripture/teaching. A cheap literal
    # prefilter avoids running every promotional regex over millions of words.
    lowered = stripped.lower()
    if not any(token in lowered for token in (
        "subscrib", "subscription", "follow", "share", "sharing", "save", "comment", "tag",
        "like", "react", "repost", "gospel warrior", "library", "support", "discount", "%",
        "product", "merchandise", "ebook", "book", "free", "access", "unlock", "download",
        "thank", "price", "call to action", "notifications", "stars", "mission", "paypal", "patreon",
        "buymeacoffee", "ko-fi", "facebook.com", "invited", "join", "donate", "feeds your spirit", "t-shirt", "mug", "journal",
    )):
        return False
    # Use actions and offers, rather than words such as "follow", "share", or
    # "support" alone: following Jesus and caring for others are study content.
    return any(pattern.search(stripped) for pattern in (
        SOCIAL_URL_RE, CTA_DIRECT_RE, CTA_PROMO_RE, SOCIAL_ACTION_RE,
        SUBSCRIPTION_RE, LIBRARY_PROMO_RE, SUPPORT_PROMO_RE, OFFER_PROMO_RE,
        PROMO_HEADING_RE, STANDALONE_SOCIAL_RE,
        OLDER_SOCIAL_PROMO_RE,
    )) or all(PRODUCT_LIST_RE.fullmatch(line.strip()) for line in stripped.splitlines())


def clean_social_calls(text: str) -> tuple[str, int]:
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n"))
    kept: list[str] = []
    removed = 0
    promotional_context = False
    remove_following_list = False
    remove_following_title_or_reply = False
    for block in blocks:
        value = block.strip()
        if not value:
            continue
        lines = value.splitlines()
        if remove_following_list and all(re.match(r"^\s*[•✅✓✔*-]", line) for line in lines):
            removed += 1
            continue
        remove_following_list = False
        if remove_following_title_or_reply and len(lines) == 1 and len(value) < 180:
            removed += 1
            remove_following_title_or_reply = False
            continue
        remove_following_title_or_reply = False
        # A plain newline can separate an invitation from Scripture. Remove
        # the invitation line without discarding the teaching beside it.
        retained_lines = [line for line in lines if not is_cta_block(line)]
        if len(retained_lines) != len(lines):
            removed += 1
            promotional_context = True
            remove_following_list = bool(re.search(r"this\s+e?book\s+(?:will|can)\s+help", value, re.I))
            remove_following_title_or_reply = bool(re.search(r"(?:comment|(?:unlock|get|download)\s+your\s+free\s+copy\s+of)\s*:\s*$", value, re.I))
            if not retained_lines:
                continue
            value = "\n".join(retained_lines).strip()
        elif is_cta_block(value):
            removed += 1
            promotional_context = True
            continue
        if promotional_context and PROMO_CONTINUATION_RE.search(value):
            removed += 1
            continue
        kept.append(value)
    return "\n\n".join(kept).strip(), removed


def title_and_subtitle(text: str) -> tuple[str, str]:
    blocks = [part.strip() for part in re.split(r"\n\s*\n", text) if part.strip()]
    if not blocks:
        return "Untitled Bible Study", ""
    first_lines = [line.strip() for line in blocks[0].splitlines() if line.strip()]
    title = first_lines[0] if first_lines else blocks[0]
    if len(first_lines) > 1 and len(title) < 45:
        # Preserve compact two-line headings that are clearly one title.
        candidate = " ".join(first_lines[:2])
        if len(candidate) <= 180:
            title = candidate
    subtitle = blocks[1] if len(blocks) > 1 else ""
    if len(subtitle) > 420:
        subtitle = subtitle[:417].rstrip() + "…"
    return title.strip(), subtitle.strip()


def classify_subject(title: str, text: str) -> str:
    headline = title.lower()
    intro = f"{title}\n{text[:1800]}".lower()

    # Headline-level themes first: the title is the strongest signal of intent.
    if re.search(r"\b(sex|sexual|semen|menstru|adulter|porn|lust|purity|seduct|attract|desire|covet|bleeding|circumcision)\w*", headline):
        return "Sexuality & Purity"
    if re.search(r"\b(marriage|married|husband|wife|wedding|divorce|bride|bridegroom|dating|relationship)\w*", headline):
        return "Marriage & Relationships"
    if re.search(r"\b(parent|parenting|mother|father|son|daughter|child|children|family|sibling)\w*", headline):
        return "Family & Parenting"
    if re.search(r"\b(pray|prayer|intercession|fasting|devotion|spiritual discipline)\w*", headline):
        return "Prayer & Spiritual Life"
    if re.search(r"\b(healing|grief|grieving|anxiety|depression|encourag|comfort|brokenhearted|suffering)\w*", headline):
        return "Healing & Encouragement"
    if re.search(r"\b(demon|satan|devil|spiritual warfare|deliverance|temptation)\w*", headline):
        return "Spiritual Warfare"
    if re.search(r"\b(money|wealth|giving|tithe|offering|steward|debt|finance|rich)\w*", headline):
        return "Money & Stewardship"
    if re.search(r"\b(church|pastor|preach|ministry|minister|elder|deacon|worship team)\w*", headline):
        return "Church & Ministry"

    # Explicit headline passages and characters outrank incidental cross-references.
    if re.search(r"\b(revelation|rapture|tribulation|antichrist|second coming|eternity|hell|new jerusalem)\w*", headline):
        return "Revelation & Eternity"
    if re.search(r"\b(acts|apostle|paul|peter|stephen|barnabas|silas)\w*", headline):
        return "Acts & Early Church"
    if re.search(r"\b(jesus|christ|messiah|gospel|sermon on the mount|parable|calvary|cross|resurrection|wise man built|good tree)\w*", headline):
        return "Jesus & Gospels"
    if re.search(r"\b(jeremiah|isaiah|ezekiel|daniel|elijah|elisha|david|solomon|prophet)\w*", headline):
        return "Kings & Prophets"
    if re.search(r"\b(psalm|proverb|ecclesiastes|song of songs|wisdom|worship|guard your heart|trust in the lord)\w*", headline):
        return "Wisdom, Psalms & Worship"
    if re.search(r"\b(genesis|abraham|sarah|isaac|rebekah|jacob|rachel|leah|joseph|adam|eve|noah|eden)\w*", headline):
        return "Genesis & Patriarchs"
    if re.search(r"\b(exodus|leviticus|numbers|deuteronomy|moses|aaron|sinai|tabernacle|torah|covenant|israelites|promised land)\w*", headline):
        return "Torah & Covenant"
    if re.search(r"\b(grace|salvation|saved|justify|justification|faith)\w*", headline):
        return "Faith, Grace & Salvation"

    # The opening passage normally states the controlling biblical text.
    if re.search(r"\b(?:revelation)\s+\d|\b(?:rapture|tribulation|antichrist)\b", intro):
        return "Revelation & Eternity"
    if re.search(r"\bacts\s+\d|\b(?:corinthians|galatians|ephesians|philippians|colossians|thessalonians|timothy|titus|philemon)\s+\d", intro):
        return "Acts & Early Church"
    if re.search(r"\b(?:matthew|mark|luke|john)\s+\d", intro):
        return "Jesus & Gospels"
    if re.search(r"\bgenesis\s+\d", intro):
        return "Genesis & Patriarchs"
    if re.search(r"\b(?:exodus|leviticus|numbers|deuteronomy)\s+\d", intro):
        return "Torah & Covenant"
    if re.search(r"\b(?:psalm|psalms|proverbs|ecclesiastes|song of songs)\s+\d", intro):
        return "Wisdom, Psalms & Worship"
    if re.search(r"\b(?:joshua|judges|samuel|kings|chronicles|isaiah|jeremiah|ezekiel|daniel|hosea|jonah|zechariah|malachi)\s+\d", intro):
        return "Kings & Prophets"
    return "Christian Living"


def canonical_book(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value.strip()).casefold()
    replacements = {
        "psalm": "Psalms", "psalms": "Psalms", "song of songs": "Song of Solomon",
        "song of song": "Song of Solomon", "first samuel": "1 Samuel", "second samuel": "2 Samuel",
        "first kings": "1 Kings", "second kings": "2 Kings", "first chronicles": "1 Chronicles",
        "second chronicles": "2 Chronicles", "first corinthians": "1 Corinthians", "second corinthians": "2 Corinthians",
        "first thessalonians": "1 Thessalonians", "second thessalonians": "2 Thessalonians",
        "first timothy": "1 Timothy", "second timothy": "2 Timothy", "first peter": "1 Peter",
        "second peter": "2 Peter", "first john": "1 John", "second john": "2 John", "third john": "3 John",
    }
    if normalized in replacements:
        return replacements[normalized]
    return value.strip().title()


def extract_bible_references(text: str) -> list[str]:
    references: list[str] = []
    for match in REFERENCE_RE.finditer(text):
        book = canonical_book(match.group("book"))
        reference = f"{book} {match.group('chapter')}"
        if reference not in references:
            references.append(reference)
    return references


def extract_bible_books(text: str) -> list[str]:
    found = {_BOOK_SCAN_ALIASES.get(match.group(0).casefold(), match.group(0).strip().title()) for match in BOOK_SCAN_RE.finditer(text)}
    return [book for book, _testament, _pattern in BIBLE_BOOK_RULES if book in found]


def extract_characters(title: str, text: str) -> list[str]:
    counts = Counter(match.group(0).casefold() for match in CHARACTER_SCAN_RE.finditer(text))
    title_lower = title.casefold()
    return [name for name, _pattern in BIBLICAL_CHARACTER_RULES if name.casefold() in title_lower or counts[name.casefold()] >= 2]


def derive_metadata(title: str, text: str, subject: str | None = None) -> dict[str, Any]:
    full_text = f"{title}\n{text}"
    # The title and opening section carry the primary intent; the full body is
    # still used for books/references/characters because those are explicit
    # searchable facts rather than editorial guesses.
    intent_text = f"{title}\n{text[:2600]}"
    books = extract_bible_books(full_text)
    references = extract_bible_references(full_text)
    characters = extract_characters(title, full_text)
    topics: list[str] = []
    if subject:
        topics.append(subject)
    for topic, pattern in TOPIC_RULES:
        if pattern.search(intent_text) and topic not in topics:
            topics.append(topic)
    topics = topics[:5] or ["Christian Living"]
    testaments = {testament for book, testament, _pattern in BIBLE_BOOK_RULES if book in books}
    if not testaments:
        if subject in {"Genesis & Patriarchs", "Kings & Prophets", "Torah & Covenant", "Wisdom, Psalms & Worship"}:
            testaments.add("Old Testament")
        elif subject in {"Jesus & Gospels", "Acts & Early Church"}:
            testaments.add("New Testament")
    if len(testaments) > 1:
        testament = "Both Testaments"
    else:
        testament = next(iter(testaments), "Unclassified")
    gospel_categories = [category for category, pattern in GOSPEL_CATEGORY_RULES if pattern.search(intent_text)]
    if subject != "Jesus & Gospels" and not gospel_categories:
        gospel_categories = []
    return {
        "bibleReferences": references,
        "bibleBooks": books,
        "biblicalCharacters": characters,
        "topics": topics,
        "testament": testament,
        "gospelCategory": gospel_categories,
    }


def enrich_post(post: dict[str, Any]) -> bool:
    """Add/update index metadata without changing the original study text."""
    metadata = derive_metadata(post.get("title", ""), post.get("text", ""), post.get("subject"))
    if post.get("importedFrom") == "Arena AI Gospel Warrior archive":
        full_text = f"{post.get('title', '')}\n{post.get('text', '')}"
        compact_text = re.sub(r"\s+", "", full_text.casefold()).replace("–", "-").replace("—", "-")
        references = [ref for ref in post.get("bibleReferences", []) if re.sub(r"\s+", "", ref.casefold()).replace("–", "-").replace("—", "-") in compact_text]
        metadata["bibleReferences"] = list(dict.fromkeys(metadata["bibleReferences"] + references))
        books = [book for book in post.get("bibleBooks", []) if re.search(r"\b" + re.escape(book) + r"\b", full_text, re.I) or any(ref.startswith(book + " ") for ref in metadata["bibleReferences"])]
        metadata["bibleBooks"] = list(dict.fromkeys(metadata["bibleBooks"] + books))
        characters = [name for name in post.get("biblicalCharacters", []) if re.search(r"\b" + re.escape(name) + r"\b", full_text, re.I)]
        metadata["biblicalCharacters"] = list(dict.fromkeys(metadata["biblicalCharacters"] + characters))
        for field in ("topics", "gospelCategory"):
            metadata[field] = list(dict.fromkeys(metadata[field] + post.get(field, [])))
        testaments = {testament for book, testament, _ in BIBLE_BOOK_RULES if book in metadata["bibleBooks"]}
        if testaments:
            metadata["testament"] = "Both Testaments" if len(testaments) > 1 else next(iter(testaments))
    metadata.update({
        "source": "Gospel Warrior public archive",
        "sourceUrl": post.get("url"),
        "originalDate": post.get("date"),
        "originalMedia": post.get("media") or [],
        "duplicateGroup": body_hash(post.get("text", "")),
        "metadataSchemaVersion": 2,
    })
    changed = any(post.get(key) != value for key, value in metadata.items())
    post.update(metadata)
    return changed


def download_image(session: requests.Session, url: str, post_id: str) -> tuple[str, str]:
    response = session.get(url, headers=HEADERS, timeout=90)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "").lower()
    if not content_type.startswith("image/") or len(response.content) < 1500:
        raise RuntimeError("Public post image did not return image data")

    # Facebook commonly returns 1024×1536 images around 400–500 KB each. The
    # reader never displays them above 960 px, so normalize new imports to a
    # progressive JPEG. This keeps frequent automatic updates within the
    # workspace/deployment size budget without changing study text.
    target = ASSETS / f"archive-{post_id}.jpg"
    fd, tmp = tempfile.mkstemp(prefix=target.name + ".", dir=ASSETS)
    os.close(fd)
    try:
        with Image.open(io.BytesIO(response.content)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail((960, 960), Image.Resampling.LANCZOS)
            if image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            ):
                rgba = image.convert("RGBA")
                background = Image.new("RGB", rgba.size, "white")
                background.paste(rgba, mask=rgba.getchannel("A"))
                image = background
            elif image.mode != "RGB":
                image = image.convert("RGB")
            image.save(
                tmp,
                format="JPEG",
                quality=72,
                optimize=True,
                progressive=True,
            )
        os.replace(tmp, target)
    except Exception as exc:
        raise RuntimeError("Public post image could not be optimized") from exc
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return f"assets/{target.name}", "image/jpeg"


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def make_post(session: requests.Session, raw: dict[str, Any], known_titles: set[str], known_bodies: set[str]) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    cleaned, removed_blocks = clean_social_calls(raw["text"])
    title, subtitle = title_and_subtitle(cleaned)
    words = word_count(cleaned)
    info = {"id": raw["id"], "title": title, "words": words, "ctaBlocksRemoved": removed_blocks}
    if reader_excludes(raw["id"], title):
        info["result"] = "excluded-from-study-reader"
        return None, info
    if words < MIN_STUDY_WORDS or not BIBLE_SIGNAL_RE.search(cleaned):
        info["result"] = "not-a-bible-study"
        return None, info
    nt = normalize_title(title)
    bh = body_hash(cleaned)
    study_digest = study_body_hash(cleaned, title)
    if study_digest in known_bodies:
        info["result"] = "duplicate-body"
        return None, info
    local_image, _ = download_image(session, raw["image"], raw["id"])
    timestamp = int(raw.get("timestamp") or time.time())
    date = datetime.fromtimestamp(timestamp, timezone.utc).isoformat()
    post = {
        "id": raw["id"], "title": title, "subtitle": subtitle, "text": cleaned,
        "url": raw["url"], "timestamp": timestamp, "date": date,
        "author": "John Domino Sanchez Asis", "mediaType": "photo",
        "image": raw["image"], "imageLocal": local_image,
        "media": [{"type": "photo", "url": raw["image"], "local": local_image}],
        "reactions": 0, "comments": 0, "shares": 0,
        "pinned": False, "with": None,
        "subject": classify_subject(title, cleaned),
        "socialCallsCleanupVersion": SOCIAL_CALLS_CLEANUP_VERSION,
        "socialCallsCleanupHash": bh,
    }
    enrich_post(post)
    known_titles.add(nt)
    known_bodies.add(study_digest)
    info.update({"result": "added", "subject": post["subject"], "url": post["url"], "date": post["date"]})
    return post, info


def archive_summary(posts: list[dict[str, Any]]) -> dict[str, Any]:
    timestamps = [int(p.get("timestamp") or 0) for p in posts if p.get("timestamp")]
    words = sum(word_count(p.get("text", "")) for p in posts)
    subjects = len({p.get("subject") for p in posts if p.get("subject")})
    metadata_fields = ("bibleReferences", "bibleBooks", "biblicalCharacters", "topics", "testament", "gospelCategory")
    structured_metadata = sum(1 for post in posts if all(field in post for field in metadata_fields))
    return {
        "total": len(posts), "words": words, "subjects": subjects,
        "structuredMetadata": structured_metadata,
        "oldestTimestamp": min(timestamps) if timestamps else None,
        "newestTimestamp": max(timestamps) if timestamps else None,
    }


def run_update() -> dict[str, Any]:
    started = now_iso()
    config = {**DEFAULT_CONFIG, **read_json(CONFIG_PATH, {})}
    data = load_archive()
    posts = data.get("posts") or []
    metadata_changed = False
    for post in posts:
        if post.get("metadataSchemaVersion") == 2 and all(key in post for key in ("bibleReferences", "bibleBooks", "biblicalCharacters", "topics", "testament", "gospelCategory")):
            continue
        metadata_changed = enrich_post(post) or metadata_changed
    archive = data.setdefault("archive", {})
    if archive.get("metadataSchemaVersion") != 2:
        archive["metadataSchemaVersion"] = 2
        metadata_changed = True
    before = archive_summary(posts)
    status = write_status(
        state="checking", message="Checking the public profile for new studies…",
        running=True, lastCheckStarted=started, currentTotal=before["total"],
        intervalMinutes=int(config.get("intervalMinutes", 15)), error=None,
    )
    session = requests.Session()
    known_ids = {str(post.get("id")) for post in posts} | {str(value) for value in reader_policy().get("excludedPostIds", [])}
    known_titles = {normalize_title(post.get("title", "")) for post in posts}
    known_bodies = {study_body_hash(post.get("text", ""), post.get("title", "")) for post in posts}
    added: list[dict[str, Any]] = []
    details: list[dict[str, Any]] = []
    pages = 0
    try:
        frontier, pages, boundary_complete = scan_frontier(session, known_ids, config)
        if frontier and not boundary_complete:
            raise RuntimeError(
                f"The new-post frontier exceeded {pages} pages before reaching an archived post. "
                "No partial import was written; increase maxFrontierPages and retry."
            )
        # Album is newest-first. Fetch oldest-first so same-run duplicate decisions are deterministic.
        for index, record in enumerate(reversed(frontier), 1):
            write_status(
                state="importing", running=True,
                message=f"Reading new public study {index} of {len(frontier)}…",
                discovered=len(frontier), processed=index - 1,
            )
            try:
                raw = fetch_story(session, record)
                post, info = make_post(session, raw, known_titles, known_bodies)
                details.append(info)
                if post:
                    added.append(post)
            except Exception as exc:
                details.append({"id": record.get("post_id"), "result": "unavailable", "error": str(exc)[:300]})
            time.sleep(max(0.2, float(config.get("requestDelaySeconds", 0.45))))

        if added or metadata_changed:
            posts.extend(added)
            posts.sort(key=lambda item: (int(bool(item.get("pinned"))), int(item.get("timestamp") or 0)), reverse=True)
            data["posts"] = posts
            archive["publicRecordsRecovered"] = len(posts)
            archive["lastAutomaticUpdate"] = now_iso()
            archive["automaticUpdateEnabled"] = True
            archive["automaticUpdateIntervalMinutes"] = int(config.get("intervalMinutes", 15))
            archive["socialCallsRemoved"] = True
            save_archive(data)

        after = archive_summary(posts)
        latest = max(posts, key=lambda item: int(item.get("timestamp") or 0)) if posts else {}
        previous_status = read_json(STATUS_PATH, {})
        new_recent = [
            {"id": p["id"], "title": p["title"], "date": p["date"], "subject": p["subject"], "url": p["url"]}
            for p in sorted(added, key=lambda item: item["timestamp"], reverse=True)[:20]
        ]
        recent = new_recent or previous_status.get("recentAdded") or []
        last_import_count = len(added) if added else int(previous_status.get("lastImportCount") or len(recent))
        last_import_at = now_iso() if added else previous_status.get("lastImportAt")
        completed = now_iso()
        result = {
            "started": started, "completed": completed, "pagesScanned": pages,
            "discovered": len(frontier), "added": len(added), "before": before,
            "after": after, "latest": {"id": latest.get("id"), "title": latest.get("title"), "date": latest.get("date")},
            "details": details,
        }
        write_status(
            state="current", running=False,
            message=(f"Added {len(added)} new public {'study' if len(added) == 1 else 'studies'}." if added else "Archive is current; no new public studies were found."),
            lastCheck=completed, lastSuccess=completed, currentTotal=after["total"],
            totalWords=after["words"], subjects=after["subjects"], addedLastRun=len(added),
            structuredMetadata=after["structuredMetadata"],
            lastImportCount=last_import_count, lastImportAt=last_import_at,
            discoveredLastRun=len(frontier), pagesScanned=pages, latest=latest and result["latest"],
            recentAdded=recent, processed=len(frontier), error=None,
        )
        append_log({"event": "update", **result})
        return result
    except Exception as exc:
        failed = now_iso()
        write_status(
            state="error", running=False, message="The public source could not be checked. The existing archive is unchanged.",
            lastCheck=failed, currentTotal=before["total"], addedLastRun=0,
            pagesScanned=pages, error=str(exc)[:600],
        )
        append_log({"event": "error", "started": started, "completed": failed, "error": str(exc)})
        raise


def enrich_archive_metadata() -> dict[str, Any]:
    """Backfill the searchable index fields without contacting Facebook."""
    data = load_archive()
    posts = data.get("posts") or []
    changed = False
    for post in posts:
        if post.get("metadataSchemaVersion") == 2 and all(key in post for key in ("bibleReferences", "bibleBooks", "biblicalCharacters", "topics", "testament", "gospelCategory")):
            continue
        changed = enrich_post(post) or changed
    archive = data.setdefault("archive", {})
    if archive.get("metadataSchemaVersion") != 2:
        archive["metadataSchemaVersion"] = 2
        changed = True
    data["posts"] = posts
    if changed:
        save_archive(data)
    summary = archive_summary(posts)
    return {"changed": changed, "metadataSchemaVersion": 2, **summary}


def post_cleanup_is_current(post: dict[str, Any]) -> bool:
    return post.get("socialCallsCleanupVersion") == SOCIAL_CALLS_CLEANUP_VERSION and post.get("socialCallsCleanupHash") == body_hash(post.get("text", "")) and not any(is_cta_block(post.get(field, "")) for field in ("title", "subtitle"))


def archive_posts_need_cleanup(data: dict[str, Any]) -> bool:
    return data.get("archive", {}).get("socialCallsCleanupVersion") != SOCIAL_CALLS_CLEANUP_VERSION or any(not post_cleanup_is_current(post) for post in data.get("posts", []))


def clean_archive_posts(data: dict[str, Any], *, force: bool = False) -> dict[str, int]:
    """Clean bodies/previews and rebuild affected search metadata in memory."""
    posts = data.get("posts") or []
    changed = 0
    removed_blocks = 0
    for post in posts:
        if not force and post_cleanup_is_current(post):
            continue
        cleaned, removed = clean_social_calls(post.get("text", ""))
        title_changed = is_cta_block(post.get("title", ""))
        if title_changed:
            post["title"] = title_and_subtitle(cleaned)[0]
        if cleaned != post.get("text", "") or title_changed:
            changed += 1
            post["text"] = cleaned
            post["subtitle"] = title_and_subtitle(cleaned)[1]
            post["wordCount"] = word_count(cleaned)
            post["readingMinutes"] = max(1, round(post["wordCount"] / 235))
            enrich_post(post)
        elif is_cta_block(post.get("subtitle", "")):
            changed += 1
            post["subtitle"] = title_and_subtitle(cleaned)[1]
        removed_blocks += removed
        post["socialCallsCleanupVersion"] = SOCIAL_CALLS_CLEANUP_VERSION
        post["socialCallsCleanupHash"] = body_hash(cleaned)
    data["posts"] = posts
    archive = data.setdefault("archive", {})
    archive["metadataSchemaVersion"] = 2
    archive["socialCallsRemoved"] = True
    archive["socialCallsCleanupVersion"] = SOCIAL_CALLS_CLEANUP_VERSION
    return {"changedPosts": changed, "removedBlocks": removed_blocks}


def clean_archive_content() -> dict[str, Any]:
    """Clean the entire retained archive locally, including older imports."""
    with gzip.open(CONTENT_PATH, "rt", encoding="utf-8") as handle:
        data = json.load(handle)
    apply_reader_policy(data, clean_promotions=False)
    cleanup = clean_archive_posts(data, force=True)
    save_archive(data, compresslevel=6)
    summary = archive_summary(data["posts"])
    write_status(currentTotal=summary["total"], totalWords=summary["words"], subjects=summary["subjects"], structuredMetadata=summary["structuredMetadata"])
    return {**cleanup, **summary}


def ensure_defaults() -> None:
    if not CONFIG_PATH.exists():
        atomic_json(CONFIG_PATH, DEFAULT_CONFIG)
    if not STATUS_PATH.exists():
        try:
            summary = archive_summary(load_archive().get("posts") or [])
        except Exception:
            summary = {"total": 0, "words": 0, "subjects": 0}
        write_status(
            state="ready", running=False,
            message="Automatic updater is ready. Start the Update Server to schedule public checks.",
            lastCheck=None, lastSuccess=None, currentTotal=summary["total"],
            totalWords=summary["words"], subjects=summary["subjects"],
            structuredMetadata=summary.get("structuredMetadata", 0),
            addedLastRun=0, recentAdded=[], error=None,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update the Gospel Warrior archive from logged-out public Facebook routes.")
    parser.add_argument("--once", action="store_true", help="Run one update check (default).")
    parser.add_argument("--status", action="store_true", help="Print current updater status without checking Facebook.")
    parser.add_argument("--enrich-metadata", action="store_true", help="Backfill books, references, characters, topics, and testament fields locally.")
    parser.add_argument("--clean-archive", action="store_true", help="Remove recognized social-action blocks from the retained archive locally.")
    parser.add_argument("--curate-reader", action="store_true", help="Apply the Bible-study reader's requested content exclusions locally.")
    args = parser.parse_args()
    ensure_defaults()
    if args.status:
        print(json.dumps(read_json(STATUS_PATH, {}), indent=2, ensure_ascii=False))
    elif args.curate_reader:
        print(json.dumps(curate_reader_archive(), indent=2, ensure_ascii=False))
    elif args.enrich_metadata:
        print(json.dumps(enrich_archive_metadata(), indent=2, ensure_ascii=False))
    elif args.clean_archive:
        print(json.dumps(clean_archive_content(), indent=2, ensure_ascii=False))
    else:
        try:
            print(json.dumps(run_update(), indent=2, ensure_ascii=False))
        except Exception as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            raise SystemExit(1)
