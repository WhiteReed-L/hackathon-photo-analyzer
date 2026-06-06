"""
Database layer — SQLite WAL + connection pool.
Tables: users, sessions, assets, conversations, generation_jobs, ai_runs.
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
SCHEMA_VERSION = "2026-architecture-v1"


async def init_db():
    config.UPLOAD_DIR.mkdir(exist_ok=True)

    global _pool, _pool_sem
    if _pool:
        await close_db()

    db = await aiosqlite.connect(str(config.DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute(f"PRAGMA busy_timeout={config.DB_BUSY_TIMEOUT_MS}")
    await db.execute("PRAGMA foreign_keys=ON")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     TEXT PRIMARY KEY,
            applied_at  TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

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
    await db.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_users_nickname_unique ON users(nickname)"
    )

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
        CREATE TABLE IF NOT EXISTS assets (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            type             TEXT NOT NULL,
            filename         TEXT NOT NULL UNIQUE,
            original_filename TEXT,
            mime_type        TEXT,
            size_bytes       INTEGER,
            width            INTEGER,
            height           INTEGER,
            source_asset_id  INTEGER,
            created_at       TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (source_asset_id) REFERENCES assets(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_assets_user ON assets(user_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversation_sessions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            path        TEXT,
            title       TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_conv_sessions_user ON conversation_sessions(user_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id           INTEGER,
            user_id              INTEGER NOT NULL,
            role                 TEXT NOT NULL,
            text                 TEXT,
            asset_id             INTEGER,
            generation_job_id    INTEGER,
            metadata_json        TEXT,
            created_at           TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES conversation_sessions(id),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (asset_id) REFERENCES assets(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_conv_messages_user ON conversation_messages(user_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS generation_jobs (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id          INTEGER NOT NULL,
            status           TEXT NOT NULL,
            input_json       TEXT NOT NULL,
            vision_result    TEXT,
            style_directive  TEXT,
            final_prompt     TEXT,
            output_asset_id  INTEGER,
            result_json      TEXT,
            style_brief_json TEXT,
            current_outfit_state_json TEXT,
            previous_job_id  INTEGER,
            error_message    TEXT,
            created_at       TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at       TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (output_asset_id) REFERENCES assets(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_generation_jobs_user ON generation_jobs(user_id)")
    cursor = await db.execute("PRAGMA table_info(generation_jobs)")
    job_columns = {row[1] for row in await cursor.fetchall()}
    if "result_json" not in job_columns:
        await db.execute("ALTER TABLE generation_jobs ADD COLUMN result_json TEXT")
    if "style_brief_json" not in job_columns:
        await db.execute("ALTER TABLE generation_jobs ADD COLUMN style_brief_json TEXT")
    if "current_outfit_state_json" not in job_columns:
        await db.execute("ALTER TABLE generation_jobs ADD COLUMN current_outfit_state_json TEXT")
    if "previous_job_id" not in job_columns:
        await db.execute("ALTER TABLE generation_jobs ADD COLUMN previous_job_id INTEGER")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS ai_runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            job_id      INTEGER,
            step        TEXT NOT NULL,
            model       TEXT,
            prompt      TEXT,
            input_json  TEXT,
            output_text TEXT,
            latency_ms  INTEGER,
            status      TEXT NOT NULL,
            error       TEXT,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (job_id) REFERENCES generation_jobs(id)
        )
    """)
    await db.execute("CREATE INDEX IF NOT EXISTS idx_ai_runs_job ON ai_runs(job_id)")

    await db.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id       INTEGER NOT NULL,
            role          TEXT NOT NULL,
            image_url     TEXT,
            text          TEXT,
            clothing_tags TEXT,
            style_tags    TEXT,
            scene_tags    TEXT,
            created_at    TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    cursor = await db.execute("PRAGMA table_info(conversations)")
    conv_columns = {row[1] for row in await cursor.fetchall()}
    if "clothing_tags" not in conv_columns:
        await db.execute("ALTER TABLE conversations ADD COLUMN clothing_tags TEXT")
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_conv_user ON conversations(user_id)"
    )

    await db.commit()
    await db.execute(
        "INSERT OR IGNORE INTO schema_migrations (version) VALUES (?)",
        (SCHEMA_VERSION,),
    )
    await db.commit()
    await db.close()

    # Warm pool
    _pool_sem = asyncio.Semaphore(config.DB_POOL_SIZE)
    for _ in range(config.DB_POOL_SIZE):
        conn = await aiosqlite.connect(str(config.DATABASE_PATH))
        conn.row_factory = aiosqlite.Row
        await conn.execute(f"PRAGMA busy_timeout={config.DB_BUSY_TIMEOUT_MS}")
        _pool.append(conn)


async def close_db():
    global _pool_sem
    for conn in _pool:
        await conn.close()
    _pool.clear()
    _pool_sem = None


