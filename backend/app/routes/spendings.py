from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.schemas.spending import SpendingCreate, SpendingResponse, SpendingStats
from app.services.spending import SpendingService
from app.providers.llm import DeepSeekProvider
from app.config import settings

router = APIRouter(tags=["spendings"], prefix="/spendings")

llm = DeepSeekProvider(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)


def get_service(db: AsyncSession = Depends(get_db)) -> SpendingService:
    return SpendingService(db, llm)


@router.post("", response_model=SpendingResponse)
async def create_spending(body: SpendingCreate, svc=Depends(get_service)):
    return await svc.create_spending(body.amount, body.category, body.note, body.conversation_id)


@router.get("", response_model=list[SpendingResponse])
async def list_spendings(page: int = Query(1, ge=1), category: str | None = None,
                         svc=Depends(get_service)):
    return await svc.list_spendings(page=page, category=category)


@router.get("/stats", response_model=SpendingStats)
async def spending_stats(svc=Depends(get_service)):
    return await svc.get_stats()
