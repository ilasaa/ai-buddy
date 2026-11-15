from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import User
from app.models.quiz import KnowledgeQuiz, QuizAttempt
from app.services import quizzes
from app.services.adaptation import serialize
from app.services.auth import current_user

router = APIRouter(prefix="/quizzes", tags=["Мини-тесты"])


class Answers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answers: list[int] = Field(min_length=1, max_length=20)


@router.get("")
def catalog(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return [
        dict(id=q.id, title=q.title)
        for q in db.scalars(select(KnowledgeQuiz).order_by(KnowledgeQuiz.id)).all()
    ]


@router.get("/tasks/{task_id}")
def get_quiz(task_id: int, user: User = Depends(current_user), db: Session = Depends(get_db)):
    task, quiz = quizzes.task_quiz(db, user, task_id)
    return quizzes.public(quiz) | {
        "attempts": [
            serialize(a)
            for a in db.scalars(
                select(QuizAttempt)
                .where(QuizAttempt.task_id == task.id, QuizAttempt.user_id == user.id)
                .order_by(QuizAttempt.id)
            ).all()
        ]
    }


@router.post("/tasks/{task_id}")
def attempt(
    task_id: int, body: Answers, user: User = Depends(current_user), db: Session = Depends(get_db)
):
    return quizzes.submit(db, user, task_id, body.answers)
