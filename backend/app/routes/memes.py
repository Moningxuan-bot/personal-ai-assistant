import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.database import get_db
from app.models.meme import Meme
from app.providers.llm import get_llm
from app.providers.embedding import embed_provider
from app.services.memory import MemoryService
from app.services.meme import MemeService


router = APIRouter(tags=["memes"], prefix="/memes")

llm = get_llm()


class MemeResponse(BaseModel):
    id: uuid.UUID
    title: str
    source: str
    url: str | None
    summary: str | None
    tags: str | None
    kept: bool
    discarded: bool
    asked: bool
    fetched_at: datetime

    model_config = {"from_attributes": True}


def get_meme_service(db: AsyncSession = Depends(get_db)) -> MemeService:
    return MemeService(db, llm)


@router.get("/today", response_model=list[MemeResponse])
async def today_memes(service: MemeService = Depends(get_meme_service)):
    return await service.get_today_pending()


@router.post("/fetch", response_model=list[MemeResponse])
async def fetch_memes(
    db: AsyncSession = Depends(get_db),
    service: MemeService = Depends(get_meme_service),
):
    """开发期手动触发：抓取 B 站热门并按用户偏好筛选。"""
    memory = MemoryService(db, embed_provider)
    prefs = await memory.get_preference_tags()
    raw = await service.fetch_bilibili_hot()
    return await service.filter_rewrite_and_store(raw, prefs)


@router.post("/{meme_id}/keep", response_model=MemeResponse)
async def keep_meme(
    meme_id: uuid.UUID,
    service: MemeService = Depends(get_meme_service),
):
    meme = await service.keep(meme_id)
    if not meme:
        raise HTTPException(status_code=404, detail="Meme not found")
    return meme


@router.post("/{meme_id}/discard", response_model=MemeResponse)
async def discard_meme(
    meme_id: uuid.UUID,
    service: MemeService = Depends(get_meme_service),
):
    meme = await service.discard(meme_id)
    if not meme:
        raise HTTPException(status_code=404, detail="Meme not found")
    return meme
