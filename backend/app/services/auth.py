import secrets
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import User
from app.schemas.dashboard import MentorSummary, Profile, TeamSummary

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))
COOKIE = "ai_buddy_session"


def signing_key():
    if len(settings.jwt_secret) < 32:
        raise HTTPException(503, "Настройте JWT_SECRET: минимум 32 символа")
    return settings.jwt_secret


def issue_token(user_id: int):
    now = datetime.now(UTC)
    return jwt.encode(
        {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.session_minutes)},
        signing_key(),
        algorithm="HS256",
    )


def current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(COOKIE)
    if not token:
        raise HTTPException(401, "Войдите в аккаунт")
    try:
        claims = jwt.decode(
            token, signing_key(), algorithms=["HS256"], options={"require": ["exp", "sub", "iat"]}
        )
        user_id = int(claims["sub"])
    except jwt.InvalidTokenError, ValueError, TypeError:
        raise HTTPException(401, "Сессия истекла. Войдите снова") from None
    user = db.get(User, user_id)
    if not user or not user.is_active:
        raise HTTPException(401, "Сессия недействительна")
    if user.role not in ("intern", "mentor", "manager"):
        raise HTTPException(403, "Недостаточно прав")
    return user


def intern_user(user: User = Depends(current_user)):
    if user.role != "intern":
        raise HTTPException(403, "Раздел доступен стажёрам")
    return user


def authenticate(db: Session, email: str, password: str):
    user = db.scalar(select(User).where(User.email == email.strip().lower()))
    try:
        valid = passwords.verify(
            password, user.password_hash if user and user.password_hash else DUMMY_HASH
        )
    except UnknownHashError:
        passwords.verify(password, DUMMY_HASH)
        raise HTTPException(401, "Неверный email или пароль") from None
    if not valid or not user or not user.password_hash:
        raise HTTPException(401, "Неверный email или пароль")
    if not user.is_active or user.role not in ("intern", "mentor", "manager"):
        raise HTTPException(403, "Аккаунт недоступен")
    return user


def profile(db: Session, user: User):
    mentor = db.get(User, user.mentor_id) if user.mentor_id else None
    # A cross-team or incorrectly assigned mentor must never leak into the profile.
    visible = mentor and mentor.team_id == user.team_id and mentor.role == "mentor"
    return Profile(
        id=user.id,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        team=TeamSummary.model_validate(user.team),
        internship_started_at=user.internship_started_at,
        mentor=MentorSummary(
            id=mentor.id,
            full_name=mentor.full_name,
            role=mentor.role,
            team=TeamSummary.model_validate(mentor.team),
        )
        if visible
        else None,
    )
