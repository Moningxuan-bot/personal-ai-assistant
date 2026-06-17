import json
import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timedelta, timezone
from app.services.spending import SpendingService
from app.models.spending import Spending
from app.providers.llm import LLMProvider


@pytest.mark.anyio
async def test_create_spending_with_reaction(db_session):
    """提交消费应返回阿玖卡片级反应。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    # side_effect: 第 1 次调用=判定, 第 2 次=reaction 文本 (via voice)
    mock_llm.chat.side_effect = [
        json.dumps({"needs_chat": False, "risk_level": "low", "risk_reason": ""}),
        "又吃麻辣烫？行吧，记下了。",
    ]
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(35.5, "餐饮", "麻辣烫", None)
    assert r["amount"] == 35.5
    assert "麻辣烫" in r["reaction"]
    assert r["chat_reaction"] is None


@pytest.mark.anyio
async def test_cigarette_triggers_chat():
    """烟酒类应触发聊天级反应。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.side_effect = [
        json.dumps({"needs_chat": True, "risk_level": "high", "risk_reason": "smoking_frequent"}),
        "又买烟？行吧。",
        "这个月第N次了。你的肺不是我的，但我在意。记下了。",
    ]
    svc = SpendingService(None, mock_llm)
    r = await svc._judge_spending(25, "烟酒", "买烟",
        {"same_category_count_24h":2,"same_category_count_month":5,"same_category_total":125,"monthly_total":2000})
    assert r["needs_chat"] is True
    assert len(r["chat_reaction"]) > 10
    assert "肺" in r["chat_reaction"]


@pytest.mark.anyio
async def test_normal_spending_no_chat(db_session):
    """普通小消费不应触发聊天级反应。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.side_effect = [
        json.dumps({"needs_chat": False, "risk_level": "low", "risk_reason": ""}),
        "4块地铁，记下了。",
    ]
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(4, "交通", "地铁", None)
    assert r["chat_reaction"] is None


@pytest.mark.anyio
async def test_list_spendings(db_session):
    """列表查询应返回消费记录。"""
    db_session.add(Spending(amount=10, category="餐饮", note="早", reaction="嗯。"))
    db_session.add(Spending(amount=50, category="购物", note="书", reaction="行。"))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    r = await SpendingService(db_session, mock_llm).list_spendings()
    assert len(r) >= 2


@pytest.mark.anyio
async def test_category_filter(db_session):
    """分类筛选应只返回指定分类。"""
    db_session.add(Spending(amount=10, category="餐饮", note="早", reaction="嗯。"))
    db_session.add(Spending(amount=50, category="购物", note="书", reaction="行。"))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    r = await SpendingService(db_session, mock_llm).list_spendings(category="餐饮")
    assert len(r) == 1 and r[0]["category"] == "餐饮"


@pytest.mark.anyio
async def test_stats(db_session):
    """统计接口应返回总额和分类占比。"""
    now = datetime.now(timezone.utc)
    db_session.add_all([
        Spending(amount=100, category="餐饮", note="", reaction="嗯", created_at=now),
        Spending(amount=200, category="购物", note="", reaction="嗯", created_at=now),
    ])
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "还行。"  # voice 的月度点评
    s = await SpendingService(db_session, mock_llm).get_stats()
    assert s["total"] == 300.0
    assert s["by_category"]["餐饮"] == 100.0


@pytest.mark.anyio
async def test_llm_failure_fallback(db_session):
    """LLM 宕了应有默认 reaction。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.side_effect = Exception("down")
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(25, "烟酒", "买烟", None)
    assert r["reaction"]
    assert len(r["reaction"]) > 0
    # 烟酒 LLM 异常时仍触发聊天（默认逻辑）
    assert r["chat_reaction"] is not None


@pytest.mark.anyio
async def test_recent_context(db_session):
    """get_recent_context 应返回近期消费摘要文本。"""
    now = datetime.now(timezone.utc)
    db_session.add(Spending(amount=35, category="餐饮", note="麻辣烫", reaction="又吃！", created_at=now))
    db_session.add(Spending(amount=25, category="烟酒", note="烟", reaction="唉。", created_at=now - timedelta(hours=2)))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "还行。"
    text = await SpendingService(db_session, mock_llm).get_recent_context(hours=48)
    assert "麻辣烫" in text
    assert "烟酒" in text
    assert "本月累计" in text


