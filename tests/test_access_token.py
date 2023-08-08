import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from pydantic import UUID4
from sqlalchemy import Engine, create_engine, exc
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyAccessTokenDatabase,
    SQLAlchemyBaseAccessTokenTableUUID,
    SQLAlchemySynchronousAccessTokenDatabase,
)
from tests.conftest import DATABASE_URL, SYNC_DATABASE_URL


class Base(DeclarativeBase):
    pass


class AccessToken(SQLAlchemyBaseAccessTokenTableUUID, Base):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    pass


def create_session_maker(engine: Engine):
    return sessionmaker(engine)


def create_async_session_maker(engine: AsyncEngine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


def pytest_generate_tests(metafunc):
    if "access_token_db" in metafunc.fixturenames:
        metafunc.parametrize("access_token_db", ["sync", "async"], indirect=True)


@pytest.fixture
def user_id() -> UUID4:
    return uuid.uuid4()


@pytest.fixture
async def access_token_db(
    request,
    user_id: UUID4,
) -> AsyncGenerator[SQLAlchemyAccessTokenDatabase[AccessToken], None]:
    if request.param == "async":
        engine = create_async_engine(DATABASE_URL)
        sessionmaker = create_async_session_maker(engine)

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

        async with sessionmaker() as session:
            user = User(
                id=user_id, email="lancelot@camelot.bt", hashed_password="guinevere"
            )
            session.add(user)
            await session.commit()

            yield SQLAlchemyAccessTokenDatabase(session, AccessToken)

        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.drop_all)
    elif request.param == "sync":
        engine = create_engine(
            SYNC_DATABASE_URL, connect_args={"check_same_thread": False}
        )
        sessionmaker = create_session_maker(engine)

        Base.metadata.create_all(bind=engine)

        with sessionmaker() as session:
            user = User(
                id=user_id, email="lancelot@camelot.bt", hashed_password="guinevere"
            )
            session.add(user)
            session.commit()

            yield SQLAlchemySynchronousAccessTokenDatabase(session, AccessToken)

        Base.metadata.drop_all(bind=engine)
    else:
        raise ValueError("invalid internal test config")


@pytest.mark.asyncio
async def test_queries(
    access_token_db: SQLAlchemyAccessTokenDatabase[AccessToken],
    user_id: UUID4,
):
    access_token_create = {"token": "TOKEN", "user_id": user_id}

    # Create
    access_token = await access_token_db.create(access_token_create)
    assert access_token.token == "TOKEN"
    assert access_token.user_id == user_id

    # Update
    update_dict = {"created_at": datetime.now(timezone.utc)}
    updated_access_token = await access_token_db.update(access_token, update_dict)
    assert updated_access_token.created_at.replace(microsecond=0) == update_dict[
        "created_at"
    ].replace(microsecond=0)

    # Get by token
    access_token_by_token = await access_token_db.get_by_token(access_token.token)
    assert access_token_by_token is not None

    # Get by token expired
    access_token_by_token = await access_token_db.get_by_token(
        access_token.token, max_age=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    assert access_token_by_token is None

    # Get by token not expired
    access_token_by_token = await access_token_db.get_by_token(
        access_token.token, max_age=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    assert access_token_by_token is not None

    # Get by token unknown
    access_token_by_token = await access_token_db.get_by_token("NOT_EXISTING_TOKEN")
    assert access_token_by_token is None

    # Delete token
    await access_token_db.delete(access_token)
    deleted_access_token = await access_token_db.get_by_token(access_token.token)
    assert deleted_access_token is None


@pytest.mark.asyncio
async def test_insert_existing_token(
    access_token_db: SQLAlchemyAccessTokenDatabase[AccessToken],
    user_id: UUID4,
):
    access_token_create = {"token": "TOKEN", "user_id": user_id}
    await access_token_db.create(access_token_create)

    with pytest.raises(exc.IntegrityError):
        await access_token_db.create(access_token_create)
