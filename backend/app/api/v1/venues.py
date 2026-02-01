from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_admin, require_manager
from app.api.v1.schemas import (
    SyncStatusResponse,
    SyncTriggerRequest,
    VenueCreate,
    VenueListResponse,
    VenueResponse,
    VenueUpdate,
)
from app.db.models import User, Venue, SyncStatus
from app.db.session import get_db

router = APIRouter(prefix="/venues", tags=["Venues"])


@router.get("", response_model=List[VenueListResponse])
async def list_venues(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> List[VenueListResponse]:
    """List all venues for the current organization."""
    query = select(Venue).where(
        Venue.organization_id == current_user.organization_id
    )

    # Filter by allowed venues if user has restrictions
    if current_user.allowed_venue_ids:
        allowed_ids = [uuid.UUID(vid) for vid in current_user.allowed_venue_ids]
        query = query.where(Venue.id.in_(allowed_ids))

    query = query.order_by(Venue.name)
    result = await db.execute(query)
    venues = result.scalars().all()

    return [VenueListResponse.model_validate(v) for v in venues]


@router.post("", response_model=VenueResponse, status_code=status.HTTP_201_CREATED)
async def create_venue(
    venue_data: VenueCreate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VenueResponse:
    """Create a new venue. Requires admin role."""
    venue = Venue(
        organization_id=current_user.organization_id,
        name=venue_data.name,
        address=venue_data.address,
        city=venue_data.city,
        timezone=venue_data.timezone,
        pos_type=venue_data.pos_type,
        pos_config=venue_data.pos_config.model_dump(exclude_none=True),
    )
    db.add(venue)
    await db.flush()
    await db.refresh(venue)

    return VenueResponse.model_validate(venue)


@router.get("/{venue_id}", response_model=VenueResponse)
async def get_venue(
    venue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> VenueResponse:
    """Get venue details."""
    venue = await _get_venue_or_404(venue_id, current_user, db)
    return VenueResponse.model_validate(venue)


@router.patch("/{venue_id}", response_model=VenueResponse)
async def update_venue(
    venue_id: uuid.UUID,
    venue_data: VenueUpdate,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> VenueResponse:
    """Update venue. Requires admin role."""
    venue = await _get_venue_or_404(venue_id, current_user, db)

    update_data = venue_data.model_dump(exclude_unset=True)

    # Handle pos_config separately
    if "pos_config" in update_data and update_data["pos_config"]:
        venue.pos_config = {
            **venue.pos_config,
            **update_data.pop("pos_config"),
        }

    for field, value in update_data.items():
        setattr(venue, field, value)

    await db.flush()
    await db.refresh(venue)

    return VenueResponse.model_validate(venue)


@router.delete("/{venue_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_venue(
    venue_id: uuid.UUID,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete venue. Requires admin role."""
    venue = await _get_venue_or_404(venue_id, current_user, db)
    await db.delete(venue)


@router.post("/{venue_id}/sync", response_model=SyncStatusResponse)
async def trigger_sync(
    venue_id: uuid.UUID,
    sync_request: SyncTriggerRequest,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    """Trigger data synchronization for a venue. Requires manager role."""
    venue = await _get_venue_or_404(venue_id, current_user, db)

    if venue.sync_status == SyncStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Sync already in progress",
        )

    # Import here to avoid circular imports
    from app.services.sync.tasks import sync_venue_data

    # Trigger Celery task
    sync_venue_data.delay(str(venue_id), full_sync=sync_request.full_sync)

    # Update status
    venue.sync_status = SyncStatus.IN_PROGRESS
    venue.sync_error = None
    await db.flush()

    return SyncStatusResponse(
        venue_id=venue.id,
        status=venue.sync_status,
        last_sync_at=venue.last_sync_at,
        error=venue.sync_error,
    )


@router.get("/{venue_id}/sync/status", response_model=SyncStatusResponse)
async def get_sync_status(
    venue_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> SyncStatusResponse:
    """Get sync status for a venue."""
    venue = await _get_venue_or_404(venue_id, current_user, db)

    return SyncStatusResponse(
        venue_id=venue.id,
        status=venue.sync_status,
        last_sync_at=venue.last_sync_at,
        error=venue.sync_error,
    )


async def _get_venue_or_404(
    venue_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
) -> Venue:
    """Get venue by ID or raise 404."""
    result = await db.execute(
        select(Venue).where(
            Venue.id == venue_id,
            Venue.organization_id == current_user.organization_id,
        )
    )
    venue = result.scalar_one_or_none()

    if venue is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Venue not found",
        )

    # Check if user has access to this venue
    if current_user.allowed_venue_ids:
        if str(venue_id) not in current_user.allowed_venue_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access to this venue is not allowed",
            )

    return venue
