from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Team, User
from app.schemas.team import TeamResponse
from app.services.auth import current_user

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=list[TeamResponse])
def get_teams(user: User = Depends(current_user), db: Session = Depends(get_db)):
    team = db.get(Team, user.team_id)
    return [team] if team else []


@router.get("/{team_id}", response_model=TeamResponse)
def get_team(team_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    if team_id != user.team_id:
        raise HTTPException(404, "Команда не найдена")
    return db.get(Team, team_id)
