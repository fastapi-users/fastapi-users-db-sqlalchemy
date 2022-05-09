import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, Generic, Optional, Type

from fastapi_users.authentication.strategy.db import AP, AccessTokenDatabase
from fastapi_users.models import ID
from sqlalchemy import Column, ForeignKey, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_mixin, declared_attr

from fastapi_users_db_sqlalchemy.generics import GUID, TIMESTAMPAware, now_utc


@declarative_mixin
class SQLAlchemyBaseAccessTokenTable(Generic[ID]):
    """Base SQLAlchemy access token table definition."""

    __tablename__ = "accesstoken"

    if TYPE_CHECKING:  # pragma: no cover
        token: str
        created_at: datetime
        user_id: ID
    else:
        token: str = Column(String(length=43), primary_key=True)
        created_at: datetime = Column(
            TIMESTAMPAware(timezone=True), index=True, nullable=False, default=now_utc
        )


@declarative_mixin
class SQLAlchemyBaseAccessTokenTableUUID(SQLAlchemyBaseAccessTokenTable[uuid.UUID]):
    if TYPE_CHECKING:  # pragma: no cover
        user_id: uuid.UUID
    else:

        @declared_attr
        def user_id(cls) -> Column[GUID]:
            return Column(
                GUID, ForeignKey("user.id", ondelete="cascade"), nullable=False
            )


class SQLAlchemyAccessTokenDatabase(Generic[AP], AccessTokenDatabase[AP]):
    """
    Access token database adapter for SQLAlchemy.

    :param session: SQLAlchemy session instance.
    :param access_token_table: SQLAlchemy access token model.
    """

    def __init__(
        self,
        session: AsyncSession,
        access_token_table: Type[AP],
    ):
        self.session = session
        self.access_token_table = access_token_table

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional[AP]:
        statement = select(self.access_token_table).where(
            self.access_token_table.token == token
        )
        if max_age is not None:
            statement = statement.where(self.access_token_table.created_at >= max_age)

        results = await self.session.execute(statement)
        access_token = results.first()
        if access_token is None:
            return None
        return access_token[0]

    async def create(self, create_dict: Dict[str, Any]) -> AP:
        access_token = self.access_token_table(**create_dict)
        self.session.add(access_token)
        await self.session.commit()
        await self.session.refresh(access_token)
        return access_token

    async def update(self, access_token: AP, update_dict: Dict[str, Any]) -> AP:
        for key, value in update_dict.items():
            setattr(access_token, key, value)
        self.session.add(access_token)
        await self.session.commit()
        await self.session.refresh(access_token)
        return access_token

    async def delete(self, access_token: AP) -> None:
        await self.session.delete(access_token)
        await self.session.commit()
