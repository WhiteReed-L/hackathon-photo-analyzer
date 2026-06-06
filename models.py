from pydantic import BaseModel


# ── Upload ───────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    id: int
    filename: str
    status: str


# ── User ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    nickname: str
    password: str
    height: float | None = None
    weight: float | None = None
    bust: float | None = None
    waist: float | None = None
    hip: float | None = None


class LoginRequest(BaseModel):
    nickname: str
    password: str


class LoginResponse(BaseModel):
    success: bool
    message: str
    user: dict | None = None


class UserProfile(BaseModel):
    id: int
    nickname: str
    height: float | None = None
    weight: float | None = None
    bust: float | None = None
    waist: float | None = None
    hip: float | None = None


# ── Generate ─────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    text: str | None = ""
    user_image_url: str | None = None        # user's own photo
    reference_image_url: str | None = None   # outfit reference photo
    clothing_tags: list[str] | None = None   # clothing type preferences
    style_tags: list[str] | None = None
    scene_tags: list[str] | None = None


class GenerateResponse(BaseModel):
    image_url: str       # compressed thumbnail for display
    original_url: str    # full-resolution image for download
    revised_prompt: str
    conversation_id: int


# ── Conversation ─────────────────────────────────────────────────────

class ConversationItem(BaseModel):
    id: int
    role: str
    image_url: str | None = None
    text: str | None = None
    style_tags: list[str] | None = None
    scene_tags: list[str] | None = None
    created_at: str


class SyncRequest(BaseModel):
    """Sync a batch of conversation entries from localStorage."""
    entries: list[dict]


# ── Error ────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
