#!/usr/bin/env python3
"""Sends scheduled posts to a Telegram channel, looping forever.

Reads posts.json from the repo root. Posts go out one at a time, one per
run, starting at start_time and repeating every interval_minutes. When the
last post in the list has been sent, the schedule automatically continues
again from post #1, cycling through the list forever (1 -> 2 -> ... ->
last -> 1 -> 2 -> ...).

The script is meant to be run every ~30 minutes by GitHub Actions. On each
run it works out whether a new posting slot is due and, if so, sends the
next post in the never-ending cycle. The cycle position is remembered in
.state/cycle.json (committed back to the repo by the workflow) so posting
picks up exactly where it left off across runs and across days.

Special start times:
  * Today only, posting starts at 16:10 UTC (5:10 PM Nigeria time, UTC+1).
  * From tomorrow onward, posting starts every day at start_time from
    posts.json (09:00 UTC).

Environment variables:
  BOT_TOKEN        Telegram bot token from @BotFather (required)
  CHANNEL_ID       @channelusername or -100xxxxxxxxxx id (required)
  TEST_POST_INDEX  If set (1-based), sends that post immediately and
                   exits, ignoring the schedule. For testing only.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
CONFIG_FILE = ROOT / "posts.json"
STATE_DIR = ROOT / ".state"
STATE_FILE = STATE_DIR / "cycle.json"

# Today only, the first post of the day starts at this time (interpreted in
# the configured timezone, which is UTC). 16:30 UTC == 5:30 PM Nigeria time
# (UTC+1) and lands exactly on a */30 cron tick. Every other day uses
# start_time from posts.json.
FIRST_DAY = date(2026, 7, 2)
FIRST_DAY_START = "16:30"


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
    except urllib.error.URLError as err:
        raise SystemExit(
            f"Could not reach Telegram API for {method}: {err.reason}\n"
            "Check your network connection and try again."
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


def load_state() -> dict:
    """Return the persistent cycle state, tolerating a missing/corrupt file."""
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return {
                "next_index": int(data.get("next_index", 0)),
                "date": str(data.get("date", "")),
                "slots_today": int(data.get("slots_today", 0)),
            }
        except (ValueError, OSError):
            pass
    return {"next_index": 0, "date": "", "slots_today": 0}


def start_time_for(now: datetime, config: dict) -> datetime:
    """Return the datetime at which posting starts on now's date."""
    if now.date() == FIRST_DAY:
        start_str = FIRST_DAY_START
    else:
        start_str = config.get("start_time", "09:00")
    # Accept "HH:MM" (and tolerate a stray ":SS" if present).
    parts = start_str.split(":")
    hour, minute = int(parts[0]), int(parts[1])
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


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
    interval_min = int(config.get("interval_minutes", 30))
    start = start_time_for(now, config)

    state = load_state()
    today = now.date().isoformat()
    if state["date"] != today:
        # A new day: the daily slot counter resets, but next_index carries
        # over so the cycle keeps advancing across days without repeating a
        # slot or ever stopping.
        state["date"] = today
        state["slots_today"] = 0

    if now < start:
        print(f"Before today's start ({start:%H:%M %Z}); nothing due yet.")
        return

    # How many posting slots have opened today, counting the one at `start`.
    elapsed = (now - start).total_seconds()
    slots_due_today = int(elapsed // (interval_min * 60)) + 1

    if slots_due_today <= state["slots_today"]:
        print(
            f"Nothing due at {now:%Y-%m-%d %H:%M %Z}. "
            f"{state['slots_today']} post(s) already sent today."
        )
        return

    # Send exactly one post per run, so a missed run never floods the
    # channel with catch-up posts and the cadence stays ~one per interval.
    n = len(posts)
    idx = state["next_index"] % n
    print(f"Sending post #{idx + 1} of {n} (cycle position {state['next_index'] + 1})...")
    send_post(token, chat_id, posts[idx])

    state["next_index"] += 1
    state["slots_today"] += 1
    STATE_DIR.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(state), encoding="utf-8")

    next_up = state["next_index"] % n + 1
    print(f"Post #{idx + 1} sent. {state['slots_today']} sent today; next up is post #{next_up}.")


if __name__ == "__main__":
    main()
