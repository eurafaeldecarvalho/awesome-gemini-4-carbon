#!/usr/bin/env python3
"""Verify every X status in data/entries.yml against a public post API.

x.com pages block anonymous link checkers, so lychee skips them.
This script is the check that the post exists, the handle and UTC date
match, and the stored prompt is text the author actually published.
"""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_entries import load_entries, validate

UA = {"User-Agent": "awesome-gemini-4-carbon-linkcheck/1.0"}
STATUS = re.compile(r"/status/(\d+)$")


def _request(url: str) -> dict:
    last_error = "no attempt"
    for attempt in range(3):
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            time.sleep(0.6 * (attempt + 1))
    raise RuntimeError(last_error)


def _note_text(note: object) -> str:
    if isinstance(note, str):
        return note
    if not isinstance(note, dict):
        return ""
    chunks: list[str] = []
    for key in ("text", "note_tweet_results"):
        value = note.get(key)
        if isinstance(value, str):
            chunks.append(value)
        elif isinstance(value, dict):
            text = value.get("text")
            if isinstance(text, str):
                chunks.append(text)
            result = value.get("result")
            if isinstance(result, dict) and isinstance(result.get("text"), str):
                chunks.append(result["text"])
    return "\n".join(chunks)


def _date(value: str) -> str:
    value = value.strip()
    if "T" in value and value.endswith("Z"):
        return value[:10]
    parsed = datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
    return parsed.astimezone(timezone.utc).date().isoformat()


def _from_syndication(status_id: str) -> dict:
    payload = _request(
        f"https://cdn.syndication.twimg.com/tweet-result?id={status_id}&token=x"
    )
    user = payload.get("user") or {}
    text = html.unescape(
        "\n".join(
            part
            for part in (payload.get("text") or "", _note_text(payload.get("note_tweet")))
            if part
        )
    )
    return {
        "id": payload.get("id_str") or status_id,
        "handle": user.get("screen_name") or "",
        "text": text,
        "date": _date(payload["created_at"]),
    }


def _from_fxtwitter(status_id: str) -> dict:
    payload = _request(f"https://api.fxtwitter.com/status/{status_id}")
    tweet = payload["tweet"]
    author = tweet.get("author") or {}
    raw = (tweet.get("raw_text") or {}).get("text") or ""
    text = html.unescape("\n".join(part for part in (tweet.get("text") or "", raw) if part))
    return {
        "id": str(tweet.get("id") or status_id),
        "handle": author.get("screen_name") or "",
        "text": text,
        "date": _date(tweet["created_at"]),
    }


def fetch_status(url: str) -> dict:
    match = STATUS.search(url)
    if not match:
        raise RuntimeError(f"not a status URL: {url}")
    status_id = match.group(1)
    found = []
    errors = []
    for fetcher in (_from_syndication, _from_fxtwitter):
        try:
            tweet = fetcher(status_id)
            if tweet["id"] != status_id or not tweet["text"]:
                raise RuntimeError("empty or mismatched status")
            found.append(tweet)
        except Exception as exc:  # noqa: BLE001 - try the other public API
            errors.append(f"{fetcher.__name__}: {exc}")
    if not found:
        raise RuntimeError(f"{url} unreachable ({'; '.join(errors)})")
    # Syndication sometimes cuts a post at the t.co link. Keep every copy
    # so the prompt check sees the full text the author published.
    base = found[0]
    for extra in found[1:]:
        if extra["handle"].lower() != base["handle"].lower():
            raise RuntimeError(f"{url}: sources disagree on handle")
        if extra["date"] != base["date"]:
            raise RuntimeError(f"{url}: sources disagree on date")
        base["text"] = base["text"] + "\n" + extra["text"]
    return base


def _contains(haystack: str, needle: str) -> bool:
    folded = " ".join(haystack.split())
    return " ".join(needle.split()) in folded


def check(entries: list[dict]) -> None:
    cache: dict[str, dict] = {}

    def get(url: str) -> dict:
        if url not in cache:
            cache[url] = fetch_status(url)
            time.sleep(0.15)
        return cache[url]

    for entry in entries:
        eid = entry["id"]
        post = get(entry["post"])
        handle = entry["author"]["handle"]
        if post["handle"].lower() != handle.lower():
            raise SystemExit(f"{eid}: post handle is @{post['handle']}, expected @{handle}")
        if post["date"] != entry["date"]:
            raise SystemExit(f"{eid}: post date is {post['date']}, file says {entry['date']}")
        if not _contains(post["text"], entry["prompt"]):
            raise SystemExit(
                f"{eid}: prompt is not in the post text:\n{post['text'][:500]}"
            )
        comparison = entry.get("comparison")
        if comparison:
            other = get(comparison["url"])
            if other["handle"].lower() != comparison["handle"].lower():
                raise SystemExit(f"{eid}: comparison handle mismatch")
            if "Opus 5.5" not in other["text"]:
                raise SystemExit(f"{eid}: comparison post does not mention Opus 5.5")
            if not _contains(other["text"], entry["prompt"]):
                raise SystemExit(f"{eid}: comparison post does not contain the prompt")
        for credit in entry.get("credits") or []:
            blob = post["text"]
            if comparison:
                blob += "\n" + get(comparison["url"])["text"]
            if f"@{credit['handle']}" not in blob:
                raise SystemExit(f"{eid}: @{credit['handle']} is not credited on the post")
        for related in entry.get("related") or []:
            extra = get(related["url"])
            if extra["handle"].lower() != related["handle"].lower():
                raise SystemExit(f"{eid}: related handle mismatch for {related['url']}")
        print(f"ok {eid} @{handle} {entry['date']}")


def main() -> None:
    entries = load_entries()
    validate(entries)
    check(entries)


if __name__ == "__main__":
    try:
        main()
    except BrokenPipeError:
        sys.exit(0)
