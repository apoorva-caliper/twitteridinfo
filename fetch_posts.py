#!/usr/bin/env python3
"""
Fetch tweet stats (content, likes, reposts, comments).

Usage:
    python fetch_posts.py --interactive          # paste tweet URLs one by one
    python fetch_posts.py --url https://x.com/user/status/123...
    python fetch_posts.py --ids 1234567890
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from twitter_utils import (
    create_client,
    filter_by_min_likes,
    parse_tweet_id,
    prompt_min_likes,
    tweet_to_dict,
)

TWEET_IDS_FILE = Path(__file__).parent / "tweet_ids.txt"
OUTPUT_JSON = Path(__file__).parent / "posts_output.json"
OUTPUT_CSV = Path(__file__).parent / "posts_output.csv"


def load_tweet_ids(path: Path) -> list[str]:
    if not path.exists():
        return []

    ids: list[str] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        tweet_id = parse_tweet_id(line)
        if tweet_id:
            ids.append(tweet_id)
        else:
            print(f"Skipping invalid line: {line}", file=sys.stderr)
    return ids


def prompt_for_tweet_ids() -> list[str]:
    print("\nEnter tweet URLs or IDs one at a time.")
    print("Example: https://x.com/user/status/1234567890123456789")
    print("Press Enter on an empty line when you are done.\n")

    ids: list[str] = []
    while True:
        try:
            line = input("Tweet URL or ID: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            if ids:
                break
            print("Add at least one tweet, or press Ctrl+C to quit.")
            continue

        tweet_id = parse_tweet_id(line)
        if not tweet_id:
            print("  Could not find a tweet ID. Paste the full post URL or numeric ID.")
            continue
        if tweet_id in ids:
            print(f"  {tweet_id} already added.")
            continue

        ids.append(tweet_id)
        print(f"  Added tweet {tweet_id}")

    return ids


async def fetch_tweets(ids: list[str]) -> list[dict]:
    client = await create_client()
    tweets = await client.get_tweets_by_ids(ids)

    results: list[dict] = []
    for tweet_id, tweet in zip(ids, tweets):
        if tweet is None:
            results.append({"id": tweet_id, "error": "Tweet not found or unavailable"})
        else:
            results.append(tweet_to_dict(tweet))
    return results


def save_results(results: list[dict]) -> None:
    OUTPUT_JSON.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")

    fieldnames = [
        "id",
        "url",
        "author",
        "username",
        "created_at",
        "content",
        "likes",
        "reposts",
        "comments",
        "views",
        "bookmarks",
        "error",
    ]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)


def print_results(results: list[dict]) -> None:
    for item in results:
        if "error" in item:
            print(f"[{item['id']}] ERROR: {item['error']}")
            continue
        print(f"[{item['id']}] @{item['username']}")
        print(f"  Likes: {item['likes']} | Reposts: {item['reposts']} | Comments: {item['comments']}")
        print(f"  {item['content'][:200]}{'...' if len(item['content']) > 200 else ''}")
        print()


async def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch stats for specific tweets.")
    parser.add_argument("--interactive", "-i", action="store_true", help="Enter tweet URLs in the terminal")
    parser.add_argument("--url", nargs="+", help="Tweet URL(s)")
    parser.add_argument("--ids", nargs="+", help="Tweet ID(s)")
    parser.add_argument("--file", type=Path, default=TWEET_IDS_FILE, help="File with tweet IDs/URLs")
    parser.add_argument(
        "--min-likes",
        type=int,
        default=None,
        help="Only include posts with at least this many likes (default: 0, or MIN_LIKES from .env)",
    )
    args = parser.parse_args()

    load_dotenv()

    default_min_likes = int(os.environ.get("MIN_LIKES", "0") or "0")
    min_likes = args.min_likes if args.min_likes is not None else default_min_likes
    if min_likes < 0:
        raise SystemExit("--min-likes must be 0 or greater.")

    ids: list[str] = []
    if args.ids:
        ids = [tid for tid in (parse_tweet_id(value) for value in args.ids) if tid]
    elif args.url:
        ids = [tid for tid in (parse_tweet_id(value) for value in args.url) if tid]
    elif args.interactive:
        ids = prompt_for_tweet_ids()
    else:
        ids = load_tweet_ids(args.file)

    if not ids:
        ids = prompt_for_tweet_ids()
    if not ids:
        raise SystemExit("No tweet IDs provided.")

    if args.min_likes is None and sys.stdin.isatty() and (args.interactive or not args.url and not args.ids):
        min_likes = prompt_min_likes(default_min_likes)

    print(f"\nFetching {len(ids)} tweet(s)...")
    results = await fetch_tweets(ids)
    matched = filter_by_min_likes(results, min_likes)
    skipped = len(results) - len(matched)

    if min_likes > 0:
        print(f"Filter: >= {min_likes} likes — {len(matched)} matched, {skipped} excluded")

    save_results(matched)
    print_results(matched)
    print(f"Saved: {OUTPUT_JSON.name}, {OUTPUT_CSV.name}")


if __name__ == "__main__":
    asyncio.run(main())
