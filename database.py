"""
database.py – All database interactions
========================================
Schema is defined in  sql/schema.sql   (table definitions + comments).
Query reference is in sql/queries.sql  (every SQL statement, annotated).

Key design point
----------------
users.id          — stable surrogate INTEGER PRIMARY KEY, always present.
                    Used in foreign keys (wishes) and keyboard callback data.
users.telegram_id — Telegram's numeric ID, NULL for pending users.
                    Filled in by activate_user() when they send /start.
users.pending     — 1 until the user sends /start, then 0.

All user-facing menus (write, collate, admin, removeuser) only show
active users (pending=0) unless explicitly noted.

Error Handling
--------------
All database operations use get_conn() context manager which automatically:
  - Commits on success
  - Rolls back on any exception
  - Closes the connection

Handlers should wrap database calls in try-except blocks and use
utils/error_handler.py functions to provide user feedback.
"""

import sqlite3
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH

logger = logging.getLogger(__name__)

_SQL_DIR = Path(__file__).parent / "sql"

def _read_sql(filename: str) -> str:
    """Return the full contents of a file in the sql/ directory."""
    try:
        return (_SQL_DIR / filename).read_text(encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to read SQL file {filename}: {e}")
        raise

# -------------------- CONNECTION HELPER --------------------

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
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Unexpected error in database operation: {e}")
        raise
    finally:
        if conn:
            conn.close()

# -------------------- SCHEMA --------------------

def init_db() -> None:
    """Create tables from sql/schema.sql if they do not already exist."""
    try:
        schema = _read_sql("schema.sql")
        with get_conn() as conn:
            conn.executescript(schema)
        logger.info("Database schema initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        raise

# -------------------- USER CRUD --------------------

def add_pending_user(telehandle: str, name: str,
                     birthday: str, role: str = "normal") -> None:
    """
    Insert a new user in pending state (telegram_id is unknown until /start).
    Called by the /adduser flow.

    telehandle : @username without @, lowercase — admin provides this.
    birthday   : ISO date string 'YYYY-MM-DD'.
    role       : 'admin' or 'normal'.
    """
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (telehandle, name, birthday, role, pending) "
                "VALUES (?, ?, ?, ?, 1)",
                (telehandle, name, birthday, role),
            )
    except sqlite3.IntegrityError as e:
        logger.error(f"Integrity error while adding pending user: {e}")
        raise
    except Exception as e:
        logger.error(f"Error adding pending user: {e}")
        raise

def add_active_user(telegram_id: int, telehandle: str, name: str,
                    birthday: str, role: str = "normal") -> None:
    """
    Insert a fully active user with a known telegram_id.
    Used only by seed_admin.py for the first admin setup.
    """
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (telegram_id, telehandle, name, birthday, role, pending) "
                "VALUES (?, ?, ?, ?, ?, 0)",
                (telegram_id, telehandle, name, birthday, role),
            )
    except sqlite3.IntegrityError as e:
        logger.error(f"Integrity error while adding active user: {e}")
        raise
    except Exception as e:
        logger.error(f"Error adding active user: {e}")
        raise

def activate_user(telehandle: str, telegram_id: int) -> bool:
    """
    Complete registration for a pending user when they send /start.
    Fills in their real telegram_id and marks them active (pending=0).
    Returns True if a matching pending entry was found and updated.
    """
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "UPDATE users SET telegram_id = ?, pending = 0 "
                "WHERE telehandle = ? AND pending = 1",
                (telegram_id, telehandle),
            )
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Error activating user @{telehandle} {telegram_id}: {e}")

def remove_user(user_id: int) -> bool:
    """
    Delete a user (active or pending) by their surrogate id, and all their
    wishes.  Returns True if the user existed.
    Note: takes users.id (not telegram_id) as the stable identifier.
    """
    try:
        with get_conn() as conn:
            cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.execute(
                "DELETE FROM wishes WHERE wisher_id = ? OR birthday_person_id = ?",
                (user_id, user_id),
            )
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Error removing user {user_id}: {e}")
        raise

def get_user_by_telegram_id(telegram_id: int) -> Optional[sqlite3.Row]:
    """Fetch an active user by their Telegram numeric ID, or None."""
    try:
        with get_conn() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE telegram_id = ? AND pending = 0",
                (telegram_id,)
            ).fetchone()
    except Exception as e:
        logger.error(f"Error fetching user by telegram_id {telegram_id}: {e}")
        raise

def get_user_by_id(user_id: int) -> Optional[sqlite3.Row]:
    """Fetch any user (active or pending) by their surrogate id, or None."""
    try:
        with get_conn() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
    except Exception as e:
        logger.error(f"Error fetching user by id {user_id}: {e}")
        raise

def get_user_by_telehandle(telehandle: str) -> Optional[sqlite3.Row]:
    """
    Fetch a user (active or pending) by their @telehandle (without @).
    Used by /adduser to check for duplicate handles.
    """
    try:
        handle = telehandle.lstrip("@").lower()
        with get_conn() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE telehandle = ?", (handle,)
            ).fetchone()
    except Exception as e:
        logger.error(f"Error fetching user by telehandle {telehandle}: {e}")
        raise

def get_all_active_users() -> list[sqlite3.Row]:
    """Return all fully active users (pending=0), ordered by name."""
    try:
        with get_conn() as conn:
            return conn.execute(
                "SELECT * FROM users WHERE pending = 0 ORDER BY name"
            ).fetchall()
    except Exception as e:
        logger.error(f"Error fetching all active users: {e}")
        raise

