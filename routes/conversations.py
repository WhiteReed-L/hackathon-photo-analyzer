"""Conversation history endpoints."""
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import (
    create_conversation_session,
    get_conversations,
    list_conversation_messages,
    list_conversation_sessions,
    save_conversation,
    save_conversation_message,
)
from models import SyncRequest
from routes.user import require_user

router = APIRouter()


class ConversationSessionRequest(BaseModel):
    path: str | None = None
    title: str | None = None


class ConversationMessageRequest(BaseModel):
    role: str
    text: str | None = None
    asset_id: int | None = None
    generation_job_id: int | None = None
    metadata: dict | None = None


@router.get("/conversations")
async def list_conversations(user_id: int = Depends(require_user)):
    conversations = await get_conversations(user_id)
    return {"conversations": conversations}


@router.post("/conversations/sync")
async def sync_conversations(
    body: SyncRequest,
    user_id: int = Depends(require_user),
):
    """Accept a batch of entries from localStorage, save to DB."""
    synced = 0
    for entry in body.entries:
        await save_conversation(
            user_id=user_id,
            role=entry.get("role", "user"),
            text=entry.get("text"),
            image_url=entry.get("image_url"),
            clothing_tags=entry.get("clothing_tags"),
            style_tags=entry.get("style_tags"),
            scene_tags=entry.get("scene_tags"),
        )
        synced += 1
    return {"synced": synced}


@router.post("/conversation-sessions")
async def create_session(
    body: ConversationSessionRequest,
    user_id: int = Depends(require_user),
):
    session_id = await create_conversation_session(user_id, path=body.path, title=body.title)
    return {"id": session_id}


@router.get("/conversation-sessions")
async def list_sessions(user_id: int = Depends(require_user)):
    return {"sessions": await list_conversation_sessions(user_id)}


@router.get("/conversation-sessions/{session_id}/messages")
async def list_messages(session_id: int, user_id: int = Depends(require_user)):
    return {"messages": await list_conversation_messages(user_id, session_id)}


@router.post("/conversation-sessions/{session_id}/messages")
async def create_message(
    session_id: int,
    body: ConversationMessageRequest,
    user_id: int = Depends(require_user),
):
    message_id = await save_conversation_message(
        user_id=user_id,
        session_id=session_id,
        role=body.role,
        text=body.text,
        asset_id=body.asset_id,
        generation_job_id=body.generation_job_id,
        metadata=body.metadata,
    )
    return {"id": message_id}
