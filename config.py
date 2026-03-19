"""
Loads up configurations from .env file (or default values)
"""

import os
from dotenv import load_dotenv

load_dotenv()

# -------------------- REQUIRED --------------------
BOT_TOKEN: str = os.getenv("BOT_TOKEN")

# -------------------- OPTIONAL --------------------
DATABASE_PATH: str = os.getenv("DATABASE_PATH", "birthday_bot.db")
REMINDER_HOUR: int = int(os.getenv("REMINDER_HOUR", "4"))   # 04:00 UTC
REMINDER_DAYS_BEFORE_END: int = int(os.getenv("REMINDER_DAYS_BEFORE_END", "7"))
