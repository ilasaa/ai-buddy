"""Две роли; условия завершения задач отправкой заявки. Данные и пароли сохраняются."""

import sqlalchemy as sa

from alembic import op

revision = "a62411050001"
down_revision = "a62411040003"
branch_labels = None
depends_on = None


def upgrade():
    # Preserve former managers as mentors, never delete their accounts or history.
    op.execute(
        "UPDATE users AS i SET mentor_id=t.leader_id FROM teams AS t WHERE i.team_id=t.id AND i.role='intern' AND i.mentor_id IS NULL AND EXISTS (SELECT 1 FROM users m WHERE m.id=t.leader_id AND m.role IN ('manager','mentor') AND m.team_id=i.team_id)"
    )
    op.execute("UPDATE users SET role='mentor' WHERE role='manager'")
    op.create_check_constraint("ck_user_role", "users", "role IN ('intern','mentor')")
    # Only pending requests are rerouted; historical decisions retain their author.
    op.execute(
        "UPDATE access_requests a SET approver_id=i.mentor_id FROM users i WHERE a.user_id=i.id AND a.status='pending'"
    )
    op.alter_column("adaptation_plans", "manager_id", new_column_name="mentor_id")
    op.add_column("onboarding_tasks", sa.Column("request_resource", sa.String(20)))
    op.drop_constraint("ck_task_verification_type", "onboarding_tasks", type_="check")
    op.create_check_constraint(
        "ck_task_verification_type",
        "onboarding_tasks",
        "verification_type IN ('self','review','quiz','request')",
    )
    op.create_check_constraint(
        "ck_task_request_resource",
        "onboarding_tasks",
        "(verification_type='request' AND request_resource IN ('jira','confluence','gitlab') AND request_resource IS NOT NULL) OR (verification_type<>'request' AND request_resource IS NULL)",
    )
    # Only the explicitly named request-submission task changes its completion rule.
    op.execute(
        "UPDATE onboarding_tasks SET verification_type='request', request_resource='jira' WHERE title='Оформить доступ к Jira через AI-buddy' AND status<>'done' AND verification_type='self'"
    )


def downgrade():
    raise RuntimeError(
        "Автоматическое восстановление разделённых ролей небезопасно; используйте резервную копию"
    )
