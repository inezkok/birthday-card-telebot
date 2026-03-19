"""
handlers/user_handlers.py – Commands available to all users
=============================================================
/start  – register the user and enable messaging
/help   – show available commands based on role
"""

from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils.auth import registered_only, admin_only


@registered_only
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /start — Registers the user in the DB if they are already added by an admin,
    or simply greets them if they are new.
    """
    user = update.effective_user
    tg_id = user.id

    if db.user_exists(tg_id):
        row = db.get_user_by_telegram_id(tg_id)
        await update.message.reply_text(
            f"👋 Welcome back, *{row['name']}*!\n"
            "Use /help to see what you can do.",
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(
            "👋 Hello! You're not yet in the birthday bot's user list.\n\n"
            "Please ask an *admin* to add you with `/adduser`.",
            parse_mode="Markdown",
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /help — Show commands.  Admin users see extra commands.
    """
    tg_id = update.effective_user.id

    common = (
        "🎂 *Birthday Wishes Bot* 🎂\n\n"
        "*Commands available to everyone:*\n"
        "/start — Check in & see your status\n"
        "/help — Show this message\n"
        "/write — Write a birthday wish for someone\n"
    )

    admin_extra = (
        "\n*Admin-only commands:*\n"
        "/bump — Remind users who haven't written wishes yet\n"
        "/collate — Generate a birthday card for someone\n"
        "/clear — Delete wishes from previous months\n"
        "/admin — Change a user's role (admin ↔ normal)\n"
        "/adduser — Add a new user to the database\n"
        "/removeuser — Remove a user from the database\n"
    )

    msg = common + (admin_extra if db.is_admin(tg_id) else "")
    await update.message.reply_text(msg, parse_mode="Markdown")
