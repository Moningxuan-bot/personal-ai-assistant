import json
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.schemas.chat import ChatRequest, MessageResponse
from app.services.chat import ChatService
from app.services.memory import MemoryService
from app.providers.llm import DeepSeekProvider
from app.providers.embedding import embed_provider
from app.config import settings

router = APIRouter(tags=["chat"])

# Singleton providers (initialized at import time)
llm_provider = DeepSeekProvider(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    memory = MemoryService(db, embed_provider)
    return ChatService(db, llm_provider, memory)


@router.post("/chat")
async def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)):
    async def event_stream():
        try:
            async for event in service.chat(
                request.message, request.conversation_id
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except HTTPException:
            raise
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.execute(
        delete(Conversation).where(Conversation.id == conversation_id)
    )
    await db.commit()
    return {"status": "deleted"}
