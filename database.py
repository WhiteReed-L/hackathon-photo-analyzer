import aiosqlite
import config


async def init_db():
    """Initialize database: create uploads dir, tables, indexes."""
    config.UPLOAD_DIR.mkdir(exist_ok=True)

    db = await aiosqlite.connect(str(config.DATABASE_PATH))
    db.row_factory = aiosqlite.Row

    await db.execute("""
        CREATE TABLE IF NOT EXISTS photos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            filename        TEXT NOT NULL UNIQUE,
            original_name   TEXT NOT NULL,
            mime_type       TEXT NOT NULL DEFAULT 'image/jpeg',
            file_size       INTEGER NOT NULL DEFAULT 0,
            created_at      TEXT NOT NULL DEFAULT (datetime('now')),
            analysis        TEXT,
            analyzed_at     TEXT
        )
    """)
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_photos_filename ON photos(filename)"
    )
    await db.execute(
        "CREATE INDEX IF NOT EXISTS idx_photos_created_at ON photos(created_at DESC)"
    )
    await db.commit()
    await db.close()


async def _get_db() -> aiosqlite.Connection:
    """Get a database connection."""
    db = await aiosqlite.connect(str(config.DATABASE_PATH))
    db.row_factory = aiosqlite.Row
    return db


async def insert_photo(
    filename: str, original_name: str, mime_type: str, file_size: int
) -> int:
    """Insert a new photo record, return its ID."""
    db = await _get_db()
    cursor = await db.execute(
        "INSERT INTO photos (filename, original_name, mime_type, file_size) "
        "VALUES (?, ?, ?, ?)",
        (filename, original_name, mime_type, file_size),
    )
    await db.commit()
    photo_id = cursor.lastrowid
    await db.close()
    return photo_id


async def get_all_photos(limit: int = 50, offset: int = 0) -> list[dict]:
    """Get paginated photo list, newest first."""
    db = await _get_db()
    cursor = await db.execute(
        "SELECT * FROM photos ORDER BY created_at DESC LIMIT ? OFFSET ?",
        (limit, offset),
    )
    rows = await cursor.fetchall()
    await db.close()
    return [dict(row) for row in rows]


async def get_photo_by_id(photo_id: int) -> dict | None:
    """Get a single photo by ID."""
    db = await _get_db()
    cursor = await db.execute("SELECT * FROM photos WHERE id = ?", (photo_id,))
    row = await cursor.fetchone()
    await db.close()
    return dict(row) if row else None


async def update_photo_analysis(photo_id: int, analysis: str) -> None:
    """Store analysis result for a photo."""
    db = await _get_db()
    await db.execute(
        "UPDATE photos SET analysis = ?, analyzed_at = datetime('now') "
        "WHERE id = ?",
        (analysis, photo_id),
    )
    await db.commit()
    await db.close()


async def get_photo_count() -> int:
    """Get total number of photos."""
    db = await _get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM photos")
    row = await cursor.fetchone()
    await db.close()
    return row[0] if row else 0
