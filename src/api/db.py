"""SQLite persistence for EHR API sessions.

Call init_db() once at app startup, then use get_db() to obtain a connection
for each request.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id           TEXT PRIMARY KEY,
    created_at   TEXT NOT NULL,
    hook         TEXT NOT NULL,
    scenario_key TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'created',
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS crd_results (
    id            TEXT PRIMARY KEY,
    session_id    TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    hook_request  TEXT NOT NULL,
    raw_response  TEXT NOT NULL,
    pa_needed     INTEGER NOT NULL,
    smart_url     TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS questionnaire_sessions (
    id                 TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    questionnaire_url  TEXT NOT NULL,
    questionnaire_json TEXT NOT NULL,
    mode               TEXT NOT NULL,
    answered_items     TEXT NOT NULL DEFAULT '[]',
    qr_reference       TEXT,
    submitted_at       TEXT,
    created_at         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS pas_submissions (
    id             TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    bundle_json    TEXT NOT NULL,
    claim_response TEXT,
    disposition    TEXT,
    auth_number    TEXT,
    submitted_at   TEXT,
    created_at     TEXT NOT NULL
);
"""

_db_path: str = "sessions.db"


async def init_db(db_path: str = "sessions.db") -> None:
    """Create all tables if they don't exist and enable WAL mode."""
    global _db_path
    _db_path = db_path
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.executescript(_SCHEMA)
        await db.commit()


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """Yield a connection with foreign keys enabled and row access by name."""
    async with aiosqlite.connect(_db_path) as db:
        await db.execute("PRAGMA foreign_keys=ON")
        db.row_factory = aiosqlite.Row
        yield db
