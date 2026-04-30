"""
utils/error_handler.py – Centralized error handling and user feedback
=====================================================================
Provides decorators and utility functions for graceful error handling
throughout the bot, ensuring the application doesn't crash on errors
and users always receive clear feedback.
"""

import logging
import functools
from typing import Callable, Any
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import TelegramError

logger = logging.getLogger(__name__)


class BotError(Exception):
    """Base exception for bot-specific errors."""
    def __init__(self, user_message: str, log_message: str = None):
        self.user_message = user_message
        self.log_message = log_message or user_message
        super().__init__(self.log_message)


class DatabaseError(BotError):
    """Raised when database operations fail."""
    pass


class TelegramAPIError(BotError):
    """Raised when Telegram API calls fail."""
    pass


class CardGenerationError(BotError):
    """Raised when card generation fails."""
    pass


class ValidationError(BotError):
    """Raised when user input validation fails."""
    pass


def safe_handler(func: Callable) -> Callable:
    """
    Decorator for Telegram handler functions to catch all errors gracefully.
    
    - Catches exceptions and logs them
    - Sends user-friendly error messages
    - Returns ConversationHandler.END on error to exit conversation flows
    - Prevents bot crashes
    """
    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs) -> Any:
        try:
            return await func(update, context, *args, **kwargs)
        except ValidationError as e:
            logger.info(f"Validation error in {func.__name__}: {e.log_message}")
            await send_error_message(update, e.user_message)
            # Return current state to retry
            return None
        except DatabaseError as e:
            logger.error(f"Database error in {func.__name__}: {e.log_message}")
            await send_error_message(
                update,
                "⚠️ Database error occurred. Please try again later or contact an admin."
            )
            from telegram.ext import ConversationHandler
            return ConversationHandler.END
        except TelegramAPIError as e:
            logger.error(f"Telegram API error in {func.__name__}: {e.log_message}")
            await send_error_message(
                update,
                "⚠️ Communication error with Telegram. Please try again."
            )
            from telegram.ext import ConversationHandler
            return ConversationHandler.END
        except CardGenerationError as e:
            logger.error(f"Card generation error in {func.__name__}: {e.log_message}")
            await send_error_message(
                update,
                "⚠️ Failed to generate birthday card. Please try again or contact an admin."
            )
            from telegram.ext import ConversationHandler
            return ConversationHandler.END
        except Exception as e:
            logger.exception(f"Unexpected error in {func.__name__}: {str(e)}")
            await send_error_message(
                update,
                "⚠️ An unexpected error occurred. Our team has been notified. Please try again later."
            )
            from telegram.ext import ConversationHandler
            return ConversationHandler.END
    return wrapper


async def send_error_message(update: Update, message: str) -> None:
    """
    Send an error message to the user via reply_text or edit_message_text.
    
    Handles both message updates (text) and callback queries (button presses).
    """
    try:
        if update.callback_query:
            await update.callback_query.answer(message, show_alert=False)
        elif update.message:
            await update.message.reply_text(message, parse_mode="Markdown")
    except TelegramError as e:
        logger.error(f"Could not send error message to user: {e}")
    except Exception as e:
        logger.error(f"Unexpected error when sending error message: {e}")


async def safe_send_message(
    bot,
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown",
    **kwargs
) -> bool:
    """
    Safely send a message via Telegram API.
    
    Returns True if successful, False otherwise.
    Logs errors but doesn't raise exceptions (for use in fire-and-forget scenarios).
    """
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            **kwargs
        )
        return True
    except TelegramError as e:
        logger.warning(f"Failed to send message to {chat_id}: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending message to {chat_id}: {e}")
        return False


def handle_database_error(operation_name: str) -> Callable:
    """
    Decorator for database operation functions to catch and wrap errors.
    
    Usage:
        @handle_database_error("user lookup")
        def get_user(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Database error during {operation_name}: {e}")
                raise DatabaseError(
                    user_message="Database error occurred",
                    log_message=f"Error in {operation_name}: {str(e)}"
                )
        return wrapper
    return decorator


async def ensure_user_exists(update: Update, tg_id: int) -> bool:
    """
    Check if user exists. If not, send a helpful message.
    Returns True if user exists, False otherwise.
    """
    import database as db
    try:
        if not db.user_exists(tg_id):
            if update.message:
                await update.message.reply_text(
                    "⚠️ You are not registered in the bot's system. "
                    "Please contact an admin to add you.",
                    parse_mode="Markdown"
                )
            return False
        return True
    except Exception as e:
        logger.error(f"Error checking user existence: {e}")
        await send_error_message(
            update,
            "⚠️ Failed to verify your account. Please try again."
        )
        return False
