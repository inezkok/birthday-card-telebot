CREATE TABLE IF NOT EXISTS users (
    telegram_id   INTEGER  PRIMARY KEY,
    name          TEXT     NOT NULL,
    telehandle    TEXT     NOT NULL UNIQUE,
    birthday      TEXT     NOT NULL,
    role          TEXT     NOT NULL DEFAULT 'normal'
                           CHECK(role IN ('admin', 'normal'))
);

CREATE TABLE IF NOT EXISTS wishes (
    id                   INTEGER  PRIMARY KEY AUTOINCREMENT,
    wisher_id            INTEGER  NOT NULL  REFERENCES users(telegram_id),
    birthday_person_id   INTEGER  NOT NULL  REFERENCES users(telegram_id),
    target_month         TEXT     NOT NULL,
    message              TEXT     NOT NULL,
    created_at           TEXT     NOT NULL  DEFAULT (datetime('now')),
    UNIQUE(wisher_id, birthday_person_id, target_month)
);