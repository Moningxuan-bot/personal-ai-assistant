# 个人专属 AI 助手 — Phase 1 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 搭建一个可用的基础 AI 助手：Flutter APP（安卓 + Windows）+ Python 后端（香港 VPS）+ DeepSeek API + 无限记忆系统。

**Architecture:** Flutter 前端 ↔ HTTPS ↔ FastAPI 后端（Docker Compose 部署）↔ PostgreSQL + pgvector（存储和向量检索）↔ DeepSeek API（对话）。Provider 抽象层预留未来扩展。

**Tech Stack:** Python 3.12 + FastAPI + SQLAlchemy + pgvector + DeepSeek API + Flutter 3.x + Dart + Riverpod + Dio + Docker Compose

**Target:** 2-3 周完成，交付可用的聊天 APP。

---

## 文件结构

```
个人API应用/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                     # FastAPI 入口，路由注册
│   │   ├── config.py                   # 环境变量配置
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── database.py             # SQLAlchemy 异步引擎 + Base
│   │   │   ├── conversation.py         # 对话会话表
│   │   │   ├── message.py              # 消息表 + 嵌入向量
│   │   │   └── memory.py               # 长期记忆表
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   └── chat.py                 # Pydantic 请求/响应模型
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                 # DeepSeek 聊天（含记忆注入）
│   │   │   └── memory.py               # 记忆提取 + 向量检索
│   │   ├── providers/
│   │   │   ├── __init__.py
│   │   │   ├── llm.py                  # LLM Provider 抽象 + DeepSeek 实现
│   │   │   └── embedding.py            # Embedding Provider 抽象
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py                 # /chat 路由
│   │   │   └── health.py               # /health 健康检查
│   │   ├── middleware/
│   │   │   ├── __init__.py
│   │   │   └── auth.py                 # 设备认证中间件
│   │   └── utils/
│   │       └── __init__.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py                 # 异步测试 fixtures
│   │   ├── test_chat.py
│   │   └── test_memory.py
│   ├── alembic/                        # 数据库迁移
│   │   ├── env.py
│   │   └── versions/
│   ├── alembic.ini
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── requirements.txt
│   └── .env.example
├── app/                                # Flutter 项目
│   ├── lib/
│   │   ├── main.dart                   # 入口
│   │   ├── app.dart                    # MaterialApp 配置
│   │   ├── core/
│   │   │   ├── api_client.dart         # Dio HTTP 客户端
│   │   │   └── theme.dart             # Apple 风格主题定义
│   │   ├── models/
│   │   │   └── chat_message.dart       # 消息模型
│   │   ├── providers/
│   │   │   └── chat_provider.dart      # Riverpod 状态管理
│   │   ├── screens/
│   │   │   ├── chat_screen.dart        # 聊天主界面
│   │   │   └── settings_screen.dart    # 设置页面
│   │   └── widgets/
│   │       ├── chat_bubble.dart        # 聊天气泡组件
│   │       └── message_input.dart      # 输入栏组件
│   ├── pubspec.yaml
│   └── analysis_options.yaml
└── docs/
    └── superpowers/
        ├── specs/
        └── plans/
```

---

### Task 1: 项目脚手架 — 后端

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/.env.example`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/main.py`

- [ ] **Step 1: 创建 requirements.txt**

```bash
cd "D:/Claude code/个人API应用"
mkdir -p backend/app
```

写入 `backend/requirements.txt`：

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
sqlalchemy[asyncio]==2.0.35
asyncpg==0.30.0
pgvector==0.3.0
alembic==1.13.0
python-dotenv==1.0.1
httpx==0.27.0
pydantic==2.9.0
pydantic-settings==2.5.0
sse-starlette==2.1.0
```

- [ ] **Step 2: 创建 .env.example**

写入 `backend/.env.example`：

```env
# 服务器配置
HOST=0.0.0.0
PORT=8000

# 数据库
DATABASE_URL=postgresql+asyncpg://aiuser:aipass@db:5432/aiassistant

# DeepSeek API
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com

# 设备认证
DEVICE_SECRET=change-me-to-a-random-string

# 记忆配置
MEMORY_RETRIEVAL_COUNT=5
```

- [ ] **Step 3: 创建 config.py**

写入 `backend/app/config.py`：

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    host: str = "0.0.0.0"
    port: int = 8000
    database_url: str = "postgresql+asyncpg://aiuser:aipass@db:5432/aiassistant"

    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"

    # Auth
    device_secret: str = "change-me"

    # Memory
    memory_retrieval_count: int = 5

    class Config:
        env_file = ".env"

settings = Settings()
```

- [ ] **Step 4: 创建 main.py**

