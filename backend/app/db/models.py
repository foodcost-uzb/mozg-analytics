import enum
import uuid
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    VIEWER = "viewer"


class POSType(str, enum.Enum):
    IIKO = "iiko"
    RKEEPER = "rkeeper"


class SyncStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


# ==================== Organization ====================


class Organization(Base, UUIDMixin, TimestampMixin):
    """Multi-tenant organization (restaurant group/company)."""

    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[Optional[dict]] = mapped_column(JSONB, default=dict)

    # Subscription info
    subscription_plan: Mapped[str] = mapped_column(String(50), default="free")
    subscription_expires_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Relationships
    users: Mapped[List["User"]] = relationship(
        "User", back_populates="organization", cascade="all, delete-orphan"
    )
    venues: Mapped[List["Venue"]] = relationship(
        "Venue", back_populates="organization", cascade="all, delete-orphan"
    )


# ==================== User ====================


class User(Base, UUIDMixin, TimestampMixin):
    """User with role-based access."""

    __tablename__ = "users"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )

    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Telegram auth
    telegram_id: Mapped[Optional[int]] = mapped_column(Integer, unique=True, nullable=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Profile
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Access
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.VIEWER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Allowed venues (NULL = all venues)
    allowed_venue_ids: Mapped[Optional[List[str]]] = mapped_column(JSONB, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="users"
    )

    __table_args__ = (
        Index("ix_users_telegram_id", "telegram_id"),
        Index("ix_users_email", "email"),
    )


# ==================== Venue ====================


class Venue(Base, UUIDMixin, TimestampMixin):
    """Individual restaurant/cafe venue."""

    __tablename__ = "venues"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE")
    )

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # POS Configuration
    pos_type: Mapped[POSType] = mapped_column(Enum(POSType), nullable=False)
    pos_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    # For iiko: {"organization_id": "...", "api_login": "..."}
    # For rkeeper: {"server_url": "...", "api_key": "..."}

    # Sync status
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    sync_status: Mapped[SyncStatus] = mapped_column(
        Enum(SyncStatus), default=SyncStatus.PENDING
    )
    sync_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="venues"
    )
    categories: Mapped[List["Category"]] = relationship(
        "Category", back_populates="venue", cascade="all, delete-orphan"
    )
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="venue", cascade="all, delete-orphan"
    )
    employees: Mapped[List["Employee"]] = relationship(
        "Employee", back_populates="venue", cascade="all, delete-orphan"
    )
    receipts: Mapped[List["Receipt"]] = relationship(
        "Receipt", back_populates="venue", cascade="all, delete-orphan"
    )
    daily_sales: Mapped[List["DailySales"]] = relationship(
        "DailySales", back_populates="venue", cascade="all, delete-orphan"
    )
    hourly_sales: Mapped[List["HourlySales"]] = relationship(
        "HourlySales", back_populates="venue", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_venues_organization_id", "organization_id"),)


# ==================== Category ====================


class Category(Base, UUIDMixin, TimestampMixin):
    """Product category from POS."""

    __tablename__ = "categories"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE")
    )

    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="categories")
    parent: Mapped[Optional["Category"]] = relationship(
        "Category", remote_side="Category.id", backref="children"
    )
    products: Mapped[List["Product"]] = relationship(
        "Product", back_populates="category"
    )

    __table_args__ = (
        UniqueConstraint("venue_id", "external_id", name="uq_category_venue_external"),
        Index("ix_categories_venue_id", "venue_id"),
    )


# ==================== Product ====================


class Product(Base, UUIDMixin, TimestampMixin):
    """Menu item/product from POS."""

    __tablename__ = "products"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE")
    )
    category_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )

    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Pricing
    price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    cost_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    # Classification
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_modifier: Mapped[bool] = mapped_column(Boolean, default=False)
    unit: Mapped[str] = mapped_column(String(20), default="pcs")

    # Metadata
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="products")
    category: Mapped[Optional["Category"]] = relationship(
        "Category", back_populates="products"
    )
    receipt_items: Mapped[List["ReceiptItem"]] = relationship(
        "ReceiptItem", back_populates="product"
    )

    __table_args__ = (
        UniqueConstraint("venue_id", "external_id", name="uq_product_venue_external"),
        Index("ix_products_venue_id", "venue_id"),
        Index("ix_products_category_id", "category_id"),
    )


