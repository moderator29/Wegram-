# DM Scheduler Bot

DM the bot a post (photo + caption, or text). It asks what time to post
it. You reply with a daily time like `14:30`. From then on it posts that
to your channel at that time **every day, forever** — until you delete it.

This bot listens for your DMs, so unlike the GitHub Actions version it
needs to be **always running** on a small host. Setup is still easy.

---

## What you send the bot

- **A photo with a caption** → it posts the photo + caption daily.
- **Plain text** → it posts the text daily.
- The bot only listens to **you** (set by `OWNER_ID`), so no one else
  can control it.

Commands (send in the DM):
- `/start` – help
- `/list` – see all scheduled posts
- `/delete` – remove one (it asks for the number)
- `/cancel` – cancel the post you're currently adding

---

## Setup

### 1. Create the bot and get your details
- Message **@BotFather** → `/newbot` → copy the **token**.
- Message **@userinfobot** → it replies with your numeric **user id**
  (that's your `OWNER_ID`).
- Add the bot as an **admin** of your channel (Post messages permission).
- Your `CHANNEL_ID` is `@yourchannel` (public) or the `-100...` number
  (private – forward a channel post to @userinfobot to get it).

### 2. Pick a host (choose one)

**Option A — Railway (easiest, has a free tier):**
1. Go to [railway.app](https://railway.app), sign in with GitHub.
2. **New Project → Deploy from GitHub repo →** pick this repo.
3. In the service **Settings → Start Command**, enter:
   `python3 bot/scheduler_bot.py`
4. In **Variables**, add: `BOT_TOKEN`, `OWNER_ID`, `CHANNEL_ID`,
   `TIMEZONE` (e.g. `Africa/Lagos`).
5. Deploy. That's it — the bot is now live 24/7.

**Option B — Any cheap VPS (~$4/month, e.g. a small droplet):**
```bash
git clone <your repo url> && cd Wegram-
export BOT_TOKEN=... OWNER_ID=... CHANNEL_ID=@yourchannel TIMEZONE=Africa/Lagos
# keep it running after you log out:
nohup python3 bot/scheduler_bot.py > bot.log 2>&1 &
```
(For a permanent setup, run it as a `systemd` service so it restarts on
reboot — ask me and I'll write the service file.)

### 3. Use it
Open a DM with your bot, send `/start`, then send your first post. Reply
with a time when asked. Repeat for all your posts. Check `/list` anytime.

---

## Notes
- Times use the `TIMEZONE` you set. `/list` shows the timezone.
- The bot's memory of your posts lives in `bot/scheduled_posts.json` on
  the host. On Railway, add a **Volume** if you want it to survive
  redeploys; on a VPS it's just a file that persists automatically.
- Photos are stored by Telegram's `file_id`, so you don't need imgbb here
  — sending the image straight to the bot is enough.
- Requires **Python 3.9+** (uses the built-in `zoneinfo`). No extra
  packages to install.
