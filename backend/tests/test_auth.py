import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_register(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        params={"org_name": "New Org", "org_slug": "new-org"},
        json={
            "email": "new@example.com",
            "password": "newpassword",
            "first_name": "New",
            "last_name": "User",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login(client: AsyncClient, test_user):
    """Test user login."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "testpassword",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_invalid_password(client: AsyncClient, test_user):
    """Test login with invalid password."""
    response = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "test@example.com",
            "password": "wrongpassword",
        },
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient, auth_headers):
    """Test get current user."""
    response = await client.get(
        "/api/v1/auth/me",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["first_name"] == "Test"


@pytest.mark.asyncio
async def test_get_me_unauthorized(client: AsyncClient):
    """Test get current user without auth."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 403  # No auth header
