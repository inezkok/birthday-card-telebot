"""
One-time setup script to create the first admin user in the database.
"""

from database import init_db, add_user, get_all_users

def main():
    init_db()

    print("=== Birthday Bot — First Admin Setup ===\n")
    print("You need to know your Telegram numeric user ID.")
    print("Get it by messaging @userinfobot on Telegram.\n")

    tg_id  = int(input("Your Telegram numeric ID: ").strip())
    name   = input("Your full name: ").strip()
    handle = input("Your Telegram handle (without @): ").strip().lstrip("@")
    bday   = input("Your birthday (DD/MM/YYYY): ").strip()

    # Parse birthday
    parts = bday.split("/")
    from datetime import date
    bday_obj = date(int(parts[2]), int(parts[1]), int(parts[0]))
    bday_str = bday_obj.strftime("%Y-%m-%d")

    add_user(telegram_id=tg_id, name=name, telehandle=handle,
             birthday=bday_str, role="admin")

    print(f"\n✅ Admin user '{name}' added successfully!")
    print("Now start the bot with: python bot.py")
    print("Then open Telegram and send /start to the bot.\n")

if __name__ == "__main__":
    main()
