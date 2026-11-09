from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Team
from app.schemas.team import TeamResponse


router = APIRouter(
    prefix="/teams",
    tags=["Teams"],
)


@router.get("", response_model=list[TeamResponse])
def get_teams(db: Session = Depends(get_db)):
    teams = db.scalars(
        select(Team).order_by(Team.id)
    ).all()

    return teams