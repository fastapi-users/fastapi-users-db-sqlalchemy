import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncGenerator

import pytest
from fastapi_users.authentication.strategy.db.models import BaseAccessToken
from pydantic import UUID4
from sqlalchemy import exc
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.orm import sessionmaker

from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from fastapi_users_db_sqlalchemy.access_token import (
    SQLAlchemyAccessTokenDatabase,
    SQLAlchemyBaseAccessTokenTable,
)


class AccessToken(BaseAccessToken):
    pass


def create_async_session_maker(engine: AsyncEngine):
    return sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


@pytest.fixture
def user_id() -> UUID4:
    return uuid.uuid4()


@pytest.fixture
async def sqlalchemy_access_token_db(
    user_id: UUID4,
) -> AsyncGenerator[SQLAlchemyAccessTokenDatabase, None]:
    Base: DeclarativeMeta = declarative_base()

    class AccessTokenTable(SQLAlchemyBaseAccessTokenTable, Base):
        pass

    class UserTable(SQLAlchemyBaseUserTable, Base):
        pass

    DATABASE_URL = "sqlite+aiosqlite:///./test-sqlalchemy-access-token.db"
    engine = create_async_engine(
        DATABASE_URL, connect_args={"check_same_thread": False}
    )
    sessionmaker = create_async_session_maker(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

        async with sessionmaker() as session:
            user = UserTable(
                id=user_id, email="lancelot@camelot.bt", hashed_password="guinevere"
            )
            session.add(user)
            await session.commit()

            yield SQLAlchemyAccessTokenDatabase(AccessToken, session, AccessTokenTable)

        await connection.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries(
    sqlalchemy_access_token_db: SQLAlchemyAccessTokenDatabase[AccessToken],
    user_id: UUID4,
):
    access_token = AccessToken(token="TOKEN", user_id=user_id)

    # Create
    access_token_db = await sqlalchemy_access_token_db.create(access_token)
    assert access_token_db.token == "TOKEN"
    assert access_token_db.user_id == user_id

    # Update
    access_token_db.created_at = datetime.now(timezone.utc)
    await sqlalchemy_access_token_db.update(access_token_db)

    # Get by token
    access_token_by_token = await sqlalchemy_access_token_db.get_by_token(
        access_token_db.token
    )
    assert access_token_by_token is not None

    # Get by token expired
    access_token_by_token = await sqlalchemy_access_token_db.get_by_token(
        access_token_db.token, max_age=datetime.now(timezone.utc) + timedelta(hours=1)
    )
    assert access_token_by_token is None

    # Get by token not expired
    access_token_by_token = await sqlalchemy_access_token_db.get_by_token(
        access_token_db.token, max_age=datetime.now(timezone.utc) - timedelta(hours=1)
    )
    assert access_token_by_token is not None

    # Get by token unknown
    access_token_by_token = await sqlalchemy_access_token_db.get_by_token(
        "NOT_EXISTING_TOKEN"
    )
    assert access_token_by_token is None

    # Delete token
    await sqlalchemy_access_token_db.delete(access_token_db)
    deleted_access_token = await sqlalchemy_access_token_db.get_by_token(
        access_token_db.token
    )
    assert deleted_access_token is None


@pytest.mark.asyncio
@pytest.mark.db
async def test_insert_existing_token(
    sqlalchemy_access_token_db: SQLAlchemyAccessTokenDatabase[AccessToken],
    user_id: UUID4,
):
    access_token = AccessToken(token="TOKEN", user_id=user_id)
    await sqlalchemy_access_token_db.create(access_token)

    with pytest.raises(exc.IntegrityError):
        await sqlalchemy_access_token_db.create(
            AccessToken(token="TOKEN", user_id=user_id)
        )
