# Error Handling Guide - Birthday Card Telebot

## Overview

This document explains the comprehensive error handling system added to the Birthday Card Telebot. The system ensures that:

1. **The bot never crashes unexpectedly** - All errors are caught and logged
2. **Users receive clear, helpful error messages** - No cryptic Python tracebacks
3. **The application continues running** - Individual operation failures don't break the whole bot
4. **Errors are properly logged** - Issues are tracked in `bot.log` for debugging

---

## Architecture

### Core Components

#### 1. **Error Handler Module** (`utils/error_handler.py`)

The central error handling utility providing:

- **Custom Exception Classes:**
  - `BotError` - Base exception for all bot-specific errors
  - `DatabaseError` - Database operation failures
  - `TelegramAPIError` - Telegram API communication issues
  - `CardGenerationError` - Birthday card generation problems
  - `ValidationError` - User input validation failures

- **Decorators:**
  - `@safe_handler` - Wraps async handlers to catch all exceptions and send user-friendly error messages
  - `@handle_database_error` - Wraps database operations with error context

- **Utility Functions:**
  - `send_error_message()` - Safely sends error messages to users via Telegram
  - `safe_send_message()` - Fire-and-forget message sending (for scheduler/reminders)
  - `ensure_user_exists()` - Validates user registration before operations

### Error Flow

```
Handler Function
    ↓
Exception Occurs
    ↓
@safe_handler Decorator
    ↓
Catch & Log Error ← Specific Exception Type
    ↓
Send User-Friendly Message (via Telegram)
    ↓
Return Safe State (ConversationHandler.END)
    ↓
Bot Continues Running
```

---

## Error Handling by Component

### 1. **Command Handlers** (`handlers/admin_handlers.py`, `handlers/user_handlers.py`)

All handlers are wrapped with `@safe_handler` decorator:

```python
@admin_only
@safe_handler
async def bump(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Command that bumps reminders to users."""
    try:
        # Database operation with error handling
        bday_babies = db.get_birthdays_in_month(month_num)
    except Exception as e:
        logger.error(f"Failed to fetch birthdays: {e}")
        await send_error_message(update, "⚠️ Failed to fetch birthday list. Please try again.")
        return
```

**What happens if it fails:**
- Database error → User sees: "⚠️ Failed to fetch birthday list. Please try again."
- Telegram API error → User sees: "⚠️ Communication error with Telegram. Please try again."
- Unexpected error → User sees: "⚠️ An unexpected error occurred. Our team has been notified."

### 2. **Conversation Handlers** (`handlers/conversation_handlers.py`)

Multi-step flows with state management:

```python
@safe_handler
async def write_person_selected(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        # Step 1: Get person from database
        person = db.get_user_by_id(person_id)
        if not person:
            await query.edit_message_text("User not found...")
            return ConversationHandler.END
        
        # Step 2: Try to fetch existing wish
        try:
            existing = db.get_wish(my_id, person_id, target)
        except Exception as e:
            logger.error(f"Failed to fetch wish: {e}")
            existing = None  # Continue without existing wish
        
        # Step 3: Continue conversation
        await query.edit_message_text(...)
        return WRITE_TYPE_MESSAGE
        
    except Exception as e:
        logger.exception("Unexpected error...")
        await send_error_message(update, "⚠️ An unexpected error occurred...")
        return ConversationHandler.END
```

**Key strategies:**
- Graceful degradation (fetch existing wish is optional)
- Return `ConversationHandler.END` on fatal errors (exits conversation)
- Continue conversation on non-fatal errors (retry message)

### 3. **Database Operations** (`database.py`)

Enhanced error handling with logging:

```python
@contextmanager
def get_conn():
    """Yield a SQLite connection, commit on success, rollback on error."""
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except sqlite3.Error as e:
        if conn:
            conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()
```

**Features:**
- Automatic transaction rollback on errors
- Connection cleanup guaranteed (finally block)
- Specific logging for SQLite vs. unexpected errors

### 4. **Card Generation** (`utils/card_generator.py`)

Defensive programming with fallbacks:

```python
def generate_card(person, wishes, target_month: str) -> str:
    """Generate birthday card with comprehensive error handling."""
    try:
        # Validate inputs
        name = person.get("name", "Birthday Person")
        if not name:
            raise ValueError("Person name is required")
        
        # Handle missing template gracefully
        try:
            template = _TEMPLATE_PATH.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.error(f"Template file not found: {_TEMPLATE_PATH}")
            raise
        
        # Format template with error context
        try:
            html = template.format(...)
        except KeyError as e:
            raise ValueError(f"Invalid template structure: {e}")
        
        # Write file with IO error handling
        try:
            tmp = tempfile.NamedTemporaryFile(...)
            tmp.write(html)
            tmp.close()
            return tmp.name
        except IOError as e:
            logger.error(f"Failed to write card file: {e}")
            raise
            
    except Exception:
        logger.exception("Error in generate_card")
        raise
```

**Techniques:**
- Input validation with helpful error messages
- Specific exception types for each failure mode
- Fallback values for optional data (e.g., "Anonymous" wisher)

### 5. **Scheduler** (`scheduler.py`)

Background job error handling:

