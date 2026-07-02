# Telegram Daily Channel Poster

A simple bot that automatically posts to your Telegram channel every day —
one post every 30 minutes (or whatever gap you choose), each with its own
text and banner image.

**No server or paid hosting needed.** GitHub Actions (built into this repo,
free) runs the bot on schedule for you.

---

## One-time setup (about 10 minutes)

### 1. Create your bot

1. In Telegram, open **@BotFather**.
2. Send `/newbot`, follow the prompts, and copy the **token** it gives you
   (looks like `123456789:AAH6k9...`). Keep it secret.

### 2. Make the bot an admin of your channel

1. Open your channel → channel name → **Administrators** → **Add Admin**.
2. Search for your bot's username and add it. It only needs the
   **Post messages** permission.

### 3. Get your channel ID

- **Public channel:** just use the handle, e.g. `@mychannel`.
- **Private channel:** forward any post from the channel to **@userinfobot**
  (or @getidsbot). It replies with an ID like `-1001234567890` — that whole
  number, including the minus sign, is your channel ID.

### 4. Add the two secrets to this repo

On GitHub: **Settings → Secrets and variables → Actions → New repository secret**

| Name | Value |
|------|-------|
| `BOT_TOKEN` | the token from BotFather |
| `CHANNEL_ID` | `@mychannel` or `-100...` from step 3 |

### 5. Upload your banners to imgbb

1. Go to [imgbb.com](https://imgbb.com) and upload each banner.
2. On the uploaded image page, open the **Embed codes** dropdown and pick
   **"Direct links"**. Copy the link — it must look like
   `https://i.ibb.co/AbCdEf/banner1.jpg` and end in `.jpg` or `.png`.

   ⚠️ The normal page link (`https://ibb.co/AbCdEf`, no `i.` in front)
   will NOT work — Telegram needs the direct image link.

### 6. Put your posts in `posts.json`

Edit `posts.json` in this repo. Example:

```json
{
  "timezone": "Africa/Lagos",
  "start_time": "09:00",
  "interval_minutes": 30,
  "posts": [
    { "text": "First post caption here", "image": "https://i.ibb.co/xxxx/banner1.jpg" },
    { "text": "Second post, 30 min later", "image": "https://i.ibb.co/xxxx/banner2.jpg" },
    { "text": "A text-only post also works" }
  ]
}
```

- `timezone` — your timezone (e.g. `Africa/Lagos`, `Europe/London`,
  `America/New_York`).
- `start_time` — when the FIRST post of the day goes out, in 24-hour time.
- `interval_minutes` — gap between posts (30 = every half hour).
- Add as many posts as you like; they go out in order, top to bottom,
  every single day.
- Captions on image posts can be up to **1024 characters** (Telegram limit).
  Text-only posts can be up to 4096.

---

## Test it

1. Go to the **Actions** tab → **Daily channel posts** → **Run workflow**.
2. Type `1` in the test box and click **Run workflow**.
3. Post #1 should appear in your channel within a minute. If it doesn't,
   open the run and read the log — the error message tells you what's wrong
   (usually a wrong secret, the bot not being admin, or a non-direct image link).

After that, it's fully automatic: every day at your `start_time`, the posts
go out one by one, 30 minutes apart.

> **Note:** the schedule only runs from the **main branch**, so make sure
> these files are merged into main. Also, GitHub's scheduler is not to the
> exact second — posts may land a few minutes after their slot time, which
> is normal.

---

## Changing your posts

Just edit `posts.json` (you can do it right on the GitHub website — open the
file, click the pencil icon, save). The next day's posts use the new content
automatically. The `.state/` folder is the bot's memory of what it already
sent today — you never need to touch it.
