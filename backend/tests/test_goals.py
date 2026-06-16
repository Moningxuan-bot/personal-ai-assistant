"""Goals API 测试"""
import pytest
from unittest.mock import AsyncMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.models.goal import Goal, GoalCheck
from app.models.conversation import Conversation
from app.models.database import get_db


async def _create_conv_and_goal(db_session, **goal_kwargs):
    """Helper: 创建 Conversation + 关联 Goal。"""
    conv = Conversation()
    db_session.add(conv)
    await db_session.commit()

    goal = Goal(
        conversation_id=conv.id,
        title=goal_kwargs.get("title", "测试目标"),
        description=goal_kwargs.get("description", "test"),
        milestones=goal_kwargs.get("milestones", []),
        status=goal_kwargs.get("status", "active"),
    )
    db_session.add(goal)
    await db_session.commit()
    return conv, goal


@pytest.mark.anyio
async def test_goal_detail_loads_checks_without_lazy_load(db_session):
    """Goal 详情应通过 selectinload 预加载 checks，避免 async lazy-load 错误。"""
    _, goal = await _create_conv_and_goal(
        db_session,
        title="学Python",
        description="学习Python基础",
        milestones=[{"text": "完成第一章", "done": False}],
    )

    # 添加打卡记录
    check1 = GoalCheck(goal_id=goal.id, status="done", note="完成第一章")
    check2 = GoalCheck(goal_id=goal.id, status="skipped", note="今天太累")
    db_session.add_all([check1, check2])
    await db_session.commit()

    # 通过 API 获取详情
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                f"/api/goals/{goal.id}",
                headers={"X-Device-Token": "local-dev-secret"},
            )
            assert response.status_code == 200
            data = response.json()
            assert data["title"] == "学Python"
            assert len(data["checks"]) == 2
            assert data["checks"][0]["status"] == "done"
            assert data["checks"][1]["status"] == "skipped"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_goal_status_literal_validation(db_session):
    """Pydantic Literal 应拒绝无效的 goal status。"""
    _, goal = await _create_conv_and_goal(db_session)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 有效状态
            response = await client.patch(
                f"/api/goals/{goal.id}",
                json={"status": "paused"},
                headers={"X-Device-Token": "local-dev-secret"},
            )
            assert response.status_code == 200

            # 无效状态
            response = await client.patch(
                f"/api/goals/{goal.id}",
                json={"status": "invalid_status"},
                headers={"X-Device-Token": "local-dev-secret"},
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_goal_check_status_literal_validation(db_session):
    """Pydantic Literal 应拒绝无效的 check status。"""
    _, goal = await _create_conv_and_goal(db_session)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 有效状态
            response = await client.post(
                f"/api/goals/{goal.id}/checks",
                json={"status": "done", "note": "完成"},
                headers={"X-Device-Token": "local-dev-secret"},
            )
            assert response.status_code == 200

            # 无效状态
            response = await client.post(
                f"/api/goals/{goal.id}/checks",
                json={"status": "garbage_status"},
                headers={"X-Device-Token": "local-dev-secret"},
            )
            assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()
