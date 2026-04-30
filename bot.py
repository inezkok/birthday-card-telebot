"""
Birthday Wishes Bot - Main Entry Point
======================================
Run this file to start the bot: python bot.py
"""

import logging
import asyncio
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
    ContextTypes,
)
from telegram.error import TelegramError

from config import BOT_TOKEN
from database import init_db
from handlers import admin_handlers, user_handlers, conversation_handlers
from scheduler import setup_scheduler

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log"),
    ],
)

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Log the error and send a message to the user if possible.
    This is the global error handler that catches any unhandled exceptions.
    """
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    # Try to send an error message to the user
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred while processing your request. "
                "Our team has been notified. Please try again later."
            )
        elif update and update.callback_query:
            await update.callback_query.answer(
                "⚠️ An error occurred. Please try again.",
                show_alert=False
            )
    except Exception as e:
        logger.error(f"Failed to send error message to user: {e}")


def main() -> None:
    """Build and run the bot."""
    # Initialise the SQLite database (creates tables if not present)
    try:
        init_db()
        logger.info("Database initialised.")
    except Exception as e:
        logger.error(f"Failed to initialise database: {e}")
        logger.error("Exiting bot due to database initialization failure.")
        return

    # Build the Application
    try:
        app = Application.builder().token(BOT_TOKEN).build()
    except Exception as e:
        logger.error(f"Failed to create Application: {e}")
        return

    # ── Conversation handler: /write ─────────────────────────────────────────
    write_conv = ConversationHandler(
        entry_points=[CommandHandler("write", conversation_handlers.write_start)],
        states=conversation_handlers.WRITE_STATES,
        fallbacks=[CommandHandler("cancel", conversation_handlers.cancel)],
    )

    # ── Conversation handler: /collate ───────────────────────────────────────
    collate_conv = ConversationHandler(
        entry_points=[CommandHandler("collate", conversation_handlers.collate_start)],
        states=conversation_handlers.COLLATE_STATES,
        fallbacks=[CommandHandler("cancel", conversation_handlers.cancel)],
    )

    # ── Conversation handler: /admin ─────────────────────────────────────────
    admin_conv = ConversationHandler(
        entry_points=[CommandHandler("admin", conversation_handlers.admin_role_start)],
        states=conversation_handlers.ADMIN_STATES,
        fallbacks=[CommandHandler("cancel", conversation_handlers.cancel)],
    )

    # ── Conversation handler: /adduser ───────────────────────────────────────
    adduser_conv = ConversationHandler(
        entry_points=[CommandHandler("adduser", conversation_handlers.adduser_start)],
        states=conversation_handlers.ADDUSER_STATES,
        fallbacks=[CommandHandler("cancel", conversation_handlers.cancel)],
    )

    # ── Conversation handler: /removeuser ───────────────────────────────────
    removeuser_conv = ConversationHandler(
        entry_points=[CommandHandler("removeuser", conversation_handlers.removeuser_start)],
        states=conversation_handlers.REMOVEUSER_STATES,
        fallbacks=[CommandHandler("cancel", conversation_handlers.cancel)],
    )

    # ── Simple command handlers ──────────────────────────────────────────────
    app.add_handler(CommandHandler("start", user_handlers.start))
    app.add_handler(CommandHandler("help", user_handlers.help_command))
    app.add_handler(CommandHandler("bump", admin_handlers.bump))
    app.add_handler(CommandHandler("clear", admin_handlers.clear))

    # ── Conversation handlers ────────────────────────────────────────────────
    app.add_handler(write_conv)
    app.add_handler(collate_conv)
    app.add_handler(admin_conv)
    app.add_handler(adduser_conv)
    app.add_handler(removeuser_conv)

    # ── Inline button callbacks (outside conversation flows) ─────────────────
    app.add_handler(CallbackQueryHandler(conversation_handlers.handle_stray_callback))

    # ── Error handler ────────────────────────────────────────────────────────
    app.add_error_handler(error_handler)

    # ── Scheduler (monthly reminders) ───────────────────────────────────────
    try:
        setup_scheduler(app)
        logger.info("Scheduler set up.")
    except Exception as e:
        logger.error(f"Failed to set up scheduler: {e}")
        logger.warning("Bot will run without scheduled reminders.")

    logger.info("Bot is polling…")
    try:
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Error while polling: {e}")
        logger.error("Bot stopped due to an error.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
