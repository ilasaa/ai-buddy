from contextlib import contextmanager
from types import SimpleNamespace

from sqlalchemy import func, select

from app.models import OnboardingTask, User
from scripts import seed_demo


def test_seed_idempotent_preserves_progress(db_session, monkeypatch):
    @contextmanager
    def transaction():
        yield db_session
        db_session.flush()

    monkeypatch.setattr(seed_demo, "SessionLocal", SimpleNamespace(begin=transaction))
    monkeypatch.setenv("DEMO_PASSWORD", "Synthetic-demo-password")
    seed_demo.seed()
    intern = db_session.scalar(select(User).where(User.email == "intern@ai-buddy.example"))
    assert intern.mentor_id is not None
    original_hash = intern.password_hash
    tasks = db_session.scalars(
        select(OnboardingTask).where(OnboardingTask.user_id == intern.id)
    ).all()
    assert len(tasks) == 8
    assert sum(t.status == "done" for t in tasks) == 3
    tasks[0].status = "in_progress"
    tasks[0].completed_at = None
    db_session.flush()
    seed_demo.seed()
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(OnboardingTask)
            .where(OnboardingTask.user_id == intern.id)
        )
        == 8
    )
    assert tasks[0].status == "in_progress"
    assert intern.password_hash == original_hash
