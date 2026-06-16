import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.database import Base
from app.models.spending import Spending


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), default="新对话")
    coach_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # coach_state schema:
    # {
    #   "active": true,
    #   "current_question": 1-6,
    #   "answers": {"goal_picture": "...", "baseline": "...", ...},
    #   "follow_up_count": 0,
    #   "last_question_at": "ISO..."
    # }
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")
    goals = relationship("Goal", back_populates="conversation")
    spendings = relationship("Spending", back_populates="conversation", order_by="Spending.created_at")
