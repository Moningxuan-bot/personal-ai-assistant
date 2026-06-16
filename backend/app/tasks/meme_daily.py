"""每晚 22:00 的热梗更新任务。

生产环境由外部 cron 或 scheduler 调用，不在应用进程里常驻定时器。
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.llm import LLMProvider
from app.providers.embedding import EmbeddingProvider
from app.services.memory import MemoryService
from app.services.meme import MemeService


async def run_daily_meme_fetch(
    db: AsyncSession,
    llm: LLMProvider,
    embed_provider: EmbeddingProvider,
    limit: int = 20,
) -> list:
    """抓取 B 站热门、按偏好过滤改写，并保存为待确认热梗。"""
    memory_svc = MemoryService(db, embed_provider)
    meme_svc = MemeService(db, llm)
    prefs = await memory_svc.get_preference_tags()
    raw_memes = await meme_svc.fetch_bilibili_hot(limit=limit)
    return await meme_svc.filter_rewrite_and_store(raw_memes, prefs)
