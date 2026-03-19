"""
config.py – Central configuration
==================================
Edit the values in this file (or use a .env file) to configure the bot.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # loads from .env if present

# ── Required ──────────────────────────────────────────────────────────────────
# Get this from @BotFather on Telegram
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── Optional tweaks ───────────────────────────────────────────────────────────
# Path to the SQLite database file
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "birthday_bot.db")

# Hour (24h, UTC) at which the monthly reminder fires
REMINDER_HOUR: int = int(os.getenv("REMINDER_HOUR", "4"))   # 04:00 UTC

# How many days before month-end to send the reminder (default = 3)
REMINDER_DAYS_BEFORE_END: int = int(os.getenv("REMINDER_DAYS_BEFORE_END", "7"))