```python
async def send_monthly_reminder(bot) -> None:
    """Send monthly reminders with robust error handling."""
    try:
        # Database operations
        try:
            babies = db.get_birthdays_in_month(next_month_num)
        except Exception as e:
            logger.error(f"Failed to fetch birthdays: {e}")
            return  # Gracefully exit without crashing scheduler
        
        # Batch message sending
        sent = 0
        failed = 0
        for user in all_users:
            try:
                success = await safe_send_message(bot, chat_id=user["telegram_id"], ...)
                if success:
                    sent += 1
                else:
                    failed += 1
            except Exception as e:
                logger.warning(f"Error messaging {user['name']}: {e}")
                failed += 1
        
        logger.info(f"Sent {sent}/{len(all_users)} reminders. {failed} failed.")
        
    except Exception:
        logger.exception("Unexpected error in send_monthly_reminder")
```

**Features:**
- Errors don't stop the scheduler
- Individual message failures don't stop the batch
- Detailed logging of success/failure counts

### 6. **Global Error Handler** (`bot.py`)

Last-resort error handler for unhandled exceptions:

```python
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log errors and notify user."""
    logger.error("Exception while handling an update:", exc_info=context.error)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ An error occurred. Our team has been notified. Please try again later."
            )
    except Exception as e:
        logger.error(f"Failed to send error message: {e}")
```

---

## User Messages

All error messages shown to users are user-friendly and non-technical:

| Error Type | User Message |
|-----------|--------------|
| Database Error | ⚠️ Database error occurred. Please try again later or contact an admin. |
| Telegram API Error | ⚠️ Communication error with Telegram. Please try again. |
| Card Generation | ⚠️ Failed to generate birthday card. Please try again or contact an admin. |
| Validation | ⚠️ Invalid input. Please check and try again. |
| Generic Error | ⚠️ An unexpected error occurred. Our team has been notified. Please try again later. |

---

## Logging

All errors are logged to both console and file (`bot.log`):

```
2025-04-30 14:23:45,123 | ERROR   | handlers.admin_handlers | Failed to fetch birthdays: [error details]
2025-04-30 14:23:46,456 | WARNING | scheduler | Could not message user_id: Bot was blocked
2025-04-30 14:23:47,789 | ERROR   | database | Database error: UNIQUE constraint failed
```

### Log Levels Used

- **INFO**: Normal operations ("Database initialized", "Scheduler set up")
- **WARNING**: Recoverable errors ("User blocked bot", "Could not message user")
- **ERROR**: Serious issues ("Failed database operation", "Missing template file")
- **EXCEPTION**: Unhandled exceptions with full traceback

---

## Testing Error Handling

### Test Scenarios

1. **Database Unavailable:**
   ```bash
   rm birthday_bot.db  # Remove database
   python bot.py       # See graceful startup error
   ```

2. **Network Error (Simulate with Telegram API):**
   - Block bot in Telegram
   - Run `/bump` command
   - Should log error but continue

3. **Invalid User Input:**
   - Run `/adduser`
   - Enter invalid birthday format
   - See validation error message

4. **Missing Template:**
   ```bash
   rm templates/card.html
   python bot.py
   /collate <user>  # See card generation error
   ```

---

## Best Practices for Developers

### Adding New Handlers

```python
@admin_only
@safe_handler
async def my_new_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        # Main logic here
        try:
            result = db.some_operation()
        except Exception as e:
            logger.error(f"Failed to do something: {e}")
            await send_error_message(update, "⚠️ Operation failed. Please try again.")
            return
        
        # Continue with success path
        await update.message.reply_text("✅ Success!")
        
    except Exception as e:
        logger.exception("Unexpected error in my_new_handler")
        await send_error_message(update, "⚠️ An unexpected error occurred.")
```

### Key Rules

1. **Always catch database errors** - Even if you think they shouldn't happen
2. **Log before sending to user** - Ensures debugging info is captured
3. **Use @safe_handler** - Catches any errors you miss
4. **Return ConversationHandler.END** - On fatal errors in conversations
5. **Provide context in logs** - Include the operation being attempted
6. **User messages should be helpful** - Not "Internal Server Error"

---

## Monitoring

### Check Log File

```bash
tail -f bot.log                    # Live monitoring
grep ERROR bot.log                 # Find all errors
grep -c ERROR bot.log              # Count errors
tail -100 bot.log | grep WARNING   # Recent warnings
```

### Error Patterns to Watch

- Repeated database errors → Database issue
- Repeated Telegram errors → Bot blocked by many users
- Missing template files → Deployment issue
- Date parsing errors → User input validation needed

---

## Future Improvements

Potential enhancements to error handling:

1. **Error Recovery**: Automatic retry with exponential backoff
2. **Error Metrics**: Track error frequency per handler
3. **Alerts**: Send admin notifications for critical errors
4. **Circuit Breaker**: Temporarily disable handlers on repeated failures
5. **Database Connection Pool**: Handle concurrent database access better
6. **Monitoring Dashboard**: Real-time error tracking and visualization

---

## Summary

The error handling system ensures:

✅ **Reliability** - Bot continues running despite individual failures  
✅ **Transparency** - Users know what went wrong (without technical jargon)  
✅ **Debuggability** - All errors are logged with context  
✅ **Graceful Degradation** - Non-critical failures don't stop operations  
✅ **Recovery** - Users can retry operations without restarting bot  

For more details, see the docstrings in:
- `utils/error_handler.py` - Error handling utilities
- `database.py` - Database error handling
- `utils/card_generator.py` - Card generation errors
