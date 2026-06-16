import json
import uuid
from datetime import datetime
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.goal import Goal
from app.services.memory import MemoryService
from app.services.coach import CoachEngine
from app.providers.llm import LLMProvider, ChatMessage
from app.prompts.ajiu import AJIU_SYSTEM_PROMPT, CONTRADICTION_PROMPT, MODE_PROMPTS

# 教练模式触发词
COACH_TRIGGERS = [
    "我想", "我打算", "我要不要", "能不能帮我规划",
    "帮我制定", "怎么学", "怎么开始", "帮我安排",
    "想学", "想减肥", "想锻炼", "想养成",
    "定个目标", "制定计划", "给我建议", "阿玖说正事",
]

# 确认词
CONFIRM_WORDS = {"行", "可以", "好", "ok", "嗯", "确认", "没问题", "就这样", "对的", "是的"}

# 拒绝词（明确不要这个计划）
REJECT_WORDS = {"不行", "不要", "不好", "算了", "重新来", "重来", "取消", "不对", "不", "no"}


class ChatService:
    def __init__(
        self,
        db: AsyncSession,
        llm: LLMProvider,
        memory: MemoryService,
    ):
        self.db = db
        self.llm = llm
        self.memory = memory
        self.coach = CoachEngine(llm)

    def _detect_mode(
        self, user_message: str, coach_state: dict | None = None
    ) -> str:
        """检测当前交互模式：casual / coach / butler"""
        # 如果教练对话进行中，保持教练模式
        if coach_state and coach_state.get("active"):
            return "coach"
        if "阿玖说正事" in user_message:
            return "coach"
        if any(kw in user_message for kw in COACH_TRIGGERS):
            return "coach"
        return "casual"

    def _time_context(self) -> str:
        """根据当前时间生成时间上下文"""
        hour = datetime.now().hour
        if 5 <= hour < 9:
            return "现在是清晨。如果用户刚醒，可以打个招呼，问问他今天的计划。语气轻快一点。"
        elif 9 <= hour < 12:
            return "现在是上午。用户可能在摸鱼，你可以随口问他在干嘛。"
        elif 12 <= hour < 14:
            return "现在是中午。可以关心一下用户有没有好好吃饭。"
        elif 14 <= hour < 18:
            return "现在是下午。如果用户有任务没完成，可以念叨两句。"
        elif 18 <= hour < 22:
            return "现在是晚上。用户可能刚下班或放学，语气可以轻松一点。"
        elif 22 <= hour < 24:
            return "现在是深夜。你按惯例去搜 B 站梗了。用户如果还在线，催他早点睡。"
        else:
            return "现在是凌晨。这么晚不睡？念叨他两句，但别太凶——他可能在熬夜赶工。"

    def _build_system_prompt(
        self,
        mode: str,
        memory_context: str = "",
        spending_context: str = "",
        meme_context: str = "",
        contradiction_context: str = "",
    ) -> str:
        """组装完整 System Prompt：基础人格 + 模式 + 时间 + 记忆 + 消费 + 热梗"""
        parts = [AJIU_SYSTEM_PROMPT]

        if mode in MODE_PROMPTS:
            parts.append(MODE_PROMPTS[mode])

        parts.append(f"## 当前时间\n{self._time_context()}")

        if memory_context:
            parts.append(f"## 关于用户的记忆\n{memory_context}")

        if spending_context:
            parts.append(
                f"## 用户近期消费\n{spending_context}\n\n"
                f"你可以根据这些消费记录自然地和用户聊天。比如他说「昨天花了多少」"
                f"你就去翻记录。看到烟酒消费可以念叨两句。"
            )

        if meme_context:
            parts.append(meme_context)

        if contradiction_context:
            parts.append(contradiction_context)

        return "\n\n".join(parts)

    async def chat(
        self, user_message: str, conversation_id: uuid.UUID | None = None
    ) -> AsyncIterator[dict]:
        # 1. Get or create conversation
        conv = await self._get_or_create_conversation(conversation_id)

        # 2. Detect mode (consider existing coach state)
        mode = self._detect_mode(user_message, conv.coach_state)
        yield {
            "type": "meta",
            "conversation_id": str(conv.id),
            "mode": mode,
            "coach_state": conv.coach_state,
        }

        # 3. Save user message
        user_msg = Message(
            conversation_id=conv.id, role="user", content=user_message
        )
        self.db.add(user_msg)
        await self.db.commit()

        # ================================================
        # 教练模式 — CoachEngine 接管
        # ================================================
        if mode == "coach":
            async for event in self._handle_coach_mode(conv, user_message, user_msg):
                yield event
            return

        # ================================================
        # 闲聊模式 — 正常 LLM 对话
        # ================================================
        contradiction_mockery = ""
        contradiction_prompt = ""
        memory_extracted = False
        try:
            await self.memory.extract_and_save_memories(user_msg, self.llm)
            memory_extracted = True
            if self.memory.last_contradictions:
                contradiction_mockery = self._build_contradiction_mockery(
                    self.memory.last_contradictions[0]
                )
                max_count = max(
                    item.get("count", 0) for item in self.memory.last_contradictions
                )
                contradiction_prompt = CONTRADICTION_PROMPT.format(count=max_count)
        except Exception:
            pass

        # 4. Retrieve relevant memories
        memories = await self.memory.retrieve_relevant(user_message)
        memory_context = "\n".join(
            f"[{m.category}] {m.content}" for m in memories
        )

        # 4.5. Fetch recent spending context for casual chat
        from app.services.spending import SpendingService
        spending_svc = SpendingService(self.db, self.llm)
        spending_context = await spending_svc.get_recent_context(hours=24, limit=5)

        from app.services.meme import MemeService
        meme_svc = MemeService(self.db, self.llm)
        meme_context = await meme_svc.get_kept_today_context(limit=5)

        # 5. Get recent messages
        recent = await self._get_recent_messages(conv.id, limit=20)

        # 6. Build messages array
        system_prompt = self._build_system_prompt(
            mode,
            memory_context,
            spending_context,
            meme_context,
            contradiction_prompt,
        )
        llm_messages = [ChatMessage(role="system", content=system_prompt)]

        for msg in recent:
            llm_messages.append(ChatMessage(role=msg.role, content=msg.content))

        llm_messages.append(ChatMessage(role="user", content=user_message))

        # 7. Stream response tokens
        full_response = []
        if contradiction_mockery:
            full_response.append(contradiction_mockery)
            yield {"type": "delta", "content": contradiction_mockery}

        stream = await self.llm.chat(llm_messages, stream=True)

        async for chunk in stream:
            full_response.append(chunk)
            yield {"type": "delta", "content": chunk}

        # 8. Save assistant message
        response_text = "".join(full_response)
        assistant_msg = Message(
            conversation_id=conv.id, role="assistant", content=response_text
        )
        self.db.add(assistant_msg)
        await self.db.commit()

        # 9. Signal done
        yield {"type": "done"}

        # 10. Background indexing
        try:
            await self.memory.index_message(user_msg)
            await self.memory.index_message(assistant_msg)
        except Exception:
            pass
        if not memory_extracted:
            try:
                await self.memory.extract_and_save_memories(user_msg, self.llm)
            except Exception:
                pass

    def _build_contradiction_mockery(self, contradiction: dict) -> str:
        """把矛盾检测结果变成阿玖开场吐槽。"""
        new = contradiction.get("new") or "刚才那套新说法"
        old = contradiction.get("old") or "之前那套说法"
        count = contradiction.get("count") or 1
        return (
            f"等下——你说你{new}？不对啊，我记得你之前明明说{old}的。"
            f"这是第{count}次变了。真是多变的笨蛋。\n\n"
        )

    # ---------- 教练模式 ----------

    async def _handle_coach_mode(
        self,
        conv: Conversation,
        user_message: str,
        user_msg: Message,
    ) -> AsyncIterator[dict]:
        """处理教练模式消息：可能是回答教练问题，也可能是确认/拒绝计划。"""
        coach_state = conv.coach_state

        # 检测是否是计划确认/拒绝/修改
        if coach_state and coach_state.get("pending_plan"):
            if self._is_confirmation(user_message) and len(user_message.strip()) <= 5:
                # 明确简短的确认词 → 确认
                result = await self.coach.confirm_plan(coach_state, True)
                await self._save_coach_result(conv, user_msg, result)
                async for event in self._emit_coach_responses(result):
                    yield event
                return
            elif self._is_rejection(user_message):
                # 明确的拒绝词 → 重开
                result = await self.coach.confirm_plan(coach_state, False)
                await self._save_coach_result(conv, user_msg, result)
                async for event in self._emit_coach_responses(result):
                    yield event
                return
            else:
                # 既不是确认也不是拒绝 → 用户的修改意见，让 LLM 修订计划
                result = await self.coach.revise_plan(coach_state, user_message)
                await self._save_coach_result(conv, user_msg, result)
                async for event in self._emit_coach_responses(result):
                    yield event
                return

        # 正常教练流程
        result = await self.coach.process(user_message, coach_state)
        await self._save_coach_result(conv, user_msg, result)
        async for event in self._emit_coach_responses(result):
            yield event

    async def _save_coach_result(
        self, conv: Conversation, user_msg: Message, result: dict
    ) -> None:
        """持久化教练结果：更新 coach_state、存 assistant message、创建 Goal。"""
        # Update coach state on conversation
        conv.coach_state = result["coach_state"]
        flag_modified(conv, "coach_state")

        # Save assistant message
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=result["message"],
        )
        self.db.add(assistant_msg)
        await self.db.commit()

        # Create goal if plan confirmed
        if result["action"] == "confirmed" and result.get("goal"):
            goal_data = result["goal"]
            goal = Goal(
                conversation_id=conv.id,
                title=goal_data["title"],
                description=goal_data["description"],
                milestones=goal_data.get("milestones", []),
                status="active",
            )
            self.db.add(goal)
            await self.db.commit()

        # Background indexing
        try:
            await self.memory.index_message(user_msg)
            await self.memory.index_message(assistant_msg)
        except Exception:
            pass

    async def _emit_coach_responses(self, result: dict) -> AsyncIterator[dict]:
        """把教练结果转换为 SSE delta 事件。"""
        message = result["message"]

        # 模拟流式输出：按句子拆分，逐句 yield
        # （简单实现：直接整个 message 作为 delta，对教练模式够用）
        yield {"type": "delta", "content": message}

        # 附带 coach_state 更新和 action 信息
        yield {
            "type": "done",
            "coach_action": result["action"],
            "coach_state": result["coach_state"],
        }

    def _is_confirmation(self, text: str) -> bool:
        """检测用户消息是否为确认。"""
        cleaned = text.strip().lower().rstrip("。！!？?.")
        return cleaned in CONFIRM_WORDS or len(cleaned) <= 2

    def _is_rejection(self, text: str) -> bool:
        """检测用户消息是否为明确拒绝。"""
        cleaned = text.strip().lower().rstrip("。！!？?.")
        # 单字拒绝或短拒绝词
        if cleaned in REJECT_WORDS:
            return True
        # "不行，..." 也算拒绝
        if any(cleaned.startswith(w) for w in REJECT_WORDS if len(w) >= 2):
            return True
        return False

    async def _get_or_create_conversation(
        self, conversation_id: uuid.UUID | None
    ) -> Conversation:
        if conversation_id:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await self.db.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                return conv
            # Unknown conversation_id — route layer should pre-validate and return 404
            raise ValueError(f"Conversation {conversation_id} not found")

        # Only create new conversation when no ID provided
        conv = Conversation()
        self.db.add(conv)
        await self.db.commit()
        return conv

    async def _get_recent_messages(
        self, conversation_id: uuid.UUID, limit: int = 20
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(reversed(result.scalars().all()))
