import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Category,
    DailySales,
    Employee,
    HourlySales,
    Product,
    Receipt,
    ReceiptItem,
    SyncStatus,
    Venue,
)
from app.integrations.iiko.client import IikoClient

logger = logging.getLogger(__name__)


class IikoSyncService:
    """Service for synchronizing data from iiko to local database."""

    def __init__(self, venue: Venue, db: AsyncSession):
        self.venue = venue
        self.db = db
        self.pos_config = venue.pos_config
        self.api_login = self.pos_config.get("api_login")
        self.organization_id = self.pos_config.get("organization_id")

        if not self.api_login or not self.organization_id:
            raise ValueError("Venue missing iiko API configuration")

    async def sync_full(self) -> Dict:
        """
        Perform full synchronization of all data.

        Returns:
            Dictionary with sync statistics
        """
        logger.info(f"Starting full sync for venue {self.venue.id}")

        stats = {
            "categories": 0,
            "products": 0,
            "employees": 0,
            "receipts": 0,
            "errors": [],
        }

        try:
            async with IikoClient(self.api_login) as client:
                # Sync nomenclature (categories and products)
                cat_count, prod_count = await self._sync_nomenclature(client)
                stats["categories"] = cat_count
                stats["products"] = prod_count

                # Sync employees
                emp_count = await self._sync_employees(client)
                stats["employees"] = emp_count

                # Sync receipts for last 30 days
                date_to = datetime.utcnow()
                date_from = date_to - timedelta(days=30)
                receipt_count = await self._sync_receipts(client, date_from, date_to)
                stats["receipts"] = receipt_count

            # Update venue sync status
            self.venue.last_sync_at = datetime.utcnow()
            self.venue.sync_status = SyncStatus.COMPLETED
            self.venue.sync_error = None

            logger.info(f"Full sync completed for venue {self.venue.id}: {stats}")

        except Exception as e:
            logger.error(f"Full sync failed for venue {self.venue.id}: {e}")
            self.venue.sync_status = SyncStatus.FAILED
            self.venue.sync_error = str(e)
            stats["errors"].append(str(e))

        return stats

    async def sync_incremental(self, since: Optional[datetime] = None) -> Dict:
        """
        Perform incremental sync of recent data.

        Args:
            since: Sync changes since this time. Defaults to last 4 hours.
        """
        logger.info(f"Starting incremental sync for venue {self.venue.id}")

        if since is None:
            since = datetime.utcnow() - timedelta(hours=4)

        stats = {
            "receipts": 0,
            "errors": [],
        }

        try:
            async with IikoClient(self.api_login) as client:
                # Only sync recent receipts for incremental
                date_to = datetime.utcnow()
                receipt_count = await self._sync_receipts(client, since, date_to)
                stats["receipts"] = receipt_count

            self.venue.last_sync_at = datetime.utcnow()
            self.venue.sync_status = SyncStatus.COMPLETED
            self.venue.sync_error = None

            logger.info(f"Incremental sync completed for venue {self.venue.id}: {stats}")

        except Exception as e:
            logger.error(f"Incremental sync failed for venue {self.venue.id}: {e}")
            self.venue.sync_status = SyncStatus.FAILED
            self.venue.sync_error = str(e)
            stats["errors"].append(str(e))

        return stats

    async def _sync_nomenclature(self, client: IikoClient) -> Tuple[int, int]:
        """Sync categories and products from iiko."""
        data = await client.get_nomenclature(self.organization_id)

        # Sync categories (groups)
        groups = data.get("groups", [])
        cat_count = await self._upsert_categories(groups)

        # Sync products
        products = data.get("products", [])
        prod_count = await self._upsert_products(products)

        return cat_count, prod_count

    async def _upsert_categories(self, groups: List[Dict]) -> int:
        """Upsert categories from iiko groups."""
        if not groups:
            return 0

        # Build external_id to internal_id mapping for parent references
        result = await self.db.execute(
            select(Category.external_id, Category.id).where(
                Category.venue_id == self.venue.id
            )
        )
        category_map = {row[0]: row[1] for row in result.fetchall()}

        count = 0
        for group in groups:
            if group.get("isDeleted"):
                continue

            external_id = group.get("id")
            parent_external_id = group.get("parentGroup")

            category_data = {
                "venue_id": self.venue.id,
                "external_id": external_id,
                "name": group.get("name", "Unknown"),
                "parent_id": category_map.get(parent_external_id),
                "sort_order": group.get("order", 0),
                "is_active": not group.get("isDeleted", False),
            }

            stmt = insert(Category).values(**category_data)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_category_venue_external",
                set_={
                    "name": stmt.excluded.name,
                    "parent_id": stmt.excluded.parent_id,
                    "sort_order": stmt.excluded.sort_order,
                    "is_active": stmt.excluded.is_active,
                    "updated_at": datetime.utcnow(),
                },
            )
            await self.db.execute(stmt)
            count += 1

        await self.db.flush()
        return count

    async def _upsert_products(self, products: List[Dict]) -> int:
        """Upsert products from iiko."""
        if not products:
            return 0

        # Get category mapping
        result = await self.db.execute(
            select(Category.external_id, Category.id).where(
                Category.venue_id == self.venue.id
            )
        )
        category_map = {row[0]: row[1] for row in result.fetchall()}

        count = 0
        for product in products:
            if product.get("isDeleted"):
                continue

            external_id = product.get("id")
            parent_group = product.get("parentGroup")

            # Get price from sizePrices if available
            price = Decimal("0")
            size_prices = product.get("sizePrices", [])
            if size_prices:
                price_info = size_prices[0].get("price", {})
                price = Decimal(str(price_info.get("currentPrice", 0)))

            # Get image URL
            image_url = None
            image_links = product.get("imageLinks", [])
            if image_links:
                image_url = image_links[0]

            product_data = {
                "venue_id": self.venue.id,
                "external_id": external_id,
                "category_id": category_map.get(parent_group),
                "name": product.get("name", "Unknown"),
                "description": product.get("description"),
                "sku": product.get("code"),
                "price": price,
                "is_active": not product.get("isDeleted", False),
                "is_modifier": product.get("type") == "Modifier",
                "unit": product.get("measureUnit", "pcs"),
                "image_url": image_url,
                "extra_data": {
                    "type": product.get("type"),
                    "groupId": parent_group,
                },
            }

            stmt = insert(Product).values(**product_data)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_product_venue_external",
                set_={
                    "category_id": stmt.excluded.category_id,
                    "name": stmt.excluded.name,
                    "description": stmt.excluded.description,
                    "sku": stmt.excluded.sku,
                    "price": stmt.excluded.price,
                    "is_active": stmt.excluded.is_active,
                    "is_modifier": stmt.excluded.is_modifier,
                    "unit": stmt.excluded.unit,
                    "image_url": stmt.excluded.image_url,
                    "extra_data": stmt.excluded.extra_data,
                    "updated_at": datetime.utcnow(),
                },
            )
            await self.db.execute(stmt)
            count += 1

        await self.db.flush()
        return count

    async def _sync_employees(self, client: IikoClient) -> int:
        """Sync employees from iiko."""
        data = await client.get_employees([self.organization_id])

        employees = []
        for org_data in data.get("employees", []):
            employees.extend(org_data.get("items", []))

        count = 0
        for emp in employees:
            if emp.get("isDeleted"):
                continue

            emp_data = {
                "venue_id": self.venue.id,
                "external_id": emp.get("id"),
                "name": emp.get("name", "Unknown"),
                "role": emp.get("mainRole"),
                "is_active": not emp.get("isDeleted", False),
            }

            stmt = insert(Employee).values(**emp_data)
            stmt = stmt.on_conflict_do_update(
                constraint="uq_employee_venue_external",
                set_={
                    "name": stmt.excluded.name,
                    "role": stmt.excluded.role,
                    "is_active": stmt.excluded.is_active,
                    "updated_at": datetime.utcnow(),
                },
            )
            await self.db.execute(stmt)
            count += 1

        await self.db.flush()
        return count

    async def _sync_receipts(
        self,
        client: IikoClient,
        date_from: datetime,
        date_to: datetime,
    ) -> int:
        """Sync receipts from iiko OLAP or orders endpoint."""
        # Get product mapping
        result = await self.db.execute(
            select(Product.external_id, Product.id).where(
                Product.venue_id == self.venue.id
            )
        )
        product_map = {row[0]: row[1] for row in result.fetchall()}

        # Get employee mapping
        result = await self.db.execute(
            select(Employee.external_id, Employee.id).where(
                Employee.venue_id == self.venue.id
            )
        )
        employee_map = {row[0]: row[1] for row in result.fetchall()}

        # For simplicity, we'll use the OLAP report to get sales data
        # In production, you might want to use the orders endpoint for detailed data
        count = 0

        try:
            # Use OLAP for aggregated sales data
            olap_data = await client.get_olap_report(
                organization_id=self.organization_id,
                date_from=date_from,
                date_to=date_to,
                report_type="SALES",
                group_by=["OpenDate", "DishId", "DishName", "Waiter.Id"],
                aggregate_fields=[
                    "DishSum",
                    "DishAmount",
                    "DishDiscountSum",
                    "UniqOrderId.OrdersCount",
                    "GuestNum",
                ],
            )

            # Process OLAP data
            # This is simplified - in production you'd want to create proper receipts
            for row in olap_data.get("data", []):
                count += 1

        except Exception as e:
            logger.warning(f"OLAP sync failed, skipping receipts: {e}")

        await self.db.flush()
        return count


