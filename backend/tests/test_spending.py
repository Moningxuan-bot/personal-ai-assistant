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
    mock_llm.chat.return_value = json.dumps({"reaction":"又吃麻辣烫？","needs_chat":False,"chat_reaction":""})
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(35.5, "餐饮", "麻辣烫", None)
    assert r["amount"] == 35.5
    assert "麻辣烫" in r["reaction"]
    assert r["chat_reaction"] is None


@pytest.mark.anyio
async def test_cigarette_triggers_chat():
    """烟酒类应触发聊天级反应。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = json.dumps(
        {"reaction":"又买烟？","needs_chat":True,"chat_reaction":"这个月第N次了。你的肺不是我的。"})
    svc = SpendingService(None, mock_llm)
    r = await svc._judge_spending(25, "烟酒", "买烟",
        {"same_category_count_24h":2,"same_category_count_month":5,"same_category_total":125,"monthly_total":2000})
    assert r["needs_chat"] is True
    assert len(r["chat_reaction"]) > 10


@pytest.mark.anyio
async def test_normal_spending_no_chat(db_session):
    """普通小消费不应触发聊天级反应。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = json.dumps({"reaction":"4块地铁，记下了。","needs_chat":False,"chat_reaction":""})
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
    mock_llm.chat.return_value = "还行。"
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
