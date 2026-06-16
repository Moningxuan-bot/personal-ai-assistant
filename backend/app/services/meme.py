import json
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.meme import Meme
from app.providers.llm import ChatMessage, LLMProvider


class MemeService:
    """阿玖的 B 站热梗抓取、筛选和留存服务。"""

    def __init__(self, db: AsyncSession, llm: LLMProvider):
        self.db = db
        self.llm = llm

    async def fetch_bilibili_hot(self, limit: int = 20) -> list[dict]:
        """调用 B 站热门 API 获取原始热梗候选。"""
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                "https://api.bilibili.com/x/web-interface/popular",
                params={"ps": min(limit, 50)},
                headers={"User-Agent": "Mozilla/5.0"},
            )
            data = resp.json()
            if data.get("code") != 0:
                raise RuntimeError(f"Bilibili API error: {data.get('message')}")

            return [
                {
                    "title": item["title"],
                    "url": f"https://www.bilibili.com/video/{item['bvid']}",
                    "tags": item.get("tname", ""),
                    "summary": (item.get("desc") or "")[:200],
                }
                for item in data.get("data", {}).get("list", [])
            ]

    async def filter_rewrite_and_store(
        self, memes: list[dict], prefs: list[str] | None = None
    ) -> list[Meme]:
        """用 LLM 按偏好过滤并改写热梗，然后写入待询问列表。"""
        candidates = await self._remove_discarded(memes)
        if not candidates:
            return []

        rewritten = await self._filter_and_rewrite(candidates, prefs or [])
        saved: list[Meme] = []
        for item in await self._remove_discarded(rewritten):
            meme = Meme(
                title=item["title"],
                source="bilibili",
                url=item.get("url"),
                summary=item.get("summary"),
                tags=item.get("tags"),
                asked=False,
                kept=False,
                discarded=False,
                fetched_at=datetime.now(timezone.utc),
            )
            self.db.add(meme)
            saved.append(meme)

        if saved:
            await self.db.commit()
        return saved

    async def get_today_pending(self) -> list[Meme]:
        """获取今天抓到、还没问用户要不要留的梗。"""
        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        stmt = (
            select(Meme)
            .where(
                Meme.fetched_at >= today,
                Meme.asked == False,
                Meme.discarded == False,
            )
            .order_by(Meme.fetched_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_kept_today_context(self, limit: int = 5) -> str:
        """获取今天已保留、可自然注入闲聊的热梗文本。"""
        today = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        stmt = (
            select(Meme)
            .where(
                Meme.fetched_at >= today,
                Meme.kept == True,
                Meme.discarded == False,
            )
            .order_by(Meme.fetched_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        memes = list(result.scalars().all())
        if not memes:
            return ""

        lines = ["## 今天的热梗"]
        for meme in memes:
            summary = meme.summary or "这个梗今天挺热，适合闲聊时顺手提一下。"
            lines.append(f"- [{meme.title}] {summary}")
        lines.append("\n你可以在闲聊中自然地提到这些梗，但不要生硬地背诵。")
        return "\n".join(lines)

    async def keep(self, meme_id) -> Meme | None:
        """保留一个梗，后续可注入闲聊。"""
        meme = await self.db.get(Meme, meme_id)
        if not meme:
            return None
        meme.kept = True
        meme.discarded = False
        meme.asked = True
        await self.db.commit()
        return meme

    async def discard(self, meme_id) -> Meme | None:
        """永久丢弃一个梗，不再展示。"""
        meme = await self.db.get(Meme, meme_id)
        if not meme:
            return None
        meme.kept = False
        meme.discarded = True
        meme.asked = True
        await self.db.commit()
        return meme

    async def _remove_discarded(self, memes: list[dict]) -> list[dict]:
        titles = [m.get("title") for m in memes if m.get("title")]
        urls = [m.get("url") for m in memes if m.get("url")]
        if not titles and not urls:
            return memes

        stmt = select(Meme).where(
            Meme.discarded == True,
            (Meme.title.in_(titles)) | (Meme.url.in_(urls)),
        )
        result = await self.db.execute(stmt)
        discarded = result.scalars().all()
        discarded_titles = {m.title for m in discarded}
        discarded_urls = {m.url for m in discarded if m.url}
        return [
            meme
            for meme in memes
            if meme.get("title") not in discarded_titles
            and meme.get("url") not in discarded_urls
        ]

    async def _filter_and_rewrite(self, memes: list[dict], prefs: list[str]) -> list[dict]:
        """让 LLM 一次性完成偏好过滤和阿玖式改写。"""
        if not prefs:
            return memes

        prompt = ChatMessage(
            role="system",
            content=(
                "你是阿玖，正在帮用户筛选 B 站热梗。\n"
                f"用户偏好标签：{', '.join(prefs)}\n"
                "候选热梗 JSON：\n"
                f"{json.dumps(memes, ensure_ascii=False)}\n\n"
                "请只返回 JSON 数组，每项包含 title/url/tags/summary。"
                "只保留和用户偏好相关的内容，summary 用阿玖口吻改写成 1-2 句中文。"
            ),
        )

        try:
            response = await self.llm.chat([prompt], stream=False)
            text = response.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                if text.endswith("```"):
                    text = text[:-3]
            parsed = json.loads(text)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return memes
