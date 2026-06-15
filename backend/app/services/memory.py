import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.message import Message
from app.models.memory import Memory
from app.providers.embedding import EmbeddingProvider


class MemoryService:
    def __init__(self, db: AsyncSession, embed_provider: EmbeddingProvider):
        self.db = db
        self.embed_provider = embed_provider

    async def index_message(self, message: Message) -> None:
        """Generate embedding for a message and store it."""
        vec = await self.embed_provider.embed(message.content)
        message.embedding = vec
        await self.db.commit()

    async def retrieve_relevant(
        self, query: str, limit: int = 5
    ) -> list[Memory]:
        """Vector search: find memories semantically similar to query."""
        query_vec = await self.embed_provider.embed(query)

        stmt = (
            select(Memory)
            .where(Memory.is_active == True)
            .order_by(Memory.embedding.cosine_distance(query_vec))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def retrieve_messages(
        self, query: str, limit: int = 3
    ) -> list[Message]:
        """Vector search on raw messages for recent context."""
        query_vec = await self.embed_provider.embed(query)

        stmt = (
            select(Message)
            .where(Message.embedding.is_not(None))
            .order_by(Message.embedding.cosine_distance(query_vec))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def extract_and_save_memories(
        self, message: Message, llm
    ) -> list[Memory]:
        """Ask LLM to extract facts/preferences/plans from a message."""
        from app.providers.llm import ChatMessage as CM

        prompt = CM(
            role="system",
            content=(
                "从以下用户消息中提取值得长期记住的信息。"
                "分类为: fact(事实), preference(偏好), plan(计划), general(通用)。"
                "每行一条，格式: [分类] 内容。只提取有用信息，没有就返回空。\n\n"
                f"用户消息: {message.content}"
            ),
        )
        response = await llm.chat([prompt], stream=False)

        memories = []
        for line in response.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if line.startswith("[fact]"):
                cat, content = "fact", line[6:].strip()
            elif line.startswith("[preference]"):
                cat, content = "preference", line[12:].strip()
            elif line.startswith("[plan]"):
                cat, content = "plan", line[6:].strip()
            elif line.startswith("[general]"):
                cat, content = "general", line[9:].strip()
            else:
                continue

            if content:
                vec = await self.embed_provider.embed(content)
                mem = Memory(
                    content=content,
                    embedding=vec,
                    source_message_id=message.id,
                    category=cat,
                )
                self.db.add(mem)
                memories.append(mem)

        if memories:
            await self.db.commit()
        return memories
