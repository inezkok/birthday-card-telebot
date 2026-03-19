"""
Permission decorators
"""

import functools
import logging
from telegram import Update
from telegram.ext import ContextTypes

import database as db

logger = logging.getLogger(__name__)

def registered_only(func):
    """Decorator: reject unregistered users with a friendly message."""
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        tg_id = update.effective_user.id

        # Check for pending registration (set by /adduser flow)
        handle = (update.effective_user.username or "").lower()
        pending = context.bot_data.get("pending_users", {})
        if handle and handle in pending and not db.user_exists(tg_id):
            info = pending.pop(handle)
            db.add_user(
                telegram_id=tg_id,
                name=info["name"],
                telehandle=info["telehandle"],
                birthday=info["birthday"],
                role=info["role"],
            )
            logger.info("Auto-registered pending user: %s (id=%d)", info["name"], tg_id)

        if not db.user_exists(tg_id):
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