写入 `backend/app/main.py`：

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.middleware.auth import AuthMiddleware
from app.routes import chat, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: verify DB connection
    from app.models.database import engine
    async with engine.begin() as conn:
        await conn.run_sync(lambda _: None)
    yield
    # Shutdown
    await engine.dispose()


app = FastAPI(title="Personal AI Assistant", version="0.1.0", lifespan=lifespan)

app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router, prefix="/api")
```

- [ ] **Step 5: Commit**

```bash
cd "D:/Claude code/个人API应用"
git init
git add backend/
git commit -m "feat: scaffold backend project structure"
```

---

### Task 2: 数据库模型 + 异步引擎

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/database.py`
- Create: `backend/app/models/conversation.py`
- Create: `backend/app/models/message.py`
- Create: `backend/app/models/memory.py`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 创建数据库引擎**

写入 `backend/app/models/__init__.py`（空文件）。

写入 `backend/app/models/database.py`：

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        try:
            yield session
        finally:
            await session.close()
```

- [ ] **Step 2: 创建 conversation model**

写入 `backend/app/models/conversation.py`：

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from app.models.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), default="新对话")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
```

- [ ] **Step 3: 创建 message model（含 pgvector）**

写入 `backend/app/models/message.py`：

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.models.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(20))  # "user" or "assistant"
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(1536), nullable=True  # DeepSeek embedding dimension
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    conversation = relationship("Conversation", back_populates="messages")
```

- [ ] **Step 4: 创建 memory model**

写入 `backend/app/models/memory.py`：

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from pgvector.sqlalchemy import Vector
from app.models.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    category: Mapped[str] = mapped_column(String(50), default="general")
    # "fact", "preference", "plan", "general"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
```

- [ ] **Step 5: 创建 conftest.py**

写入 `backend/tests/conftest.py`：

```python
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.models.database import Base

TEST_DATABASE_URL = "postgresql+asyncpg://aitest:aitest@localhost:5432/aitest"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture(autouse=True)
async def setup_db():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
```

- [ ] **Step 6: 更新 models/__init__.py**

写入 `backend/app/models/__init__.py`：

```python
from app.models.database import Base, engine, async_session, get_db
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.memory import Memory

__all__ = ["Base", "engine", "async_session", "get_db", "Conversation", "Message", "Memory"]
```

- [ ] **Step 7: Commit**

```bash
git add backend/
git commit -m "feat: add database models with pgvector support"
```

---

### Task 3: Provider 抽象层

**Files:**
- Create: `backend/app/providers/__init__.py`
- Create: `backend/app/providers/llm.py`
- Create: `backend/app/providers/embedding.py`

- [ ] **Step 1: 创建 LLM Provider 抽象**

写入 `backend/app/providers/__init__.py`（空文件）。

写入 `backend/app/providers/llm.py`：

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncIterator


@dataclass
class ChatMessage:
    role: str  # "system", "user", "assistant"
    content: str


