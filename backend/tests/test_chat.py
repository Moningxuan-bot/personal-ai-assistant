import pytest
from unittest.mock import AsyncMock
from app.services.chat import ChatService
from app.services.memory import MemoryService
from app.models.message import Message
from app.providers.llm import LLMProvider


def _collect_deltas(events):
    """Helper: extract delta content from stream events, return joined text."""
    parts = []
    for event in events:
        if event["type"] == "delta":
            parts.append(event["content"])
    return "".join(parts)


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
async def test_get_or_create_conversation_unknown_raises(db_session):
    """Should raise 404 when conversation_id is unknown."""
    import uuid

    mock_llm = AsyncMock(spec=LLMProvider)
    mock_embed = AsyncMock()

    memory = MemoryService(db_session, mock_embed)
    service = ChatService(db_session, mock_llm, memory)

    fake_id = uuid.uuid4()
    with pytest.raises(ValueError, match="not found"):
        await service._get_or_create_conversation(fake_id)


@pytest.mark.anyio
async def test_chat_emits_meta_delta_done_events(db_session):
    """Should emit meta → delta... → done events in order."""
    mock_llm = AsyncMock(spec=LLMProvider)

    async def mock_stream(*args, **kwargs):
        yield "你好！"

    mock_llm.chat.return_value = mock_stream()

    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    memory = MemoryService(db_session, mock_embed)
    service = ChatService(db_session, mock_llm, memory)

    events = []
    async for event in service.chat("测试消息", None):
        events.append(event)

    # Should start with meta
    assert events[0]["type"] == "meta"
    assert events[0]["conversation_id"] is not None

    # Should end with done
    assert events[-1]["type"] == "done"

    # Should have delta events between
    deltas = [e for e in events if e["type"] == "delta"]
    assert len(deltas) >= 1
    assert "你好！" in "".join(d["content"] for d in deltas)

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

    events = []
    async for event in service.chat("Python相关", None):
        events.append(event)

    response_text = _collect_deltas(events)
    assert "收到！" in response_text
    assert events[0]["type"] == "meta"
    assert events[-1]["type"] == "done"


@pytest.mark.anyio
async def test_chat_prepends_mockery_when_memory_changes_three_times(db_session):
    """同一记忆话题第 3 次变化时，闲聊回复开头应先吐槽。"""
    from app.models.memory import Memory

    mock_llm = AsyncMock(spec=LLMProvider)

    async def mock_stream(*args, **kwargs):
        yield "那继续说正事。"

    mock_llm.chat.side_effect = [
        "[preference] 用户喜欢红色",
        '{"contradicts": true, "topic": "喜欢的颜色", "old": "用户喜欢蓝色", "new": "用户喜欢红色"}',
        mock_stream(),
    ]

    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    old_mem = Memory(
        content="用户喜欢蓝色",
        embedding=[0.1] * 512,
        category="preference",
        contradiction_topic="喜欢的颜色",
        contradiction_count=2,
    )
    db_session.add(old_mem)
    await db_session.commit()

    memory = MemoryService(db_session, mock_embed)
    service = ChatService(db_session, mock_llm, memory)

    events = []
    async for event in service.chat("我现在喜欢红色", None):
        events.append(event)

    response_text = _collect_deltas(events)
    assert response_text.startswith("等下——你说你用户喜欢红色？")
    assert "这是第3次变了" in response_text
    assert "那继续说正事。" in response_text


@pytest.mark.anyio
async def test_config_rejects_weak_secret_in_production():
    """生产环境下弱密钥应抛出 RuntimeError。"""
    import os
    from unittest.mock import patch

    # 模拟 production + 弱密钥
    with patch.dict(os.environ, {
        "APP_ENV": "production",
        "DEVICE_SECRET": "CHANGE_ME",
    }, clear=False):
        from importlib import reload
        import app.config
        with pytest.raises(RuntimeError, match="DEVICE_SECRET"):
            reload(app.config)


@pytest.mark.anyio
async def test_config_allows_weak_secret_in_development():
    """开发环境下弱密钥应不报错。"""
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {
        "APP_ENV": "development",
        "DEVICE_SECRET": "CHANGE_ME",
    }, clear=False):
        from importlib import reload
        import app.config
        # 不应抛异常
        reload(app.config)
        assert app.config.settings.app_env == "development"


@pytest.mark.anyio
async def test_unknown_conversation_returns_404():
    """未知 conversation_id 的 POST /chat 应返回 404（而非 200 + 流中断）。"""
    import uuid
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        fake_id = uuid.uuid4()
        response = await client.post(
            "/api/chat",
            json={"message": "hello", "conversation_id": str(fake_id)},
            headers={"X-Device-Token": "local-dev-secret"},
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data.get("detail", "").lower()
