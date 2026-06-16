import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Literal

from pydantic import BaseModel
from datetime import datetime

from app.models.database import get_db
from app.models.goal import Goal, GoalCheck

router = APIRouter(tags=["goals"], prefix="/goals")


# ---- schemas ----

class GoalResponse(BaseModel):
    id: uuid.UUID
    conversation_id: uuid.UUID
    title: str
    description: str
    milestones: list[dict]
    status: str
    revive_count: int
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class GoalCheckResponse(BaseModel):
    id: uuid.UUID
    goal_id: uuid.UUID
    check_time: datetime
    status: str
    note: str | None

    model_config = {"from_attributes": True}


class GoalDetailResponse(GoalResponse):
    checks: list[GoalCheckResponse] = []


class GoalStatusUpdate(BaseModel):
    status: Literal["active", "paused", "completed", "abandoned"]


class GoalCheckCreate(BaseModel):
    status: Literal["done", "skipped", "missed", "pending"] = "done"
    note: str | None = None


# ---- routes ----

@router.get("", response_model=list[GoalResponse])
async def list_goals(db: AsyncSession = Depends(get_db)):
    """列出所有目标，按创建时间倒序。"""
    stmt = select(Goal).order_by(Goal.created_at.desc())
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/active", response_model=list[GoalResponse])
async def list_active_goals(db: AsyncSession = Depends(get_db)):
    """列出进行中的目标。"""
    stmt = (
        select(Goal)
        .where(Goal.status == "active")
        .order_by(Goal.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/{goal_id}", response_model=GoalDetailResponse)
async def get_goal(goal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """获取目标详情，含打卡记录。"""
    stmt = select(Goal).options(selectinload(Goal.checks)).where(Goal.id == goal_id)
    result = await db.execute(stmt)
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")
    return goal


@router.patch("/{goal_id}", response_model=GoalResponse)
async def update_goal_status(
    goal_id: uuid.UUID,
    body: GoalStatusUpdate,
    db: AsyncSession = Depends(get_db),
):
    """更新目标状态。"""
    stmt = select(Goal).where(Goal.id == goal_id)
    result = await db.execute(stmt)
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal.status = body.status
    if body.status == "completed":
        goal.completed_at = datetime.now()
    await db.commit()
    return goal


@router.post("/{goal_id}/revive", response_model=GoalResponse)
async def revive_goal(goal_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """复活已放弃的目标。阿玖会翻旧账嘲讽。"""
    stmt = select(Goal).where(Goal.id == goal_id)
    result = await db.execute(stmt)
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    goal.revive_count += 1
    goal.status = "active"
    goal.completed_at = None
    await db.commit()
    return goal


@router.post("/{goal_id}/checks", response_model=GoalCheckResponse)
async def add_check(
    goal_id: uuid.UUID,
    body: GoalCheckCreate,
    db: AsyncSession = Depends(get_db),
):
    """为目标添加一次打卡记录。"""
    # Verify goal exists
    stmt = select(Goal).where(Goal.id == goal_id)
    result = await db.execute(stmt)
    goal = result.scalar_one_or_none()
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found")

    check = GoalCheck(
        goal_id=goal_id,
        status=body.status,
        note=body.note,
    )
    db.add(check)
    await db.commit()
    return check
