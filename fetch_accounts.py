#!/usr/bin/env python3
"""
Fetch the last N posts for X/Twitter company profiles.

Usage:
    python fetch_accounts.py                         # interactive: paste profile URLs
    python fetch_accounts.py --url https://x.com/OpenAI
    python fetch_accounts.py --file accounts.txt
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from twitter_utils import (
    create_client,
    filter_by_min_likes,
    parse_profile_input,
    prompt_for_profiles,
    prompt_min_likes,
    tweet_to_dict,
)

ACCOUNTS_FILE = Path(__file__).parent / "accounts.txt"
OUTPUT_JSON = Path(__file__).parent / "accounts_posts.json"
OUTPUT_CSV = Path(__file__).parent / "accounts_posts.csv"
OUTPUT_SUMMARY = Path(__file__).parent / "accounts_patterns.json"

TWITTER_DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"


def load_accounts(path: Path) -> list[str]:
    if not path.exists():
        return []

    accounts: list[str] = []
    for line in path.read_text().splitlines():
        handle, error = parse_profile_input(line)
        if error and line.strip() and not line.strip().startswith("#"):
            print(f"Skipping line: {error}", file=sys.stderr)
        elif handle:
            accounts.append(handle)
    return accounts


def parse_accounts_from_args(values: list[str]) -> list[str]:
    accounts: list[str] = []
    for value in values:
        handle, error = parse_profile_input(value)
        if error:
            raise SystemExit(error)
        if handle not in accounts:
            accounts.append(handle)
    return accounts


def parse_tweet_date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, TWITTER_DATE_FORMAT)
    except ValueError:
        return None


def build_patterns(posts: list[dict]) -> dict:
    dated = []
    for post in posts:
        dt = parse_tweet_date(post.get("created_at", ""))
        if dt:
            dated.append((dt, post))

    dated.sort(key=lambda item: item[0], reverse=True)

    gaps_days: list[float] = []
    for i in range(len(dated) - 1):
        gap = (dated[i][0] - dated[i + 1][0]).total_seconds() / 86400
        gaps_days.append(round(gap, 2))

    weekday_counts = Counter(dt.strftime("%A") for dt, _ in dated)
    hour_counts = Counter(dt.hour for dt, _ in dated)

    likes = [p["likes"] for p in posts if isinstance(p.get("likes"), int)]
    reposts = [p["reposts"] for p in posts if isinstance(p.get("reposts"), int)]
    comments = [p["comments"] for p in posts if isinstance(p.get("comments"), int)]
    lengths = [len(p.get("content") or "") for p in posts]

    def avg(values: list[int | float]) -> float | None:
        return round(sum(values) / len(values), 2) if values else None

    return {
        "posts_fetched": len(posts),
        "date_range": {
            "newest": dated[0][0].isoformat() if dated else None,
            "oldest": dated[-1][0].isoformat() if dated else None,
        },
        "posting_cadence": {
            "avg_days_between_posts": avg(gaps_days),
            "median_days_between_posts": (
                sorted(gaps_days)[len(gaps_days) // 2] if gaps_days else None
            ),
        },
        "posting_by_weekday": dict(sorted(weekday_counts.items())),
        "posting_by_hour_utc": {str(k): v for k, v in sorted(hour_counts.items())},
        "engagement_averages": {
            "likes": avg(likes),
            "reposts": avg(reposts),
            "comments": avg(comments),
        },
        "content": {
            "avg_char_length": avg(lengths),
            "posts_with_media": sum(1 for p in posts if p.get("has_media")),
        },
    }


async def fetch_account_posts(
    client, screen_name: str, limit: int, min_likes: int = 0
) -> tuple[list[dict], int]:
    user = await client.get_user_by_screen_name(screen_name)
    collected: list[dict] = []
    scanned = 0
    batch_size = min(max(limit, 40), 40)
    result = await client.get_user_tweets(user.id, "Tweets", count=batch_size)

    while True:
        for tweet in result:
            if tweet is None:
                continue
            scanned += 1
            item = tweet_to_dict(tweet)
            item["account"] = screen_name
            item["account_name"] = user.name
            item["profile_url"] = f"https://x.com/{screen_name}"
            item["has_media"] = bool(getattr(tweet, "media", None))

            if min_likes > 0 and item["likes"] < min_likes:
                continue

            collected.append(item)
            if len(collected) >= limit:
                return collected[:limit], scanned

        if not result.next_cursor:
            break
        result = await result.next()
        if not result:
            break

    return collected, scanned


async def fetch_all(
    accounts: list[str], limit: int, min_likes: int
) -> tuple[list[dict], dict]:
    client = await create_client()
    all_posts: list[dict] = []
    summaries: dict[str, dict] = {}

    for screen_name in accounts:
        filter_note = f", min likes {min_likes}" if min_likes > 0 else ""
        print(f"Fetching @{screen_name} (up to {limit} posts{filter_note})...")
        try:
            posts, scanned = await fetch_account_posts(
                client, screen_name, limit, min_likes
            )
            all_posts.extend(posts)
            summaries[screen_name] = {
                "account_name": posts[0]["account_name"] if posts else None,
                "profile_url": f"https://x.com/{screen_name}",
                "min_likes_filter": min_likes,
                "posts_scanned": scanned,
                "posts_matched": len(posts),
                "patterns": build_patterns(posts),
            }
            if min_likes > 0:
                print(f"  Got {len(posts)} posts with >= {min_likes} likes (scanned {scanned})")
            else:
                print(f"  Got {len(posts)} posts")
        except Exception as exc:
            summaries[screen_name] = {"error": str(exc)}
            print(f"  ERROR: {exc}", file=sys.stderr)
        await asyncio.sleep(2)

    return all_posts, summaries


def save_results(posts: list[dict], summaries: dict) -> None:
    payload = {"accounts": summaries, "posts": posts}
    OUTPUT_JSON.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    OUTPUT_SUMMARY.write_text(json.dumps(summaries, indent=2, ensure_ascii=False) + "\n")

    fieldnames = [
        "account",
        "account_name",
        "profile_url",
        "id",
        "url",
        "created_at",
        "content",
        "likes",
        "reposts",
        "comments",
        "views",
        "bookmarks",
        "has_media",
    ]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(posts)


def print_summary(summaries: dict) -> None:
    print("\n--- Pattern summary ---")
    for account, data in summaries.items():
        if "error" in data:
            print(f"@{account}: ERROR - {data['error']}")
            continue
        patterns = data["patterns"]
        cadence = patterns["posting_cadence"]["avg_days_between_posts"]
        engagement = patterns["engagement_averages"]
        print(
            f"@{account}: {patterns['posts_fetched']} posts matched | "
            f"avg gap {cadence} days | "
            f"avg likes {engagement['likes']} | "
            f"avg reposts {engagement['reposts']} | "
            f"avg comments {engagement['comments']}"
        )
        if data.get("min_likes_filter", 0) > 0:
            print(
                f"  (min likes {data['min_likes_filter']}, "
                f"scanned {data.get('posts_scanned', '?')} total posts)"
            )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch recent posts for X/Twitter company profiles."
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Enter profile URLs one by one in the terminal",
    )
    parser.add_argument(
        "--url",
        nargs="+",
        help="Profile URL(s), e.g. https://x.com/OpenAI",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help=f"Read profiles from a file (default: {ACCOUNTS_FILE.name} if it exists)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Max matching posts per profile (default: 50)",
    )
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

    accounts: list[str] = []
    if args.url:
        accounts = parse_accounts_from_args(args.url)
    elif args.interactive:
        accounts = prompt_for_profiles()
    elif args.file:
        accounts = load_accounts(args.file)
    elif ACCOUNTS_FILE.exists():
        accounts = load_accounts(ACCOUNTS_FILE)

    if not accounts:
        accounts = prompt_for_profiles()

    if not accounts:
        raise SystemExit("No profiles provided.")

    if args.min_likes is None and sys.stdin.isatty() and not args.url and not args.file:
        min_likes = prompt_min_likes(default_min_likes)

    if min_likes > 0:
        print(f"Filter: only posts with >= {min_likes} likes")

    print(f"\nProfiles to fetch: {', '.join(f'@{a}' for a in accounts)}")
    posts, summaries = await fetch_all(accounts, args.limit, min_likes)
    save_results(posts, summaries)
    print_summary(summaries)
    print(
        f"\nSaved {len(posts)} posts to {OUTPUT_JSON.name}, "
        f"{OUTPUT_CSV.name}, and patterns to {OUTPUT_SUMMARY.name}"
    )


if __name__ == "__main__":
    asyncio.run(main())
