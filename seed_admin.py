"""
seed_admin.py – One-time setup script
======================================
Run this ONCE to create the first admin user in the database.
After that, use /adduser in the bot to add everyone else.

Usage:
    python seed_admin.py
"""

from database import init_db, add_active_user


def main():
    init_db()

    print("=== Birthday Bot — First Admin Setup ===\n")

    tg_id  = int(input("Your Telegram numeric ID   : ").strip())
    handle = input("Your Telegram handle (@...) : ").strip().lstrip("@").lower()
    name   = input("Your full name              : ").strip()
    bday   = input("Your birthday (DD/MM/YYYY)  : ").strip()

    parts    = bday.split("/")
    from datetime import date
    bday_str = date(int(parts[2]), int(parts[1]), int(parts[0])).strftime("%Y-%m-%d")

    add_active_user(telegram_id=tg_id, telehandle=handle,
                    name=name, birthday=bday_str, role="admin")

    print(f"\n✅ Admin '{name}' (@{handle}) added successfully!")
    print("Start the bot:  python bot.py")
    print("Then send /start to your bot in Telegram.\n")


if __name__ == "__main__":
    main()
