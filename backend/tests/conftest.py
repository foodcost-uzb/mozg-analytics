import asyncio
from typing import AsyncGenerator, Generator
import uuid

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.core.security import create_access_token, get_password_hash
from app.db.base import Base
from app.db.models import Organization, User, UserRole
from app.db.session import get_db
from app.main import app

# Test database URL
TEST_DATABASE_URL = "postgresql+asyncpg://mozg:mozg_secret_password@localhost:5432/mozg_analytics_test"

# Create test engine
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Create test database session."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestAsyncSessionLocal() as session:
        yield session
        await session.rollback()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create test HTTP client."""

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_organization(db: AsyncSession) -> Organization:
    """Create test organization."""
    org = Organization(
        name="Test Organization",
        slug="test-org",
    )
    db.add(org)
    await db.flush()
    await db.refresh(org)
    return org


@pytest_asyncio.fixture
async def test_user(db: AsyncSession, test_organization: Organization) -> User:
    """Create test user."""
    user = User(
        organization_id=test_organization.id,
        email="test@example.com",
        hashed_password=get_password_hash("testpassword"),
        first_name="Test",
        last_name="User",
        role=UserRole.OWNER,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


@pytest_asyncio.fixture
async def auth_headers(test_user: User) -> dict:
    """Create auth headers for test user."""
    token = create_access_token(
        data={"sub": str(test_user.id), "org_id": str(test_user.organization_id)}
    )
    return {"Authorization": f"Bearer {token}"}
