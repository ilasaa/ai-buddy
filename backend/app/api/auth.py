from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.schemas.dashboard import LoginRequest, Profile
from app.services.auth import COOKIE, authenticate, current_user, issue_token, profile

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/login", response_model=Profile)
def login(body: LoginRequest, response: Response, db: Session = Depends(get_db)):
    user = authenticate(db, body.email, body.password)
    response.set_cookie(
        COOKIE,
        issue_token(user.id),
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.session_minutes * 60,
        path="/",
    )
    return profile(db, user)


@router.get("/me", response_model=Profile)
def me(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return profile(db, user)


@router.post("/logout", status_code=204)
def logout(response: Response):
    response.delete_cookie(
        COOKIE, path="/", secure=settings.cookie_secure, httponly=True, samesite="lax"
    )