@pytest.mark.anyio
async def test_llm_string_false_needs_chat_ignored():
    """LLM 返回 needs_chat: 'false'（字符串）不应触发聊天级反应。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    # 判定返回 needs_chat="false"（字符串），reaction 文本
    mock_llm.chat.side_effect = [
        json.dumps({"needs_chat": "false", "risk_level": "low", "risk_reason": ""}),
        "行吧。",
    ]
    svc = SpendingService(None, mock_llm)
    r = await svc._judge_spending(10, "餐饮", "午餐", {
        "same_category_count_24h":1,"same_category_count_month":3,"same_category_total":100,"monthly_total":500})
    assert r["needs_chat"] is False  # 字符串 "false" 应转为 False
    assert r["chat_reaction"] == ""


@pytest.mark.anyio
async def test_llm_empty_reaction_fallback():
    """LLM 返回空 reaction 时应使用默认 reaction。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    # 判定正常，voice 渲染返回空字符串 → 回落默认模板
    mock_llm.chat.side_effect = [
        json.dumps({"needs_chat": False, "risk_level": "low", "risk_reason": ""}),
        "",
    ]
    svc = SpendingService(None, mock_llm)
    r = await svc._judge_spending(20, "餐饮", "午饭", {
        "same_category_count_24h":1,"same_category_count_month":1,"same_category_total":20,"monthly_total":20})
    assert len(r["reaction"]) > 0
    assert r["reaction"] != ""


@pytest.mark.anyio
async def test_chat_reaction_with_conversation_id(db_session):
    """有 conversation_id 的烟酒消费应创建 assistant Message 且 chat_delivered=True。"""
    from app.models.conversation import Conversation
    conv = Conversation()
    db_session.add(conv)
    await db_session.commit()

    mock_llm = AsyncMock(spec=LLMProvider)
    # side_effect: 判定 → reaction 文本 → chat_reaction 文本
    mock_llm.chat.side_effect = [
        json.dumps({"needs_chat": True, "risk_level": "high", "risk_reason": "smoking_frequent"}),
        "又抽烟？行吧。",
        "第N根了吧。你的肺不是我的，但我在意。记下了。",
    ]
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(30, "烟酒", "买烟", conv.id)

    assert r["chat_reaction"] is not None
    assert r["chat_delivered"] is True
    # 确认 assistant message 已写入
    from sqlalchemy import select
    from app.models.message import Message
    stmt = select(Message).where(Message.conversation_id == conv.id, Message.role == "assistant")
    msgs = (await db_session.execute(stmt)).scalars().all()
    assert len(msgs) == 1
    assert "第N根" in msgs[0].content


@pytest.mark.anyio
async def test_get_recent_context_does_not_call_llm(db_session):
    """get_recent_context 不应调用 LLM（不生成月度点评）。"""
    now = datetime.now(timezone.utc)
    db_session.add(Spending(amount=10, category="交通", note="", reaction="嗯。", created_at=now))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    # 不 mock chat — 如果调用了 LLM 就会报错
    svc = SpendingService(db_session, mock_llm)
    text = await svc.get_recent_context(hours=24)
    assert "本月累计" in text
    assert "阿玖点评" not in text  # 不应包含 LLM 点评
    # LLM.chat 不应被调用
    mock_llm.chat.assert_not_called()


@pytest.mark.anyio
async def test_get_stats_includes_comment_by_default(db_session):
    """get_stats() 默认应包含阿玖点评。"""
    now = datetime.now(timezone.utc)
    db_session.add(Spending(amount=50, category="餐饮", note="", reaction="嗯", created_at=now))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "吃得不赖。"
    s = await SpendingService(db_session, mock_llm).get_stats()
    assert len(s["ajiu_comment"]) > 0
    mock_llm.chat.assert_called_once()


@pytest.mark.anyio
async def test_get_stats_skip_comment(db_session):
    """get_stats(include_comment=False) 不应调用 LLM。"""
    now = datetime.now(timezone.utc)
    db_session.add(Spending(amount=50, category="餐饮", note="", reaction="嗯", created_at=now))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    s = await SpendingService(db_session, mock_llm).get_stats(include_comment=False)
    assert s["ajiu_comment"] == ""
    assert s["total"] == 50.0
    mock_llm.chat.assert_not_called()


@pytest.mark.anyio
async def test_schema_rejects_negative_amount():
    """SpendingCreate 应拒绝 amount <= 0（Pydantic Field 校验）。"""
    from pydantic import ValidationError
    from app.schemas.spending import SpendingCreate

    # amount = 0 应拒绝
    with pytest.raises(ValidationError):
        SpendingCreate(amount=0, category="餐饮")

    # amount = -100 应拒绝
    with pytest.raises(ValidationError):
        SpendingCreate(amount=-100, category="餐饮")

    # amount = 50 应成功
    s = SpendingCreate(amount=50, category="餐饮", note="测试")
    assert s.amount == 50.0
