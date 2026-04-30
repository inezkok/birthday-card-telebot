# 🎂 Birthday Wishes Bot

A Telegram bot that collects birthday wishes from your group and compiles them into a beautiful HTML card — automatically, every month.

---

## Table of Contents

1. [Features](#features)
2. [How It Works](#how-it-works)
3. [Project Structure](#project-structure)
4. [Setup Guide](#setup-guide)
5. [Configuration](#configuration)
6. [Commands Reference](#commands-reference)
7. [Running the Bot 24/7 (Free Options)](#running-the-bot-247-free-options)
8. [Handover Guide for Non-Programmers](#handover-guide-for-non-programmers)
9. [Troubleshooting](#troubleshooting)

---

## Features

- **Monthly birthday reminders** — 7 days before month-end, everyone gets a Telegram message asking them to write wishes for next month's birthday people
- **Wish collection** — interactive `/write` flow; people pick the birthday baby and type their message
- **Beautiful birthday cards** — generated as self-contained HTML files with confetti animation, dark theme, and all collected wishes
- **Admin tools** — bump stragglers, collate cards, manage users
- **Lightweight SQLite database** — no external DB server needed
- **Configurable** — all key settings live in a single `.env` file
- **Robust error handling** — the bot never crashes; all errors are logged and users receive helpful feedback
- **Production-ready** — comprehensive error recovery for database, API, and file system issues

---

## How It Works

Example Scenario:

**Users**: 
- 

```
7th-last day of current Month (e.g. March)  →  Bot reminds everyone to write for next month's birthdays (i.e. April)
                          (e.g. Charlie & Daniel both have April birthdays)
                          (Charlie & Daniel can write for each other,
                           but not for themselves)

Anyone runs /write     →  Pick the birthday person → Type message → Confirm

Admin runs /collate    →  Pick birthday person → Bot generates & sends HTML card

Admin runs /bump       →  Bot DMs anyone who hasn't written yet
```

---

## Project Structure

```
birthday-card-telebot/
├── bot.py                  # Entry point — run this to start the bot
├── config.py               # Reads settings from environment / .env
├── database.py             # All SQLite operations (with error handling)
├── scheduler.py            # APScheduler — fires monthly reminders (fault-tolerant)
├── seed_admin.py           # One-time setup: create the first admin user
├── requirements.txt        # Python dependencies
├── .env.example            # Template for your secrets
├── ERROR_HANDLING.md       # Comprehensive error handling documentation
├── .gitignore
│
├── handlers/
│   ├── user_handlers.py        # /start, /help (with error recovery)
│   ├── admin_handlers.py       # /bump, /clear (graceful error handling)
│   └── conversation_handlers.py # /write, /collate, /admin, /adduser, /removeuser (state-safe)
│
└── utils/
    ├── auth.py             # @admin_only / @registered_only decorators
    ├── card_generator.py   # Builds the HTML birthday card (defensive programming)
    ├── date_utils.py       # Month helpers
    └── error_handler.py    # Centralized error handling & user feedback utilities
```

**Key design principles:** 
- Each file has one clear responsibility — you'll always know where to look
- All errors are caught, logged, and handled gracefully — the bot never crashes
- Users see helpful, non-technical error messages
- For detailed error handling info, see [ERROR_HANDLING.md](ERROR_HANDLING.md)

---

## Setup Guide

### Step 1 — Create a Telegram Bot

1. Open Telegram and search for **@BotFather**
2. Send `/newbot` and follow the prompts
3. Copy the **token** it gives you (looks like `123456789:ABCdef...`)

### Step 2 — Get Python 3.11+

Check your version:
```bash
python3 --version
```
If it's below 3.11, download from https://python.org

### Step 3 — Download the bot code

```bash
git clone <your-repo-url> birthday-card-telebot
cd birthday-card-telebot
```

Or just copy the folder to your machine / server.

### Step 4 — Install dependencies

```bash
# Create a virtual environment (keeps things tidy)
python3 -m venv .venv
source .venv/bin/activate     # On Windows: .venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

**Note:** If you want to deactivate your virtual environment, just run the following command.

```bash
deactivate
```

### Step 5 — Create your `.env` file

```bash
cp .env.example .env
```

Open `.env` in any text editor and paste your bot token (for example):
```
BOT_TOKEN=123456789:ABCdefGHIjklMNO...
```

### Step 6 — Create the first admin user

```bash
python seed_admin.py
```

This will ask for your Telegram numeric ID (get it from @userinfobot), your name, handle, and birthday. It registers you as an admin in the database.

### Step 7 — Start the bot

```bash
python bot.py
```

You should see:
```
2025-01-01 09:00:00 | INFO     | __main__ | Database initialised.
2025-01-01 09:00:00 | INFO     | scheduler | Scheduler started — reminder fires daily at 04:00 UTC, active on the 7-days-before-end-of-month trigger.
2025-01-01 09:00:00 | INFO     | __main__ | Scheduler set up.
2025-01-01 09:00:00 | INFO     | __main__ | Bot is polling…
2025-01-01 09:00:00 | INFO     | telegram.ext.Application | Application started
```

Open Telegram, find your bot, and send `/start`.

---

## Configuration

All settings can be changed in `.env`:

| Variable | Default | Description |
|---|---|---|
| `BOT_TOKEN` | *(required)* | From @BotFather |
| `DATABASE_PATH` | `birthday_bot.db` | Where to store the SQLite file |
| `REMINDER_HOUR` | `4` | UTC hour for the daily scheduler check |
| `REMINDER_DAYS_BEFORE_END` | `7` | Days before month-end to send reminder |

---

## Commands Reference

### Everyone can use:

| Command | What it does |
|---|---|
| `/start` | Check in with the bot; completes registration if pending |
| `/help` | Show available commands |
| `/write` | Write a birthday wish for someone (interactive menu) |
| `/cancel` | Cancel any in-progress flow |

### Admin-only:

| Command | What it does |
|---|---|
| `/bump` | DM everyone who hasn't written wishes yet |
| `/collate` | Generate an HTML birthday card and send it to you |
| `/clear` | Delete wishes from previous months (keeps DB tidy) |
| `/admin` | Change another user's role (admin ↔ normal) |
| `/adduser` | Add a new person to the database |
| `/removeuser` | Remove a person and all their wishes |

### Adding a user (the flow)

1. Admin runs `/adduser` and fills in their name, handle, birthday, role
2. Bot tells the admin to ask that person to send `/start`
3. When they send `/start`, the bot recognises their Telegram handle, links their ID, and they're fully registered
4. They can now use `/write` and receive reminders

---

## Running the Bot 24/7 (Free Options)

You need the bot running constantly so it can receive messages and fire the monthly reminder. Here are the best **free** options:

---

### Option A — Railway.app ⭐ (Recommended for beginners)

**Why:** Generous free tier, extremely simple deploy, no credit card for basic use.

1. Create a free account at https://railway.app
2. Click **New Project → Deploy from GitHub repo**
3. Connect your GitHub account and select your bot repo
4. In the Railway dashboard → **Variables**, add:
   - `BOT_TOKEN` = your token
5. Railway auto-detects Python. Make sure you have a `Procfile`:

Create a file called `Procfile` (no extension) with:
```
worker: python bot.py
```

6. Deploy. Railway will keep the bot running 24/7.
7. The SQLite database persists on Railway's disk between deploys.

**Free tier:** 5 USD/month of usage included free — more than enough for a small bot.

---

### Option B — Render.com

1. Sign up at https://render.com
2. Create a **New Background Worker** (not a Web Service)
3. Connect your GitHub repo
4. Set the start command to: `python bot.py`
5. Add environment variable `BOT_TOKEN`
6. Deploy

**Note:** Render's free tier spins down after inactivity, which can cause missed reminders. Use the "Background Worker" type, not "Web Service", to avoid this.

---

### Option C — Oracle Cloud Free Tier (Most reliable, slightly technical)

Oracle gives you a **permanently free** small VM (1 OCPU, 1 GB RAM) — enough for this bot forever.

1. Sign up at https://cloud.oracle.com (requires a credit card for verification, but the free tier is genuinely free)
2. Create an **Always Free** Compute instance (choose Ubuntu 22.04)
3. SSH into the server
4. Run the setup commands:

```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv git
git clone <your-repo> birthday-card-telebot
cd birthday-card-telebot
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
nano .env   # paste your BOT_TOKEN
python seed_admin.py
```

5. Keep it running with **systemd**. Create `/etc/systemd/system/birthdaybot.service`:

```ini
[Unit]
Description=Birthday Wishes Telegram Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/birthday-card-telebot
ExecStart=/home/ubuntu/birthday-card-telebot/.venv/bin/python bot.py
Restart=always
RestartSec=10
EnvironmentFile=/home/ubuntu/birthday-card-telebot/.env

[Install]
WantedBy=multi-user.target
```

Then enable it:
```bash
sudo systemctl daemon-reload
sudo systemctl enable birthdaybot
sudo systemctl start birthdaybot
sudo systemctl status birthdaybot   # should say "active (running)"
```

The bot will now auto-start on reboot and restart if it crashes.

Note: The bot is designed to handle errors gracefully and continue running. If it does stop, systemd will automatically restart it.

---

### Option D — Fly.io

```bash
# Install flyctl: https://fly.io/docs/hands-on/install-flyctl/
fly auth signup
fly launch   # follow prompts
fly secrets set BOT_TOKEN=your_token_here
fly deploy
```

Fly.io's free tier includes 3 small VMs — plenty for one bot.

---

## Handover Guide for Non-Programmers

If you're taking over this bot and have never coded before, here's all you need to know:

### Starting the bot

```bash
cd birthday-card-telebot
source .venv/bin/activate
python bot.py
```

Leave this terminal window open. The bot runs as long as the window is open. On a server (Railway/Oracle), it runs automatically.

### Stopping the bot

Press `Ctrl + C` in the terminal.

### Checking logs

Logs are saved to `bot.log` in the project folder. Open it with any text editor.

### If the bot stops responding

1. Check `bot.log` for error messages
2. Restart with `python bot.py`
3. If you get "Module not found" errors: run `pip install -r requirements.txt` first

### Changing the bot token

Open `.env` and replace the `BOT_TOKEN` line with the new token.

### Backing up the database

Just copy `birthday_bot.db` to a safe place. That single file contains everything.

### Common questions

**"A new person joined the team — how do I add them?"**
Run `/adduser` in the bot (admin only). Fill in their details. Ask them to message the bot and send `/start`.

**"Someone left — how do I remove them?"**
Run `/removeuser` in the bot (admin only).

**"The reminder didn't fire this month!"**
Check that the bot was actually running on the 3rd-last day of the month. Also check `bot.log` for any errors around that date.

**"Someone wants to update their wish after submitting"**
Tell them to run `/write` again — submitting again will overwrite their previous wish.

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` in your activated venv |
| `Invalid token` | Double-check `BOT_TOKEN` in your `.env` file |
| Bot doesn't respond | Make sure `python bot.py` is running; check `bot.log` for errors |
| User can't use `/write` | They haven't been added via `/adduser` + sent `/start` |
| Reminder never fires | Confirm the bot was running on the trigger day; check `REMINDER_HOUR` is UTC |
| Card shows "No wishes yet" | Nobody has submitted wishes yet; use `/bump` to remind them |
| Error messages in bot | Check `bot.log` for details; these are logged but non-fatal |
| Database errors | The bot automatically handles these; see [ERROR_HANDLING.md](ERROR_HANDLING.md) for recovery info |

---

---

## Error Handling & Reliability

This bot is built with production-grade error handling:

- **Never crashes** — All errors are caught and logged
- **User feedback** — People see helpful error messages (no Python tracebacks)
- **Automatic recovery** — Database errors are rolled back automatically; failed reminders don't stop other operations
- **Comprehensive logging** — All issues are logged to `bot.log` with full context for debugging

For detailed information about error handling, recovery strategies, and monitoring, see [ERROR_HANDLING.md](ERROR_HANDLING.md).

---

*Made with 💜 — feel free to customise the card design in `utils/card_generator.py`*
