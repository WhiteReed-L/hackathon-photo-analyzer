from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

import config
from database import close_db, init_db
from limiter import limiter


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.validate_config()
    await init_db()
    config.UPLOAD_DIR.mkdir(exist_ok=True)
    yield
    await close_db()


app = FastAPI(
    title="Fashion AI Assistant",
    description="AI-powered fashion outfit generator",
    version="2.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── API Routes ──────────────────────────────────────────────────────
from routes import conversations, chat, generate, upload, user

app.include_router(user.router, prefix="/api", tags=["User"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(generate.router, prefix="/api", tags=["Generate"])
app.include_router(chat.router, prefix="/api", tags=["Chat"])
app.include_router(conversations.router, prefix="/api", tags=["Conversations"])

# ── Static file mounts (order matters) ──────────────────────────────
config.UPLOAD_DIR.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory="static", html=True), name="static")
