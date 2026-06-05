from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

import config
from database import init_db
from routes import auth, upload, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: initialize database and upload directory."""
    await init_db()
    config.UPLOAD_DIR.mkdir(exist_ok=True)
    yield


app = FastAPI(
    title="Hackathon Photo Analyzer",
    description="Capture photos from camera and analyze them with AI",
    version="1.0.0",
    lifespan=lifespan,
)

# --- API Routes ---
app.include_router(auth.router, prefix="/api", tags=["Auth"])
app.include_router(upload.router, prefix="/api", tags=["Upload"])
app.include_router(admin.router, prefix="/api", tags=["Admin"])

# --- Static file mounts (order matters: /api/uploads before /) ---
config.UPLOAD_DIR.mkdir(exist_ok=True)
app.mount(
    "/api/uploads",
    StaticFiles(directory=str(config.UPLOAD_DIR)),
    name="uploads",
)

app.mount("/", StaticFiles(directory="static", html=True), name="static")
