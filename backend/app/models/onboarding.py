from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"
    __table_args__ = (
        CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="ck_task_status"),
        CheckConstraint(
            "(status = 'done' AND completed_at IS NOT NULL) OR (status <> 'done' AND completed_at IS NULL)",
            name="ck_task_completion",
        ),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(250))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="todo", server_default="todo")
    due_date: Mapped[date | None] = mapped_column(Date)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    user: Mapped[User] = relationship()
