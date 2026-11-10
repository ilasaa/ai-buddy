"""Add authentication fields and onboarding tasks without replacing existing data."""

from alembic import op
import sqlalchemy as sa

revision = "c28e67a901af"
down_revision = "b09d2d5a1a04"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("password_hash", sa.String(255), nullable=True))
    op.add_column(
        "users", sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False)
    )
    op.add_column(
        "users",
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_table(
        "onboarding_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("title", sa.String(250), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("status", sa.String(20), server_default="todo", nullable=False),
        sa.Column("due_date", sa.Date()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint("status IN ('todo', 'in_progress', 'done')", name="ck_task_status"),
        sa.CheckConstraint(
            "(status = 'done' AND completed_at IS NOT NULL) OR (status <> 'done' AND completed_at IS NULL)",
            name="ck_task_completion",
        ),
    )
    op.create_index("ix_onboarding_tasks_user_id", "onboarding_tasks", ["user_id"])


def downgrade():
    op.drop_table("onboarding_tasks")
    op.drop_column("users", "created_at")
    op.drop_column("users", "is_active")
    op.drop_column("users", "password_hash")
