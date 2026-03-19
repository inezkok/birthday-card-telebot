"""
Handles databae interactions
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH

# -------------------- PATH HELPERS --------------------

_SQL_DIR = Path(__file__).parent / "sql"

def _read_sql(filename: str) -> str:
    """Return the full contents of a file in the sql/ directory."""
    return (_SQL_DIR / filename).read_text(encoding="utf-8")

# -------------------- CONNECTION HELPER --------------------

@contextmanager
def get_conn():
    """Yield a SQLite connection, commit on success, rollback on error."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row       # access columns by name: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# -------------------- SCHEMA --------------------

def init_db() -> None:
    """Create tables from sql/schema.sql if they do not already exist."""
    schema = _read_sql("schema.sql")
    with get_conn() as conn:
        conn.executescript(schema)

# -------------------- USER CRUD --------------------

def add_user(telegram_id: int, name: str, telehandle: str, 
             birthday: str, role: str = "normal") -> None:
    """
    Insert a new user.
    telegram_id : Telegram's numeric user ID (get via @userinfobot)
    birthday    : ISO date string 'YYYY-MM-DD'
    role        : 'admin' or 'normal'
    """
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO users (telegram_id, name, telehandle, birthday, role) VALUES (?, ?, ?, ?, ?)",
            (telegram_id, name, telehandle, birthday, role),
        )

def remove_user(telegram_id: int) -> bool:
    """Delete a user and all their wishes. Returns True if the user existed."""
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM users WHERE telegram_id = ?", (telegram_id,))
        conn.execute(
            "DELETE FROM wishes WHERE wisher_id = ? OR birthday_person_id = ?",
            (telegram_id, telegram_id),
        )
        return cur.rowcount > 0

def get_user(telegram_id: int) -> Optional[sqlite3.Row]:
    """Fetch a single user by their Telegram ID, or None if not found."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)
        ).fetchone()
    
def get_user_by_handle(telehandle: str) -> Optional[sqlite3.Row]:
    handle = telehandle.lstrip("@")
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE telehandle = ?", (handle,)
        ).fetchone()

def get_all_users() -> list[sqlite3.Row]:
    """Return all users ordered alphabetically by name."""
    with get_conn() as conn:
        return conn.execute("SELECT * FROM users ORDER BY name").fetchall()

def set_user_role(telegram_id: int, role: str) -> bool:
    """Change a user's role to 'admin' or 'normal'. Returns True if found."""
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET role = ? WHERE telegram_id = ?", (role, telegram_id)
        )
        return cur.rowcount > 0

def is_admin(telegram_id: int) -> bool:
    """Return True if the user exists and has role='admin'."""
    user = get_user(telegram_id)
    return user is not None and user["role"] == "admin"

def user_exists(telegram_id: int) -> bool:
    """Return True if a user with this Telegram ID is in the database."""
    return get_user(telegram_id) is not None

# -------------------- BIRTHDAY HELPER --------------------

def get_birthdays_in_month(month: int) -> list[sqlite3.Row]:
    """
    Return all users whose birthday falls in the given calendar month (1-12).
    Uses strftime('%m', birthday) so the birthday column must be 'YYYY-MM-DD'.
    """
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM users "
            "WHERE CAST(strftime('%m', birthday) AS INTEGER) = ?",
            (month,),
        ).fetchall()

# -------------------- WISH CRUD --------------------

def upsert_wish(wisher_id: int, birthday_person_id: int,
                target_month: str, message: str) -> None:
    """
    Insert a wish, or overwrite the message if one already exists for this
    (wisher, birthday_person, month) combination.
    target_month must be 'YYYY-MM' (e.g. '2025-04').
    """
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

def get_wishes_for_person(birthday_person_id: int,
                           target_month: str) -> list[sqlite3.Row]:
    """
    Return all wishes written for a birthday person in a given month.
    Each row includes the wisher's name (joined from users).
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT   w.message,
                     u.name AS wisher_name
            FROM     wishes w
            JOIN     users  u ON u.telegram_id = w.wisher_id
            WHERE    w.birthday_person_id = ?
            AND      w.target_month       = ?
            ORDER BY u.name
            """,
            (birthday_person_id, target_month),
        ).fetchall()

def get_wish(wisher_id: int, birthday_person_id: int,
             target_month: str) -> Optional[sqlite3.Row]:
    """Fetch a specific wish, or None if the wisher has not written one yet."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM wishes "
            "WHERE wisher_id = ? AND birthday_person_id = ? AND target_month = ?",
            (wisher_id, birthday_person_id, target_month),
        ).fetchone()

def get_missing_wishers(birthday_person_id: int,
                         target_month: str) -> list[sqlite3.Row]:
    """
    Return every user who has NOT yet written a wish for this person/month,
    excluding the birthday person themselves (can't wish yourself).
    Used by /bump to find who needs a reminder.
    """
    with get_conn() as conn:
        return conn.execute(
            """
            SELECT u.*
            FROM   users u
            WHERE  u.telegram_id != ?
            AND    u.telegram_id NOT IN (
                       SELECT wisher_id
                       FROM   wishes
                       WHERE  birthday_person_id = ?
                       AND    target_month       = ?
                   )
            ORDER BY u.name
            """,
            (birthday_person_id, birthday_person_id, target_month),
        ).fetchall()

def clear_old_wishes(before_month: str) -> int:
    """
    Delete all wishes whose target_month is strictly before `before_month`.
    before_month must be 'YYYY-MM'.  Returns the number of deleted rows.
    """
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM wishes WHERE target_month < ?", (before_month,)
        )
        return cur.rowcount
