import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Team, User


def test_create_user(db_session: Session):
    # Создаём команду
    team = Team(
        name="Test Backend Team",
        description="Тестовая команда",
    )

    db_session.add(team)
    db_session.flush()

    # Создаём наставника
    mentor = User(
        full_name="Дмитрий Смирнов",
        email="mentor-test@example.com",
        role="mentor",
        team_id=team.id,
    )

    # Создаём руководителя
    manager = User(
        full_name="Анна Петрова",
        email="manager-test@example.com",
        role="manager",
        team_id=team.id,
    )

    db_session.add_all([mentor, manager])
    db_session.flush()

    # Создаём стажёра
    intern = User(
        full_name="Алексей Иванов",
        email="intern-test@example.com",
        role="intern",
        team_id=team.id,
        mentor_id=mentor.id,
    )

    db_session.add(intern)

    # Назначаем руководителя команды
    team.leader_id = manager.id

    db_session.flush()

    # Получаем стажёра из базы
    saved_intern = db_session.scalar(select(User).where(User.email == "intern-test@example.com"))

    # Проверяем данные
    assert saved_intern is not None

    assert saved_intern.full_name == "Алексей Иванов"
    assert saved_intern.role == "intern"

    assert saved_intern.team_id == team.id
    assert saved_intern.mentor_id == mentor.id

    assert team.leader_id == manager.id


def test_duplicate_email(db_session: Session):
    # Создаём команду
    team = Team(
        name="Test Team",
    )

    db_session.add(team)
    db_session.flush()

    # Создаём первого пользователя
    user1 = User(
        full_name="Алексей Иванов",
        email="alex@example.com",
        role="intern",
        team_id=team.id,
    )

    db_session.add(user1)
    db_session.flush()

    # Создаём второго пользователя с такой же почтой
    user2 = User(
        full_name="Иван Петров",
        email="alex@example.com",
        role="intern",
        team_id=team.id,
    )

    db_session.add(user2)

    # Проверяем, что PostgreSQL запретит добавление
    with pytest.raises(IntegrityError):
        db_session.flush()


def test_user_with_invalid_team(db_session: Session):
    user = User(
        full_name="Алексей Иванов",
        email="alex-invalid-team@example.com",
        role="intern",
        team_id=-1,
    )

    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_user_without_name(db_session: Session):
    team = Team(
        name="Test Team Without Name",
    )

    db_session.add(team)
    db_session.flush()

    user = User(
        full_name=None,
        email="no-name@example.com",
        role="intern",
        team_id=team.id,
    )

    db_session.add(user)

    with pytest.raises(IntegrityError):
        db_session.flush()


def test_delete_mentor(db_session: Session):
    # 1. Создаём команду
    team = Team(
        name="Backend Team Delete Mentor",
    )

    db_session.add(team)
    db_session.flush()

    # 2. Создаём наставника
    mentor = User(
        full_name="Дмитрий Смирнов",
        email="mentor-delete@example.com",
        role="mentor",
        team_id=team.id,
    )

    db_session.add(mentor)
    db_session.flush()

    # 3. Создаём стажёра
    intern = User(
        full_name="Алексей Иванов",
        email="intern-delete@example.com",
        role="intern",
        team_id=team.id,
        mentor_id=mentor.id,
    )

    db_session.add(intern)
    db_session.flush()

    intern_id = intern.id

    # 4. Проверяем, что наставник назначен
    assert intern.mentor_id == mentor.id

    # 5. Удаляем наставника
    db_session.delete(mentor)
    db_session.flush()

    # 6. Получаем актуальные данные стажёра из БД
    db_session.refresh(intern)

    # 7. Проверяем, что стажёр остался
    saved_intern = db_session.get(User, intern_id)

    assert saved_intern is not None
    assert saved_intern.full_name == "Алексей Иванов"

    # 8. Проверяем, что наставник больше не назначен
    assert saved_intern.mentor_id is None

    # 9. Проверяем, что команда стажёра сохранилась
    assert saved_intern.team_id == team.id
