"""Обращения стажёра к назначенному наставнику."""

import sqlalchemy as sa

from alembic import op

revision = "a62411040003"
down_revision = "a62411040002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mentor_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("intern_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("mentor_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text()),
        sa.Column("answered_by", sa.Integer(), sa.ForeignKey("users.id")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("answered_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    raise RuntimeError("Откат удаляет историю обращений; используйте резервную копию")
