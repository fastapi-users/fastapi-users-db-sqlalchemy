import asyncio
import os
from typing import Any, Dict, Optional

import pytest
from fastapi_users import schemas

DATABASE_URL = os.getenv(
    "DATABASE_URL", "sqlite+aiosqlite:///./test-sqlalchemy-user.db"
)


class User(schemas.BaseUser):
    first_name: Optional[str]


class UserCreate(schemas.BaseUserCreate):
    first_name: Optional[str]


class UserUpdate(schemas.BaseUserUpdate):
    pass


class UserOAuth(User, schemas.BaseOAuthAccountMixin):
    pass


@pytest.fixture(scope="session")
def event_loop():
    """Force the pytest-asyncio loop to be the main one."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def oauth_account1() -> Dict[str, Any]:
    return {
        "oauth_name": "service1",
        "access_token": "TOKEN",
        "expires_at": 1579000751,
        "account_id": "user_oauth1",
        "account_email": "king.arthur@camelot.bt",
    }


@pytest.fixture
def oauth_account2() -> Dict[str, Any]:
    return {
        "oauth_name": "service2",
        "access_token": "TOKEN",
        "expires_at": 1579000751,
        "account_id": "user_oauth2",
        "account_email": "king.arthur@camelot.bt",
    }
