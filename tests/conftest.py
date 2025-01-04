import os
from typing import Any, Optional

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


@pytest.fixture
def oauth_account1() -> dict[str, Any]:
    return {
        "oauth_name": "service1",
        "access_token": "TOKEN",
        "expires_at": 1579000751,
        "account_id": "user_oauth1",
        "account_email": "king.arthur@camelot.bt",
    }


@pytest.fixture
def oauth_account2() -> dict[str, Any]:
    return {
        "oauth_name": "service2",
        "access_token": "TOKEN",
        "expires_at": 1579000751,
        "account_id": "user_oauth2",
        "account_email": "king.arthur@camelot.bt",
    }
