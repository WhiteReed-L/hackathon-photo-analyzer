import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "dall-e-3")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4o")
OPENAI_TEXT_MODEL = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o")
OPENAI_CHAT_MODEL = os.getenv("OPENAI_CHAT_MODEL", "gpt-4o")
OPENAI_CHAT_BASE_URL = os.getenv("OPENAI_CHAT_BASE_URL", os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"))
OPENAI_CHAT_API_KEY = os.getenv("OPENAI_CHAT_API_KEY", os.getenv("OPENAI_API_KEY", ""))
OPENAI_TIMEOUT_SECONDS = float(os.getenv("OPENAI_TIMEOUT_SECONDS", "120"))
OPENAI_MAX_RETRIES = int(os.getenv("OPENAI_MAX_RETRIES", "2"))
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "auto")
IMAGE_SIZE = os.getenv("IMAGE_SIZE", "1024x1536")
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "photos.db")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}
COOKIE_SECURE = os.getenv("COOKIE_SECURE", "false").lower() == "true"
MAX_IMAGE_PIXELS = int(os.getenv("MAX_IMAGE_PIXELS", "25000000"))

# Rate limiting
UPLOAD_RATE_LIMIT = os.getenv("UPLOAD_RATE_LIMIT", "30/minute")
AUTH_RATE_LIMIT = os.getenv("AUTH_RATE_LIMIT", "10/minute")
GENERATE_RATE_LIMIT = os.getenv("GENERATE_RATE_LIMIT", "5/minute")
CHAT_RATE_LIMIT = os.getenv("CHAT_RATE_LIMIT", "30/minute")

# Database
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_BUSY_TIMEOUT_MS = int(os.getenv("DB_BUSY_TIMEOUT_MS", "5000"))


def validate_config() -> None:
    """Fail fast for configuration errors that would otherwise surface at runtime."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is required")
    if DB_POOL_SIZE < 1:
        raise RuntimeError("DB_POOL_SIZE must be at least 1")
    if MAX_UPLOAD_SIZE_MB < 1:
        raise RuntimeError("MAX_UPLOAD_SIZE_MB must be at least 1")
    if MAX_IMAGE_PIXELS < 1_000_000:
        raise RuntimeError("MAX_IMAGE_PIXELS is too small")
