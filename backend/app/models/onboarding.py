from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.user import User


class OnboardingTask(Base):
    __tablename__ = "onboarding_tasks"
    __table_args__ = (
        CheckConstraint(
            "(verification_type='request' AND request_resource IN ('jira','confluence','gitlab') AND request_resource IS NOT NULL) OR (verification_type<>'request' AND request_resource IS NULL)",
            name="ck_task_request_resource",
        ),
        CheckConstraint(
            "verification_type IN ('self','review','quiz','request')",
            name="ck_task_verification_type",
        ),
        CheckConstraint(
            "(verification_type = 'quiz' AND quiz_id IS NOT NULL) OR (verification_type <> 'quiz' AND quiz_id IS NULL)",
            name="ck_task_quiz",
        ),
        CheckConstraint(
            "status IN ('todo', 'in_progress', 'done', 'submitted', 'changes_requested', 'blocked')",
            name="ck_task_status",
        ),
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
    request_resource: Mapped[str | None] = mapped_column(String(20))
    quiz_id: Mapped[int | None] = mapped_column(ForeignKey("knowledge_quizzes.id"))
    goal_id: Mapped[int | None] = mapped_column(ForeignKey("adaptation_goals.id"), index=True)
    verification_type: Mapped[str] = mapped_column(
        String(20), default="self", server_default="self"
    )
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence: Mapped[str | None] = mapped_column(Text)
    review_comment: Mapped[str | None] = mapped_column(Text)
    user: Mapped[User] = relationship(foreign_keys=[user_id])
