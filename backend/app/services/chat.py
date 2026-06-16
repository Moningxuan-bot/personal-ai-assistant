import json
import uuid
from datetime import datetime
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.memory import MemoryService
from app.providers.llm import LLMProvider, ChatMessage
from app.prompts.ajiu import AJIU_SYSTEM_PROMPT, MODE_PROMPTS

# 教练模式触发词
COACH_TRIGGERS = [
    "我想", "我打算", "我要不要", "能不能帮我规划",
    "帮我制定", "怎么学", "怎么开始", "帮我安排",
    "想学", "想减肥", "想锻炼", "想养成",
    "定个目标", "制定计划", "给我建议", "阿玖说正事",
]


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

    def _detect_mode(self, user_message: str) -> str:
        """检测当前交互模式：casual / coach / butler"""
        if "阿玖说正事" in user_message:
            return "coach"
        if any(kw in user_message for kw in COACH_TRIGGERS):
            return "coach"
        # TODO: 当有进行中的任务时，自动进入 butler 模式
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
        self, mode: str, memory_context: str = ""
    ) -> str:
        """组装完整 System Prompt：基础人格 + 模式 + 时间 + 记忆"""
        parts = [AJIU_SYSTEM_PROMPT]

        # 模式行为准则
        if mode in MODE_PROMPTS:
            parts.append(MODE_PROMPTS[mode])

        # 时间上下文
        parts.append(f"## 当前时间\n{self._time_context()}")

        # 相关记忆
        if memory_context:
            parts.append(f"## 关于用户的记忆\n{memory_context}")

        return "\n\n".join(parts)

    async def chat(
        self, user_message: str, conversation_id: uuid.UUID | None = None
    ) -> AsyncIterator[dict]:
        # 1. Get or create conversation
        conv = await self._get_or_create_conversation(conversation_id)

        # 2. Emit meta frame FIRST — so frontend knows the conversation_id
        mode = self._detect_mode(user_message)
        yield {"type": "meta", "conversation_id": str(conv.id), "mode": mode}

        # 3. Retrieve relevant memories
        memories = await self.memory.retrieve_relevant(user_message)
        memory_context = "\n".join(
            f"[{m.category}] {m.content}" for m in memories
        )

        # 4. Get recent messages from this conversation
        recent = await self._get_recent_messages(conv.id, limit=20)

        # 5. Build messages array — personality as system prompt
        system_prompt = self._build_system_prompt(mode, memory_context)
        llm_messages = [ChatMessage(role="system", content=system_prompt)]

        for msg in recent:
            llm_messages.append(ChatMessage(role=msg.role, content=msg.content))

        llm_messages.append(ChatMessage(role="user", content=user_message))

        # 6. Save user message
        user_msg = Message(
            conversation_id=conv.id, role="user", content=user_message
        )
        self.db.add(user_msg)
        await self.db.commit()

        # 7. Stream response tokens
        full_response = []
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

        # 9. Signal done BEFORE background work — client unblocks immediately
        yield {"type": "done"}

        # 10. Index messages and extract memories (runs after client receives done)
        try:
            await self.memory.index_message(user_msg)
            await self.memory.index_message(assistant_msg)
        except Exception:
            pass

        try:
            await self.memory.extract_and_save_memories(user_msg, self.llm)
        except Exception:
            pass

    async def _get_or_create_conversation(
        self, conversation_id: uuid.UUID | None
    ) -> Conversation:
        if conversation_id:
            stmt = select(Conversation).where(Conversation.id == conversation_id)
            result = await self.db.execute(stmt)
            conv = result.scalar_one_or_none()
            if conv:
                return conv
            # Unknown conversation_id → 404, don't silently create
            from fastapi import HTTPException
            raise HTTPException(
                status_code=404,
                detail=f"Conversation {conversation_id} not found",
            )

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
