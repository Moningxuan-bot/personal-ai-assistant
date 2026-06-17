from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.schemas.spending import SpendingCreate, SpendingResponse, SpendingStats
from app.services.spending import SpendingService
from app.services.chat import ChatService
from app.services.memory import MemoryService
from app.services.ajiu_voice import AjiuVoiceService
from app.providers.llm import DeepSeekProvider
from app.providers.embedding import embed_provider
from app.config import settings

router = APIRouter(tags=["spendings"], prefix="/spendings")

llm = DeepSeekProvider(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
voice = AjiuVoiceService(llm)


def get_spending_service(db: AsyncSession = Depends(get_db)) -> SpendingService:
    return SpendingService(db, llm, voice=voice)


def get_chat_service(db: AsyncSession = Depends(get_db)) -> ChatService:
    memory = MemoryService(db, embed_provider)
    return ChatService(db, llm, memory)


@router.post("", response_model=SpendingResponse)
async def create_spending(
    body: SpendingCreate,
    svc: SpendingService = Depends(get_spending_service),
    chat_svc: ChatService = Depends(get_chat_service),
):
    result = await svc.create_spending(body.amount, body.category, body.note, body.conversation_id)

    # 需要聊天回应 → 走 ChatService 统一人格链路
    if result.get("needs_chat"):
        event = result.get("event_payload", {})
        conversation_id = body.conversation_id
        # 无活跃对话时自动创建一个
        if not conversation_id:
            from app.models.conversation import Conversation
            conv = Conversation(title="消费记账")
            db = svc.db
            db.add(conv)
            await db.flush()
            conversation_id = conv.id
            result["conversation_id"] = str(conversation_id)

        try:
            chat_reaction = await chat_svc.respond_to_spending(event, conversation_id)
            result["chat_reaction"] = chat_reaction
            result["chat_delivered"] = True
        except Exception:
            # LLM 故障不阻塞记账
            pass

    # 清理内部字段（不在 SpendingResponse schema 中）
    result.pop("needs_chat", None)
    result.pop("event_payload", None)

    return result


@router.get("", response_model=list[SpendingResponse])
async def list_spendings(page: int = Query(1, ge=1), category: str | None = None,
                         svc: SpendingService = Depends(get_spending_service)):
    return await svc.list_spendings(page=page, category=category)


@router.get("/stats", response_model=SpendingStats)
async def spending_stats(svc: SpendingService = Depends(get_spending_service)):
    return await svc.get_stats()
