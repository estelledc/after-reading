#!/usr/bin/env python3
"""Fetch weread shelf via Agent API Gateway, save to data/raw-shelf.json.

Reads WEREAD_API_KEY from env. Writes ./data/raw-shelf.json (utf-8, indent=2, sort_keys for stable diff).

Usage:
    WEREAD_API_KEY=wrk-xxx python scripts/fetch_weread.py
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request

API_URL = "https://i.weread.qq.com/api/agent/gateway"
SKILL_VERSION = "1.0.3"
OUTPUT_PATH = "data/raw-shelf.json"
MAX_RETRIES = 6
RETRY_DELAY_SEC = 3


def fetch_once(api_key: str, api_name: str) -> tuple[int, dict]:
    """Single POST. Returns (http_code, parsed_json)."""
    payload = json.dumps({
        "api_name": api_name,
        "skill_version": SKILL_VERSION,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"errcode": -1, "errmsg": str(e)}
        return e.code, body


def fetch_shelf(api_key: str) -> dict:
    """Retry around -202 (session warm-up): weread gateway sometimes rejects
    /shelf/sync first few times before binding session.

    Success: HTTP 200 + body has no errcode field (data shape: mp/albums/books/archive).
    Failure: HTTP 499 + body {errcode: -202, ...}.
    """
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        code, data = fetch_once(api_key, "/shelf/sync")
        errcode = data.get("errcode")
        # Success when 200 + payload has expected shape (books or albums or mp keys)
        if code == 200 and errcode is None and any(k in data for k in ("books", "albums", "mp")):
            print(f"OK on attempt {attempt}", file=sys.stderr)
            return data
        last_err = (code, errcode, data.get("errlog"))
        print(f"attempt {attempt}/{MAX_RETRIES}: HTTP {code} errcode={errcode}", file=sys.stderr)
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SEC)
    raise RuntimeError(f"shelf fetch failed after {MAX_RETRIES} retries; last: {last_err}")


def main() -> int:
    api_key = os.environ.get("WEREAD_API_KEY", "").strip()
    if not api_key:
        print("ERROR: WEREAD_API_KEY env var not set", file=sys.stderr)
        return 1

    try:
        data = fetch_shelf(api_key)
    except Exception as e:
        print(f"ERROR: weread fetch failed: {e}", file=sys.stderr)
        return 2

    errcode = data.get("errcode")
    if errcode is not None and errcode != 0:
        print(f"ERROR: weread returned errcode={errcode} errlog={data.get('errlog')}", file=sys.stderr)
        return 3

    books = data.get("books") or []
    finished = [b for b in books if b.get("finishReading") == 1]
    print(f"OK: {len(books)} total, {len(finished)} finished")

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
    print(f"WROTE: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
