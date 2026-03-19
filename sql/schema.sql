-- =============================================================================
-- schema.sql  –  Birthday Bot database schema
-- =============================================================================
-- This file is the single source of truth for table definitions.
-- It is read by database.py at startup (init_db) to create tables if missing.
-- To add a column: add it here, then add matching code in database.py.
-- To reset the database: delete birthday_bot.db and restart the bot.
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER  PRIMARY KEY AUTOINCREMENT,
    telegram_id   INTEGER  UNIQUE,
    telehandle    TEXT     NOT NULL UNIQUE,
    name          TEXT     NOT NULL,
    birthday      TEXT     NOT NULL,
    role          TEXT     NOT NULL DEFAULT 'normal'
                           CHECK(role IN ('admin', 'normal')),
    pending       INTEGER  NOT NULL DEFAULT 1
                           CHECK(pending IN (0, 1))
);


CREATE TABLE IF NOT EXISTS wishes (
    id                   INTEGER  PRIMARY KEY AUTOINCREMENT,
    wisher_id            INTEGER  NOT NULL  REFERENCES users(id),
    birthday_person_id   INTEGER  NOT NULL  REFERENCES users(id),
    target_month         TEXT     NOT NULL,
    message              TEXT     NOT NULL,
    created_at           TEXT     NOT NULL  DEFAULT (datetime('now')),
    UNIQUE(wisher_id, birthday_person_id, target_month)
);