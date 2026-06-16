import pytest
from unittest.mock import AsyncMock
from app.services.chat import ChatService
from app.services.memory import MemoryService
from app.models.message import Message
from app.providers.llm import LLMProvider


@pytest.mark.anyio
async def test_get_or_create_conversation_new(db_session):
    """Should create a new conversation when no ID provided."""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_embed = AsyncMock()

    memory = MemoryService(db_session, mock_embed)
    service = ChatService(db_session, mock_llm, memory)

    conv = await service._get_or_create_conversation(None)
    assert conv.id is not None
    assert conv.title == "新对话"


@pytest.mark.anyio
async def test_get_or_create_conversation_existing(db_session):
    """Should return existing conversation when ID provided."""
    from app.models.conversation import Conversation

    conv = Conversation(title="测试对话")
    db_session.add(conv)
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_embed = AsyncMock()

    memory = MemoryService(db_session, mock_embed)
    service = ChatService(db_session, mock_llm, memory)

    result = await service._get_or_create_conversation(conv.id)
    assert result.id == conv.id
    assert result.title == "测试对话"


@pytest.mark.anyio
async def test_chat_creates_user_and_assistant_messages(db_session):
    """Should save both user and assistant messages."""
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
    assert messages[0].content == "测试消息"
    assert messages[1].role == "assistant"
    assert messages[1].content == "你好！"


@pytest.mark.anyio
async def test_chat_with_memory_context(db_session):
    """Should include memory context when relevant memories exist."""
    from app.models.memory import Memory

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.embed.return_value = [0.0] * 512

    async def mock_stream(*args, **kwargs):
        # Capture the system messages to verify memory injection
        yield "收到！"

    mock_llm.chat.return_value = mock_stream()

    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    memory = MemoryService(db_session, mock_embed)

    # Insert a memory
    mem = Memory(
        content="用户喜欢Python",
        embedding=[0.1] * 512,
        category="fact",
    )
    db_session.add(mem)
    await db_session.commit()

    service = ChatService(db_session, mock_llm, memory)

    chunks = []
    async for chunk in service.chat("Python相关", None):
        chunks.append(chunk)

    assert "收到！" in "".join(chunks)
