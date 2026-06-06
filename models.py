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
    # New explicit image semantics. Legacy fields below remain supported.
    user_photo_url: str | None = None        # user's own photo for identity/base edit
    outfit_reference_url: str | None = None  # outfit/clothing reference, not the person to edit
    base_image_url: str | None = None        # current image to edit, e.g. previous result
    previous_result_url: str | None = None   # previous generated result for multi-turn editing
    user_image_url: str | None = None        # legacy alias for user_photo_url
    reference_image_url: str | None = None   # legacy alias for outfit_reference_url/base image in old clients
    path: str | None = None                  # "a" strict reference try-on, "b" inspiration generation
    reference_strength: str | None = None    # "strict" or "inspiration"
    previous_job_id: int | None = None
    chat_intent: dict | None = None
    patch: dict | None = None
    constraints: dict | None = None
    clothing_tags: list[str] | None = None   # clothing type preferences
    style_tags: list[str] | None = None
    scene_tags: list[str] | None = None


class GenerateResponse(BaseModel):
    image_url: str       # compressed thumbnail for display
    original_url: str    # full-resolution image for download
    revised_prompt: str
    description: str     # user-facing outfit description (color, style, material)
    conversation_id: int
    job_id: int | None = None


class GenerationJobCreateResponse(BaseModel):
    job_id: int
    status: str


class GenerationJobStatusResponse(BaseModel):
    job_id: int
    status: str
    result: dict | None = None
    error_message: str | None = None


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


# ── Chat ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    text: str
    history: list[dict] | None = None
    path: str | None = None                 # "a" or "b"
    clothing_tags: list[str] | None = None
    style_tags: list[str] | None = None
    scene_tags: list[str] | None = None


class ChatResponse(BaseModel):
    action: str   # "reply" or "generate"
    text: str
    intent: str | None = None
    patch: dict | None = None
    constraints: dict | None = None
    prompt: str | None = None  # legacy compatibility


# ── Error ────────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    detail: str
