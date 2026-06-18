import logging
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.spending import Spending
from app.providers.llm import LLMProvider
from app.services.ajiu_voice import AjiuVoiceService, AjiuEventType, VoiceEvent

logger = logging.getLogger("ajiur.spending")


class SpendingService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, voice: AjiuVoiceService | None = None):
        self.db = db
        self.llm = llm
        self.voice = voice or AjiuVoiceService(llm)

    async def create_spending(
        self, amount: float, category: str, note: str | None,
        conversation_id: uuid.UUID | None,
    ) -> dict:
        """保存消费记录 + 卡片级反应。不生成聊天回复。

        聊天回复统一由 ChatService.respond_to_spending() 通过
        AJIU_SYSTEM_PROMPT 完整链路生成——不在此处写 assistant 消息。"""
        stats = await self._gather_stats(category)
        needs_chat = await self._needs_chat_check(category, stats, note)

        # 卡片级 reaction（短确认，≤80 字）
        reaction = await self.voice.render_event(VoiceEvent(
            event_type=AjiuEventType.SPENDING_REACTION,
            payload={
                "amount": amount, "category": category, "note": note,
                "stats": stats,
            },
        ))

        spending = Spending(
            conversation_id=conversation_id,
            amount=amount, category=category, note=note,
            reaction=reaction,
            chat_reaction=None,  # 聊天回复由 ChatService 统一生成
            chat_delivered=False,
        )
        self.db.add(spending)
        await self.db.commit()
        await self.db.refresh(spending)

        logger.info(
            f"spending_created id={spending.id} category={category} "
            f"amount={amount:.0f} needs_chat={needs_chat}",
            extra={
                "extra_fields": {
                    "spending_id": str(spending.id),
                    "spending_category": category,
                    "spending_amount": amount,
                    "spending_needs_chat": needs_chat,
                },
            },
        )

        return {
            **self._to_dict(spending),
            "needs_chat": needs_chat,
            "event_payload": {
                "amount": amount, "category": category, "note": note,
                "same_category_count_24h": stats["same_category_count_24h"],
            },
        }

    async def list_spendings(
        self, page: int = 1, category: str | None = None, limit: int = 20
    ) -> list[dict]:
        stmt = select(Spending).order_by(Spending.created_at.desc())
        if category:
            stmt = stmt.where(Spending.category == category)
        stmt = stmt.offset((page - 1) * limit).limit(limit)
        result = await self.db.execute(stmt)
        return [self._to_dict(s) for s in result.scalars().all()]

    async def get_stats(self, include_comment: bool = True) -> dict:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        # SQL 聚合，不拉全月数据到 Python 内存
        r = await self.db.execute(
            select(func.coalesce(func.sum(Spending.amount), 0))
            .where(Spending.created_at >= month_start))
        total = float(r.scalar() or 0)

        r = await self.db.execute(
            select(Spending.category, func.sum(Spending.amount))
            .where(Spending.created_at >= month_start)
            .group_by(Spending.category))
        by_category: dict[str, float] = {row[0]: float(row[1]) for row in r.all()}

        ajiu_comment = await self._monthly_comment(total, by_category) if include_comment else ""
        return {
            "month": now.strftime("%Y-%m"), "total": total,
            "by_category": by_category, "ajiu_comment": ajiu_comment,
        }

    # ---- internal ----

    async def _gather_stats(self, category: str) -> dict:
        now = datetime.now(timezone.utc)
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

    async def _needs_chat_check(
        self, category: str, stats: dict, note: str | None
    ) -> bool:
        """简单判定：这笔消费是否需要触发阿玖聊天回应。

        烟酒类 → 总是需要。高频/冲动备注 → 需要。
        不再调用 LLM——判定逻辑规则化即可。"""
        if category == "烟酒":
            return True
        # 24h 内同类 ≥3 次 → 触发
        if stats.get("same_category_count_24h", 0) >= 3:
            return True
        # 备注含冲动关键词 → 触发
        if note and any(w in note for w in ("冲动", "忍不住", "又买了", "剁手")):
            return True
        return False

    async def _monthly_comment(self, total: float, by_category: dict[str, float]) -> str:
        return await self.voice.render_event(VoiceEvent(
            event_type=AjiuEventType.SPENDING_MONTHLY_COMMENT,
            payload={"total": total, "by_category": by_category},
        ))

    async def get_recent_context(self, hours: int = 24, limit: int = 10) -> str:
        """返回近期消费的文本摘要，供聊天上下文注入。"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
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
        stats = await self.get_stats(include_comment=False)
        lines.append(f"\n本月累计 ¥{stats['total']:.0f}")
        return "\n".join(lines)

    @staticmethod
    def _to_dict(s: Spending) -> dict:
        return {"id": str(s.id), "conversation_id": str(s.conversation_id) if s.conversation_id else None,
                "amount": float(s.amount), "category": s.category, "note": s.note,
                "reaction": s.reaction, "chat_reaction": s.chat_reaction,
                "chat_delivered": s.chat_delivered, "created_at": s.created_at.isoformat()}
