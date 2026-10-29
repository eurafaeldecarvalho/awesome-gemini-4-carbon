#!/usr/bin/env python3
"""Check data/entries.yml shape: required fields, ISO dates, unique posts."""

from __future__ import annotations

import re
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
ENTRIES = ROOT / "data" / "entries.yml"

CATEGORIES = (
    "3d-threejs",
    "games",
    "simulations",
    "ui-svg",
    "agents",
    "failures",
)

REQUIRED = (
    "id",
    "title",
    "category",
    "featured",
    "author",
    "post",
    "date",
    "prompt",
    "note",
    "verified_on",
)

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
STATUS = re.compile(r"^https://x\.com/([A-Za-z0-9_]+)/status/(\d+)$")


def _as_iso(value: object) -> object:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value


def load_entries(path: Path = ENTRIES) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not data:
        raise SystemExit(f"{path}: expected a non-empty list")
    for entry in data:
        if isinstance(entry, dict):
            for key in ("date", "verified_on"):
                if key in entry:
                    entry[key] = _as_iso(entry[key])
    return data


def _author(entry: dict, label: str) -> tuple[str, str, str]:
    author = entry.get(label)
    if not isinstance(author, dict):
        raise SystemExit(f"{entry.get('id')}: {label} must be a mapping")
    name = author.get("name")
    handle = author.get("handle")
    url = author.get("url")
    if not all(isinstance(v, str) and v.strip() for v in (name, handle, url)):
        raise SystemExit(f"{entry.get('id')}: {label} needs name, handle, url")
    if url != f"https://x.com/{handle}":
        raise SystemExit(f"{entry.get('id')}: {label} url must be https://x.com/{handle}")
    return name, handle, url


def validate(entries: list[dict]) -> None:
    ids: set[str] = set()
    posts: set[str] = set()
    featured = 0
    for entry in entries:
        missing = [key for key in REQUIRED if key not in entry or entry[key] in ("", None)]
        if missing:
            raise SystemExit(f"{entry.get('id')}: missing {', '.join(missing)}")
        eid = entry["id"]
        if not re.fullmatch(r"[a-z0-9-]{3,60}", eid):
            raise SystemExit(f"{eid}: id must be lowercase words and hyphens")
        if eid in ids:
            raise SystemExit(f"duplicate id {eid}")
        ids.add(eid)
        if entry["category"] not in CATEGORIES:
            raise SystemExit(f"{eid}: unknown category {entry['category']}")
        if not isinstance(entry["featured"], int) or not 0 <= entry["featured"] <= 5:
            raise SystemExit(f"{eid}: featured must be an integer 0-5")
        if entry["featured"]:
            featured += 1
        for key in ("date", "verified_on"):
            if not isinstance(entry[key], str) or not ISO_DATE.match(entry[key]):
                raise SystemExit(f"{eid}: {key} must be YYYY-MM-DD")
        name, handle, _url = _author(entry, "author")
        post = entry["post"]
        match = STATUS.match(post)
        if not match or match.group(1) != handle:
            raise SystemExit(f"{eid}: post must be https://x.com/{handle}/status/<id>")
        if post in posts:
            raise SystemExit(f"{eid}: duplicate post URL {post}")
        posts.add(post)
        prompt = entry["prompt"]
        if not isinstance(prompt, str) or not prompt.strip():
            raise SystemExit(f"{eid}: empty prompt")
        if prompt.strip() != prompt:
            raise SystemExit(f"{eid}: prompt has leading or trailing whitespace")
        if "…" in prompt or prompt.rstrip().endswith("..."):
            raise SystemExit(f"{eid}: do not store a truncated prompt")
        note = entry["note"]
        if not isinstance(note, str) or len(note.strip()) < 12:
            raise SystemExit(f"{eid}: note must say how the prompt appears on the post")
        arena = entry.get("arena_label")
        if arena is not None and (not isinstance(arena, str) or not arena.strip()):
            raise SystemExit(f"{eid}: arena_label must be a non-empty string")
        comparison = entry.get("comparison")
        if comparison is not None:
            if not isinstance(comparison, dict):
                raise SystemExit(f"{eid}: comparison must be a mapping")
            url = comparison.get("url")
            chandle = comparison.get("handle")
            if not isinstance(url, str) or not STATUS.match(url):
                raise SystemExit(f"{eid}: comparison.url is not a status URL")
            if not isinstance(chandle, str) or STATUS.match(url).group(1) != chandle:
                raise SystemExit(f"{eid}: comparison handle does not match its URL")
        for credit in entry.get("credits") or []:
            _author({"id": eid, "author": credit}, "author")
        for related in entry.get("related") or []:
            if not isinstance(related, dict):
                raise SystemExit(f"{eid}: related items must be mappings")
            url = related.get("url")
            rhandle = related.get("handle")
            label = related.get("label")
            if not isinstance(url, str) or not STATUS.match(url):
                raise SystemExit(f"{eid}: related url is not a status URL")
            if STATUS.match(url).group(1) != rhandle:
                raise SystemExit(f"{eid}: related handle does not match its URL")
            if not isinstance(label, str) or not label.strip():
                raise SystemExit(f"{eid}: related label is required")
            if url == post:
                raise SystemExit(f"{eid}: related URL duplicates the post")
        if not isinstance(entry["title"], str) or not entry["title"].strip():
            raise SystemExit(f"{eid}: empty title")
        if not name:
            raise SystemExit(f"{eid}: empty author name")
    if featured < 3 or featured > 5:
        raise SystemExit(f"featured count must be 3-5, got {featured}")
    ranks = sorted(e["featured"] for e in entries if e["featured"])
    if ranks != list(range(1, len(ranks) + 1)):
        raise SystemExit(f"featured ranks must be 1..N without gaps, got {ranks}")


def main() -> None:
    validate(load_entries())
    print(f"ok {ENTRIES.relative_to(ROOT)} ({len(load_entries())} entries)")


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