async def aggregate_daily_sales(venue_id: uuid.UUID, date: datetime.date, db: AsyncSession):
    """Aggregate receipts into daily sales record."""
    from sqlalchemy import func

    # Get receipts for the date
    result = await db.execute(
        select(
            func.sum(Receipt.total).label("total_revenue"),
            func.count(Receipt.id).label("total_receipts"),
            func.sum(Receipt.guests_count).label("total_guests"),
            func.sum(Receipt.discount_amount).label("total_discount"),
        ).where(
            Receipt.venue_id == venue_id,
            func.date(Receipt.closed_at) == date,
            Receipt.is_deleted == False,
            Receipt.is_paid == True,
        )
    )
    row = result.fetchone()

    if not row or not row.total_revenue:
        return

    # Get items count
    items_result = await db.execute(
        select(func.sum(ReceiptItem.quantity)).where(
            ReceiptItem.receipt_id.in_(
                select(Receipt.id).where(
                    Receipt.venue_id == venue_id,
                    func.date(Receipt.closed_at) == date,
                )
            )
        )
    )
    total_items = items_result.scalar() or 0

    # Calculate averages
    total_receipts = row.total_receipts or 1
    total_guests = row.total_guests or 1
    avg_receipt = row.total_revenue / total_receipts
    avg_guest_check = row.total_revenue / total_guests

    daily_data = {
        "venue_id": venue_id,
        "date": date,
        "total_revenue": row.total_revenue,
        "total_receipts": total_receipts,
        "total_items": int(total_items),
        "total_guests": total_guests,
        "avg_receipt": avg_receipt,
        "avg_guest_check": avg_guest_check,
        "total_discount": row.total_discount or 0,
    }

    stmt = insert(DailySales).values(**daily_data)
    stmt = stmt.on_conflict_do_update(
        constraint="uq_daily_sales_venue_date",
        set_={
            "total_revenue": stmt.excluded.total_revenue,
            "total_receipts": stmt.excluded.total_receipts,
            "total_items": stmt.excluded.total_items,
            "total_guests": stmt.excluded.total_guests,
            "avg_receipt": stmt.excluded.avg_receipt,
            "avg_guest_check": stmt.excluded.avg_guest_check,
            "total_discount": stmt.excluded.total_discount,
        },
    )
    await db.execute(stmt)
    await db.flush()
