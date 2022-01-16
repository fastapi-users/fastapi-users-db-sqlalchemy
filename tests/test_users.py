from typing import AsyncGenerator, Type

import pytest
from fastapi_users import models
from sqlalchemy import Column, String, exc
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.orm import relationship, sessionmaker

from fastapi_users_db_sqlalchemy import (
    SQLAlchemyBaseOAuthAccountTable,
    SQLAlchemyBaseUserTable,
    SQLAlchemyUserDatabase,
)
from tests.conftest import UserDB, UserDBOAuth


async def create_database(
    database_url: str,
    base_class: Type[DeclarativeMeta],
    user_db_model: Type[models.BaseUserDB],
    user_table: Type[SQLAlchemyBaseUserTable],
    oauth_account_table: Type[SQLAlchemyBaseOAuthAccountTable] = None,
) -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    engine = create_async_engine(
        database_url, connect_args={"check_same_thread": False}
    )
    async_sessionmaker = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with engine.begin() as connection:
        await connection.run_sync(base_class.metadata.create_all)

        async with async_sessionmaker() as session:
            yield SQLAlchemyUserDatabase(
                user_db_model, session, user_table, oauth_account_table
            )

        await connection.run_sync(base_class.metadata.drop_all)


@pytest.fixture
async def sqlalchemy_user_db() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    Base: DeclarativeMeta = declarative_base()

    class User(SQLAlchemyBaseUserTable, Base):
        first_name = Column(String, nullable=True)

    async for session in create_database(
        database_url="sqlite+aiosqlite:///./test-sqlalchemy-user.db",
        base_class=Base,
        user_db_model=UserDB,
        user_table=User,
    ):
        yield session


@pytest.fixture
async def sqlalchemy_user_db_custom() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    Base: DeclarativeMeta = declarative_base()

    class User(SQLAlchemyBaseUserTable, Base):
        first_name = Column(String, nullable=False, default="default_username")

    async for session in create_database(
        database_url="sqlite+aiosqlite:///./test-sqlalchemy-user-custom.db",
        base_class=Base,
        user_db_model=UserDB,
        user_table=User,
    ):
        yield session


@pytest.fixture
async def sqlalchemy_user_db_oauth() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    Base: DeclarativeMeta = declarative_base()

    class User(SQLAlchemyBaseUserTable, Base):
        first_name = Column(String, nullable=True)
        oauth_accounts = relationship("OAuthAccount")

    class OAuthAccount(SQLAlchemyBaseOAuthAccountTable, Base):
        pass

    async for session in create_database(
        database_url="sqlite+aiosqlite:///./test-sqlalchemy-user-oauth.db",
        base_class=Base,
        user_db_model=UserDBOAuth,
        user_table=User,
        oauth_account_table=OAuthAccount,
    ):
        yield session


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries(sqlalchemy_user_db: SQLAlchemyUserDatabase[UserDB]):
    user = UserDB(
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
    )

    # Create
    user_db = await sqlalchemy_user_db.create(user)
    assert user_db.id is not None
    assert user_db.is_active is True
    assert user_db.is_superuser is False
    assert user_db.email == user.email

    # Update
    user_db.is_superuser = True
    await sqlalchemy_user_db.update(user_db)

    # Get by id
    id_user = await sqlalchemy_user_db.get(user.id)
    assert id_user is not None
    assert id_user.id == user_db.id
    assert id_user.is_superuser is True

    # Get by email
    email_user = await sqlalchemy_user_db.get_by_email(str(user.email))
    assert email_user is not None
    assert email_user.id == user_db.id

    # Get by uppercased email
    email_user = await sqlalchemy_user_db.get_by_email("Lancelot@camelot.bt")
    assert email_user is not None
    assert email_user.id == user_db.id

    # Unknown user
    unknown_user = await sqlalchemy_user_db.get_by_email("galahad@camelot.bt")
    assert unknown_user is None

    # Delete user
    await sqlalchemy_user_db.delete(user)
    deleted_user = await sqlalchemy_user_db.get(user.id)
    assert deleted_user is None


@pytest.mark.asyncio
@pytest.mark.db
async def test_insert_existing_email(
    sqlalchemy_user_db: SQLAlchemyUserDatabase[UserDB],
):
    user = UserDB(
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
    )
    await sqlalchemy_user_db.create(user)

    with pytest.raises(exc.IntegrityError):
        await sqlalchemy_user_db.create(
            UserDB(email=user.email, hashed_password="guinevere")
        )


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries_custom_fields(
    sqlalchemy_user_db_custom: SQLAlchemyUserDatabase[UserDB],
):
    """It should output custom fields in query result, even if they are not
    in query but have default values."""
    user = UserDB(
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
        first_name="Lancelot",
    )

    db_user = await sqlalchemy_user_db_custom.create(user)

    assert db_user is not None
    assert db_user.id == user.id
    assert db_user.first_name == user.first_name

    await sqlalchemy_user_db_custom.delete(user)

    user = UserDB(
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
    )

    db_user = await sqlalchemy_user_db_custom.create(user)

    assert db_user is not None
    assert db_user.id == user.id
    assert db_user.first_name is not None
    assert db_user.first_name == "default_username"


@pytest.mark.asyncio
@pytest.mark.db
async def test_queries_oauth(
    sqlalchemy_user_db_oauth: SQLAlchemyUserDatabase[UserDBOAuth],
    oauth_account1,
    oauth_account2,
):
    user = UserDBOAuth(
        email="lancelot@camelot.bt",
        hashed_password="guinevere",
        oauth_accounts=[oauth_account1, oauth_account2],
    )

    # Create
    user_db = await sqlalchemy_user_db_oauth.create(user)
    assert user_db.id is not None
    assert hasattr(user_db, "oauth_accounts")
    assert len(user_db.oauth_accounts) == 2

    # Update
    user_db.oauth_accounts[0].access_token = "NEW_TOKEN"
    await sqlalchemy_user_db_oauth.update(user_db)

    # Get by id
    id_user = await sqlalchemy_user_db_oauth.get(user.id)
    assert id_user is not None
    assert id_user.id == user_db.id
    assert id_user.oauth_accounts[0].access_token == "NEW_TOKEN"

    # Get by email
    email_user = await sqlalchemy_user_db_oauth.get_by_email(str(user.email))
    assert email_user is not None
    assert email_user.id == user_db.id
    assert len(email_user.oauth_accounts) == 2

    # Get by OAuth account
    oauth_user = await sqlalchemy_user_db_oauth.get_by_oauth_account(
        oauth_account1.oauth_name, oauth_account1.account_id
    )
    assert oauth_user is not None
    assert oauth_user.id == user.id

    # Unknown OAuth account
    unknown_oauth_user = await sqlalchemy_user_db_oauth.get_by_oauth_account(
        "foo", "bar"
    )
    assert unknown_oauth_user is None
