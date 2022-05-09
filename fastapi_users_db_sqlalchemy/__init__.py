"""FastAPI Users database adapter for SQLAlchemy."""
import uuid
from typing import TYPE_CHECKING, Any, Dict, Generic, Optional, Type

from fastapi_users.db.base import BaseUserDatabase
from fastapi_users.models import ID, OAP, UP
from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_mixin, declared_attr
from sqlalchemy.sql import Select

from fastapi_users_db_sqlalchemy.generics import GUID

__version__ = "4.0.3"

UUID_ID = uuid.UUID


@declarative_mixin
class SQLAlchemyBaseUserTable(Generic[ID]):
    """Base SQLAlchemy users table definition."""

    __tablename__ = "user"

    if TYPE_CHECKING:  # pragma: no cover
        id: ID
        email: str
        hashed_password: str
        is_active: bool
        is_superuser: bool
        is_verified: bool
    else:
        email: str = Column(String(length=320), unique=True, index=True, nullable=False)
        hashed_password: str = Column(String(length=1024), nullable=False)
        is_active: bool = Column(Boolean, default=True, nullable=False)
        is_superuser: bool = Column(Boolean, default=False, nullable=False)
        is_verified: bool = Column(Boolean, default=False, nullable=False)


@declarative_mixin
class SQLAlchemyBaseUserTableUUID(SQLAlchemyBaseUserTable[UUID_ID]):
    if TYPE_CHECKING:  # pragma: no cover
        id: UUID_ID
    else:
        id: UUID_ID = Column(GUID, primary_key=True, default=uuid.uuid4)


@declarative_mixin
class SQLAlchemyBaseOAuthAccountTable(Generic[ID]):
    """Base SQLAlchemy OAuth account table definition."""

    __tablename__ = "oauth_account"

    if TYPE_CHECKING:  # pragma: no cover
        id: ID
        oauth_name: str
        access_token: str
        expires_at: Optional[int]
        refresh_token: Optional[str]
        account_id: str
        account_email: str
    else:
        oauth_name: str = Column(String(length=100), index=True, nullable=False)
        access_token: str = Column(String(length=1024), nullable=False)
        expires_at: Optional[int] = Column(Integer, nullable=True)
        refresh_token: Optional[str] = Column(String(length=1024), nullable=True)
        account_id: str = Column(String(length=320), index=True, nullable=False)
        account_email: str = Column(String(length=320), nullable=False)


@declarative_mixin
class SQLAlchemyBaseOAuthAccountTableUUID(SQLAlchemyBaseOAuthAccountTable[UUID_ID]):
    if TYPE_CHECKING:  # pragma: no cover
        id: UUID_ID
    else:
        id: UUID_ID = Column(GUID, primary_key=True, default=uuid.uuid4)

    @declared_attr
    def user_id(cls) -> Column[GUID]:
        return Column(GUID, ForeignKey("user.id", ondelete="cascade"), nullable=False)


class SQLAlchemyUserDatabase(Generic[UP, ID], BaseUserDatabase[UP, ID]):
    """
    Database adapter for SQLAlchemy.

    :param session: SQLAlchemy session instance.
    :param user_table: SQLAlchemy user model.
    :param oauth_account_table: Optional SQLAlchemy OAuth accounts model.
    """

    session: AsyncSession
    user_table: Type[UP]
    oauth_account_table: Optional[Type[SQLAlchemyBaseOAuthAccountTable]]

    def __init__(
        self,
        session: AsyncSession,
        user_table: Type[UP],
        oauth_account_table: Optional[Type[SQLAlchemyBaseOAuthAccountTable]] = None,
    ):
        self.session = session
        self.user_table = user_table
        self.oauth_account_table = oauth_account_table

    async def get(self, id: ID) -> Optional[UP]:
        statement = select(self.user_table).where(self.user_table.id == id)
        return await self._get_user(statement)

    async def get_by_email(self, email: str) -> Optional[UP]:
        statement = select(self.user_table).where(
            func.lower(self.user_table.email) == func.lower(email)
        )
        return await self._get_user(statement)

    async def get_by_oauth_account(self, oauth: str, account_id: str) -> Optional[UP]:
        if self.oauth_account_table is None:
            raise NotImplementedError()

        statement = (
            select(self.user_table)
            .join(self.oauth_account_table)
            .where(self.oauth_account_table.oauth_name == oauth)
            .where(self.oauth_account_table.account_id == account_id)
        )
        return await self._get_user(statement)

    async def create(self, create_dict: Dict[str, Any]) -> UP:
        user = self.user_table(**create_dict)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update(self, user: UP, update_dict: Dict[str, Any]) -> UP:
        for key, value in update_dict.items():
            setattr(user, key, value)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def delete(self, user: UP) -> None:
        await self.session.delete(user)
        await self.session.commit()

    async def add_oauth_account(self, user: UP, create_dict: Dict[str, Any]) -> UP:
        if self.oauth_account_table is None:
            raise NotImplementedError()

        oauth_account = self.oauth_account_table(**create_dict)
        self.session.add(oauth_account)
        user.oauth_accounts.append(oauth_account)  # type: ignore
        self.session.add(user)

        await self.session.commit()

        return user

    async def update_oauth_account(
        self, user: UP, oauth_account: OAP, update_dict: Dict[str, Any]
    ) -> UP:
        if self.oauth_account_table is None:
            raise NotImplementedError()

        for key, value in update_dict.items():
            setattr(oauth_account, key, value)
        self.session.add(oauth_account)
        await self.session.commit()

        return user

    async def _get_user(self, statement: Select) -> Optional[UP]:
        results = await self.session.execute(statement)
        user = results.first()
        if user is None:
            return None

        return user[0]
