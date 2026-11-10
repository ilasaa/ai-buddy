import pytest
from sqlalchemy import create_engine, delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import database_url
from app.models import Team, User


def test_create_team():
    # Подключаемся к тестовой базе данных
    test_url = database_url.set(database="ai_buddy_test")
    engine = create_engine(test_url)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()

            try:
                with Session(bind=connection) as session:
                    # Создаём команду
                    team = Team(
                        name="Backend Team",
                        description="Команда backend-разработки",
                    )

                    session.add(team)
                    session.flush()

                    # Ищем созданную команду
                    result = session.scalar(select(Team).where(Team.name == "Backend Team"))

                    # Проверяем результат
                    assert result is not None
                    assert result.name == "Backend Team"
                    assert result.description == "Команда backend-разработки"

            finally:
                # Отменяем изменения теста
                transaction.rollback()

    finally:
        engine.dispose()


def test_delete_team_with_users(db_session: Session):
    # 1. Создаём команду
    team = Team(
        name="Backend Team Restrict",
        description="Команда для проверки удаления",
    )

    db_session.add(team)
    db_session.flush()

    # 2. Создаём пользователя этой команды
    user = User(
        full_name="Алексей Иванов",
        email="restrict-test@example.com",
        role="intern",
        team_id=team.id,
    )

    db_session.add(user)
    db_session.flush()

    # 3. Пытаемся удалить команду
    with pytest.raises(IntegrityError):
        db_session.execute(delete(Team).where(Team.id == team.id))
