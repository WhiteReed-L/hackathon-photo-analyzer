"""
Database layer — SQLite WAL + connection pool.
Tables: users, sessions, conversations.
"""
import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

import aiosqlite

import config

_pool: list[aiosqlite.Connection] = []
_pool_lock = asyncio.Lock()
_pool_sem: asyncio.Semaphore | None = None

SESSION_MAX_AGE = 86400  # 24 hours


async def init_db():
    config.UPLOAD_DIR.mkdir(exist_ok=True)

    db = await aiosqlite.connect(str(config.DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute(f"PRAGMA busy_timeout={config.DB_BUSY_TIMEOUT_MS}")
    await db.execute("PRAGMA foreign_keys=ON")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            nickname        TEXT NOT NULL,
            password_hash   TEXT NOT NULL,
            height          REAL,
            weight          REAL,
            bust            REAL,
            waist           REAL,
            hip             REAL,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    await db.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            token       TEXT PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            created_at  REAL NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at)"
    )

    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            role          TEXT NOT NULL,
            image_url     TEXT,
            text          TEXT,
            style_tags    TEXT,
            scene_tags    TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)"
    )

    await db.commit()
    await db.close()

    # Warm pool
    global _pool, _pool_sem
    _pool_sem = asyncio.Semaphore(config.DB_POOL_SIZE)
    for _ in range(config.DB_POOL_SIZE):
        conn = await aiosqlite.connect(str(config.DATABASE_PATH))
        conn.row_factory = aiosqlite.Row
        await conn.execute(f"PRAGMA busy_timeout={config.DB_BUSY_TIMEOUT_MS}")
        _pool.append(conn)


async def close_db():
    for conn in _pool:
        await conn.close()
    _pool.clear()


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    await _pool_sem.acquire()
    conn = None
    try:
        async with _pool_lock:
            conn = _pool.pop()
        yield conn
    finally:
        if conn is not None:
            async with _pool_lock:
                _pool.append(conn)
            _pool_sem.release()


# ── Users ────────────────────────────────────────────────────────────

async def create_user(
    nickname: str,
    password_hash: str,
    height: float | None,
    weight: float | None,
    bust: float | None = None,
    waist: float | None = None,
    hip: float | None = None,
) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO users (nickname, password_hash, height, weight, bust, waist, hip) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (nickname, password_hash, height, weight, bust, waist, hip),
        )
        await db.commit()
        return cursor.lastrowid


async def get_user_by_nickname(nickname: str) -> dict | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE nickname = ?", (nickname,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_user_by_id(user_id: int) -> dict | None:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT id, nickname, height, weight, bust, waist, hip, created_at "
            "FROM users WHERE id = ?",
            (user_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None


# ── Sessions ─────────────────────────────────────────────────────────

async def create_session(token: str, user_id: int) -> None:
    async with get_db() as db:
        await db.execute(
            "INSERT INTO sessions (token, user_id, created_at) VALUES (?, ?, ?)",
            (token, user_id, time.time()),
        )
        await db.commit()


async def delete_session(token: str) -> None:
    async with get_db() as db:
        await db.execute("DELETE FROM sessions WHERE token = ?", (token,))
        await db.commit()


async def get_user_id_by_session(token: str) -> int | None:
    async with get_db() as db:
        await db.execute(
            "DELETE FROM sessions WHERE ? - created_at > ?",
            (time.time(), SESSION_MAX_AGE),
        )
        await db.commit()
        cursor = await db.execute(
            "SELECT user_id FROM sessions WHERE token = ?", (token,)
        )
        row = await cursor.fetchone()
        return row["user_id"] if row else None


# ── Conversations ────────────────────────────────────────────────────

async def save_conversation(
    user_id: int,
    role: str,
    text: str | None = None,
    image_url: str | None = None,
    style_tags: list[str] | None = None,
    scene_tags: list[str] | None = None,
) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO conversations (user_id, role, image_url, text, style_tags, scene_tags) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                user_id,
                role,
                image_url,
                text,
                json.dumps(style_tags) if style_tags else None,
                json.dumps(scene_tags) if scene_tags else None,
            ),
        )
        await db.commit()
        return cursor.lastrowid


async def get_conversations(user_id: int, limit: int = 100) -> list[dict]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM conversations WHERE user_id = ? "
            "ORDER BY created_at ASC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        results = []
        for row in rows:
            d = dict(row)
            if d.get("style_tags"):
                d["style_tags"] = json.loads(d["style_tags"])
            if d.get("scene_tags"):
                d["scene_tags"] = json.loads(d["scene_tags"])
            results.append(d)
        return results
