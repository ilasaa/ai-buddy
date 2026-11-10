#!/bin/sh
set -eu
python -c 'from app.core.config import settings; assert len(settings.jwt_secret) >= 32, "Set JWT_SECRET in .env (at least 32 characters)"'
alembic upgrade head
# Existing users and their passwords are preserved by the idempotent seed.
export DEMO_PASSWORD="${DEMO_PASSWORD:-Buddy-demo-2026!}"
python -m scripts.seed_demo
python -m scripts.preload_embeddings
python -m scripts.index_knowledge