# ==================== Employee ====================


class Employee(Base, UUIDMixin, TimestampMixin):
    """Staff member from POS."""

    __tablename__ = "employees"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE")
    )

    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # For commission calculations
    commission_rate: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2), nullable=True
    )

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="employees")
    receipts: Mapped[List["Receipt"]] = relationship(
        "Receipt", back_populates="employee"
    )

    __table_args__ = (
        UniqueConstraint("venue_id", "external_id", name="uq_employee_venue_external"),
        Index("ix_employees_venue_id", "venue_id"),
    )


# ==================== Receipt ====================


class Receipt(Base, UUIDMixin, TimestampMixin):
    """Sales receipt/check from POS."""

    __tablename__ = "receipts"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE")
    )
    employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True
    )

    external_id: Mapped[str] = mapped_column(String(100), nullable=False)
    receipt_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Timing
    opened_at: Mapped[datetime] = mapped_column(nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # Amounts
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Payment
    payment_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Guest info
    guests_count: Mapped[int] = mapped_column(Integer, default=1)
    table_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Metadata
    extra_data: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="receipts")
    employee: Mapped[Optional["Employee"]] = relationship(
        "Employee", back_populates="receipts"
    )
    items: Mapped[List["ReceiptItem"]] = relationship(
        "ReceiptItem", back_populates="receipt", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("venue_id", "external_id", name="uq_receipt_venue_external"),
        Index("ix_receipts_venue_id", "venue_id"),
        Index("ix_receipts_opened_at", "opened_at"),
        Index("ix_receipts_closed_at", "closed_at"),
        Index("ix_receipts_venue_opened", "venue_id", "opened_at"),
    )


# ==================== Receipt Item ====================


class ReceiptItem(Base, UUIDMixin, TimestampMixin):
    """Individual item in a receipt."""

    __tablename__ = "receipt_items"

    receipt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("receipts.id", ondelete="CASCADE")
    )
    product_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=True
    )

    external_product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    product_name: Mapped[str] = mapped_column(String(255), nullable=False)

    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 3), default=1)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    discount_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Cost for margin calculation
    cost_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)

    # Relationships
    receipt: Mapped["Receipt"] = relationship("Receipt", back_populates="items")
    product: Mapped[Optional["Product"]] = relationship(
        "Product", back_populates="receipt_items"
    )

    __table_args__ = (
        Index("ix_receipt_items_receipt_id", "receipt_id"),
        Index("ix_receipt_items_product_id", "product_id"),
    )


# ==================== Daily Sales Aggregate ====================


class DailySales(Base, UUIDMixin):
    """Pre-aggregated daily sales data."""

    __tablename__ = "daily_sales"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE")
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)

    # Totals
    total_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_receipts: Mapped[int] = mapped_column(Integer, default=0)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    total_guests: Mapped[int] = mapped_column(Integer, default=0)

    # Averages
    avg_receipt: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    avg_guest_check: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Discounts
    total_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)

    # Payment breakdown (JSONB)
    payment_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Category breakdown (JSONB)
    category_breakdown: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="daily_sales")

    __table_args__ = (
        UniqueConstraint("venue_id", "date", name="uq_daily_sales_venue_date"),
        Index("ix_daily_sales_venue_id", "venue_id"),
        Index("ix_daily_sales_date", "date"),
        Index("ix_daily_sales_venue_date", "venue_id", "date"),
    )


# ==================== Hourly Sales Aggregate ====================


class HourlySales(Base, UUIDMixin):
    """Pre-aggregated hourly sales data."""

    __tablename__ = "hourly_sales"

    venue_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("venues.id", ondelete="CASCADE")
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    hour: Mapped[int] = mapped_column(Integer, nullable=False)  # 0-23

    # Totals
    total_revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    total_receipts: Mapped[int] = mapped_column(Integer, default=0)
    total_items: Mapped[int] = mapped_column(Integer, default=0)
    total_guests: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    venue: Mapped["Venue"] = relationship("Venue", back_populates="hourly_sales")

    __table_args__ = (
        UniqueConstraint(
            "venue_id", "date", "hour", name="uq_hourly_sales_venue_date_hour"
        ),
        Index("ix_hourly_sales_venue_id", "venue_id"),
        Index("ix_hourly_sales_venue_date", "venue_id", "date"),
    )
