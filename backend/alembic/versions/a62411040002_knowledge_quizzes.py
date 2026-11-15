"""Мини-тесты с сохранённым ключом и попытками; роль автора в истории."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "a62411040002"
down_revision = "a62411040001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "knowledge_quizzes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(60), unique=True, nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("questions", JSONB(), nullable=False),
        sa.Column("passing_score", sa.Integer(), nullable=False),
    )
    op.add_column(
        "onboarding_tasks",
        sa.Column("quiz_id", sa.Integer(), sa.ForeignKey("knowledge_quizzes.id")),
    )
    op.drop_constraint("ck_task_verification_type", "onboarding_tasks", type_="check")
    op.create_check_constraint(
        "ck_task_verification_type",
        "onboarding_tasks",
        "verification_type IN ('self','review','quiz')",
    )
    op.create_check_constraint(
        "ck_task_quiz",
        "onboarding_tasks",
        "(verification_type = 'quiz' AND quiz_id IS NOT NULL) OR (verification_type <> 'quiz' AND quiz_id IS NULL)",
    )
    op.create_table(
        "quiz_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("onboarding_tasks.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("quiz_id", sa.Integer(), sa.ForeignKey("knowledge_quizzes.id"), nullable=False),
        sa.Column("answers", JSONB(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("feedback", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.add_column(
        "plan_agreements",
        sa.Column("actor_role", sa.String(20), nullable=False, server_default="unknown"),
    )
    op.execute(
        "UPDATE plan_agreements SET actor_role = users.role FROM users WHERE users.id = plan_agreements.actor_id"
    )
    op.create_check_constraint(
        "ck_goal_status", "adaptation_goals", "status IN ('active','achieved')"
    )


def downgrade():
    raise RuntimeError("Откат удаляет результаты проверок; используйте резервную копию")
