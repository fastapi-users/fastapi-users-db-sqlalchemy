from datetime import datetime
from typing import Generic, Optional, Type

from databases import Database
from fastapi_users.authentication.strategy.db import A, AccessTokenDatabase
from sqlalchemy import Column, DateTime, ForeignKey, String, Table
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
    :param database: `Database` instance from `encode/databases`.
    :param access_tokens: SQLAlchemy access token table instance.
    """

    def __init__(
        self, access_token_model: Type[A], database: Database, access_tokens: Table
    ):
        self.access_token_model = access_token_model
        self.database = database
        self.access_tokens = access_tokens

    async def get_by_token(
        self, token: str, max_age: Optional[datetime] = None
    ) -> Optional[A]:
        query = self.access_tokens.select().where(self.access_tokens.c.token == token)
        if max_age is not None:
            query = query.where(self.access_tokens.c.created_at >= max_age)

        access_token = await self.database.fetch_one(query)
        if access_token is not None:
            return self.access_token_model(**access_token)
        return None

    async def create(self, access_token: A) -> A:
        query = self.access_tokens.insert()
        await self.database.execute(query, access_token.dict())
        return access_token

    async def update(self, access_token: A) -> A:
        update_query = (
            self.access_tokens.update()
            .where(self.access_tokens.c.token == access_token.token)
            .values(access_token.dict())
        )
        await self.database.execute(update_query)
        return access_token

    async def delete(self, access_token: A) -> None:
        query = self.access_tokens.delete().where(
            self.access_tokens.c.token == access_token.token
        )
        await self.database.execute(query)