class LLMProvider(ABC):
    """Abstract LLM provider — swap DeepSeek for Claude/OpenAI/etc."""

    @abstractmethod
    async def chat(
        self, messages: list[ChatMessage], stream: bool = False
    ) -> str | AsyncIterator[str]:
        """Send messages, return full response or stream chunks."""
        ...

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Convert text to embedding vector."""
        ...


class DeepSeekProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=60.0,
            )
        return self._client

    async def chat(
        self, messages: list[ChatMessage], stream: bool = False
    ) -> str | AsyncIterator[str]:
        client = self._get_client()
        body = {
            "model": "deepseek-chat",
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "stream": stream,
        }
        if stream:
            return self._stream_chat(client, body)
        else:
            resp = await client.post("/v1/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def _stream_chat(self, client, body):
        async def generate():
            async with client.stream("POST", "/v1/chat/completions", json=body) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        import json
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
        return generate()

    async def embed(self, text: str) -> list[float]:
        """DeepSeek doesn't have a dedicated embedding API yet.
        Use a lightweight local model as fallback, or delegate to EmbeddingProvider."""
        raise NotImplementedError("Use EmbeddingProvider for embeddings")
```

- [ ] **Step 2: 创建 Embedding Provider**

写入 `backend/app/providers/embedding.py`：

```python
from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):
    """Abstract embedding provider — local model or API."""

    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        ...


class SentenceTransformerProvider(EmbeddingProvider):
    """Local embedding using sentence-transformers (lightweight, free)."""

    def __init__(self, model_name: str = "BAAI/bge-small-zh-v1.5"):
        self.model_name = model_name
        self._model = None

    def _load_model(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(self.model_name)
        return self._model

    async def embed(self, text: str) -> list[float]:
        import asyncio
        model = self._load_model()
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, model.encode, text)
        return result.tolist()

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import asyncio
        model = self._load_model()
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, model.encode, texts)
        return [r.tolist() for r in results]
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/providers/
git commit -m "feat: add LLM and embedding provider abstractions"
```

---

### Task 4: 聊天服务 + 记忆服务

**Files:**
- Create: `backend/app/schemas/__init__.py`
- Create: `backend/app/schemas/chat.py`
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/chat.py`
- Create: `backend/app/services/memory.py`
- Create: `backend/app/utils/__init__.py`

- [ ] **Step 1: 创建 Pydantic schemas**

写入 `backend/app/schemas/chat.py`：

```python
import uuid
from datetime import datetime
from pydantic import BaseModel


class ChatRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    message: str
    stream: bool = True


class ChatChunk(BaseModel):
    content: str
    done: bool = False


class MessageResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

- [ ] **Step 2: 创建记忆服务**

写入 `backend/app/services/memory.py`：

```python
import uuid
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.message import Message
from app.models.memory import Memory
from app.providers.embedding import EmbeddingProvider


class MemoryService:
    def __init__(self, db: AsyncSession, embed_provider: EmbeddingProvider):
        self.db = db
        self.embed = embed_provider

    async def index_message(self, message: Message) -> None:
        """Generate embedding for a message and store it."""
        vec = await self.embed.embed(message.content)
        message.embedding = vec
        await self.db.commit()

    async def retrieve_relevant(
        self, query: str, limit: int = 5
    ) -> list[Memory]:
        """Vector search: find memories semantically similar to query."""
        query_vec = await self.embed.embed(query)

        # Cosine similarity search via pgvector
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
        """Vector search on raw messages (for recent context)."""
        query_vec = await self.embed.embed(query)

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
            if not line.strip():
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
                vec = await self.embed.embed(content)
                mem = Memory(
                    content=content,
                    embedding=vec,
                    source_message_id=message.id,
                    category=cat,
                )
                self.db.add(mem)
                memories.append(mem)

        await self.db.commit()
        return memories
```

- [ ] **Step 3: 创建聊天服务**

写入 `backend/app/services/chat.py`：

```python
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

        # 8. Index both messages for vector search (async, fire-and-forget)
        # In production, run via background task
        try:
            await self.memory.index_message(user_msg)
            await self.memory.index_message(assistant_msg)
        except Exception:
            pass  # Don't block chat if indexing fails

        # 9. Extract memories from user message (async)
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
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/services/ backend/app/schemas/ backend/app/utils/
git commit -m "feat: add chat service with memory retrieval and indexing"
```

---

### Task 5: API 路由 + 认证中间件

**Files:**
- Create: `backend/app/routes/__init__.py`
- Create: `backend/app/routes/chat.py`
- Create: `backend/app/routes/health.py`
- Create: `backend/app/middleware/__init__.py`
- Create: `backend/app/middleware/auth.py`

- [ ] **Step 1: 创建健康检查路由**

写入 `backend/app/routes/health.py`：

```python
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    return {"status": "ok", "version": "0.1.0"}
```

- [ ] **Step 2: 创建认证中间件**

写入 `backend/app/middleware/auth.py`：

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from app.config import settings


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Skip health check
        if request.url.path == "/health":
            return await call_next(request)

        # Verify device token in header
        auth_header = request.headers.get("X-Device-Token", "")
        if auth_header != settings.device_secret:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized: invalid device token"},
            )

        return await call_next(request)
```

- [ ] **Step 3: 创建聊天路由**

写入 `backend/app/routes/chat.py`：

```python
import uuid
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.schemas.chat import ChatRequest, ConversationResponse, MessageResponse
from app.services.chat import ChatService
from app.services.memory import MemoryService
from app.providers.llm import DeepSeekProvider
from app.providers.embedding import SentenceTransformerProvider
from app.config import settings

router = APIRouter(tags=["chat"])

# Singleton providers (initialized at startup)
llm_provider = DeepSeekProvider(
    api_key=settings.deepseek_api_key,
    base_url=settings.deepseek_base_url,
)
embed_provider = SentenceTransformerProvider()


def get_chat_service(db: AsyncSession = Depends(get_db)):
    memory = MemoryService(db, embed_provider)
    return ChatService(db, llm_provider, memory)


@router.post("/chat")
async def chat(request: ChatRequest, service: ChatService = Depends(get_chat_service)):
    async def event_stream():
        try:
            async for chunk in service.chat(
                request.message, request.conversation_id
            ):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/conversations/{conversation_id}/messages")
async def get_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select
    from app.models.message import Message

    stmt = (
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return [MessageResponse.model_validate(m) for m in messages]


@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import select, delete
    from app.models.conversation import Conversation

    stmt = select(Conversation).where(Conversation.id == conversation_id)
    result = await db.execute(stmt)
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    await db.execute(
        delete(Conversation).where(Conversation.id == conversation_id)
    )
    await db.commit()
    return {"status": "deleted"}
```

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/ backend/app/middleware/
git commit -m "feat: add chat API routes with SSE streaming and device auth"
```

---

### Task 6: Docker Compose + 数据库迁移

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/docker-compose.yml`
- Create: `backend/alembic.ini`
- Create: `backend/alembic/env.py`

- [ ] **Step 1: 创建 Dockerfile**

写入 `backend/Dockerfile`：

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

写入 `backend/docker-compose.yml`：

```yaml
version: "3.9"

services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: aiuser
      POSTGRES_PASSWORD: aipass
      POSTGRES_DB: aiassistant
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U aiuser -d aiassistant"]
      interval: 5s
      timeout: 3s
      retries: 5

  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
    restart: unless-stopped

volumes:
  pgdata:
```

- [ ] **Step 3: 初始化 Alembic**

```bash
cd "D:/Claude code/个人API应用/backend"
pip install alembic
alembic init alembic
```

修改 `backend/alembic/env.py`（关键部分）：

```python
from app.models.database import Base
from app.models import Conversation, Message, Memory

target_metadata = Base.metadata

# Use async engine
from app.config import settings
config.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", ""))
```

- [ ] **Step 4: 生成初始迁移**

```bash
cd "D:/Claude code/个人API应用/backend"
alembic revision --autogenerate -m "initial schema"
```

- [ ] **Step 5: Commit**

```bash
git add backend/Dockerfile backend/docker-compose.yml backend/alembic.ini backend/alembic/
git commit -m "feat: add Docker Compose deployment and database migrations"
```

---

### Task 7: Flutter 项目初始化 + 主题

**Files:**
- Create: `app/pubspec.yaml`
- Create: `app/analysis_options.yaml`
- Create: `app/lib/main.dart`
- Create: `app/lib/app.dart`
- Create: `app/lib/core/theme.dart`
- Create: `app/lib/core/api_client.dart`

- [ ] **Step 1: 创建 Flutter 项目**

```bash
cd "D:/Claude code/个人API应用"
flutter create --org com.personal --project-name ai_assistant app
cd app
```

- [ ] **Step 2: 更新 pubspec.yaml**

替换 `app/pubspec.yaml` 的 dependencies：

```yaml
name: ai_assistant
description: Personal AI Assistant
publish_to: 'none'
version: 0.1.0+1

environment:
  sdk: '>=3.5.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter
  dio: ^5.7.0
  flutter_riverpod: ^2.6.0
  riverpod_annotation: ^2.6.0
  uuid: ^4.5.0
  intl: ^0.19.0
  flutter_secure_storage: ^9.2.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^4.0.0
  riverpod_generator: ^2.6.0
  build_runner: ^2.4.0
  custom_lint: ^0.7.0
  riverpod_lint: ^2.6.0
```

运行 `flutter pub get`。

- [ ] **Step 3: 创建 Apple 风格主题**

写入 `app/lib/core/theme.dart`：

```dart
import 'package:flutter/material.dart';

class AppTheme {
  // Apple-style colors
  static const Color background = Color(0xFFF5F5F7);
  static const Color surface = Color(0xFFFFFFFF);
  static const Color primaryGradientStart = Color(0xFF5E5CE6);
  static const Color primaryGradientEnd = Color(0xFF7B79FF);
  static const Color textPrimary = Color(0xFF3A3A3C);
  static const Color textSecondary = Color(0xFFAEAEB2);
  static const Color border = Color(0x0F000000);
  static const Color onlineGreen = Color(0xFF34C759);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: background,
      fontFamily: 'SF Pro Display',
      colorScheme: ColorScheme.light(
        primary: primaryGradientStart,
        surface: surface,
        onSurface: textPrimary,
        outline: border,
      ),
      appBarTheme: const AppBarTheme(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: false,
      ),
      cardTheme: CardThemeData(
        color: surface,
        elevation: 0,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(16),
          side: BorderSide(color: border, width: 1),
        ),
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: border),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: BorderSide(color: border),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(16),
          borderSide: const BorderSide(color: primaryGradientStart),
        ),
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
    );
  }
}
```

- [ ] **Step 4: 创建 API 客户端**

写入 `app/lib/core/api_client.dart`：

```dart
import 'package:dio/dio.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class ApiClient {
  late final Dio _dio;
  final _storage = const FlutterSecureStorage();

  ApiClient({required String baseUrl}) {
    _dio = Dio(BaseOptions(
      baseUrl: baseUrl,
      connectTimeout: const Duration(seconds: 10),
      receiveTimeout: const Duration(seconds: 60),
    ));

    _dio.interceptors.add(InterceptorsWrapper(
      onRequest: (options, handler) async {
        final token = await _storage.read(key: 'device_token') ?? '';
        options.headers['X-Device-Token'] = token;
        handler.next(options);
      },
    ));
  }

  Future<String> get deviceToken async =>
      await _storage.read(key: 'device_token') ?? '';

  Future<void> setDeviceToken(String token) async =>
      await _storage.write(key: 'device_token', token);

  Stream<String> chatStream(String message, String? conversationId) async* {
    final response = await _dio.post(
      '/api/chat',
      data: {
        'message': message,
        'conversation_id': conversationId,
        'stream': true,
      },
      options: Options(responseType: ResponseType.stream),
    );

    await for (final chunk in response.data.stream) {
      final text = String.fromCharCodes(chunk);
      for (final line in text.split('\n')) {
        if (line.startsWith('data: ') && !line.contains('[DONE]')) {
          yield line.substring(6);
        }
      }
    }
  }

  Future<List<Map<String, dynamic>>> getMessages(String conversationId) async {
    final response = await _dio.get('/api/conversations/$conversationId/messages');
    return List<Map<String, dynamic>>.from(response.data);
  }

  Future<void> deleteConversation(String conversationId) async {
    await _dio.delete('/api/conversations/$conversationId');
  }
}
```

- [ ] **Step 5: 创建 main.dart 和 app.dart**

写入 `app/lib/main.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'app.dart';

void main() {
  runApp(const ProviderScope(child: MyApp()));
}
```

写入 `app/lib/app.dart`：

```dart
import 'package:flutter/material.dart';
import 'core/theme.dart';
import 'screens/chat_screen.dart';

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI 助手',
      theme: AppTheme.lightTheme,
      debugShowCheckedModeBanner: false,
      home: const ChatScreen(),
    );
  }
}
```

- [ ] **Step 6: Commit**

```bash
git add app/
git commit -m "feat: initialize Flutter project with Apple-style theme and API client"
```

---

### Task 8: Flutter 聊天界面

**Files:**
- Create: `app/lib/models/chat_message.dart`
- Create: `app/lib/providers/chat_provider.dart`
- Create: `app/lib/widgets/chat_bubble.dart`
- Create: `app/lib/widgets/message_input.dart`
- Create: `app/lib/screens/chat_screen.dart`
- Create: `app/lib/screens/settings_screen.dart`

- [ ] **Step 1: 创建消息模型**

写入 `app/lib/models/chat_message.dart`：

```dart
class ChatMessage {
  final String id;
  final String role; // "user" or "assistant"
  final String content;
  final DateTime createdAt;
  final bool isStreaming;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.createdAt,
    this.isStreaming = false,
  });

  bool get isUser => role == 'user';

  ChatMessage copyWith({String? content, bool? isStreaming}) {
    return ChatMessage(
      id: id,
      role: role,
      content: content ?? this.content,
      createdAt: createdAt,
      isStreaming: isStreaming ?? this.isStreaming,
    );
  }
}
```

- [ ] **Step 2: 创建聊天 Provider**

写入 `app/lib/providers/chat_provider.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:uuid/uuid.dart';
import '../core/api_client.dart';
import '../models/chat_message.dart';

final apiClientProvider = Provider<ApiClient>((ref) {
  // During dev, use localhost. In prod, configure via settings.
  return ApiClient(baseUrl: 'http://10.0.2.2:8000'); // Android emulator
});

final chatProvider =
    StateNotifierProvider<ChatNotifier, List<ChatMessage>>((ref) {
  return ChatNotifier(ref.watch(apiClientProvider));
});

class ChatNotifier extends StateNotifier<List<ChatMessage>> {
  final ApiClient _api;
  final _uuid = const Uuid();
  String? _conversationId;

  ChatNotifier(this._api) : super([]);

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    // Add user message
    final userMsg = ChatMessage(
      id: _uuid.v4(),
      role: 'user',
      content: text,
      createdAt: DateTime.now(),
    );
    state = [...state, userMsg];

    // Add placeholder for assistant
    final assistantId = _uuid.v4();
    final assistantMsg = ChatMessage(
      id: assistantId,
      role: 'assistant',
      content: '',
      createdAt: DateTime.now(),
      isStreaming: true,
    );
    state = [...state, assistantMsg];

    try {
      final buffer = StringBuffer();
      final stream = _api.chatStream(text, _conversationId);

      await for (final chunk in stream) {
        buffer.write(chunk);
        state = state.map((m) {
          if (m.id == assistantId) {
            return m.copyWith(content: buffer.toString());
          }
          return m;
        }).toList();
      }

      // Mark streaming complete
      state = state.map((m) {
        if (m.id == assistantId) {
          return m.copyWith(isStreaming: false);
        }
        return m;
      }).toList();
    } catch (e) {
      state = state.map((m) {
        if (m.id == assistantId) {
          return m.copyWith(content: '错误: $e', isStreaming: false);
        }
        return m;
      }).toList();
    }
  }

  void clearChat() {
    state = [];
    _conversationId = null;
  }
}
```

- [ ] **Step 3: 创建聊天气泡组件**

写入 `app/lib/widgets/chat_bubble.dart`：

```dart
import 'package:flutter/material.dart';
import '../core/theme.dart';
import '../models/chat_message.dart';

class ChatBubble extends StatelessWidget {
  final ChatMessage message;

  const ChatBubble({super.key, required this.message});

  @override
  Widget build(BuildContext context) {
    final isUser = message.isUser;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) ...[
            Container(
              width: 32,
              height: 32,
              decoration: const BoxDecoration(
                gradient: LinearGradient(
                  colors: [AppTheme.primaryGradientStart, AppTheme.primaryGradientEnd],
                ),
                borderRadius: BorderRadius.all(Radius.circular(10)),
              ),
              child: const Center(
                child: Text('✦', style: TextStyle(color: Colors.white, fontSize: 14)),
              ),
            ),
            const SizedBox(width: 8),
          ],
          Flexible(
            child: Container(
              constraints: BoxConstraints(
                maxWidth: MediaQuery.of(context).size.width * 0.72,
              ),
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: isUser ? AppTheme.primaryGradientStart : AppTheme.surface,
                borderRadius: BorderRadius.only(
                  topLeft: const Radius.circular(12),
                  topRight: const Radius.circular(12),
                  bottomLeft: Radius.circular(isUser ? 12 : 4),
                  bottomRight: Radius.circular(isUser ? 4 : 12),
                ),
                border: isUser ? null : Border.all(color: AppTheme.border),
                boxShadow: isUser
                    ? []
                    : [
                        BoxShadow(
                          color: Colors.black.withOpacity(0.02),
                          blurRadius: 3,
                          offset: const Offset(0, 1),
                        ),
                      ],
              ),
              child: Text(
                message.content.isEmpty && message.isStreaming
                    ? '...'
                    : message.content,
                style: TextStyle(
                  color: isUser ? Colors.white : AppTheme.textPrimary,
                  fontSize: 13,
                  height: 1.5,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
```

- [ ] **Step 4: 创建消息输入组件**

写入 `app/lib/widgets/message_input.dart`：

```dart
import 'package:flutter/material.dart';
import '../core/theme.dart';

class MessageInput extends StatefulWidget {
  final void Function(String) onSubmit;

  const MessageInput({super.key, required this.onSubmit});

  @override
  State<MessageInput> createState() => _MessageInputState();
}

class _MessageInputState extends State<MessageInput> {
  final _controller = TextEditingController();
  bool _hasText = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(() {
      setState(() => _hasText = _controller.text.trim().isNotEmpty);
    });
  }

  void _send() {
    if (!_hasText) return;
    widget.onSubmit(_controller.text.trim());
    _controller.clear();
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
      child: Container(
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: AppTheme.border),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity(0.03),
              blurRadius: 6,
              offset: const Offset(0, 2),
            ),
          ],
        ),
        padding: const EdgeInsets.only(left: 4),
        child: Row(
          children: [
            IconButton(
              icon: const Icon(Icons.attach_file, size: 20),
              color: AppTheme.textSecondary,
              onPressed: () {},
            ),
            Expanded(
              child: TextField(
                controller: _controller,
                style: const TextStyle(fontSize: 13, color: AppTheme.textPrimary),
                decoration: const InputDecoration(
                  hintText: '输入消息...',
                  hintStyle: TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                  border: InputBorder.none,
                  contentPadding: EdgeInsets.symmetric(vertical: 8),
                ),
                textInputAction: TextInputAction.send,
                onSubmitted: (_) => _send(),
                maxLines: null,
              ),
            ),
            IconButton(
              icon: const Icon(Icons.mic, size: 20),
              color: AppTheme.textSecondary,
              onPressed: () {},
            ),
            if (_hasText)
              Container(
                margin: const EdgeInsets.only(right: 4),
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    colors: [AppTheme.primaryGradientStart, AppTheme.primaryGradientEnd],
                  ),
                  borderRadius: BorderRadius.all(Radius.circular(12)),
                ),
                child: IconButton(
                  icon: const Icon(Icons.arrow_upward, size: 18),
                  color: Colors.white,
                  onPressed: _send,
                ),
              ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
```

- [ ] **Step 5: 创建聊天主界面**

写入 `app/lib/screens/chat_screen.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../core/theme.dart';
import '../providers/chat_provider.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/message_input.dart';

class ChatScreen extends ConsumerWidget {
  const ChatScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final messages = ref.watch(chatProvider);

    return Scaffold(
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              decoration: BoxDecoration(
                color: AppTheme.surface.withOpacity(0.72),
                border: Border(bottom: BorderSide(color: AppTheme.border)),
              ),
              child: Row(
                children: [
                  Container(
                    width: 34,
                    height: 34,
                    decoration: const BoxDecoration(
                      gradient: LinearGradient(
                        colors: [AppTheme.primaryGradientStart, AppTheme.primaryGradientEnd],
                      ),
                      borderRadius: BorderRadius.all(Radius.circular(10)),
                    ),
                    child: const Center(
                      child: Text('✦', style: TextStyle(color: Colors.white, fontSize: 14)),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        '你的助手',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w600,
                          color: AppTheme.textPrimary,
                        ),
                      ),
                      Row(
                        children: [
                          Container(
                            width: 6, height: 6,
                            decoration: const BoxDecoration(
                              color: AppTheme.onlineGreen,
                              shape: BoxShape.circle,
                            ),
                          ),
                          const SizedBox(width: 4),
                          const Text(
                            '在线',
                            style: TextStyle(fontSize: 10, color: AppTheme.onlineGreen),
                          ),
                        ],
                      ),
                    ],
                  ),
                  const Spacer(),
                  // Live2D placeholder
                  Container(
                    width: 36, height: 44,
                    decoration: BoxDecoration(
                      border: Border.all(color: AppTheme.border, width: 1.5),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: const Center(
                      child: Text('🫧', style: TextStyle(fontSize: 16)),
                    ),
                  ),
                ],
              ),
            ),

            // Messages
            Expanded(
              child: messages.isEmpty
                  ? Center(
                      child: Text(
                        '开始聊天吧',
                        style: TextStyle(
                          color: AppTheme.textSecondary,
                          fontSize: 14,
                        ),
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      itemCount: messages.length,
                      itemBuilder: (_, i) => ChatBubble(message: messages[i]),
                    ),
            ),

            // Input
            MessageInput(
              onSubmit: (text) {
                ref.read(chatProvider.notifier).sendMessage(text);
              },
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 6: 创建设置页面**

写入 `app/lib/screens/settings_screen.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import '../core/theme.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final _storage = const FlutterSecureStorage();
  final _serverController = TextEditingController();
  final _tokenController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadSettings();
  }

  Future<void> _loadSettings() async {
    final server = await _storage.read(key: 'server_url') ?? '';
    final token = await _storage.read(key: 'device_token') ?? '';
    setState(() {
      _serverController.text = server;
      _tokenController.text = token;
    });
  }

  Future<void> _save() async {
    await _storage.write(key: 'server_url', value: _serverController.text);
    await _storage.write(key: 'device_token', value: _tokenController.text);
    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('已保存')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.background,
      appBar: AppBar(
        title: const Text('设置', style: TextStyle(color: AppTheme.textPrimary)),
      ),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          children: [
            TextField(
              controller: _serverController,
              decoration: const InputDecoration(
                labelText: '服务器地址',
                hintText: 'https://your-vps.com:8000',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _tokenController,
              decoration: const InputDecoration(
                labelText: '设备密钥',
                hintText: '输入你的设备密钥',
              ),
              obscureText: true,
            ),
            const SizedBox(height: 20),
            SizedBox(
              width: double.infinity,
              child: FilledButton(
                onPressed: _save,
                style: FilledButton.styleFrom(
                  backgroundColor: AppTheme.primaryGradientStart,
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                  ),
                ),
                child: const Text('保存'),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _serverController.dispose();
    _tokenController.dispose();
    super.dispose();
  }
}
```

- [ ] **Step 7: Commit**

```bash
git add app/
git commit -m "feat: add chat UI with streaming, bubbles, and settings screen"
```

---

### Task 9: 集成测试

**Files:**
- Create: `backend/tests/test_chat.py`
- Create: `backend/tests/test_memory.py`

- [ ] **Step 1: 聊天服务测试**

写入 `backend/tests/test_chat.py`：

```python
import pytest
from unittest.mock import AsyncMock, patch
from app.services.chat import ChatService
from app.services.memory import MemoryService
from app.models.conversation import Conversation
from app.models.message import Message
from app.providers.llm import ChatMessage


@pytest.mark.anyio
async def test_get_or_create_conversation_new(db_session):
    """Should create a new conversation when no ID provided."""
    from app.providers.llm import LLMProvider
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_embed = AsyncMock()

    memory = MemoryService(db_session, mock_embed)
    service = ChatService(db_session, mock_llm, memory)

    conv = await service._get_or_create_conversation(None)
    assert conv.id is not None
    assert conv.title == "新对话"


@pytest.mark.anyio
async def test_chat_creates_user_and_assistant_messages(db_session):
    """Should save both user and assistant messages."""
    from app.providers.llm import LLMProvider
    mock_llm = AsyncMock(spec=LLMProvider)

    async def mock_stream(*args, **kwargs):
        yield "你好！"
    mock_llm.chat.return_value = mock_stream()

    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    memory = MemoryService(db_session, mock_embed)
    service = ChatService(db_session, mock_llm, memory)

    chunks = []
    async for chunk in service.chat("测试消息", None):
        chunks.append(chunk)

    assert "你好！" in "".join(chunks)

    # Verify messages saved
    from sqlalchemy import select
    stmt = select(Message).order_by(Message.created_at)
    result = await db_session.execute(stmt)
    messages = result.scalars().all()
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[1].role == "assistant"
```

- [ ] **Step 2: 记忆服务测试**

写入 `backend/tests/test_memory.py`：

```python
import pytest
from unittest.mock import AsyncMock
from app.services.memory import MemoryService
from app.models.memory import Memory
from app.models.message import Message


@pytest.mark.anyio
async def test_index_message_generates_embedding(db_session):
    """Should add embedding vector to message."""
    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    memory = MemoryService(db_session, mock_embed)
    msg = Message(role="user", content="测试消息")
    db_session.add(msg)
    await db_session.commit()

    await memory.index_message(msg)

    assert msg.embedding is not None
    assert len(msg.embedding) == 512


@pytest.mark.anyio
async def test_retrieve_relevant_finds_similar(db_session):
    """Should find semantically similar memories."""
    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    memory = MemoryService(db_session, mock_embed)

    # Insert test memories
    for content in ["用户喜欢Python", "用户讨厌Java", "用户住在北京"]:
        mem = Memory(content=content, embedding=[0.1] * 512, category="fact")
        db_session.add(mem)
    await db_session.commit()

    results = await memory.retrieve_relevant("编程语言偏好", limit=2)
    assert len(results) <= 2
    assert any("Python" in m.content for m in results)
```

- [ ] **Step 3: 运行测试**

```bash
cd "D:/Claude code/个人API应用/backend"
python -m pytest tests/ -v
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: add chat and memory service tests"
```

---

### Task 10: 部署到 VPS

- [ ] **Step 1: 在 VPS 上安装 Docker**

```bash
ssh root@<your-vps-ip>
curl -fsSL https://get.docker.com | sh
apt install docker-compose -y
```

- [ ] **Step 2: 上传代码并配置**

```bash
# 在本地
cd "D:/Claude code/个人API应用/backend"
scp -r . root@<your-vps-ip>:/opt/ai-assistant/

# 在 VPS 上
ssh root@<your-vps-ip>
cd /opt/ai-assistant
cp .env.example .env
nano .env  # 填入 DeepSeek API Key 和自定义 DEVICE_SECRET
```

- [ ] **Step 3: 启动服务**

```bash
cd /opt/ai-assistant
docker compose up -d --build
docker compose logs -f  # 查看日志确认启动成功
```

- [ ] **Step 4: 配置 Nginx HTTPS 代理**（可选，建议）

```bash
apt install nginx certbot python3-certbot-nginx -y
# 如果有域名，配置 HTTPS
certbot --nginx -d your-domain.com
```

- [ ] **Step 5: 测试连接**

```bash
# 健康检查
curl http://<your-vps-ip>:8000/health

# 测试聊天（替换 DEVICE_SECRET）
curl -X POST http://<your-vps-ip>:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-Device-Token: your-device-secret" \
  -d '{"message": "你好", "stream": false}'
```

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "docs: add VPS deployment instructions"
```

---

## 验证清单

Phase 1 完成后的验收标准：

- [ ] VPS 上 Docker Compose 正常运行（`docker compose ps` 全部 healthy）
- [ ] 健康检查返回 `{"status": "ok"}`
- [ ] 无 token 请求返回 401
- [ ] 正确 token 请求返回 SSE 流式响应
- [ ] 消息在 PostgreSQL 中正确存储（含 embedding 向量）
- [ ] 记忆自动提取并存储
- [ ] Flutter APP 能连接 VPS 并收发消息
- [ ] 消息流式显示（一个字一个字出来）
- [ ] 暗色/浅色主题切换正常
- [ ] APP 设置页面能修改服务器地址和密钥

---

*本计划基于 2026-06-16 设计文档编写。Phase 2（搜索+知识库）和 Phase 3（设备操控）计划待 Phase 1 完成后另行编写。*
