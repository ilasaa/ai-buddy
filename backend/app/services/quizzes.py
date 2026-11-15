"""Проверка по утверждённому синтетическому ключу; LLM не участвует."""

from datetime import UTC, datetime

from fastapi import HTTPException
from sqlalchemy import select

from app.models import OnboardingTask, TaskVerification
from app.models.quiz import KnowledgeQuiz, QuizAttempt
from app.services.adaptation import serialize


def task_quiz(db, user, task_id):
    task = db.scalar(
        select(OnboardingTask)
        .where(OnboardingTask.id == task_id, OnboardingTask.user_id == user.id)
        .with_for_update()
    )
    if user.role != "intern" or not task or task.verification_type != "quiz":
        raise HTTPException(404, "Мини-тест недоступен")
    quiz = db.get(KnowledgeQuiz, task.quiz_id)
    if not quiz:
        raise HTTPException(404, "Мини-тест не найден")
    return task, quiz


def public(quiz):
    return dict(
        id=quiz.id,
        title=quiz.title,
        passing_score=quiz.passing_score,
        questions=[dict(text=q["text"], options=q["options"]) for q in quiz.questions],
    )


def submit(db, user, task_id, answers):
    task, quiz = task_quiz(db, user, task_id)
    if task.status == "done":
        raise HTTPException(409, "Мини-тест уже пройден")
    if len(answers) != len(quiz.questions) or any(
        a < 0 or a >= len(q["options"]) for a, q in zip(answers, quiz.questions, strict=True)
    ):
        raise HTTPException(422, "Ответьте на каждый вопрос одним допустимым вариантом")
    score = sum(a == q["correct"] for a, q in zip(answers, quiz.questions, strict=True))
    feedback = [
        dict(
            correct=a == q["correct"],
            explanation=q["explanation"] if a != q["correct"] else "Верно",
        )
        for a, q in zip(answers, quiz.questions, strict=True)
    ]
    attempt = QuizAttempt(
        task_id=task.id,
        user_id=user.id,
        quiz_id=quiz.id,
        answers=answers,
        score=score,
        passed=score >= quiz.passing_score,
        feedback=feedback,
    )
    db.add(attempt)
    if attempt.passed:
        task.status = "done"
        task.completed_at = task.verified_at = datetime.now(UTC)
        task.evidence = f"Мини-тест: {score}/{len(quiz.questions)}"
        db.add(
            TaskVerification(
                task_id=task.id,
                actor_id=user.id,
                action="quiz_passed",
                evidence=task.evidence,
                comment="Автоматическая проверка по сохранённому ключу",
            )
        )
    db.commit()
    db.refresh(attempt)
    return serialize(attempt)
