import json
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.spending import Spending
from app.models.message import Message
from app.providers.llm import LLMProvider, ChatMessage


class SpendingService:
    def __init__(self, db: AsyncSession, llm: LLMProvider):
        self.db = db
        self.llm = llm

    async def create_spending(
        self, amount: float, category: str, note: str | None,
        conversation_id: uuid.UUID | None,
    ) -> dict:
        stats = await self._gather_stats(category)
        judgment = await self._judge_spending(amount, category, note, stats)

        spending = Spending(
            conversation_id=conversation_id,
            amount=amount, category=category, note=note,
            reaction=judgment["reaction"],
            chat_reaction=judgment.get("chat_reaction") if judgment.get("needs_chat") else None,
            chat_delivered=False,
        )
        self.db.add(spending)
        await self.db.commit()

        if spending.chat_reaction and conversation_id:
            await self._deliver_chat_reaction(spending)

        return self._to_dict(spending)

    async def list_spendings(
        self, page: int = 1, category: str | None = None, limit: int = 20
    ) -> list[dict]:
        stmt = select(Spending).order_by(Spending.created_at.desc())
        if category:
            stmt = stmt.where(Spending.category == category)
        stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(stmt)
        return [self._to_dict(s) for s in result.scalars().all()]

    async def get_stats(self) -> dict:
        now = datetime.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stmt = select(Spending).where(Spending.created_at >= month_start)
        result = await self.db.execute(stmt)
        month_spendings = result.scalars().all()

        total = float(sum(s.amount for s in month_spendings))
        by_category: dict[str, float] = {}
        for s in month_spendings:
            by_category[s.category] = by_category.get(s.category, 0) + float(s.amount)

        ajiu_comment = await self._monthly_comment(total, by_category)
        return {
            "month": now.strftime("%Y-%m"), "total": total,
            "by_category": by_category, "ajiu_comment": ajiu_comment,
        }

    # ---- internal ----

    async def _gather_stats(self, category: str) -> dict:
        now = datetime.now()
        day_ago = now - timedelta(hours=24)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        r = await self.db.execute(
            select(func.count(Spending.id)).where(
                Spending.category == category, Spending.created_at >= day_ago))
        same_24h = r.scalar() or 0

        r = await self.db.execute(
            select(func.count(Spending.id), func.coalesce(func.sum(Spending.amount), 0))
            .where(Spending.category == category, Spending.created_at >= month_start))
        row = r.one()
        same_month, same_total = row[0] or 0, float(row[1] or 0)

        r = await self.db.execute(
            select(func.coalesce(func.sum(Spending.amount), 0))
            .where(Spending.created_at >= month_start))
        monthly_total = float(r.scalar() or 0)

        return {"same_category_count_24h": same_24h, "same_category_count_month": same_month,
                "same_category_total": same_total, "monthly_total": monthly_total}

    async def _judge_spending(self, amount: float, category: str, note: str | None, stats: dict) -> dict:
        system_prompt = f"""你是阿玖——毒舌但关心用户的AI伴侣。用户刚记了一笔消费。

【上下文】当月同类{stats['same_category_count_month']}次/¥{stats['same_category_total']:.0f} | 本月总计¥{stats['monthly_total']:.0f} | 24h同类{stats['same_category_count_24h']}次

【消费】{category} ¥{amount} | 备注：{note or '无'}

返回JSON：
{{"reaction":"卡片级吐槽(1-2句，阿玖语气，必填)","needs_chat":true/false,"chat_reaction":"聊天级长篇(3-5句，needs_chat=true时必填)"}}

needs_chat=true 条件：烟酒类 | 24h≥3次 | 金额>月均2倍 | 备注含冲动/忍不住/又买了/剁手"""

        messages = [ChatMessage(role="system", content=system_prompt)]
        try:
            response = await self.llm.chat(messages, stream=False)
            text = response.strip()
            if text.startswith("```"): text = text.split("\n", 1)[1].rstrip("```")
            result = json.loads(text)
            return {"reaction": result.get("reaction", "记下了。"),
                    "needs_chat": result.get("needs_chat", False),
                    "chat_reaction": result.get("chat_reaction", "")}
        except (json.JSONDecodeError, Exception):
            return {"reaction": self._default_reaction(category, amount),
                    "needs_chat": category == "烟酒", "chat_reaction": ""}

    async def _deliver_chat_reaction(self, spending: Spending) -> None:
        msg = Message(conversation_id=spending.conversation_id,
                      role="assistant", content=spending.chat_reaction)
        self.db.add(msg)
        spending.chat_delivered = True
        await self.db.commit()

    async def _monthly_comment(self, total: float, by_category: dict[str, float]) -> str:
        top = sorted(by_category.items(), key=lambda x: x[1], reverse=True)
        detail = "\n".join(f"  {c}: ¥{a:.0f}" for c, a in top)
        prompt = f"""你是阿玖。本月消费 ¥{total:.0f}：\n{detail}\n点评(2-3句，阿玖语气)。"""
        messages = [ChatMessage(role="system", content=prompt)]
        try:
            return (await self.llm.chat(messages, stream=False)).strip()
        except Exception:
            return f"这个月花了{total:.0f}。你自己看着办吧。"

    @staticmethod
    def _default_reaction(category: str, amount: float) -> str:
        return {"餐饮": f"又花了{amount:.0f}？行吧。","交通": "出行费记下了。",
                "烟酒": f"{amount:.0f}块。……算了不说了。","购物": f"买了{amount:.0f}。开心就好。",
                "娱乐": "玩得开心~","其他": f"记下了，{amount:.0f}元。"}.get(category, f"记下了。")

    async def get_recent_context(self, hours: int = 24, limit: int = 10) -> str:
        """返回近期消费的文本摘要，供聊天上下文注入。"""
        cutoff = datetime.now() - timedelta(hours=hours)
        stmt = (select(Spending)
                .where(Spending.created_at >= cutoff)
                .order_by(Spending.created_at.desc())
                .limit(limit))
        result = await self.db.execute(stmt)
        spendings = result.scalars().all()

        if not spendings:
            return ""

        lines = ["用户最近的消费记录："]
        for s in spendings:
            lines.append(
                f"  • {s.created_at.strftime('%H:%M')} [{s.category}] ¥{float(s.amount):.0f}"
                f"{' — ' + s.note if s.note else ''}"
                f"（{s.reaction}）"
            )
        stats = await self.get_stats()
        lines.append(f"\n本月累计 ¥{stats['total']:.0f}。阿玖点评：{stats['ajiu_comment']}")
        return "\n".join(lines)

    @staticmethod
    def _to_dict(s: Spending) -> dict:
        return {"id": str(s.id), "conversation_id": str(s.conversation_id) if s.conversation_id else None,
                "amount": float(s.amount), "category": s.category, "note": s.note,
                "reaction": s.reaction, "chat_reaction": s.chat_reaction,
                "chat_delivered": s.chat_delivered, "created_at": s.created_at.isoformat()}
