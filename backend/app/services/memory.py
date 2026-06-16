import json
import uuid
import re
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified
from app.models.message import Message
from app.models.memory import Memory
from app.providers.embedding import EmbeddingProvider


class MemoryService:
    def __init__(self, db: AsyncSession, embed_provider: EmbeddingProvider):
        self.db = db
        self.embed_provider = embed_provider
        self.last_contradictions: list[dict] = []

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

    async def get_preference_tags(self) -> list[str]:
        """从偏好记忆中提取阿玖用于筛选热梗的标签。"""
        stmt = (
            select(Memory)
            .where(Memory.category == "preference", Memory.is_active == True)
            .order_by(Memory.created_at.desc())
        )
        result = await self.db.execute(stmt)

        tags: list[str] = []
        seen: set[str] = set()
        for memory in result.scalars().all():
            for tag in self._split_preference_tags(memory.content):
                if tag and tag not in seen:
                    seen.add(tag)
                    tags.append(tag)
        return tags

    @staticmethod
    def _split_preference_tags(content: str) -> list[str]:
        """把“喜欢游戏、科技”这类偏好句子粗略拆成标签。"""
        cleaned = content
        for prefix in ("用户喜欢", "喜欢", "偏好标签：", "偏好标签:", "偏好"):
            cleaned = cleaned.replace(prefix, "")
        parts = re.split(r"[,，、；;\s和]+", cleaned)
        stop_words = {"用户", "的", "和", "以及", "感兴趣", "不喜欢"}
        return [
            part.strip()
            for part in parts
            if part.strip() and part.strip() not in stop_words
        ]

    async def extract_and_save_memories(
        self, message: Message, llm
    ) -> list[Memory]:
        """Ask LLM to extract facts/preferences/plans from a message."""
        from app.providers.llm import ChatMessage as CM

        self.last_contradictions = []

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
                contradiction = await self._find_contradiction(
                    content, cat, vec, llm
                )
                history = None
                count = 0
                topic = None
                if contradiction:
                    old_mem = contradiction["memory"]
                    topic = contradiction["topic"]
                    count = old_mem.contradiction_count + 1
                    history = list(old_mem.contradiction_history or [])
                    history.append(
                        {
                            "old": contradiction["old"],
                            "new": contradiction["new"],
                            "at": datetime.now(timezone.utc).isoformat(),
                        }
                    )
                    old_mem.is_active = False
                    old_mem.contradiction_topic = topic
                    old_mem.contradiction_count = count
                    old_mem.contradiction_history = history
                    flag_modified(old_mem, "contradiction_history")

                    if count >= 3:
                        self.last_contradictions.append(
                            {
                                "trigger_mockery": True,
                                "topic": topic,
                                "old": contradiction["old"],
                                "new": contradiction["new"],
                                "count": count,
                            }
                        )

                mem = Memory(
                    content=content,
                    embedding=vec,
                    source_message_id=message.id,
                    category=cat,
                    contradiction_topic=topic,
                    contradiction_count=count,
                    contradiction_history=history,
                )
                self.db.add(mem)
                memories.append(mem)

        if memories:
            await self.db.commit()
        return memories

    async def _find_contradiction(
        self, content: str, category: str, vec: list[float], llm
    ) -> dict | None:
        """用 LLM 判断新记忆是否推翻了同类旧记忆。"""
        if category not in {"fact", "preference", "plan"}:
            return None

        stmt = (
            select(Memory)
            .where(Memory.category == category, Memory.is_active == True)
            .order_by(Memory.embedding.cosine_distance(vec))
            .limit(5)
        )
        result = await self.db.execute(stmt)

        for old_mem in result.scalars().all():
            if old_mem.content == content:
                continue
            verdict = await self._judge_contradiction(
                old_mem.content, content, category, llm
            )
            if verdict.get("contradicts") is True:
                return {
                    "memory": old_mem,
                    "topic": verdict.get("topic") or old_mem.contradiction_topic or category,
                    "old": verdict.get("old") or old_mem.content,
                    "new": verdict.get("new") or content,
                }
        return None

    async def _judge_contradiction(
        self, old_content: str, new_content: str, category: str, llm
    ) -> dict:
        """让模型只返回 JSON，避免把普通补充误判成矛盾。"""
        from app.providers.llm import ChatMessage as CM

        prompt = CM(
            role="system",
            content=(
                "判断两条长期记忆是否在同一话题上互相矛盾。"
                "只有新说法明确推翻旧说法时才算矛盾；补充信息、范围变窄、无关事实都不算。"
                "只返回 JSON，不要解释。格式："
                '{"contradicts": true, "topic": "喜欢的颜色", '
                '"old": "用户喜欢蓝色", "new": "用户喜欢红色"}'
                ' 或 {"contradicts": false}。\n\n'
                f"分类: {category}\n旧记忆: {old_content}\n新记忆: {new_content}"
            ),
        )
        response = await llm.chat([prompt], stream=False)
        try:
            data = json.loads(response.strip())
        except (TypeError, json.JSONDecodeError):
            return {"contradicts": False}
        if not isinstance(data, dict):
            return {"contradicts": False}
        return data
