#!/usr/bin/env python3
"""Sends scheduled daily posts to a Telegram channel.

Reads posts.json from the repo root. Each day, post #1 goes out at
start_time, post #2 goes out interval_minutes later, and so on. A
specific date can use a different start time via start_time_overrides
(see posts.json) without affecting any other day.

The script is meant to be run every ~30 minutes by GitHub Actions.
On each run it sends every post whose scheduled time has passed and
that hasn't been sent yet today (tracked in .state/<date>.json), so a
late or skipped run simply catches up on the next one.

Environment variables:
  BOT_TOKEN        Telegram bot token from @BotFather (required)
  CHANNEL_ID       @channelusername or -100xxxxxxxxxx id (required)
  TEST_POST_INDEX  If set (1-based), sends that post immediately and
                   exits, ignoring the schedule. For testing only.
"""

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "posts.json"
STATE_DIR = ROOT / ".state"
STATE_DAYS_TO_KEEP = 7


def telegram_api(token: str, method: str, payload: dict) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = urllib.parse.urlencode(payload).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data)) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")
        raise SystemExit(
            f"Telegram API error on {method}: HTTP {err.code}\n{body}\n"
            "Common causes: wrong BOT_TOKEN, wrong CHANNEL_ID, the bot is "
            "not an admin of the channel, or an image link that is not a "
            "direct link to the image file."
        )


def send_post(token: str, chat_id: str, post: dict) -> None:
    text = post.get("text", "")
    image = post.get("image")
    if image:
        payload = {"chat_id": chat_id, "photo": image}
        if text:
            payload["caption"] = text
        telegram_api(token, "sendPhoto", payload)
    else:
        telegram_api(token, "sendMessage", {"chat_id": chat_id, "text": text})


def cleanup_old_state(today: date) -> None:
    if not STATE_DIR.is_dir():
        return
    cutoff = (today - timedelta(days=STATE_DAYS_TO_KEEP)).isoformat()
    for f in STATE_DIR.glob("*.json"):
        if f.stem < cutoff:  # ISO dates compare correctly as strings
            f.unlink()


def main() -> None:
    token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("CHANNEL_ID")
    if not token or not chat_id:
        raise SystemExit(
            "BOT_TOKEN and CHANNEL_ID must be set. In GitHub, add them under "
            "Settings -> Secrets and variables -> Actions."
        )

    config = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    posts = config.get("posts", [])
    if not posts:
        print("posts.json has no posts; nothing to do.")
        return

    test_index = os.environ.get("TEST_POST_INDEX", "").strip()
    if test_index:
        i = int(test_index) - 1
        if not 0 <= i < len(posts):
            raise SystemExit(f"TEST_POST_INDEX must be between 1 and {len(posts)}.")
        print(f"TEST MODE: sending post #{i + 1} now.")
        send_post(token, chat_id, posts[i])
        print("Test post sent successfully.")
        return

    tz = ZoneInfo(config.get("timezone", "UTC"))
    now = datetime.now(tz)
    today = now.date().isoformat()

    # start_time_overrides lets a specific date use a different start time,
    # e.g. {"2026-07-02": "13:20"} for a one-off later start today. Any
    # date not listed (including tomorrow) just uses the normal start_time.
    overrides = config.get("start_time_overrides", {})
    todays_start_time = overrides.get(today, config.get("start_time", "09:00"))
    hour, minute = map(int, todays_start_time.split(":"))
    first_post_at = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    interval_min = int(config.get("interval_minutes", 30))

    state_file = STATE_DIR / f"{today}.json"
    posted = set(json.loads(state_file.read_text())) if state_file.exists() else set()

    due = [
        i
        for i in range(len(posts))
        if i not in posted
        and now.timestamp() >= first_post_at.timestamp() + i * interval_min * 60
    ]
    if not due:
        print(f"Nothing due at {now:%Y-%m-%d %H:%M %Z}. {len(posted)}/{len(posts)} sent today.")
        return

    STATE_DIR.mkdir(exist_ok=True)
    for i in due:
        print(f"Sending post #{i + 1} of {len(posts)}...")
        send_post(token, chat_id, posts[i])
        posted.add(i)
        # Save after every send so a failure mid-run never causes repeats.
        state_file.write_text(json.dumps(sorted(posted)))
        print(f"Post #{i + 1} sent.")

    cleanup_old_state(now.date())
    print(f"Done. {len(posted)}/{len(posts)} posts sent today.")


if __name__ == "__main__":
    main()
