"""CoachEngine 单元测试 + 教练模式集成测试"""
import json
import pytest
from unittest.mock import AsyncMock
from app.services.coach import CoachEngine, QUESTIONS


def make_eval_response(pass_, summary="", praise="", critique="", follow_up=""):
    """构造 LLM 评估返回的 JSON。"""
    if pass_:
        return json.dumps({"pass": True, "summary": summary, "praise": praise})
    return json.dumps(
        {"pass": False, "critique": critique, "follow_up": follow_up}
    )


# ============================================================
# CoachEngine 单元测试
# ============================================================


@pytest.mark.anyio
async def test_init_state():
    """首次进入教练模式应该返回初始状态和第一个问题。"""
    mock_llm = AsyncMock()
    engine = CoachEngine(mock_llm)

    result = await engine.process("我想学Python", None)

    assert result["action"] == "ask_question"
    assert result["coach_state"]["active"] is True
    assert result["coach_state"]["current_question"] == 1
    assert result["coach_state"]["follow_up_count"] == 0
    # The message starts with _ajiufy prefix and Q1's ask text
    assert "算完成" in result["message"] or "衡量" in result["message"]


@pytest.mark.anyio
async def test_answer_passes_moves_to_next_question():
    """合格回答应该记录答案并进入下一问。"""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = make_eval_response(
        True,
        summary="三个月内写出能爬取网页数据的爬虫",
        praise="行吧，这次说得还挺具体的。",
    )

    engine = CoachEngine(mock_llm)
    state = engine.init_state()

    result = await engine.process("想写一个能爬取网页数据的爬虫", state)

    assert result["action"] == "ask_question"
    assert result["coach_state"]["current_question"] == 2
    assert result["coach_state"]["answers"]["goal_picture"] is not None
    assert "爬虫" in result["coach_state"]["answers"]["goal_picture"]


@pytest.mark.anyio
async def test_answer_fails_triggers_follow_up():
    """不合格回答应该追问，不进入下一问。"""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = make_eval_response(
        False,
        critique="就这？「学好Python」算什么目标画像？我要的是具体结果。",
        follow_up="给你最后一次机会——三个月后，你能做什么具体的事来证明你学会了？",
    )

    engine = CoachEngine(mock_llm)
    state = engine.init_state()

    result = await engine.process("学好Python", state)

    assert result["action"] == "follow_up"
    assert result["coach_state"]["current_question"] == 1  # 还在第一问
    assert result["coach_state"]["follow_up_count"] == 1


@pytest.mark.anyio
async def test_three_follow_ups_sigh_and_move_on():
    """追问3次后叹气放行，进入下一问。"""
    mock_llm = AsyncMock()
    mock_llm.chat.return_value = make_eval_response(
        False,
        critique="还是不够具体。",
        follow_up="再想想，到什么程度算完成？",
    )

    engine = CoachEngine(mock_llm)

    state = engine.init_state()
    r1 = await engine.process("学好Python", state)
    assert r1["coach_state"]["follow_up_count"] == 1

    r2 = await engine.process("就是学好", r1["coach_state"])
    assert r2["coach_state"]["follow_up_count"] == 2

    # 第3次 — sigh and move on
    r3 = await engine.process("...我想想", r2["coach_state"])
    assert r3["action"] == "ask_question"
    assert r3["coach_state"]["current_question"] == 2  # 进入第2问
    assert r3["coach_state"]["follow_up_count"] == 0  # 重置
    assert "算了" in r3["message"] or "叹气" in r3["message"]


