"""Persistencia: conexión a SQLite y esquema de la base de datos."""
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('admin', 'consulta')),
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS assets (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    stored_name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL CHECK (kind IN ('model', 'image', 'document', 'video')),
    mime TEXT NOT NULL,
    size INTEGER NOT NULL,
    sha256 TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS technique (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    company TEXT NOT NULL,
    platform_name TEXT NOT NULL,
    name TEXT NOT NULL,
    intro TEXT NOT NULL DEFAULT '',
    system_info TEXT NOT NULL DEFAULT '',
    cover_asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    model_asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    is_sample INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS steps (
    id INTEGER PRIMARY KEY,
    parent_id INTEGER REFERENCES steps(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    title TEXT NOT NULL,
    objective TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    procedure TEXT NOT NULL DEFAULT '',
    observations TEXT NOT NULL DEFAULT '',
    recommendations TEXT NOT NULL DEFAULT '',
    is_sample INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_steps_parent ON steps(parent_id, position);

CREATE TABLE IF NOT EXISTS instruments (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    function TEXT NOT NULL DEFAULT '',
    image_asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    model_asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    is_verified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS step_instruments (
    step_id INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    instrument_id INTEGER NOT NULL REFERENCES instruments(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    PRIMARY KEY (step_id, instrument_id)
);

CREATE TABLE IF NOT EXISTS step_media (
    id INTEGER PRIMARY KEY,
    step_id INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    caption TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS animations (
    id INTEGER PRIMARY KEY,
    step_id INTEGER NOT NULL REFERENCES steps(id) ON DELETE CASCADE,
    asset_id INTEGER NOT NULL REFERENCES assets(id),
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL,
    settings TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS piece_names (
    raw TEXT PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publications (
    id INTEGER PRIMARY KEY,
    snapshot TEXT NOT NULL,
    published_at TEXT NOT NULL DEFAULT (datetime('now')),
    published_by TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS progress (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    step_id INTEGER NOT NULL,
    PRIMARY KEY (user_id, step_id)
);

CREATE TABLE IF NOT EXISTS user_state (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    last_step_id INTEGER
);
"""


def connect(path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(path, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init(path: Path) -> None:
    conn = connect(path)
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.executescript(SCHEMA)
        # Bases creadas antes de que existieran los ajustes de cada animación.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(animations)")}
        if "settings" not in columns:
            conn.execute("ALTER TABLE animations ADD COLUMN settings TEXT NOT NULL DEFAULT '{}'")
        conn.commit()
    finally:
        conn.close()
