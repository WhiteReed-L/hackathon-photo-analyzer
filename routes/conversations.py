"""GET /api/conversations, POST /api/conversations/sync"""
from fastapi import APIRouter, Depends

from database import get_conversations, save_conversation
from models import SyncRequest
from routes.user import require_user

router = APIRouter()


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
