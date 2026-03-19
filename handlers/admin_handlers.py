"""
handlers/admin_handlers.py – Admin-only commands
==================================================
/bump  – Remind everyone who hasn't written wishes yet
/clear – Remove old wishes from the DB
"""

from datetime import date
from telegram import Update
from telegram.ext import ContextTypes

import database as db
from utils.date_utils import next_month_str, current_month_str
from utils.auth import admin_only


@admin_only
async def bump(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /bump — For every birthday person next month, DM users who haven't written yet.
    """
    target      = next_month_str()
    month_num   = (date.today().month % 12) + 1
    bday_babies = db.get_birthdays_in_month(month_num)  # active users only

    if not bday_babies:
        await update.message.reply_text(
            f"No birthdays found for next month ({target}). Nothing to bump! 🎉"
        )
        return

    bump_count = 0
    for baby in bday_babies:
        # get_missing_wishers uses users.id (surrogate key)
        missing = db.get_missing_wishers(baby["id"], target)
        for user in missing:
            try:
                # telegram_id is always set for active users (pending=0)
                await context.bot.send_message(
                    chat_id=user["telegram_id"],
                    text=(
                        f"⏰ *Reminder!*\n\n"
                        f"You haven't written a birthday wish for *{baby['name']}* yet!\n"
                        f"Their birthday is in {target}. Use /write to send them a message. 🎂"
                    ),
                    parse_mode="Markdown",
                )
                bump_count += 1
            except Exception:
                # User may have blocked the bot — skip silently
                pass

    await update.message.reply_text(
        f"✅ Bump complete! Sent {bump_count} reminder(s) across "
        f"{len(bday_babies)} birthday person(s)."
    )


@admin_only
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/clear — Delete wishes from months before the current month."""
    current = current_month_str()
    deleted = db.clear_old_wishes(current)
    await update.message.reply_text(
        f"🗑️ Cleared *{deleted}* old wish(es) from before {current}.",
        parse_mode="Markdown",
    )
