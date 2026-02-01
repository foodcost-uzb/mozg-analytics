"""Initial schema with all core tables

Revision ID: 001_initial
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE userrole AS ENUM ('owner', 'admin', 'manager', 'analyst', 'viewer')")
    op.execute("CREATE TYPE postype AS ENUM ('iiko', 'rkeeper')")
    op.execute("CREATE TYPE syncstatus AS ENUM ('pending', 'in_progress', 'completed', 'failed')")

    # Organizations table
    op.create_table(
        'organizations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('slug', sa.String(100), unique=True, nullable=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('settings', postgresql.JSONB(), default=dict),
        sa.Column('subscription_plan', sa.String(50), default='free'),
        sa.Column('subscription_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.String(255), unique=True, nullable=True),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('telegram_id', sa.Integer(), unique=True, nullable=True),
        sa.Column('telegram_username', sa.String(100), nullable=True),
        sa.Column('first_name', sa.String(100), nullable=False),
        sa.Column('last_name', sa.String(100), nullable=True),
        sa.Column('avatar_url', sa.String(500), nullable=True),
        sa.Column('role', postgresql.ENUM('owner', 'admin', 'manager', 'analyst', 'viewer', name='userrole', create_type=False), default='viewer'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('allowed_venue_ids', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_users_telegram_id', 'users', ['telegram_id'])
    op.create_index('ix_users_email', 'users', ['email'])

    # Venues table
    op.create_table(
        'venues',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.String(500), nullable=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('timezone', sa.String(50), default='Europe/Moscow'),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('pos_type', postgresql.ENUM('iiko', 'rkeeper', name='postype', create_type=False), nullable=False),
        sa.Column('pos_config', postgresql.JSONB(), default=dict),
        sa.Column('last_sync_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sync_status', postgresql.ENUM('pending', 'in_progress', 'completed', 'failed', name='syncstatus', create_type=False), default='pending'),
        sa.Column('sync_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_venues_organization_id', 'venues', ['organization_id'])

    # Categories table
    op.create_table(
        'categories',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('parent_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('sort_order', sa.Integer(), default=0),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('venue_id', 'external_id', name='uq_category_venue_external'),
    )
    op.create_index('ix_categories_venue_id', 'categories', ['venue_id'])

    # Products table
    op.create_table(
        'products',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('category_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('categories.id'), nullable=True),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sku', sa.String(100), nullable=True),
        sa.Column('price', sa.Numeric(12, 2), default=0),
        sa.Column('cost_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('is_modifier', sa.Boolean(), default=False),
        sa.Column('unit', sa.String(20), default='pcs'),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('venue_id', 'external_id', name='uq_product_venue_external'),
    )
    op.create_index('ix_products_venue_id', 'products', ['venue_id'])
    op.create_index('ix_products_category_id', 'products', ['category_id'])

    # Employees table
    op.create_table(
        'employees',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('role', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('commission_rate', sa.Numeric(5, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('venue_id', 'external_id', name='uq_employee_venue_external'),
    )
    op.create_index('ix_employees_venue_id', 'employees', ['venue_id'])

    # Receipts table
    op.create_table(
        'receipts',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('employees.id'), nullable=True),
        sa.Column('external_id', sa.String(100), nullable=False),
        sa.Column('receipt_number', sa.String(50), nullable=True),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('subtotal', sa.Numeric(12, 2), default=0),
        sa.Column('discount_amount', sa.Numeric(12, 2), default=0),
        sa.Column('total', sa.Numeric(12, 2), default=0),
        sa.Column('payment_type', sa.String(50), nullable=True),
        sa.Column('is_paid', sa.Boolean(), default=True),
        sa.Column('is_deleted', sa.Boolean(), default=False),
        sa.Column('guests_count', sa.Integer(), default=1),
        sa.Column('table_number', sa.String(20), nullable=True),
        sa.Column('extra_data', postgresql.JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.UniqueConstraint('venue_id', 'external_id', name='uq_receipt_venue_external'),
    )
    op.create_index('ix_receipts_venue_id', 'receipts', ['venue_id'])
    op.create_index('ix_receipts_opened_at', 'receipts', ['opened_at'])
    op.create_index('ix_receipts_closed_at', 'receipts', ['closed_at'])
    op.create_index('ix_receipts_venue_opened', 'receipts', ['venue_id', 'opened_at'])

    # Receipt Items table
    op.create_table(
        'receipt_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('receipt_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('receipts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('product_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('products.id'), nullable=True),
        sa.Column('external_product_id', sa.String(100), nullable=False),
        sa.Column('product_name', sa.String(255), nullable=False),
        sa.Column('quantity', sa.Numeric(12, 3), default=1),
        sa.Column('unit_price', sa.Numeric(12, 2), default=0),
        sa.Column('discount_amount', sa.Numeric(12, 2), default=0),
        sa.Column('total', sa.Numeric(12, 2), default=0),
        sa.Column('cost_price', sa.Numeric(12, 2), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )
    op.create_index('ix_receipt_items_receipt_id', 'receipt_items', ['receipt_id'])
    op.create_index('ix_receipt_items_product_id', 'receipt_items', ['product_id'])

    # Daily Sales table
    op.create_table(
        'daily_sales',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('total_revenue', sa.Numeric(14, 2), default=0),
        sa.Column('total_receipts', sa.Integer(), default=0),
        sa.Column('total_items', sa.Integer(), default=0),
        sa.Column('total_guests', sa.Integer(), default=0),
        sa.Column('avg_receipt', sa.Numeric(12, 2), default=0),
        sa.Column('avg_guest_check', sa.Numeric(12, 2), default=0),
        sa.Column('total_discount', sa.Numeric(12, 2), default=0),
        sa.Column('payment_breakdown', postgresql.JSONB(), nullable=True),
        sa.Column('category_breakdown', postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint('venue_id', 'date', name='uq_daily_sales_venue_date'),
    )
    op.create_index('ix_daily_sales_venue_id', 'daily_sales', ['venue_id'])
    op.create_index('ix_daily_sales_date', 'daily_sales', ['date'])
    op.create_index('ix_daily_sales_venue_date', 'daily_sales', ['venue_id', 'date'])

    # Hourly Sales table
    op.create_table(
        'hourly_sales',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('venue_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('venues.id', ondelete='CASCADE'), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('hour', sa.Integer(), nullable=False),
        sa.Column('total_revenue', sa.Numeric(14, 2), default=0),
        sa.Column('total_receipts', sa.Integer(), default=0),
        sa.Column('total_items', sa.Integer(), default=0),
        sa.Column('total_guests', sa.Integer(), default=0),
        sa.UniqueConstraint('venue_id', 'date', 'hour', name='uq_hourly_sales_venue_date_hour'),
    )
    op.create_index('ix_hourly_sales_venue_id', 'hourly_sales', ['venue_id'])
    op.create_index('ix_hourly_sales_venue_date', 'hourly_sales', ['venue_id', 'date'])


def downgrade() -> None:
    op.drop_table('hourly_sales')
    op.drop_table('daily_sales')
    op.drop_table('receipt_items')
    op.drop_table('receipts')
    op.drop_table('employees')
    op.drop_table('products')
    op.drop_table('categories')
    op.drop_table('venues')
    op.drop_table('users')
    op.drop_table('organizations')

    op.execute("DROP TYPE syncstatus")
    op.execute("DROP TYPE postype")
    op.execute("DROP TYPE userrole")