def get_all_users() -> list[sqlite3.Row]:
    """
    Return ALL users including pending, ordered by name.
    Used by /removeuser so admins can remove mistaken pending entries.
    """
    try:
        with get_conn() as conn:
            return conn.execute("SELECT * FROM users ORDER BY name").fetchall()
    except Exception as e:
        logger.error(f"Error fetching all users: {e}")
        raise

def set_user_role(user_id: int, role: str) -> bool:
    """
    Change a user's role to 'admin' or 'normal'.
    Takes users.id (surrogate key) — works for both active and pending users.
    Returns True if the user was found.
    """
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "UPDATE users SET role = ? WHERE id = ?", (role, user_id)
            )
            return cur.rowcount > 0
    except Exception as e:
        logger.error(f"Error setting role for user {user_id}: {e}")
        raise

def is_admin(telegram_id: int) -> bool:
    """Return True if the user is active and has role='admin'."""
    try:
        user = get_user_by_telegram_id(telegram_id)
        return user is not None and user["role"] == "admin"
    except Exception as e:
        logger.error(f"Error checking admin status for user {telegram_id}: {e}")
        raise

def user_exists(telegram_id: int) -> bool:
    """Return True if an active user with this telegram_id is in the database."""
    try:
        return get_user_by_telegram_id(telegram_id) is not None
    except Exception as e:
        logger.error(f"Error checking if user {telegram_id} exists: {e}")
        raise

# -------------------- BIRTHDAY HELPER --------------------

def get_birthdays_in_month(month: int) -> list[sqlite3.Row]:
    """
    Return all ACTIVE users whose birthday falls in the given calendar month (1-12).
    Pending users are excluded — they haven't joined yet.
    """
    try:
        with get_conn() as conn:
            return conn.execute(
                "SELECT * FROM users "
                "WHERE pending = 0 "
                "AND CAST(strftime('%m', birthday) AS INTEGER) = ?",
                (month,),
            ).fetchall()
    except Exception as e:
        logger.error(f"Error fetching birthdays for month {month}: {e}")
        raise

# -------------------- WISH CRUD --------------------

def upsert_wish(wisher_id: int, birthday_person_id: int,
                target_month: str, message: str) -> None:
    """
    Insert a wish, or overwrite the message if one already exists for this
    (wisher, birthday_person, month) combination.
    wisher_id / birthday_person_id are users.id (surrogate key).
    target_month must be 'YYYY-MM' (e.g. '2025-04').
    """
    try:
        with get_conn() as conn:
            conn.execute(
                """
                INSERT INTO wishes (wisher_id, birthday_person_id, target_month, message)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(wisher_id, birthday_person_id, target_month)
                DO UPDATE SET message    = excluded.message,
                             created_at = datetime('now')
                """,
                (wisher_id, birthday_person_id, target_month, message),
            )
    except Exception as e:
        logger.error(f"Error upserting wish from {wisher_id} to {birthday_person_id}: {e}")
        raise

def get_wishes_for_person(birthday_person_id: int,
                           target_month: str) -> list[sqlite3.Row]:
    """
    Return all wishes written for a birthday person in a given month.
    birthday_person_id is users.id (surrogate key).
    Each row includes the wisher's name and telehandle (joined from users).
    """
    try:
        with get_conn() as conn:
            return conn.execute(
                """
                SELECT   w.message,
                         u.name       AS wisher_name,
                         u.telehandle AS wisher_telehandle
                FROM     wishes w
                JOIN     users  u ON u.id = w.wisher_id
                WHERE    w.birthday_person_id = ?
                AND      w.target_month       = ?
                ORDER BY u.name
                """,
                (birthday_person_id, target_month),
            ).fetchall()
    except Exception as e:
        logger.error(f"Error fetching wishes for person {birthday_person_id} in {target_month}: {e}")
        raise

def get_wish(wisher_id: int, birthday_person_id: int,
             target_month: str) -> Optional[sqlite3.Row]:
    """
    Fetch a specific wish, or None if the wisher has not written one yet.
    Both IDs are users.id (surrogate key).
    """
    try:
        with get_conn() as conn:
            return conn.execute(
                "SELECT * FROM wishes "
                "WHERE wisher_id = ? AND birthday_person_id = ? AND target_month = ?",
                (wisher_id, birthday_person_id, target_month),
            ).fetchone()
    except Exception as e:
        logger.error(f"Error fetching wish from {wisher_id} to {birthday_person_id} for {target_month}: {e}")
        raise

def get_missing_wishers(birthday_person_id: int,
                         target_month: str) -> list[sqlite3.Row]:
    """
    Return every ACTIVE user who has NOT yet written a wish for this
    person/month, excluding the birthday person themselves.
    birthday_person_id is users.id (surrogate key).
    Used by /bump to find who needs a reminder.
    """
    try:
        with get_conn() as conn:
            return conn.execute(
                """
                SELECT u.*
                FROM   users u
                WHERE  u.pending = 0
                AND    u.id != ?
                AND    u.id NOT IN (
                           SELECT wisher_id
                           FROM   wishes
                           WHERE  birthday_person_id = ?
                           AND    target_month       = ?
                       )
                ORDER BY u.name
                """,
                (birthday_person_id, birthday_person_id, target_month),
            ).fetchall()
    except Exception as e:
        logger.error(f"Error fetching missing wishers for person {birthday_person_id} in {target_month}: {e}")
        raise

def clear_old_wishes(before_month: str) -> int:
    """
    Delete all wishes whose target_month is strictly before `before_month`.
    before_month must be 'YYYY-MM'.  Returns the number of deleted rows.
    """
    try:
        with get_conn() as conn:
            cur = conn.execute(
                "DELETE FROM wishes WHERE target_month < ?", (before_month,)
            )
            return cur.rowcount
    except Exception as e:
        logger.error(f"Error clearing old wishes before {before_month}: {e}")
        raise
