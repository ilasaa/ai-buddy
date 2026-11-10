"""Migrate only ai_buddy_test; never uses the primary database name."""

from alembic.config import Config

from alembic import command
from app.core.config import settings

if settings.postgres_db == "ai_buddy_test":
    raise SystemExit(
        "POSTGRES_DB must name the primary DB; this script selects ai_buddy_test itself"
    )
# env.py imports db.session only when Alembic starts.
settings.postgres_db = "ai_buddy_test"
command.upgrade(Config("alembic.ini"), "head")
