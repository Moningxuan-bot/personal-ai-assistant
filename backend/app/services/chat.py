import uuid
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.conversation import Conversation
from app.models.message import Message
from app.services.memory import MemoryService
from app.providers.llm import LLMProvider, ChatMessage


SYSTEM_PROMPT = """你是一个专属 AI 助手。你的风格是直接、真诚、口语化，像和老朋友聊天。
你不会回避任何话题，保持理性分析。使用中文回复。"""


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

    async def chat(
        self, user_message: str, conversation_id: uuid.UUID | None = None
    ) -> AsyncIterator[str]:
        # 1. Get or create conversation
        conv = await self._get_or_create_conversation(conversation_id)

        # 2. Retrieve relevant memories
        memories = await self.memory.retrieve_relevant(user_message)
        memory_context = "\n".join(
            f"[记忆: {m.category}] {m.content}" for m in memories
        )

        # 3. Get recent messages from this conversation
        recent = await self._get_recent_messages(conv.id, limit=20)

        # 4. Build messages array
        llm_messages = [ChatMessage(role="system", content=SYSTEM_PROMPT)]

        if memory_context:
            llm_messages.append(
                ChatMessage(role="system", content=f"相关记忆:\n{memory_context}")
            )

        for msg in recent:
            llm_messages.append(ChatMessage(role=msg.role, content=msg.content))

        llm_messages.append(ChatMessage(role="user", content=user_message))

        # 5. Save user message
        user_msg = Message(
            conversation_id=conv.id, role="user", content=user_message
        )
        self.db.add(user_msg)
        await self.db.commit()

        # 6. Stream response
        full_response = []
        stream = await self.llm.chat(llm_messages, stream=True)

        async for chunk in stream:
            full_response.append(chunk)
            yield chunk

        # 7. Save assistant message
        response_text = "".join(full_response)
        assistant_msg = Message(
            conversation_id=conv.id, role="assistant", content=response_text
        )
        self.db.add(assistant_msg)
        await self.db.commit()

        # 8. Index messages and extract memories (fire-and-forget, don't block)
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