@asynccontextmanager
async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    if _pool_sem is None:
        raise RuntimeError("Database pool is not initialized. Call init_db() first.")
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
    clothing_tags: list[str] | None = None,
    style_tags: list[str] | None = None,
    scene_tags: list[str] | None = None,
) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO conversations (user_id, role, image_url, text, clothing_tags, style_tags, scene_tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                user_id,
                role,
                image_url,
                text,
                json.dumps(clothing_tags) if clothing_tags else None,
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
            if d.get("clothing_tags"):
                d["clothing_tags"] = json.loads(d["clothing_tags"])
            if d.get("style_tags"):
                d["style_tags"] = json.loads(d["style_tags"])
            if d.get("scene_tags"):
                d["scene_tags"] = json.loads(d["scene_tags"])
            results.append(d)
        return results


# ── Assets ────────────────────────────────────────────────────────────

async def create_asset(
    user_id: int,
    type: str,
    filename: str,
    original_filename: str | None = None,
    mime_type: str | None = None,
    size_bytes: int | None = None,
    width: int | None = None,
    height: int | None = None,
    source_asset_id: int | None = None,
) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO assets (user_id, type, filename, original_filename, mime_type,
                                size_bytes, width, height, source_asset_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (user_id, type, filename, original_filename, mime_type, size_bytes, width, height, source_asset_id),
        )
        await db.commit()
        return cursor.lastrowid


async def get_asset(asset_id: int) -> dict | None:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,))
        row = await cursor.fetchone()
        return dict(row) if row else None


async def get_asset_by_filename(filename: str) -> dict | None:
    async with get_db() as db:
        cursor = await db.execute("SELECT * FROM assets WHERE filename = ?", (filename,))
        row = await cursor.fetchone()
        return dict(row) if row else None


# ── Generation jobs / AI runs ─────────────────────────────────────────

async def create_generation_job(user_id: int, input_data: dict, status: str = "running") -> int:
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO generation_jobs (user_id, status, input_json) VALUES (?, ?, ?)",
            (user_id, status, json.dumps(input_data, ensure_ascii=False)),
        )
        await db.commit()
        return cursor.lastrowid


async def get_generation_job(job_id: int, user_id: int | None = None) -> dict | None:
    async with get_db() as db:
        if user_id is None:
            cursor = await db.execute("SELECT * FROM generation_jobs WHERE id = ?", (job_id,))
        else:
            cursor = await db.execute("SELECT * FROM generation_jobs WHERE id = ? AND user_id = ?", (job_id, user_id))
        row = await cursor.fetchone()
        if not row:
            return None
        d = dict(row)
        if d.get("input_json"):
            d["input_json"] = json.loads(d["input_json"])
        if d.get("result_json"):
            d["result_json"] = json.loads(d["result_json"])
        if d.get("style_brief_json"):
            d["style_brief_json"] = json.loads(d["style_brief_json"])
        if d.get("current_outfit_state_json"):
            d["current_outfit_state_json"] = json.loads(d["current_outfit_state_json"])
        return d


async def update_generation_job(job_id: int, **fields) -> None:
    allowed = {"status", "vision_result", "style_directive", "final_prompt", "output_asset_id", "result_json", "style_brief_json", "current_outfit_state_json", "previous_job_id", "error_message"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    updates["updated_at"] = "datetime('now')"
    set_parts = []
    values = []
    for key, value in updates.items():
        if key == "updated_at":
            set_parts.append("updated_at = datetime('now')")
        else:
            set_parts.append(f"{key} = ?")
            if key in ("result_json", "style_brief_json", "current_outfit_state_json") and isinstance(value, dict):
                value = json.dumps(value, ensure_ascii=False)
            values.append(value)
    values.append(job_id)
    async with get_db() as db:
        await db.execute(f"UPDATE generation_jobs SET {', '.join(set_parts)} WHERE id = ?", values)
        await db.commit()


async def record_ai_run(
    step: str,
    status: str,
    job_id: int | None = None,
    model: str | None = None,
    prompt: str | None = None,
    input_data: dict | None = None,
    output_text: str | None = None,
    latency_ms: int | None = None,
    error: str | None = None,
) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO ai_runs (job_id, step, model, prompt, input_json, output_text, latency_ms, status, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (job_id, step, model, prompt, json.dumps(input_data, ensure_ascii=False) if input_data else None,
             output_text, latency_ms, status, error),
        )
        await db.commit()
        return cursor.lastrowid


# ── Conversation sessions/messages ───────────────────────────────────

async def create_conversation_session(user_id: int, path: str | None = None, title: str | None = None) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            "INSERT INTO conversation_sessions (user_id, path, title) VALUES (?, ?, ?)",
            (user_id, path, title),
        )
        await db.commit()
        return cursor.lastrowid


async def list_conversation_sessions(user_id: int) -> list[dict]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM conversation_sessions WHERE user_id = ? ORDER BY updated_at DESC",
            (user_id,),
        )
        return [dict(row) for row in await cursor.fetchall()]


async def save_conversation_message(
    user_id: int,
    role: str,
    session_id: int | None = None,
    text: str | None = None,
    asset_id: int | None = None,
    generation_job_id: int | None = None,
    metadata: dict | None = None,
) -> int:
    async with get_db() as db:
        cursor = await db.execute(
            """
            INSERT INTO conversation_messages
            (session_id, user_id, role, text, asset_id, generation_job_id, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (session_id, user_id, role, text, asset_id, generation_job_id,
             json.dumps(metadata, ensure_ascii=False) if metadata else None),
        )
        if session_id:
            await db.execute("UPDATE conversation_sessions SET updated_at = datetime('now') WHERE id = ? AND user_id = ?", (session_id, user_id))
        await db.commit()
        return cursor.lastrowid


async def list_conversation_messages(user_id: int, session_id: int) -> list[dict]:
    async with get_db() as db:
        cursor = await db.execute(
            "SELECT * FROM conversation_messages WHERE user_id = ? AND session_id = ? ORDER BY created_at ASC",
            (user_id, session_id),
        )
        results = []
        for row in await cursor.fetchall():
            d = dict(row)
            if d.get("metadata_json"):
                d["metadata"] = json.loads(d.pop("metadata_json"))
            results.append(d)
        return results
