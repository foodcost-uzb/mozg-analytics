import uuid
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

from app.db.models import POSType, SyncStatus, UserRole


# ==================== Token Schemas ====================


class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    refresh_token: str


class TelegramAuthData(BaseModel):
    id: int
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    photo_url: Optional[str] = None
    auth_date: int
    hash: str


# ==================== User Schemas ====================


class UserBase(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    first_name: str
    last_name: Optional[str] = None
    role: UserRole = UserRole.VIEWER


class UserCreate(UserBase):
    password: Optional[str] = None
    telegram_id: Optional[int] = None


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    allowed_venue_ids: Optional[List[str]] = None


class UserResponse(UserBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    last_login_at: Optional[datetime] = None
    allowed_venue_ids: Optional[List[str]] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# ==================== Organization Schemas ====================


class OrganizationBase(BaseModel):
    name: str
    slug: str


class OrganizationCreate(OrganizationBase):
    pass


class OrganizationUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    is_active: Optional[bool] = None
    settings: Optional[dict] = None


class OrganizationResponse(OrganizationBase):
    id: uuid.UUID
    is_active: bool
    settings: Optional[dict] = None
    subscription_plan: str
    subscription_expires_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ==================== Venue Schemas ====================


class POSConfig(BaseModel):
    # iiko config
    organization_id: Optional[str] = None
    api_login: Optional[str] = None
    # rkeeper config
    server_url: Optional[str] = None
    api_key: Optional[str] = None


class VenueBase(BaseModel):
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    timezone: str = "Europe/Moscow"
    pos_type: POSType


class VenueCreate(VenueBase):
    pos_config: POSConfig


class VenueUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    timezone: Optional[str] = None
    is_active: Optional[bool] = None
    pos_config: Optional[POSConfig] = None


class VenueResponse(VenueBase):
    id: uuid.UUID
    organization_id: uuid.UUID
    is_active: bool
    pos_config: dict
    last_sync_at: Optional[datetime] = None
    sync_status: SyncStatus
    sync_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class VenueListResponse(BaseModel):
    id: uuid.UUID
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    pos_type: POSType
    is_active: bool
    last_sync_at: Optional[datetime] = None
    sync_status: SyncStatus

    class Config:
        from_attributes = True


# ==================== Category Schemas ====================


class CategoryBase(BaseModel):
    name: str
    parent_id: Optional[uuid.UUID] = None
    sort_order: int = 0


class CategoryResponse(CategoryBase):
    id: uuid.UUID
    venue_id: uuid.UUID
    external_id: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Product Schemas ====================


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    price: Decimal
    cost_price: Optional[Decimal] = None


class ProductResponse(ProductBase):
    id: uuid.UUID
    venue_id: uuid.UUID
    category_id: Optional[uuid.UUID] = None
    external_id: str
    sku: Optional[str] = None
    is_active: bool
    is_modifier: bool
    unit: str
    image_url: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Employee Schemas ====================


class EmployeeResponse(BaseModel):
    id: uuid.UUID
    venue_id: uuid.UUID
    external_id: str
    name: str
    role: Optional[str] = None
    is_active: bool
    commission_rate: Optional[Decimal] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ==================== Sync Schemas ====================


class SyncTriggerRequest(BaseModel):
    full_sync: bool = False


class SyncStatusResponse(BaseModel):
    venue_id: uuid.UUID
    status: SyncStatus
    last_sync_at: Optional[datetime] = None
    error: Optional[str] = None


# ==================== Pagination ====================


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    items: List
    total: int
    page: int
    per_page: int
    pages: int
