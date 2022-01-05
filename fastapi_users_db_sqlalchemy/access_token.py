from datetime import datetime
from typing import Generic, Optional, Type

from fastapi_users.authentication.strategy.db import A, AccessTokenDatabase
from sqlalchemy import Column, DateTime, ForeignKey, String, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.declarative import declared_attr

from fastapi_users_db_sqlalchemy.guid import GUID


class SQLAlchemyBaseAccessTokenTable:
    """Base SQLAlchemy access token table definition."""

    __tablename__ = "accesstoken"

    token = Column(String(length=43), primary_key=True)
    created_at = Column(DateTime(timezone=True), index=True, nullable=False)

    @declared_attr
    def user_id(cls):
        return Column(GUID, ForeignKey("user.id", ondelete="cascade"), nullable=False)


class SQLAlchemyAccessTokenDatabase(AccessTokenDatabase, Generic[A]):
    """
    Access token database adapter for SQLAlchemy.

    :param access_token_model: Pydantic model of a DB representation of an access token.
    :param session: SQLAlchemy session instance.
    :param access_token_table: SQLAlchemy access token model.
    """

    def __init__(
        self,
        access_token_model: Type[A],
        session: AsyncSession,
        access_token_table: Type[SQLAlchemyBaseAccessTokenTable],
    ):
        self.access_token_model = access_token_model
        self.session = session
        self.access_token_table = access_token_table

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional[A]:
        statement = select(self.access_token_table).where(
            self.access_token_table.token == token
        )
        if max_age is not None:
            statement = statement.where(self.access_token_table.created_at >= max_age)

        results = await self.session.execute(statement)
        access_token = results.first()
        if access_token is None:
            return None
        return self.access_token_model.from_orm(access_token[0])

    async def create(self, access_token: A) -> A:
        access_token_db = self.access_token_table(**access_token.dict())
        self.session.add(access_token_db)
        await self.session.commit()
        return access_token

    async def update(self, access_token: A) -> A:
        statement = (
            update(self.access_token_table)
            .where(self.access_token_table.token == access_token.token)
            .values(access_token.dict())
        )
        await self.session.execute(statement)
        return access_token

    async def delete(self, access_token: A) -> None:
        statement = delete(
            self.access_token_table, self.access_token_table.token == access_token.token
        )
        await self.session.execute(statement)
