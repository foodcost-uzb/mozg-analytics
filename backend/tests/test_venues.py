import pytest
from httpx import AsyncClient

from app.db.models import POSType


@pytest.mark.asyncio
async def test_create_venue(client: AsyncClient, auth_headers):
    """Test creating a venue."""
    response = await client.post(
        "/api/v1/venues",
        headers=auth_headers,
        json={
            "name": "Test Restaurant",
            "address": "123 Test St",
            "city": "Moscow",
            "timezone": "Europe/Moscow",
            "pos_type": "iiko",
            "pos_config": {
                "organization_id": "test-org-id",
                "api_login": "test-login",
            },
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Test Restaurant"
    assert data["pos_type"] == "iiko"
    assert data["sync_status"] == "pending"


@pytest.mark.asyncio
async def test_list_venues(client: AsyncClient, auth_headers):
    """Test listing venues."""
    # Create a venue first
    await client.post(
        "/api/v1/venues",
        headers=auth_headers,
        json={
            "name": "Test Restaurant",
            "pos_type": "iiko",
            "pos_config": {"organization_id": "test"},
        },
    )

    response = await client.get(
        "/api/v1/venues",
        headers=auth_headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1


@pytest.mark.asyncio
async def test_get_venue(client: AsyncClient, auth_headers):
    """Test getting a venue by ID."""
    # Create a venue
    create_response = await client.post(
        "/api/v1/venues",
        headers=auth_headers,
        json={
            "name": "Test Restaurant",
            "pos_type": "iiko",
            "pos_config": {"organization_id": "test"},
        },
    )
    venue_id = create_response.json()["id"]

    response = await client.get(
        f"/api/v1/venues/{venue_id}",
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert response.json()["id"] == venue_id


@pytest.mark.asyncio
async def test_update_venue(client: AsyncClient, auth_headers):
    """Test updating a venue."""
    # Create a venue
    create_response = await client.post(
        "/api/v1/venues",
        headers=auth_headers,
        json={
            "name": "Test Restaurant",
            "pos_type": "iiko",
            "pos_config": {"organization_id": "test"},
        },
    )
    venue_id = create_response.json()["id"]

    # Update it
    response = await client.patch(
        f"/api/v1/venues/{venue_id}",
        headers=auth_headers,
        json={
            "name": "Updated Restaurant",
            "city": "Saint Petersburg",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Updated Restaurant"
    assert data["city"] == "Saint Petersburg"


@pytest.mark.asyncio
async def test_delete_venue(client: AsyncClient, auth_headers):
    """Test deleting a venue."""
    # Create a venue
    create_response = await client.post(
        "/api/v1/venues",
        headers=auth_headers,
        json={
            "name": "Test Restaurant",
            "pos_type": "iiko",
            "pos_config": {"organization_id": "test"},
        },
    )
    venue_id = create_response.json()["id"]

    # Delete it
    response = await client.delete(
        f"/api/v1/venues/{venue_id}",
        headers=auth_headers,
    )

    assert response.status_code == 204

    # Verify it's deleted
    get_response = await client.get(
        f"/api/v1/venues/{venue_id}",
        headers=auth_headers,
    )
    assert get_response.status_code == 404
