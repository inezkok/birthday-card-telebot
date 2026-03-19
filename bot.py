"""
Birthday Wishes Bot - Main Entry Point
"""

import logging
import asyncio
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler,
)

from config import BOT_TOKEN
from database import init_db
from handlers import admin_handlers, user_handlers, conversation_handlers
from scheduler import setup_scheduler

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log"),
    ],
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Build and run the bot."""
    # Initialise the SQLite database (creates tables if not present)
    init_db()
    logger.info("Database initialised.")

    # Build the Application
    app = Application.builder().token(BOT_TOKEN).build()

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

    # ── Scheduler (monthly reminders) ───────────────────────────────────────
    setup_scheduler(app)
    logger.info("Scheduler set up.")

    logger.info("Bot is polling…")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
