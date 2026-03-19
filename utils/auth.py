"""
utils/auth.py – Permission decorators
=======================================
@admin_only      — only users with role='admin' may proceed
@registered_only — user must be fully active in the DB (pending=0)

Pending registration flow
--------------------------
When an admin runs /adduser, the user is inserted into the DB immediately
with pending=1 and telegram_id=NULL (see database.add_pending_user).

When that user sends /start, registered_only:
  1. Reads their @username from the Telegram update
  2. Calls db.activate_user() which fills in their telegram_id and sets pending=0
  3. Lets them through — they're now fully registered

This flow survives bot restarts because pending users live in the DB,
not in memory.
"""

import functools
import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db

logger = logging.getLogger(__name__)


def registered_only(func):
    """
    Decorator: activate any pending registration, then reject unknown users.
    The activation check runs first so a new user's very first /start
    completes their registration in the same call.
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        tg_id       = update.effective_user.id
        tg_username = (update.effective_user.username or "").lower().lstrip("@")

        # Case 1: No Telegram username set — we can't match them to a pending
        # entry, so registration is impossible until they set one.
        if not tg_username and not db.user_exists(tg_id):
            await update.message.reply_text(
                "⚠️ Your Telegram account doesn't have a username set.\n\n"
                "Please set one via *Telegram Settings → Username*, "
                "then send /start again.",
                parse_mode="Markdown",
            )
            return

        # Case 2: Username matches a pending DB entry — activate them now.
        if tg_username and not db.user_exists(tg_id):
            activated = db.activate_user(tg_username, tg_id)
            if activated:
                logger.info("Activated pending user @%s (telegram_id=%d)",
                            tg_username, tg_id)
            else:
                # No pending entry found — they were never added by an admin.
                await update.message.reply_text(
                    "⚠️ You're not registered in the bot yet.\n"
                    "Please ask an admin to add you with /adduser, "
                    "then send /start once they confirm."
                )
                return

        return await func(update, context, *args, **kwargs)
    return wrapper


def admin_only(func):
    """Decorator: reject non-admin users with a clear message."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not db.is_admin(update.effective_user.id):
            await update.message.reply_text("🚫 This command is for admins only.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapper
