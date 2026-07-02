#!/usr/bin/env python3
"""Interactive Telegram scheduler bot.

You (the owner) DM this bot a post — a photo with a caption, or just
text. The bot asks what time to post it. You reply with a daily time
like 14:30. From then on the bot posts it to your channel at that time
every single day, forever, until you delete it.

Commands (send these to the bot in DM):
  /start   - show help
  /list    - list your scheduled posts
  /delete  - delete a scheduled post
  /cancel  - cancel adding the current post

This bot must stay running (it listens for your DMs), so it needs a
small always-on host. See README-scheduler.md for hosting steps.

Environment variables:
  BOT_TOKEN   Telegram bot token from @BotFather (required)
  OWNER_ID    Your numeric Telegram user id (required; @userinfobot
              tells you yours). The bot ignores everyone else.
  CHANNEL_ID  @channelusername or -100xxxxxxxxxx (required)
  TIMEZONE    e.g. Africa/Lagos (optional, default UTC)
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

DATA_FILE = Path(__file__).resolve().parent / "scheduled_posts.json"

TOKEN = os.environ.get("BOT_TOKEN", "")
OWNER_ID = os.environ.get("OWNER_ID", "")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")
TZ = ZoneInfo(os.environ.get("TIMEZONE", "UTC"))

API = f"https://api.telegram.org/bot{TOKEN}"

HELP = (
    "Hi! I post to your channel on a daily schedule.\n\n"
    "To add a post: just send me the post here — a photo with a caption, "
    "or plain text. I'll ask what time to post it each day.\n\n"
    "Commands:\n"
    "/list - see your scheduled posts\n"
    "/delete - remove a scheduled post\n"
    "/cancel - cancel the post you're adding"
)


# --- Telegram API helpers -------------------------------------------------

def api(method: str, **params) -> dict:
    url = f"{API}/{method}"
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data)) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")
        print(f"API error on {method}: HTTP {err.code} {body}")
        try:
            return json.loads(body)
        except Exception:
            return {"ok": False}


def send(chat_id, text) -> dict:
    return api("sendMessage", chat_id=chat_id, text=text)


def deliver(post: dict, chat_id) -> dict:
    """Send a stored post to a chat (the channel, or a preview)."""
    if post.get("photo"):
        params = {"chat_id": chat_id, "photo": post["photo"]}
        if post.get("caption"):
            params["caption"] = post["caption"]
        return api("sendPhoto", **params)
    return api("sendMessage", chat_id=chat_id, text=post.get("text", ""))


# --- Storage --------------------------------------------------------------

def load() -> dict:
    if DATA_FILE.exists():
        return json.loads(DATA_FILE.read_text())
    return {"posts": [], "next_id": 1}


def save(state: dict) -> None:
    DATA_FILE.write_text(json.dumps(state, indent=2))


# In-memory per-chat conversation state: chat_id -> pending action.
pending = {}


# --- Message handling -----------------------------------------------------

def valid_time(s: str):
    s = s.strip()
    try:
        h, m = map(int, s.split(":"))
    except ValueError:
        return None
    if 0 <= h <= 23 and 0 <= m <= 59:
        return f"{h:02d}:{m:02d}"
    return None


def handle_message(msg: dict) -> None:
    chat_id = msg["chat"]["id"]
    user_id = str(msg.get("from", {}).get("id", ""))

    # Only the owner may talk to the bot.
    if OWNER_ID and user_id != OWNER_ID:
        send(chat_id, "Sorry, this is a private bot.")
        return

    text = (msg.get("text") or "").strip()

    # Commands.
    if text == "/start" or text == "/help":
        send(chat_id, HELP)
        return
    if text == "/cancel":
        pending.pop(chat_id, None)
        send(chat_id, "Cancelled.")
        return
    if text == "/list":
        state = load()
        if not state["posts"]:
            send(chat_id, "You have no scheduled posts yet. Send me a post to add one.")
        else:
            lines = ["Your scheduled posts (daily):"]
            for p in state["posts"]:
                kind = "photo" if p.get("photo") else "text"
                preview = (p.get("caption") or p.get("text") or "")[:40]
                lines.append(f"#{p['id']} at {p['time']} - {kind}: {preview}")
            send(chat_id, "\n".join(lines))
        return
    if text == "/delete":
        pending[chat_id] = {"action": "delete"}
        send(chat_id, "Send the number of the post to delete (see /list). Or /cancel.")
        return

    action = pending.get(chat_id)

    # Awaiting a delete id.
    if action and action.get("action") == "delete":
        try:
            del_id = int(text)
        except ValueError:
            send(chat_id, "Please send just the post number, e.g. 3. Or /cancel.")
            return
        state = load()
        before = len(state["posts"])
        state["posts"] = [p for p in state["posts"] if p["id"] != del_id]
        save(state)
        pending.pop(chat_id, None)
        send(chat_id, "Deleted." if len(state["posts"]) < before else f"No post #{del_id} found.")
        return

    # Awaiting a time for a post we just received.
    if action and action.get("action") == "await_time":
        t = valid_time(text)
        if not t:
            send(chat_id, "Please send a time in 24-hour HH:MM format, e.g. 09:00 or 18:30. Or /cancel.")
            return
        state = load()
        post = action["post"]
        post["id"] = state["next_id"]
        post["time"] = t
        state["next_id"] += 1
        state["posts"].append(post)
        save(state)
        pending.pop(chat_id, None)
        send(chat_id, f"Done! Post #{post['id']} will go out every day at {t} ({TZ.key}).")
        return

    # Otherwise: treat this message as a new post to schedule.
    post = {}
    if msg.get("photo"):
        # Largest available size is the last entry.
        post["photo"] = msg["photo"][-1]["file_id"]
        if msg.get("caption"):
            post["caption"] = msg["caption"]
    elif text:
        post["text"] = text
    else:
        send(chat_id, "Send me a photo with a caption, or some text, and I'll schedule it.")
        return

    pending[chat_id] = {"action": "await_time", "post": post}
    send(chat_id, "Got it. What time should I post this every day? Send a 24-hour time like 09:00 or 18:30.")


# --- Scheduler ------------------------------------------------------------

def check_schedule(last_minute: str) -> str:
    """Post anything due at the current minute. Returns the minute handled."""
    now = datetime.now(TZ)
    current = now.strftime("%H:%M")
    if current == last_minute:
        return last_minute  # already handled this minute
    state = load()
    for post in state["posts"]:
        if post.get("time") == current:
            print(f"Posting #{post['id']} at {current}")
            deliver(post, CHANNEL_ID)
    return current


# --- Main loop ------------------------------------------------------------

def main() -> None:
    missing = [n for n, v in [("BOT_TOKEN", TOKEN), ("OWNER_ID", OWNER_ID), ("CHANNEL_ID", CHANNEL_ID)] if not v]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")

    print(f"Bot starting. Timezone {TZ.key}. Channel {CHANNEL_ID}.")
    offset = 0
    last_minute = ""
    while True:
        # 1) Fetch new DMs (long poll, 10s).
        resp = api("getUpdates", offset=offset, timeout=10)
        for update in resp.get("result", []):
            offset = update["update_id"] + 1
            if "message" in update:
                try:
                    handle_message(update["message"])
                except Exception as exc:  # never let one bad message kill the bot
                    print(f"Error handling message: {exc}")

        # 2) Post anything due this minute.
        try:
            last_minute = check_schedule(last_minute)
        except Exception as exc:
            print(f"Error in scheduler: {exc}")

        time.sleep(1)


if __name__ == "__main__":
    main()
