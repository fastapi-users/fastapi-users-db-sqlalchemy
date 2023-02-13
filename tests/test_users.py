from typing import Any, AsyncGenerator, Dict, List

import pytest
from sqlalchemy import String, exc
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

from fastapi_users_db_sqlalchemy import (
    UUID_ID,
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from tests.conftest import DATABASE_URL


def create_async_session_maker(engine: AsyncEngine):
    return async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)


class OAuthBase(DeclarativeBase):
    pass


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, OAuthBase):
    pass


class UserOAuth(SQLAlchemyBaseUserTableUUID, OAuthBase):
    first_name: Mapped[str] = mapped_column(String(255), nullable=True)
    oauth_accounts: Mapped[List[OAuthAccount]] = relationship(
        "OAuthAccount", lazy="joined"
    )


@pytest.fixture
async def sqlalchemy_user_db() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    engine = create_async_engine(DATABASE_URL)
    sessionmaker = create_async_session_maker(engine)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    async with sessionmaker() as session:
        yield SQLAlchemyUserDatabase(session, User)

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def sqlalchemy_user_db_oauth() -> AsyncGenerator[SQLAlchemyUserDatabase, None]:
    engine = create_async_engine(DATABASE_URL)
    sessionmaker = create_async_session_maker(engine)

    async with engine.begin() as connection:
        await connection.run_sync(OAuthBase.metadata.create_all)

    async with sessionmaker() as session:
        yield SQLAlchemyUserDatabase(session, UserOAuth, OAuthAccount)

    async with engine.begin() as connection:
        await connection.run_sync(OAuthBase.metadata.drop_all)


@pytest.mark.asyncio
async def test_queries(sqlalchemy_user_db: SQLAlchemyUserDatabase[User, UUID_ID]):
    user_create = {
        "email": "lancelot@camelot.bt",
        "hashed_password": "guinevere",
    }

    # Create
    user = await sqlalchemy_user_db.create(user_create)
    assert user.id is not None
    assert user.is_active is True
    assert user.is_superuser is False
    assert user.email == user_create["email"]

    # Update
    updated_user = await sqlalchemy_user_db.update(user, {"is_superuser": True})
    assert updated_user.is_superuser is True

    # Get by id
    id_user = await sqlalchemy_user_db.get(user.id)
    assert id_user is not None
    assert id_user.id == user.id
    assert id_user.is_superuser is True

    # Get by email
    email_user = await sqlalchemy_user_db.get_by_email(str(user_create["email"]))
    assert email_user is not None
    assert email_user.id == user.id

    # Get by uppercased email
    email_user = await sqlalchemy_user_db.get_by_email("Lancelot@camelot.bt")
    assert email_user is not None
    assert email_user.id == user.id

    # Unknown user
    unknown_user = await sqlalchemy_user_db.get_by_email("galahad@camelot.bt")
    assert unknown_user is None

    # Delete user
    await sqlalchemy_user_db.delete(user)
    deleted_user = await sqlalchemy_user_db.get(user.id)
    assert deleted_user is None

    # OAuth without defined table
    with pytest.raises(NotImplementedError):
        await sqlalchemy_user_db.get_by_oauth_account("foo", "bar")
    with pytest.raises(NotImplementedError):
        await sqlalchemy_user_db.add_oauth_account(user, {})
    with pytest.raises(NotImplementedError):
        oauth_account = OAuthAccount()
        await sqlalchemy_user_db.update_oauth_account(user, oauth_account, {})


@pytest.mark.asyncio
async def test_insert_existing_email(
    sqlalchemy_user_db: SQLAlchemyUserDatabase[User, UUID_ID],
):
    user_create = {
        "email": "lancelot@camelot.bt",
        "hashed_password": "guinevere",
    }
    await sqlalchemy_user_db.create(user_create)

    with pytest.raises(exc.IntegrityError):
        await sqlalchemy_user_db.create(user_create)


@pytest.mark.asyncio
async def test_queries_custom_fields(
    sqlalchemy_user_db: SQLAlchemyUserDatabase[User, UUID_ID],
):
    """It should output custom fields in query result."""
    user_create = {
        "email": "lancelot@camelot.bt",
        "hashed_password": "guinevere",
        "first_name": "Lancelot",
    }
    user = await sqlalchemy_user_db.create(user_create)

    id_user = await sqlalchemy_user_db.get(user.id)
    assert id_user is not None
    assert id_user.id == user.id
    assert id_user.first_name == user.first_name


@pytest.mark.asyncio
async def test_queries_oauth(
    sqlalchemy_user_db_oauth: SQLAlchemyUserDatabase[UserOAuth, UUID_ID],
    oauth_account1: Dict[str, Any],
    oauth_account2: Dict[str, Any],
):
    user_create = {
        "email": "lancelot@camelot.bt",
        "hashed_password": "guinevere",
    }

    # Create
    user = await sqlalchemy_user_db_oauth.create(user_create)
    assert user.id is not None

    # Add OAuth account
    user = await sqlalchemy_user_db_oauth.add_oauth_account(user, oauth_account1)
    user = await sqlalchemy_user_db_oauth.add_oauth_account(user, oauth_account2)
    assert len(user.oauth_accounts) == 2
    assert user.oauth_accounts[1].account_id == oauth_account2["account_id"]
    assert user.oauth_accounts[0].account_id == oauth_account1["account_id"]

    # Update
    user = await sqlalchemy_user_db_oauth.update_oauth_account(
        user, user.oauth_accounts[0], {"access_token": "NEW_TOKEN"}
    )
    assert user.oauth_accounts[0].access_token == "NEW_TOKEN"

    # Get by id
    id_user = await sqlalchemy_user_db_oauth.get(user.id)
    assert id_user is not None
    assert id_user.id == user.id
    assert id_user.oauth_accounts[0].access_token == "NEW_TOKEN"

    # Get by email
    email_user = await sqlalchemy_user_db_oauth.get_by_email(user_create["email"])
    assert email_user is not None
    assert email_user.id == user.id
    assert len(email_user.oauth_accounts) == 2

    # Get by OAuth account
    oauth_user = await sqlalchemy_user_db_oauth.get_by_oauth_account(
        oauth_account1["oauth_name"], oauth_account1["account_id"]
    )
    assert oauth_user is not None
    assert oauth_user.id == user.id

    # Unknown OAuth account
    unknown_oauth_user = await sqlalchemy_user_db_oauth.get_by_oauth_account(
        "foo", "bar"
    )
    assert unknown_oauth_user is None
