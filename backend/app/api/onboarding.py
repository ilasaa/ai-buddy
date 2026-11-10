from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.schemas.dashboard import OnboardingResponse, TaskResponse, TaskUpdate
from app.services.auth import intern_user
from app.services.onboarding import change_status, overview

router = APIRouter(prefix="/users/me/onboarding", tags=["Onboarding"])


@router.get("", response_model=OnboardingResponse)
def get_onboarding(user: User = Depends(intern_user), db: Session = Depends(get_db)):
    return overview(db, user.id)


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int, body: TaskUpdate, user: User = Depends(intern_user), db: Session = Depends(get_db)
):
    return change_status(db, user.id, task_id, body.status)
