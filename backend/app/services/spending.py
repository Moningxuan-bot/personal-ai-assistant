import json
import uuid
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.spending import Spending
from app.models.message import Message
from app.providers.llm import LLMProvider, ChatMessage
from app.services.ajiu_voice import AjiuVoiceService, AjiuEventType, VoiceEvent


class SpendingService:
    def __init__(self, db: AsyncSession, llm: LLMProvider, voice: AjiuVoiceService | None = None):
        self.db = db
        self.llm = llm
        self.voice = voice or AjiuVoiceService(llm)

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

        if spending.chat_reaction:
            if not conversation_id:
                # 自动创建对话来承载聊天反应
                from app.models.conversation import Conversation
                conv = Conversation(title="消费记账")
                self.db.add(conv)
                await self.db.flush()
                spending.conversation_id = conv.id
            await self._deliver_chat_reaction(spending)
            await self.db.refresh(spending)

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

    async def _judge_spending(self, amount: float, category: str, note: str | None, stats: dict) -> dict:
        """判定消费是否需要聊天关注（纯逻辑判定，不生成阿玖话术）。

        文本生成全部委托给 AjiuVoiceService，确保人格统一。"""
        # ---- 第一步：调用 LLM 做纯判定（不生成话术） ----
        judgment_prompt = f"""分析这笔消费，返回 JSON 判定结果。

【消费】{category} ¥{amount} | 备注：{note or '无'}
【背景】当月同类{stats['same_category_count_month']}次/¥{stats['same_category_total']:.0f} | 本月总计¥{stats['monthly_total']:.0f} | 24h同类{stats['same_category_count_24h']}次

返回 JSON（只返回 JSON，不要其他文字）：
{{"needs_chat":true/false,"risk_level":"low|medium|high","risk_reason":"触发原因或空字符串"}}

needs_chat=true 条件：烟酒类 | 24h≥3次 | 金额>月均2倍 | 备注含冲动/忍不住/又买了/剁手
risk_level=high 条件：烟酒类 且 (24h≥3次 或 金额>月均2倍)"""

        needs_chat = category == "烟酒"  # 烟酒强制触发
        risk_level = "medium" if category == "烟酒" else "low"
        risk_reason = "smoking_frequent" if category == "烟酒" else ""

        try:
            response = await self.llm.chat(
                [ChatMessage(role="system", content=judgment_prompt)],
                stream=False,
            )
            text = response.strip()
            if text.startswith("```"): text = text.split("\n", 1)[1].rstrip("```")
            result = json.loads(text)
            if result.get("needs_chat") is True:
                needs_chat = True
            if result.get("risk_level") in ("low", "medium", "high"):
                risk_level = result["risk_level"]
            if result.get("risk_reason"):
                risk_reason = result["risk_reason"]
        except (json.JSONDecodeError, Exception):
            pass  # 使用默认判定值

        # ---- 第二步：构建结构化事件 ----
        event_payload = {
            "amount": amount,
            "category": category,
            "note": note,
            "stats": stats,
            "risk_level": risk_level,
            "risk_reason": risk_reason,
        }

        # ---- 第三步：委托 AjiuVoiceService 生成阿玖语气文本 ----
        reaction = await self.voice.render_event(VoiceEvent(
            event_type=AjiuEventType.SPENDING_REACTION,
            payload=event_payload,
        ))

        chat_reaction = ""
        if needs_chat:
            chat_reaction = await self.voice.render_event(VoiceEvent(
                event_type=AjiuEventType.SPENDING_CHAT_REACTION,
                payload=event_payload,
            ))

        return {
            "reaction": reaction,
            "needs_chat": needs_chat,
            "chat_reaction": chat_reaction,
        }

    async def _deliver_chat_reaction(self, spending: Spending) -> None:
        msg = Message(conversation_id=spending.conversation_id,
                      role="assistant", content=spending.chat_reaction)
        self.db.add(msg)
        spending.chat_delivered = True
        await self.db.commit()

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