@pytest.mark.anyio
async def test_all_six_questions_leads_to_plan():
    """6问全过后应生成计划摘要。"""
    mock_llm = AsyncMock()

    call_count = [0]

    async def mock_chat(messages, stream=False):
        call_count[0] += 1
        if call_count[0] <= 6:
            # 6 次评估都通过
            return json.dumps({
                "pass": True,
                "summary": f"Q{call_count[0]} 的回答",
                "praise": "嗯，行。",
            })
        else:
            # _build_plan_summary
            return json.dumps({
                "title": "学会Python爬虫",
                "description": "三个月内掌握Python爬虫基础，能独立完成数据采集任务。",
                "milestones": [
                    {"text": "完成基础语法学习", "criteria": "能写出循环和函数"},
                    {"text": "爬取第一个网页", "criteria": "成功获取HTML并解析"},
                    {"text": "完成一个完整项目", "criteria": "爬取+存储+展示"},
                ],
            })

    mock_llm.chat = mock_chat
    engine = CoachEngine(mock_llm)

    state = engine.init_state()
    result = None

    for i in range(6):
        result = await engine.process(f"第{i+1}问的回答内容——包含足够多的文字以通过长度检查", state)
        state = result["coach_state"]

    # 第6问后应该 plan_ready
    assert result["action"] == "plan_ready"
    assert result["plan"] is not None
    assert result["plan"]["title"] == "学会Python爬虫"
    assert len(result["plan"]["milestones"]) == 3
    assert state.get("pending_plan") is not None


@pytest.mark.anyio
async def test_confirm_creates_goal_data():
    """确认计划后返回 goal 数据。"""
    mock_llm = AsyncMock()
    engine = CoachEngine(mock_llm)

    state = {
        "active": True,
        "current_question": 7,
        "answers": {q["id"]: f"{q['label']}的回答" for q in QUESTIONS},
        "follow_up_count": 0,
        "pending_plan": {
            "title": "学Python",
            "description": "学习Python基础",
            "milestones": [{"text": "完成第一章", "criteria": "能运行Hello World"}],
        },
    }

    result = await engine.confirm_plan(state, True)

    assert result["action"] == "confirmed"
    assert result["goal"] is not None
    assert result["goal"]["title"] == "学Python"
    assert result["coach_state"]["active"] is False


@pytest.mark.anyio
async def test_reject_restarts_questions():
    """拒绝计划应从头开始。"""
    mock_llm = AsyncMock()
    engine = CoachEngine(mock_llm)

    state = {
        "active": True,
        "current_question": 7,
        "answers": {q["id"]: f"{q['label']}的回答" for q in QUESTIONS},
        "follow_up_count": 0,
        "pending_plan": {"title": "学Python", "description": "...", "milestones": []},
    }

    result = await engine.confirm_plan(state, False)

    assert result["action"] == "revise"
    assert result["coach_state"]["current_question"] == 1
    assert result["coach_state"]["follow_up_count"] == 0


# ============================================================
# 集成测试
# ============================================================


@pytest.mark.anyio
async def test_coach_mode_triggers_on_keyword(db_session):
    """触发词应激活教练模式。"""
    from app.services.chat import ChatService
    from app.services.memory import MemoryService

    mock_llm = AsyncMock()
    mock_embed = AsyncMock()

    memory = MemoryService(db_session, mock_embed)
    service = ChatService(db_session, mock_llm, memory)

    mode = service._detect_mode("我想学Python")
    assert mode == "coach"


@pytest.mark.anyio
async def test_coach_state_persists(db_session):
    """教练状态应持久化到 conversation.coach_state。"""
    from app.models.conversation import Conversation

    conv = Conversation()
    conv.coach_state = {
        "active": True,
        "current_question": 3,
        "answers": {"goal_picture": "学爬虫", "baseline": "零基础"},
        "follow_up_count": 0,
    }
    db_session.add(conv)
    await db_session.commit()

    from sqlalchemy import select
    stmt = select(Conversation).where(Conversation.id == conv.id)
    result = await db_session.execute(stmt)
    loaded = result.scalar_one()
    assert loaded.coach_state["active"] is True
    assert loaded.coach_state["current_question"] == 3
    assert loaded.coach_state["answers"]["goal_picture"] == "学爬虫"
