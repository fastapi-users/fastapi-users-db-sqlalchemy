"""FastAPI Users database adapter for SQLAlchemy."""
from typing import Optional, Type

from fastapi_users.db.base import BaseUserDatabase
from fastapi_users.models import UD
from pydantic import UUID4
from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    String,
    delete,
    func,
    select,
    update,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.orm import joinedload
from sqlalchemy.sql import Select

from fastapi_users_db_sqlalchemy.guid import GUID

__version__ = "2.0.2"


class SQLAlchemyBaseUserTable:
    """Base SQLAlchemy users table definition."""

    __tablename__ = "user"

    id = Column(GUID, primary_key=True)
    email = Column(String(length=320), unique=True, index=True, nullable=False)
    hashed_password = Column(String(length=72), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_superuser = Column(Boolean, default=False, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)


class SQLAlchemyBaseOAuthAccountTable:
    """Base SQLAlchemy OAuth account table definition."""

    __tablename__ = "oauth_account"

    id = Column(GUID, primary_key=True)
    oauth_name = Column(String(length=100), index=True, nullable=False)
    access_token = Column(String(length=1024), nullable=False)
    expires_at = Column(Integer, nullable=True)
    refresh_token = Column(String(length=1024), nullable=True)
    account_id = Column(String(length=320), index=True, nullable=False)
    account_email = Column(String(length=320), nullable=False)

    @declared_attr
    def user_id(cls):
        return Column(GUID, ForeignKey("user.id", ondelete="cascade"), nullable=False)


class SQLAlchemyUserDatabase(BaseUserDatabase[UD]):
    """
    Database adapter for SQLAlchemy.

    :param user_db_model: Pydantic model of a DB representation of a user.
    :param session: SQLAlchemy session instance.
    :param user_table: SQLAlchemy user model.
    :param oauth_account_table: Optional SQLAlchemy OAuth accounts model.
    """

    session: AsyncSession
    user_table: Type[SQLAlchemyBaseUserTable]
    oauth_account_table: Optional[Type[SQLAlchemyBaseOAuthAccountTable]]

    def __init__(
        self,
        user_db_model: Type[UD],
        session: AsyncSession,
        user_table: Type[SQLAlchemyBaseUserTable],
        oauth_account_table: Optional[Type[SQLAlchemyBaseOAuthAccountTable]] = None,
    ):
        super().__init__(user_db_model)
        self.session = session
        self.user_table = user_table
        self.oauth_account_table = oauth_account_table

    async def get(self, id: UUID4) -> Optional[UD]:
        statement = select(self.user_table).where(self.user_table.id == id)
        return await self._get_user(statement)

    async def get_by_email(self, email: str) -> Optional[UD]:
        statement = select(self.user_table).where(
            func.lower(self.user_table.email) == func.lower(email)
        )
        return await self._get_user(statement)

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> Optional[UD]:
        if self.oauth_account_table is not None:
            statement = (
                select(self.user_table)
                .join(self.oauth_account_table)
                .where(self.oauth_account_table.oauth_name == oauth)
                .where(self.oauth_account_table.account_id == account_id)
            )
            return await self._get_user(statement)

    async def create(self, user: UD) -> UD:
        user_table = self.user_table(**user.dict(exclude={"oauth_accounts"}))
        self.session.add(user_table)

        if self.oauth_account_table is not None:
            for oauth_account in user.oauth_accounts:
                oauth_account_table = self.oauth_account_table(
                    **oauth_account.dict(), user_id=user.id
                )
                self.session.add(oauth_account_table)

        await self.session.commit()
        return user

    async def update(self, user: UD) -> UD:
        user_table = await self.session.get(self.user_table, user.id)
        for key, value in user.dict(exclude={"oauth_accounts"}).items():
            setattr(user_table, key, value)
        self.session.add(user_table)

        if self.oauth_account_table is not None:
            for oauth_account in user.oauth_accounts:
                statement = update(
                    self.oauth_account_table,
                    whereclause=self.oauth_account_table.id == oauth_account.id,
                    values={**oauth_account.dict(), "user_id": user.id},
                )
                await self.session.execute(statement)

        await self.session.commit()

        return user

    async def delete(self, user: UD) -> None:
        statement = delete(self.user_table, self.user_table.id == user.id)
        await self.session.execute(statement)

    async def _get_user(self, statement: Select) -> Optional[UD]:
        if self.oauth_account_table is not None:
            statement = statement.options(joinedload("oauth_accounts"))

        results = await self.session.execute(statement)
        user = results.first()
        if user is None:
            return None

        return self.user_db_model.from_orm(user[0])
