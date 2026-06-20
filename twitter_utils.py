"""Shared helpers for X/Twitter scraping scripts."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

COOKIES_FILE = Path(__file__).parent / "cookies.json"


def parse_profile_input(value: str) -> tuple[str | None, str | None]:
    """
    Parse a profile URL, @handle, or plain handle.
    Returns (handle, error_message).
    """
    value = value.strip()
    if not value:
        return None, "Empty input."

    if re.search(r"/status/\d+", value, re.I):
        return None, (
            "That looks like a tweet URL, not a profile. "
            "Use fetch_posts.py for individual posts, or paste the company profile URL "
            "(e.g. https://x.com/OpenAI)."
        )

    match = re.search(r"(?:x\.com|twitter\.com)/(@?[^/?#]+)", value, re.I)
    if match:
        handle = match.group(1).lstrip("@")
        if handle.lower() in {"home", "search", "explore", "messages", "i"}:
            return None, f"'{handle}' is not a profile handle."
        return handle, None

    if value.startswith("@"):
        value = value[1:]

    if re.fullmatch(r"[A-Za-z0-9_]+", value):
        return value, None

    return None, "Could not parse input. Use a profile URL like https://x.com/CompanyName"


def parse_tweet_id(value: str) -> str | None:
    """Extract tweet ID from a URL or raw numeric ID."""
    value = value.strip()
    if not value:
        return None
    match = re.search(r"(\d{10,})", value)
    return match.group(1) if match else None


def tweet_to_dict(tweet) -> dict:
    username = tweet.user.screen_name if tweet.user else None
    return {
        "id": tweet.id,
        "url": (
            f"https://x.com/{username}/status/{tweet.id}"
            if username
            else f"https://x.com/i/status/{tweet.id}"
        ),
        "author": tweet.user.name if tweet.user else None,
        "username": username,
        "created_at": tweet.created_at,
        "content": tweet.text,
        "likes": tweet.favorite_count,
        "reposts": tweet.retweet_count,
        "comments": tweet.reply_count,
        "views": getattr(tweet, "view_count", None),
        "bookmarks": getattr(tweet, "bookmark_count", None),
    }


async def create_client():
    from twikit import Client

    client = Client("en-US")

    auth_token = os.environ.get("TWITTER_AUTH_TOKEN")
    ct0 = os.environ.get("TWITTER_CT0")

    if auth_token and ct0:
        client.set_cookies({"auth_token": auth_token, "ct0": ct0})
        return client

    if COOKIES_FILE.exists():
        client.load_cookies(str(COOKIES_FILE))
        return client

    username = os.environ.get("TWITTER_USERNAME")
    email = os.environ.get("TWITTER_EMAIL")
    password = os.environ.get("TWITTER_PASSWORD")

    if username and password:
        await client.login(
            auth_info_1=username,
            auth_info_2=email,
            password=password,
            cookies_file=str(COOKIES_FILE),
        )
        return client

    raise SystemExit(
        "Authentication required.\n\n"
        "Create a .env file with your browser cookies:\n"
        "  TWITTER_AUTH_TOKEN=...\n"
        "  TWITTER_CT0=...\n\n"
        "See README.md for step-by-step instructions."
    )


def filter_by_min_likes(posts: list[dict], min_likes: int) -> list[dict]:
    if min_likes <= 0:
        return posts
    return [
        post
        for post in posts
        if isinstance(post.get("likes"), int) and post["likes"] >= min_likes
    ]


def prompt_min_likes(default: int = 0) -> int:
    prompt = f"Minimum likes required (default {default}, 0 = no filter): "
    try:
        line = input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return default

    if not line:
        return default

    try:
        value = int(line)
    except ValueError:
        print(f"  Invalid number, using {default}.")
        return default

    if value < 0:
        print("  Minimum likes cannot be negative, using 0.")
        return 0

    return value


def prompt_for_profiles() -> list[str]:
    print("\nEnter company profile URLs one at a time.")
    print("Accepted formats:")
    print("  https://x.com/OpenAI")
    print("  https://twitter.com/OpenAI")
    print("  @OpenAI")
    print("  OpenAI")
    print("\nPress Enter on an empty line when you are done.\n")

    accounts: list[str] = []
    while True:
        try:
            line = input("Profile URL or handle: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if not line:
            if accounts:
                break
            print("Add at least one profile, or press Ctrl+C to quit.")
            continue

        handle, error = parse_profile_input(line)
        if error:
            print(f"  {error}")
            continue

        if handle in accounts:
            print(f"  @{handle} already added.")
            continue

        accounts.append(handle)
        print(f"  Added @{handle}")

    return accounts
