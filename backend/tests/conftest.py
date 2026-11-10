import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.session import database_url


@pytest.fixture(scope="session", autouse=True)
def guard_primary_database():
    if database_url.database == "ai_buddy_test":
        raise RuntimeError("Основная база не должна называться ai_buddy_test")


@pytest.fixture
def db_session():
    test_url = database_url.set(database="ai_buddy_test")
    engine = create_engine(test_url)

    try:
        with engine.connect() as connection:
            transaction = connection.begin()

            try:
                with Session(
                    bind=connection,
                    join_transaction_mode="create_savepoint",
                ) as session:
                    yield session

            finally:
                transaction.rollback()

    finally:
        engine.dispose()
