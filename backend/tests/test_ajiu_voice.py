"""AjiuVoiceService 统一人格层测试。"""
import pytest
from unittest.mock import AsyncMock
from app.services.ajiu_voice import (
    AjiuVoiceService, AjiuEventType, VoiceEvent, OutputValidator, ValidationResult,
)
from app.providers.llm import LLMProvider


# ============================================================
# OutputValidator 测试
# ============================================================


@pytest.mark.anyio
async def test_validator_rejects_customer_service_tone():
    """验证器应标记客服语气短语。"""
    r = OutputValidator.validate("很高兴为您服务。有什么可以帮助您的吗？")
    assert not r.passed
    assert any("客服" in issue for issue in r.issues)


@pytest.mark.anyio
async def test_validator_rejects_ai_self_identity():
    """验证器应标记自称 AI/助手 的文本。"""
    r = OutputValidator.validate("作为AI，我会帮您处理。")
    assert not r.passed
    assert any("客服" in issue for issue in r.issues)


@pytest.mark.anyio
async def test_validator_passes_normal_ajiutone():
    """正常的阿玖式文本应通过验证。"""
    r = OutputValidator.validate("又花了50？行吧行吧，下次自觉点。")
    assert r.passed


@pytest.mark.anyio
async def test_validator_rejects_start_with_nihao():
    """以'你好'或'您好'开头的应被标记。"""
    r = OutputValidator.validate("你好，请问需要什么帮助？")
    assert not r.passed
    assert any("您好/你好" in issue for issue in r.issues)


@pytest.mark.anyio
async def test_validator_rejects_too_long():
    """超过 600 字的文本应被标记。"""
    r = OutputValidator.validate("啊" * 601)
    assert not r.passed
    assert any("过长" in issue for issue in r.issues)


@pytest.mark.anyio
async def test_validator_rejects_too_short():
    """少于 2 字的文本应被标记。"""
    r = OutputValidator.validate("嗯")
    assert not r.passed  # 1 个字 → 低于下限 2
    assert any("过短" in issue for issue in r.issues)
    r2 = OutputValidator.validate("行吧。")
    assert r2.passed  # 3 个字 → 通过


@pytest.mark.anyio
async def test_validator_rejects_too_many_questions():
    """问号占比过高的文本应被标记。"""
    r = OutputValidator.validate("真？假？是？否？行？不？对？错？")
    assert not r.passed
    assert any("问号过多" in issue for issue in r.issues)


@pytest.mark.anyio
async def test_validator_spending_reaction_needs_confirm_word():
    """记账回复必须包含确认词。"""
    r = OutputValidator.validate(
        "你的肺在喊救命啊笨蛋——这都今天第几次了？",
        event_type=AjiuEventType.SPENDING_REACTION,
    )
    assert not r.passed
    assert any("确认词" in issue for issue in r.issues)

    r2 = OutputValidator.validate(
        "记下了。你的肺在喊救命啊笨蛋。",
        event_type=AjiuEventType.SPENDING_REACTION,
    )
    assert r2.passed


# ============================================================
# AjiuVoiceService 测试
# ============================================================


@pytest.mark.anyio
async def test_render_spending_reaction():
    """spending_reaction 事件应渲染为阿玖语气短文本。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "麻辣烫又吃？行吧，我记下了。"
    voice = AjiuVoiceService(mock_llm)

    text = await voice.render_event(VoiceEvent(
        event_type=AjiuEventType.SPENDING_REACTION,
        payload={
            "amount": 35.5, "category": "餐饮", "note": "麻辣烫",
            "stats": {"same_category_count_24h": 1, "same_category_count_month": 3,
                       "same_category_total": 100, "monthly_total": 500},
            "risk_level": "low", "risk_reason": "",
        },
    ))
    assert "麻辣烫" in text
    assert len(text) > 2


@pytest.mark.anyio
async def test_render_spending_reaction_short_and_safe():
    """记账反应应短且不含禁止词。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "又买烟了。行吧，记下了。"
    voice = AjiuVoiceService(mock_llm)

    text = await voice.render_event(VoiceEvent(
        event_type=AjiuEventType.SPENDING_REACTION,
        payload={
            "amount": 25, "category": "烟酒", "note": "买烟",
            "stats": {"same_category_count_24h": 2, "same_category_count_month": 5,
                       "same_category_total": 125, "monthly_total": 2000},
            "risk_level": "high", "risk_reason": "smoking_frequent",
        },
    ))
    assert len(text) <= 80, f"超过 80 字: {len(text)} 字"
    assert any(w in text for w in ("记下", "记了", "行吧", "知道了", "记住"))
    banned = ["您", "宝贝", "肺", "救命", "储蓄", "联名", "VIP", "算笔账", "肺癌"]
    for w in banned:
        assert w not in text, f"禁止词「{w}」出现在回复中"


@pytest.mark.anyio
async def test_render_spending_monthly_comment():
    """spending_monthly_comment 事件应渲染为月度点评。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = "这个月花了不少啊。吃好喝好，别只顾着吃。"
    voice = AjiuVoiceService(mock_llm)

    text = await voice.render_event(VoiceEvent(
        event_type=AjiuEventType.SPENDING_MONTHLY_COMMENT,
        payload={"month": "2026-06", "total": 3000,
                 "by_category": {"餐饮": 1500, "购物": 1000, "交通": 500}},
    ))
    assert len(text) > 0


@pytest.mark.anyio
async def test_render_fallback_on_llm_failure():
    """LLM 抛异常时应回落默认模板。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.side_effect = Exception("LLM down")
    voice = AjiuVoiceService(mock_llm)

    text = await voice.render_event(VoiceEvent(
        event_type=AjiuEventType.SPENDING_REACTION,
        payload={"amount": 25, "category": "烟酒"},
    ))
    assert len(text) > 0
    assert "块" in text  # 默认模板有金额


@pytest.mark.anyio
async def test_render_empty_llm_response_uses_fallback():
    """LLM 返回空字符串时应使用兜底模板。"""
    mock_llm = AsyncMock(spec=LLMProvider)
    mock_llm.chat.return_value = ""
    voice = AjiuVoiceService(mock_llm)

    text = await voice.render_event(VoiceEvent(
        event_type=AjiuEventType.SPENDING_REACTION,
        payload={"amount": 20, "category": "餐饮"},
    ))
    assert len(text) > 0
    assert "20" in text or "记" in text


@pytest.mark.anyio
async def test_default_reaction_all_categories():
    """所有 6 个分类都应有默认 reaction 模板。"""
    for cat in ("餐饮", "交通", "烟酒", "购物", "娱乐", "其他"):
        text = AjiuVoiceService._default_reaction({"category": cat, "amount": 10})
        assert len(text) > 0, f"分类 {cat} 缺少默认 reaction"


@pytest.mark.anyio
async def test_validation_result_default_passed():
    """ValidationResult 默认应为通过。"""
    r = ValidationResult(passed=True)
    assert r.passed
    assert r.issues == []
