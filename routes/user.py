import hashlib
import secrets
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request, Response
import bcrypt

import config
from database import (
    create_session,
    create_user,
    delete_session,
    get_user_by_id,
    get_user_by_nickname,
    get_user_id_by_session,
)
from limiter import limiter
from models import LoginRequest, LoginResponse, RegisterRequest, UserProfile

router = APIRouter()

SESSION_MAX_AGE = 86400


def _hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _verify_password(password: str, stored_hash: str) -> bool:
    if stored_hash.startswith("$2"):
        return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
    # Backward compatibility for legacy SHA256 hashes.
    return hashlib.sha256(password.encode()).hexdigest() == stored_hash


# ── Register ─────────────────────────────────────────────────────────

@router.post("/user/register", response_model=LoginResponse)
@limiter.limit(config.AUTH_RATE_LIMIT)
async def register(request: Request, body: RegisterRequest, response: Response):
    if not body.nickname or not body.password:
        raise HTTPException(status_code=400, detail="昵称和密码不能为空")
    if len(body.password) < 8:
        raise HTTPException(status_code=400, detail="密码至少需要 8 位")

    existing = await get_user_by_nickname(body.nickname)
    if existing:
        raise HTTPException(status_code=409, detail="昵称已被注册")

    try:
        user_id = await create_user(
            nickname=body.nickname,
            password_hash=_hash_password(body.password),
            height=body.height or 0,
            weight=body.weight or 0,
            bust=body.bust,
            waist=body.waist,
            hip=body.hip,
        )
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="昵称已被注册")

    token = secrets.token_urlsafe(32)
    await create_session(token, user_id)
    response.set_cookie(
        key="fashion_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=config.COOKIE_SECURE,
        max_age=SESSION_MAX_AGE,
    )

    user = await get_user_by_id(user_id)
    return LoginResponse(success=True, message="注册成功", user=user)


# ── Login ────────────────────────────────────────────────────────────

@router.post("/user/login", response_model=LoginResponse)
@limiter.limit(config.AUTH_RATE_LIMIT)
async def login(request: Request, body: LoginRequest, response: Response):
    user = await get_user_by_nickname(body.nickname)
    if not user or not _verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="昵称或密码错误")

    token = secrets.token_urlsafe(32)
    await create_session(token, user["id"])
    response.set_cookie(
        key="fashion_token",
        value=token,
        httponly=True,
        samesite="strict",
        secure=config.COOKIE_SECURE,
        max_age=SESSION_MAX_AGE,
    )

    profile = await get_user_by_id(user["id"])
    return LoginResponse(success=True, message="登录成功", user=profile)


# ── Logout ───────────────────────────────────────────────────────────

@router.post("/user/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("fashion_token")
    if token:
        await delete_session(token)
    response.delete_cookie(key="fashion_token", path="/", httponly=True, samesite="strict", secure=config.COOKIE_SECURE)
    return {"success": True, "message": "已登出"}


# ── Me ───────────────────────────────────────────────────────────────

@router.get("/user/me", response_model=UserProfile)
async def me(request: Request):
    token = request.cookies.get("fashion_token")
    if not token:
        raise HTTPException(status_code=403, detail="未登录")
    user_id = await get_user_id_by_session(token)
    if not user_id:
        raise HTTPException(status_code=403, detail="登录已过期")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


# ── Shared dependency ────────────────────────────────────────────────

async def require_user(request: Request) -> int:
    """Return user_id if authenticated, raise 403 otherwise."""
    token = request.cookies.get("fashion_token")
    if not token:
        raise HTTPException(status_code=403, detail="未登录")
    user_id = await get_user_id_by_session(token)
    if not user_id:
        raise HTTPException(status_code=403, detail="登录已过期")
    return user_id
