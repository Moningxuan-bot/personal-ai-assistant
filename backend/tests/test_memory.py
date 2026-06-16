import pytest
from unittest.mock import AsyncMock
from sqlalchemy import select
from app.services.memory import MemoryService
from app.models.memory import Memory
from app.models.message import Message
from app.models.conversation import Conversation


@pytest.mark.anyio
async def test_index_message_generates_embedding(db_session):
    """Should add embedding vector to message."""
    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    conv = Conversation()
    db_session.add(conv)
    await db_session.commit()

    memory_svc = MemoryService(db_session, mock_embed)
    msg = Message(conversation_id=conv.id, role="user", content="测试消息")
    db_session.add(msg)
    await db_session.commit()

    await memory_svc.index_message(msg)

    assert msg.embedding is not None
    assert len(msg.embedding) == 512


@pytest.mark.anyio
async def test_retrieve_relevant_finds_similar(db_session):
    """Should find semantically similar memories via vector search."""
    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    memory_svc = MemoryService(db_session, mock_embed)

    # Insert test memories
    for content in ["用户喜欢Python", "用户讨厌Java", "用户住在北京"]:
        mem = Memory(
            content=content,
            embedding=[0.1] * 512,
            category="fact",
        )
        db_session.add(mem)
    await db_session.commit()

    results = await memory_svc.retrieve_relevant("编程语言偏好", limit=2)
    assert len(results) <= 2
    assert len(results) > 0


@pytest.mark.anyio
async def test_retrieve_relevant_respects_active_flag(db_session):
    """Should only return active memories."""
    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    memory_svc = MemoryService(db_session, mock_embed)

    # Active memory
    active_mem = Memory(
        content="活跃记忆",
        embedding=[0.1] * 512,
        category="fact",
        is_active=True,
    )
    # Inactive memory
    inactive_mem = Memory(
        content="非活跃记忆",
        embedding=[0.1] * 512,
        category="fact",
        is_active=False,
    )
    db_session.add_all([active_mem, inactive_mem])
    await db_session.commit()

    results = await memory_svc.retrieve_relevant("测试", limit=10)
    contents = [m.content for m in results]
    assert "活跃记忆" in contents
    assert "非活跃记忆" not in contents


@pytest.mark.anyio
async def test_extract_and_save_memories(db_session):
    """Should extract facts from user message and save as memories."""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = (
        "[fact] 用户喜欢Python编程\n[preference] 用户偏好VSCode\n"
    )

    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    conv = Conversation()
    db_session.add(conv)
    await db_session.commit()

    msg = Message(conversation_id=conv.id, role="user", content="我喜欢用Python在VSCode里编程")
    db_session.add(msg)
    await db_session.commit()

    memory_svc = MemoryService(db_session, mock_embed)
    memories = await memory_svc.extract_and_save_memories(msg, mock_llm)

    assert len(memories) == 2
    assert memories[0].category == "fact"
    assert "Python" in memories[0].content
    assert memories[1].category == "preference"
    assert "VSCode" in memories[1].content
    assert memories[0].source_message_id == msg.id


@pytest.mark.anyio
async def test_extract_memories_empty_response(db_session):
    """Should return empty list when LLM finds nothing to extract."""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = ""

    mock_embed = AsyncMock()

    conv = Conversation()
    db_session.add(conv)
    await db_session.commit()

    msg = Message(conversation_id=conv.id, role="user", content="你好")
    db_session.add(msg)
    await db_session.commit()

    memory_svc = MemoryService(db_session, mock_embed)
    memories = await memory_svc.extract_and_save_memories(msg, mock_llm)

    assert len(memories) == 0


@pytest.mark.anyio
async def test_extract_memory_marks_contradiction_and_carries_history(db_session):
    """新记忆推翻旧记忆时，应停用旧记忆并把矛盾历史带到新记忆上。"""
    mock_llm = AsyncMock()
    mock_llm.chat.side_effect = [
        "[preference] 用户喜欢红色",
        '{"contradicts": true, "topic": "喜欢的颜色", "old": "用户喜欢蓝色", "new": "用户喜欢红色"}',
    ]

    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    conv = Conversation()
    old_mem = Memory(
        content="用户喜欢蓝色",
        embedding=[0.1] * 512,
        category="preference",
        contradiction_topic="喜欢的颜色",
        contradiction_count=2,
        contradiction_history=[
            {"old": "用户喜欢绿色", "new": "用户喜欢蓝色", "at": "2026-06-15T10:00:00+00:00"}
        ],
    )
    db_session.add_all([conv, old_mem])
    await db_session.commit()

    msg = Message(conversation_id=conv.id, role="user", content="我现在喜欢红色")
    db_session.add(msg)
    await db_session.commit()

    memory_svc = MemoryService(db_session, mock_embed)
    memories = await memory_svc.extract_and_save_memories(msg, mock_llm)

    assert len(memories) == 1
    new_mem = memories[0]
    assert old_mem.is_active is False
    assert new_mem.content == "用户喜欢红色"
    assert new_mem.contradiction_topic == "喜欢的颜色"
    assert new_mem.contradiction_count == 3
    assert len(new_mem.contradiction_history) == 2
    assert memory_svc.last_contradictions[0]["trigger_mockery"] is True
    assert memory_svc.last_contradictions[0]["count"] == 3


@pytest.mark.anyio
async def test_extract_memory_keeps_normal_memory_when_not_contradicting(db_session):
    """LLM 判断不矛盾时，不应停用旧记忆或触发吐槽。"""
    mock_llm = AsyncMock()
    mock_llm.chat.side_effect = [
        "[fact] 用户住在上海",
        '{"contradicts": false}',
    ]

    mock_embed = AsyncMock()
    mock_embed.embed.return_value = [0.1] * 512

    conv = Conversation()
    old_mem = Memory(content="用户喜欢蓝色", embedding=[0.1] * 512, category="fact")
    db_session.add_all([conv, old_mem])
    await db_session.commit()

    msg = Message(conversation_id=conv.id, role="user", content="我住在上海")
    db_session.add(msg)
    await db_session.commit()

    memory_svc = MemoryService(db_session, mock_embed)
    memories = await memory_svc.extract_and_save_memories(msg, mock_llm)

    stmt = select(Memory).where(Memory.content == "用户喜欢蓝色")
    result = await db_session.execute(stmt)
    old_after = result.scalar_one()

    assert len(memories) == 1
    assert old_after.is_active is True
    assert memories[0].contradiction_count == 0
    assert memory_svc.last_contradictions == []
