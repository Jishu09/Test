# 🎬 AutoCaptionBot Pro

A professional, production-ready Telegram **auto-caption bot** built on **Pyrofork**. It watches the channels you connect it to, reads each uploaded file's name, detects season/episode/quality/language/year, and rewrites the caption using a template you control — per channel. Everything is backed by MongoDB, so it survives restarts and scales across many channels.

---

## ✨ Features (40+)

**Auto-Captioning**
1. Auto-detects **Season / Episode** (`S01E02`, `1x02`, `Season 1 Episode 2`, etc.)
2. Auto-detects **Quality** (`480p`–`4K`)
3. Auto-detects **Language** (`Bangla`, `Hindi`, `Multi-Audio`, etc.)
4. Auto-detects **Year**, **Source** (`WEB-DL`, `BluRay`, ...), and clean **Title**
5. **Smart fallback** — if a field is missing from the filename, the bot reuses the last successfully-detected value for that channel (great for batch uploads where only the first file has full info)
6. Per-channel **custom regex** overrides (`/setregex`) for niche naming schemes
7. File-size and duration auto-inserted into captions
8. Duplicate-file detection (won't re-caption the same file twice)
9. Media type filter — choose exactly which types get auto-captioned (video/document/audio/animation/photo)
10. Auto-caption ON/OFF toggle per channel

**Caption & Thumbnail Management**
11. Set caption **from inside the channel** with `/setcaption`
12. **Fully button-driven PM control panel** (`/channels`) — no commands needed, everything is tap-to-configure
13. Connect a channel by simply **forwarding a message from it** — the bot verifies it's an admin there *and* that you're an admin there too before connecting
14. View current template, reset to default
15. Per-channel custom **thumbnail** (`/setthumb`, `/delthumb`) — applied automatically to new posts
16. 20+ caption placeholders across video/audio/photo/document fillings: `{filename}` `{filesize}` `{duration}` `{height}` `{width}` `{resolution}` `{ext}` `{mime_type}` `{title}` `{artist}` `{caption}` `{html_caption}` `{season}` `{episode}` `{quality}` `{language}` `{year}` `{source}` `{wish}` `{channel}`
17. **Caption Font** styles — Normal / Bold / Italic / Monospace / Underline
18. **Caption Reversal** toggle — reverse the rendered caption's line order
19. **Media Details** toggle — auto-append resolution/duration/size/mime-type block
20. Custom **inline button** on every captioned post (`[Text][buttonurl:https://...]` format, multi-row/multi-column supported)
21. **Remove Text / Replace Text** word lists — clean up source captions before templating
22. **Prefix / Suffix** — text automatically added above/below every caption
23. **Custom stickers** — auto-sent alongside every captioned file
24. Every menu has consistent **Back / Cancel** buttons — you can never get stuck

**Force-Subscribe**
25. **Multi-channel** force-subscribe
26. Classic "subscribe" mode (checks membership)
27. **Join-request mode** — for private channels, auto-approves join requests and verifies via request history
28. "Try Again" recheck button
29. Sudo/owner bypass

**Broadcast**
30. Private broadcast to every bot user (`/broadcast`)
31. Channel broadcast to every connected channel (`/cbroadcast`)
32. FloodWait-safe sending with live progress + auto-cleanup of blocked/deleted accounts

**Admin & Database**
33. Full **MongoDB** (Motor async driver) backend
34. Live stats: users, channels, force-sub count, DB storage size, uptime (`/stats`)
35. Ban / unban system
36. Maintenance mode
37. Sudo-user management (`/addsudo`, `/delsudo`)
38. Hot restart (`/restart`)
39. Log channel integration (new channel connects, errors, startup)

**UI / UX**
40. **Colored inline buttons** (Bot API 9.4 `style`: primary/success/danger) instead of emoji-coded buttons, with automatic safe fallback on older library builds
41. Clean paginated Help menu
42. English / Bangla interface toggle (`/lang`)
43. `/ping` latency + uptime check
44. Auto-registers a channel the moment the bot is promoted to admin there
45. Auto-unregisters a channel if the bot is removed/demoted
46. **Duplicate parity** — every PM button-flow also has a matching in-channel command, so admins never need to connect via PM at all if they don't want to

**Deployment**
47. Ready-to-go configs for **VPS, Docker, Heroku, Render, Railway, and Koyeb**
48. Built-in lightweight health-check HTTP server (keeps PaaS platforms happy)
49. `.env`-based configuration, nothing hardcoded

---

## 📁 Project Structure

```
AutoCaptionBotPro/
├── bot/
│   ├── config.py          # Env-based configuration
│   ├── database.py        # MongoDB (Motor) data layer
│   ├── caption_engine.py  # Filename parsing + caption building
│   └── state.py           # In-memory PM conversation state
├── plugins/
│   ├── guard.py             # Ban / maintenance-mode guard
│   ├── fsub.py               # Force-subscribe (subscribe + join-request modes)
│   ├── start.py               # /start /help /about /ping + channel auto-register
│   ├── lang.py                 # Language toggle
│   ├── settings.py             # In-channel setup commands (full command parity)
│   ├── channel_manager.py     # Button-driven PM control panel (/channels)
│   ├── caption_channel.py      # The auto-caption engine itself
│   ├── broadcast.py           # /broadcast /cbroadcast
│   └── admin.py                # /stats /ban /unban /maintenance /restart /addsudo ...
├── utils/
│   ├── buttons.py          # Colored inline-button helpers
│   └── helpers.py
├── main.py                 # Entrypoint
├── requirements.txt
├── Dockerfile / docker-compose.yml
├── Procfile / app.json / runtime.txt / .python-version   (Heroku)
├── render.yaml             (Render)
├── railway.toml            (Railway)
├── koyeb.yaml              (Koyeb)
├── .env.example
└── start.sh
```

---

## ⚙️ Required Environment Variables

| Variable | Description |
|---|---|
| `API_ID` / `API_HASH` | From [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `MONGO_URI` | MongoDB connection string ([Atlas free tier](https://mongodb.com/cloud/atlas) works fine) |
| `DB_NAME` | Database name (default `AutoCaptionBotPro`) |
| `OWNER_ID` | Your numeric Telegram user ID |
| `SUDO_USERS` | Space-separated extra admin IDs (optional) |
| `LOG_CHANNEL` | Channel ID for bot logs, bot must be admin (optional) |
| `FSUB_CHANNELS` | Comma-separated force-sub channel IDs (optional, can also be added via `/addfsub`) |
| `FSUB_JOIN_REQUEST` | `True`/`False` (optional) |
| `DEFAULT_CAPTION` | Default caption template (optional) |
| `PORT` | Health-check server port (default `8080`) |

Copy `.env.example` to `.env` and fill in your values.

---

## 🚀 Deploy Guide

### 1. VPS / Local
```bash
git clone <your-repo-or-unzip-this-folder>
cd AutoCaptionBotPro
cp .env.example .env      # fill in your values
pip install -r requirements.txt
python3 main.py
```
For a persistent process, use `screen`, `tmux`, or a `systemd` service / `pm2`.

### 2. Docker
```bash
cp .env.example .env
docker compose up -d --build
```
This also spins up a local MongoDB container. If you're using MongoDB Atlas instead, delete the `mongo` service from `docker-compose.yml` and just point `MONGO_URI` at Atlas.

Or with plain Docker (no compose):
```bash
docker build -t autocaptionbotpro .
docker run -d --env-file .env -p 8080:8080 --name autocaptionbot autocaptionbotpro
```

### 3. Heroku
1. Create a new Heroku app.
2. Connect this repo (or use `heroku git:remote`) and push — `app.json` + `Procfile` + `.python-version` are already set up for the **worker** dyno.
3. Set the config vars listed above under **Settings → Config Vars**.
4. Scale the worker on: `heroku ps:scale worker=1`.

### 4. Render
1. New → **Background Worker** → connect this repo.
2. Render auto-detects `render.yaml`. Fill in the marked env vars in the dashboard.
3. Deploy.

### 5. Railway
1. New Project → Deploy from repo.
2. Railway auto-detects `railway.toml` (Nixpacks build).
3. Add the environment variables in the **Variables** tab.
4. Deploy — Railway will run `python3 main.py`.

### 6. Koyeb
1. Create App → Docker deployment → point at this repo (Dockerfile is auto-detected).
2. Set **Service type** to `Worker` (no public port needed, though the built-in health server will still bind `$PORT` if Koyeb provides one).
3. Add environment variables from the table above.
4. Deploy.

---

## 🧭 Quick Start (after deploying)

1. Add the bot to your channel as **admin** (needs: post/edit messages, invite users, if using join-request mode also needs "Add Users").
2. DM the bot and send `/channels` → tap **➕ Add Channel** → forward any message from that channel into the chat. The bot checks that it's admin there *and* that you're admin there too, then connects it automatically.
   - Or skip PM entirely: send `/connect` directly inside the channel.
3. From the channel's settings panel, tap **✏️ Caption** → **➕ Add Caption** and send your template, e.g. `{title} S{season}E{episode} [{quality}] [{language}]`
4. Upload a video — the bot rewrites its caption automatically.
5. Explore **Button**, **Words**, **Stickers**, **Prefix/Suffix**, **Caption Font**, **Caption Reversal** and **Media Details** from the same panel — every screen has Back/Cancel buttons.
6. (Optional, sudo) `/addfsub -100xxxxxxxxxx request` to force users to join a private channel via join-request before other bot features apply to them.

---

## 🎨 Colored Buttons

All inline buttons use Telegram Bot API 9.4's native `style` field (`primary` = blue, `success` = green, `danger` = red) instead of emoji-coded buttons, via `utils/buttons.py`. If your installed Pyrofork build doesn't yet support the `style` kwarg, the helper automatically falls back to a plain button — no crashes either way.

---

## 🛠 Tech Stack

- **Pyrofork** — Telegram MTProto client (Pyrogram fork with faster updates)
- **Motor** — Async MongoDB driver
- **aiohttp** — Lightweight health-check server for PaaS platforms
- **Python 3.11**
