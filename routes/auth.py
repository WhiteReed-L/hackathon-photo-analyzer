import secrets
import time

from fastapi import APIRouter, HTTPException, Request, Response

import config
from models import LoginRequest, LoginResponse

router = APIRouter()

# In-memory session store: token -> created_timestamp
_active_sessions: dict[str, float] = {}

SESSION_MAX_AGE = 86400  # 24 hours in seconds


def _cleanup_expired_sessions():
    """Remove tokens older than SESSION_MAX_AGE."""
    now = time.time()
    expired = [t for t, ts in _active_sessions.items() if now - ts > SESSION_MAX_AGE]
    for t in expired:
        del _active_sessions[t]


@router.post("/admin/login", response_model=LoginResponse)
async def admin_login(body: LoginRequest, response: Response):
    if body.password != config.ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Invalid password")

    _cleanup_expired_sessions()

    token = secrets.token_urlsafe(32)
    _active_sessions[token] = time.time()
    response.set_cookie(
        key="admin_token",
        value=token,
        httponly=True,
        samesite="strict",
        max_age=SESSION_MAX_AGE,
    )
    return LoginResponse(success=True, message="Logged in")


@router.post("/admin/logout")
async def admin_logout(request: Request, response: Response):
    """Clear session on server side and remove cookie."""
    token = request.cookies.get("admin_token")
    if token and token in _active_sessions:
        del _active_sessions[token]

    response.delete_cookie(
        key="admin_token",
        path="/",
        httponly=True,
        samesite="strict",
    )
    return {"success": True, "message": "Logged out"}


@router.get("/admin/check")
async def admin_check(request: Request):
    token = request.cookies.get("admin_token")
    _cleanup_expired_sessions()
    return {"authenticated": token in _active_sessions}


async def require_admin(request: Request):
    """Dependency: require valid admin session."""
    token = request.cookies.get("admin_token")
    _cleanup_expired_sessions()
    if token not in _active_sessions:
        raise HTTPException(status_code=403, detail="Not authenticated")
    return True
