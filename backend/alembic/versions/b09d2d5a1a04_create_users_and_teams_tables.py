"""Create users and teams tables

Revision ID: b09d2d5a1a04
Revises: 
Create Date: 2026-11-09 21:08:53.073045

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b09d2d5a1a04'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Создаём таблицу команд
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("leader_id", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # 2. Создаём таблицу пользователей
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("mentor_id", sa.Integer(), nullable=True),
        sa.Column("internship_started_at", sa.Date(), nullable=True),

        sa.ForeignKeyConstraint(
            ["team_id"],
            ["teams.id"],
            ondelete="RESTRICT",
        ),

        sa.ForeignKeyConstraint(
            ["mentor_id"],
            ["users.id"],
            ondelete="SET NULL",
        ),

        sa.PrimaryKeyConstraint("id"),
    )

    # 3. Создаём индексы
    op.create_index(
        "ix_users_email",
        "users",
        ["email"],
        unique=True,
    )

    op.create_index(
        "ix_users_team_id",
        "users",
        ["team_id"],
    )

    # 4. Добавляем связь команды с руководителем
    op.create_foreign_key(
        "fk_teams_leader_id",
        "teams",
        "users",
        ["leader_id"],
        ["id"],
        ondelete="SET NULL",
    )

def downgrade() -> None:
    # 1. Удаляем связь команды с руководителем
    op.drop_constraint(
        "fk_teams_leader_id",
        "teams",
        type_="foreignkey",
    )

    # 2. Удаляем индексы
    op.drop_index(
        "ix_users_team_id",
        table_name="users",
    )

    op.drop_index(
        "ix_users_email",
        table_name="users",
    )

    # 3. Удаляем таблицы
    op.drop_table("users")
    op.drop_table("teams")