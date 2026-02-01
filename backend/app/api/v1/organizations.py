from typing import List
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_owner
from app.api.v1.schemas import (
    OrganizationResponse,
    OrganizationUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.core.security import get_password_hash
from app.db.models import Organization, User, UserRole
from app.db.session import get_db

router = APIRouter(prefix="/organizations", tags=["Organizations"])


@router.get("/current", response_model=OrganizationResponse)
async def get_current_organization(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Get current user's organization."""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return OrganizationResponse.model_validate(organization)


@router.patch("/current", response_model=OrganizationResponse)
async def update_organization(
    org_data: OrganizationUpdate,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> OrganizationResponse:
    """Update current organization. Requires owner role."""
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    organization = result.scalar_one_or_none()

    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    # Check slug uniqueness if changing
    if org_data.slug and org_data.slug != organization.slug:
        result = await db.execute(
            select(Organization).where(Organization.slug == org_data.slug)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Slug already taken",
            )

    update_data = org_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(organization, field, value)

    await db.flush()
    await db.refresh(organization)

    return OrganizationResponse.model_validate(organization)


# ==================== User Management ====================


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> List[UserResponse]:
    """List all users in organization. Requires owner role."""
    result = await db.execute(
        select(User)
        .where(User.organization_id == current_user.organization_id)
        .order_by(User.created_at)
    )
    users = result.scalars().all()

    return [UserResponse.model_validate(u) for u in users]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Create a new user in organization. Requires owner role."""
    # Check email uniqueness
    if user_data.email:
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Check telegram_id uniqueness
    if user_data.telegram_id:
        result = await db.execute(
            select(User).where(User.telegram_id == user_data.telegram_id)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Telegram ID already registered",
            )

    hashed_password = None
    if user_data.password:
        hashed_password = get_password_hash(user_data.password)

    user = User(
        organization_id=current_user.organization_id,
        email=user_data.email,
        phone=user_data.phone,
        hashed_password=hashed_password,
        telegram_id=user_data.telegram_id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=user_data.role,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Get user by ID. Requires owner role."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_user.organization_id,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return UserResponse.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_data: UserUpdate,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Update user. Requires owner role."""
    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_user.organization_id,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent owner from demoting themselves
    if user.id == current_user.id and user_data.role and user_data.role != UserRole.OWNER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    # Check email uniqueness if changing
    if user_data.email and user_data.email != user.email:
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    update_data = user_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)

    return UserResponse.model_validate(user)


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: uuid.UUID,
    current_user: User = Depends(require_owner),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete user. Requires owner role."""
    if user_id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    result = await db.execute(
        select(User).where(
            User.id == user_id,
            User.organization_id == current_user.organization_id,
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    await db.delete(user)
