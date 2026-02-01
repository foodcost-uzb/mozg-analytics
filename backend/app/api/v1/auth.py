from datetime import datetime
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.api.v1.schemas import (
    LoginRequest,
    TelegramAuthData,
    Token,
    TokenRefresh,
    UserCreate,
    UserResponse,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
    verify_telegram_auth,
)
from app.db.models import Organization, User, UserRole
from app.db.session import get_db

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    org_name: str,
    org_slug: str,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Register a new user and organization."""
    # Check if email already exists
    if user_data.email:
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

    # Check if org slug already exists
    result = await db.execute(
        select(Organization).where(Organization.slug == org_slug)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Organization slug already taken",
        )

    # Create organization
    organization = Organization(
        name=org_name,
        slug=org_slug,
    )
    db.add(organization)
    await db.flush()

    # Create user
    hashed_password = None
    if user_data.password:
        hashed_password = get_password_hash(user_data.password)

    user = User(
        organization_id=organization.id,
        email=user_data.email,
        phone=user_data.phone,
        hashed_password=hashed_password,
        telegram_id=user_data.telegram_id,
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role=UserRole.OWNER,  # First user is owner
    )
    db.add(user)
    await db.flush()

    # Generate tokens
    access_token = create_access_token(
        data={"sub": str(user.id), "org_id": str(organization.id)}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "org_id": str(organization.id)}
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/login", response_model=Token)
async def login(
    login_data: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Login with email and password."""
    result = await db.execute(
        select(User).where(User.email == login_data.email)
    )
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(login_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    # Update last login
    user.last_login_at = datetime.utcnow()
    await db.flush()

    access_token = create_access_token(
        data={"sub": str(user.id), "org_id": str(user.organization_id)}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "org_id": str(user.organization_id)}
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/telegram", response_model=Token)
async def telegram_auth(
    auth_data: TelegramAuthData,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Authenticate via Telegram Mini App."""
    # Verify Telegram auth data
    auth_dict = auth_data.model_dump()
    if not verify_telegram_auth(auth_dict.copy()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Telegram authorization",
        )

    # Find or create user
    result = await db.execute(
        select(User).where(User.telegram_id == auth_data.id)
    )
    user = result.scalar_one_or_none()

    if user is None:
        # Create new organization and user for Telegram auth
        organization = Organization(
            name=f"{auth_data.first_name}'s Organization",
            slug=f"tg-{auth_data.id}",
        )
        db.add(organization)
        await db.flush()

        user = User(
            organization_id=organization.id,
            telegram_id=auth_data.id,
            telegram_username=auth_data.username,
            first_name=auth_data.first_name,
            last_name=auth_data.last_name,
            avatar_url=auth_data.photo_url,
            role=UserRole.OWNER,
        )
        db.add(user)
        await db.flush()
    else:
        # Update user info from Telegram
        user.telegram_username = auth_data.username
        user.first_name = auth_data.first_name
        user.last_name = auth_data.last_name
        if auth_data.photo_url:
            user.avatar_url = auth_data.photo_url
        user.last_login_at = datetime.utcnow()

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "org_id": str(user.organization_id)}
    )
    refresh_token = create_refresh_token(
        data={"sub": str(user.id), "org_id": str(user.organization_id)}
    )

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: TokenRefresh,
    db: AsyncSession = Depends(get_db),
) -> Token:
    """Refresh access token using refresh token."""
    payload = decode_token(token_data.refresh_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.type != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    result = await db.execute(
        select(User).where(User.id == uuid.UUID(payload.sub))
    )
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    access_token = create_access_token(
        data={"sub": str(user.id), "org_id": str(user.organization_id)}
    )
    new_refresh_token = create_refresh_token(
        data={"sub": str(user.id), "org_id": str(user.organization_id)}
    )

    return Token(
        access_token=access_token,
        refresh_token=new_refresh_token,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """Get current user profile."""
    return UserResponse.model_validate(current_user)
