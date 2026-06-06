import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "dall-e-3")
IMAGE_QUALITY = os.getenv("IMAGE_QUALITY", "auto")
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
DATABASE_PATH = BASE_DIR / os.getenv("DATABASE_PATH", "photos.db")
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Rate limiting
UPLOAD_RATE_LIMIT = os.getenv("UPLOAD_RATE_LIMIT", "30/minute")

# Database
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
DB_BUSY_TIMEOUT_MS = int(os.getenv("DB_BUSY_TIMEOUT_MS", "5000"))
