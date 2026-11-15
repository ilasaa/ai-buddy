"""Персональные планы, цели, согласования и проверки задач."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "a62411040001"
down_revision = "f517aa920001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "adaptation_plans",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "intern_id", sa.Integer(), sa.ForeignKey("users.id"), unique=True, nullable=False
        ),
        sa.Column("manager_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("expectations", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("agreed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "status IN ('draft','pending_agreement','active','completed','archived')"
        ),
    )
    op.create_table(
        "adaptation_goals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("adaptation_plans.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("success_criteria", sa.Text(), nullable=False),
        sa.Column("target_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("evidence", sa.Text()),
        sa.Column("verified_by", sa.Integer(), sa.ForeignKey("users.id")),
    )
    op.create_table(
        "team_objectives",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("teams.id"), nullable=False, index=True),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("key_results", JSONB(), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
    )
    op.create_table(
        "plan_agreements",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "plan_id",
            sa.Integer(),
            sa.ForeignKey("adaptation_plans.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("snapshot", JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.drop_constraint("ck_task_status", "onboarding_tasks", type_="check")
    op.create_check_constraint(
        "ck_task_status",
        "onboarding_tasks",
        "status IN ('todo','in_progress','done','submitted','changes_requested','blocked')",
    )
    op.add_column(
        "onboarding_tasks",
        sa.Column("goal_id", sa.Integer(), sa.ForeignKey("adaptation_goals.id")),
    )
    op.create_index("ix_onboarding_tasks_goal_id", "onboarding_tasks", ["goal_id"])
    op.add_column(
        "onboarding_tasks",
        sa.Column("verification_type", sa.String(20), server_default="self", nullable=False),
    )
    op.create_check_constraint(
        "ck_task_verification_type", "onboarding_tasks", "verification_type IN ('self','review')"
    )
    op.add_column(
        "onboarding_tasks", sa.Column("reviewer_id", sa.Integer(), sa.ForeignKey("users.id"))
    )
    for name in ["submitted_at", "verified_at"]:
        op.add_column("onboarding_tasks", sa.Column(name, sa.DateTime(timezone=True)))
    for name in ["evidence", "review_comment"]:
        op.add_column("onboarding_tasks", sa.Column(name, sa.Text()))
    op.add_column(
        "access_requests", sa.Column("task_id", sa.Integer(), sa.ForeignKey("onboarding_tasks.id"))
    )
    op.create_index("ix_access_requests_task_id", "access_requests", ["task_id"])
    op.create_table(
        "task_verifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "task_id",
            sa.Integer(),
            sa.ForeignKey("onboarding_tasks.id"),
            nullable=False,
            index=True,
        ),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )


def downgrade():
    # Explicitly refuse destructive rollback of signed plans and verification history.
    raise RuntimeError(
        "Откат удаляет историю согласований; используйте резервную копию и отдельную процедуру"
    )
