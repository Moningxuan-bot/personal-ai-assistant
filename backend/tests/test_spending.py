"""SpendingService 测试——新架构：只存账+卡片反应，聊天回复走 ChatService。"""
import pytest
from unittest.mock import AsyncMock
from datetime import datetime, timedelta, timezone
from app.services.spending import SpendingService
from app.models.spending import Spending
from app.providers.llm import LLMProvider


# ============================================================
# create_spending 测试
# ============================================================


@pytest.mark.anyio
async def test_create_spending_with_reaction(db_session):
    """提交消费应返回卡片级 reaction，chat_reaction 始终 None。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "又吃麻辣烫？行吧，记下了。"
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(35.5, "餐饮", "麻辣烫", None)
    assert r["amount"] == 35.5
    assert "麻辣烫" in r["reaction"]
    # chat_reaction 始终为 None——聊天回复由 ChatService 统一生成
    assert r["chat_reaction"] is None


@pytest.mark.anyio
async def test_cigarette_triggers_needs_chat(db_session):
    """烟酒类 needs_chat=True，但 chat_reaction 仍为 None（由 route 层填）。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "又买烟了。行吧，记下了。"
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(25, "烟酒", "买烟", None)
    assert r["needs_chat"] is True
    assert r["chat_reaction"] is None
    assert len(r["reaction"]) > 0


@pytest.mark.anyio
async def test_normal_spending_no_chat(db_session):
    """普通消费 needs_chat=False。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "4块地铁，记下了。"
    svc = SpendingService(db_session, mock_llm)
    r = await svc.create_spending(4, "交通", "地铁", None)
    assert r["needs_chat"] is False
    assert r["chat_reaction"] is None


# ============================================================
# _needs_chat_check 测试
# ============================================================


@pytest.mark.anyio
async def test_needs_chat_smoking_always_true():
    """烟酒分类始终触发。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    svc = SpendingService(None, mock_llm)
    assert await svc._needs_chat_check("烟酒", {"same_category_count_24h": 0}, None) is True
    assert await svc._needs_chat_check("烟酒", {"same_category_count_24h": 10}, None) is True


@pytest.mark.anyio
async def test_needs_chat_high_frequency():
    """24h 内同类 ≥3 次触发。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    svc = SpendingService(None, mock_llm)
    assert await svc._needs_chat_check("购物", {"same_category_count_24h": 3}, None) is True
    assert await svc._needs_chat_check("餐饮", {"same_category_count_24h": 2}, None) is False


@pytest.mark.anyio
async def test_needs_chat_impulse_note():
    """备注含冲动关键词触发。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    svc = SpendingService(None, mock_llm)
    assert await svc._needs_chat_check("购物", {"same_category_count_24h": 0}, "忍不住又买了") is True
    assert await svc._needs_chat_check("购物", {"same_category_count_24h": 0}, "剁手了") is True
    assert await svc._needs_chat_check("购物", {"same_category_count_24h": 0}, "日常") is False


# ============================================================
# 其他测试
# ============================================================


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
async def test_create_spending_llm_down_still_works(db_session):
    """LLM 宕了 reaction 用兜底模板，记账不中断。"""
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


@pytest.mark.anyio
async def test_get_recent_context_does_not_call_llm(db_session):
    """get_recent_context 不应调用 LLM。"""
    now = datetime.now(timezone.utc)
    db_session.add(Spending(amount=10, category="交通", note="", reaction="嗯。", created_at=now))
    await db_session.commit()
    mock_llm = AsyncMock(spec=LLMProvider)
    svc = SpendingService(db_session, mock_llm)
    text = await svc.get_recent_context(hours=24)
    assert "本月累计" in text
    mock_llm.chat.assert_not_called()


@pytest.mark.anyio
async def test_get_stats_includes_comment_by_default(db_session):
    """get_stats() 默认应包含月度点评。"""
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
    """SpendingCreate 应拒绝 amount <= 0。"""
    from pydantic import ValidationError
    from app.schemas.spending import SpendingCreate

    with pytest.raises(ValidationError):
        SpendingCreate(amount=0, category="餐饮")
    with pytest.raises(ValidationError):
        SpendingCreate(amount=-100, category="餐饮")
    s = SpendingCreate(amount=50, category="餐饮", note="测试")
    assert s.amount == 50.0
