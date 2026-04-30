"""
handlers/admin_handlers.py – Admin-only commands
==================================================
/bump  – Remind everyone who hasn't written wishes yet
/clear – Remove old wishes from the DB
"""

import logging
from datetime import date
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

import database as db
from utils.date_utils import next_month_str, current_month_str
from utils.auth import admin_only
from utils.error_handler import safe_handler, send_error_message, DatabaseError

logger = logging.getLogger(__name__)


@admin_only
@safe_handler
async def bump(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    /bump — For every birthday person next month, DM users who haven't written yet.
    """
    try:
        target = next_month_str()
        month_num = (date.today().month % 12) + 1
        
        try:
            bday_babies = db.get_birthdays_in_month(month_num)  # active users only
        except Exception as e:
            logger.error(f"Failed to fetch birthdays: {e}")
            await send_error_message(
                update,
                "⚠️ Failed to fetch birthday list. Please try again later."
            )
            return

        if not bday_babies:
            await update.message.reply_text(
                f"No birthdays found for next month ({target}). Nothing to bump! 🎉"
            )
            return

        bump_count = 0
        failed_count = 0
        
        for baby in bday_babies:
            try:
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
                    except TelegramError as e:
                        # User may have blocked the bot or other Telegram issue
                        logger.debug(f"Could not message user {user['telegram_id']}: {e}")
                        failed_count += 1
                    except Exception as e:
                        logger.error(f"Unexpected error messaging user: {e}")
                        failed_count += 1
            except Exception as e:
                logger.error(f"Error processing birthday person {baby.get('name', 'unknown')}: {e}")
                continue

        await update.message.reply_text(
            f"✅ Bump complete! Sent {bump_count} reminder(s) across "
            f"{len(bday_babies)} birthday person(s)."
            + (f"\n⚠️ {failed_count} message(s) couldn't be delivered (blocked/inactive users)."
               if failed_count > 0 else "")
        )
    except Exception as e:
        logger.exception("Unexpected error in bump command")
        await send_error_message(
            update,
            "⚠️ An unexpected error occurred during the bump operation. Please try again."
        )


@admin_only
@safe_handler
async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/clear — Delete wishes from months before the current month."""
    try:
        current = current_month_str()
        try:
            deleted = db.clear_old_wishes(current)
        except Exception as e:
            logger.error(f"Failed to clear old wishes: {e}")
            await send_error_message(
                update,
                "⚠️ Failed to clear old wishes. Please try again later."
            )
            return
            
        await update.message.reply_text(
            f"🗑️ Cleared *{deleted}* old wish(es) from before {current}.",
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.exception("Unexpected error in clear command")
        await send_error_message(
            update,
            "⚠️ An unexpected error occurred during the clear operation."
        )
