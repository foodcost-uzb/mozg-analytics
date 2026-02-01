"""Sales report service for MOZG Analytics."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailySales, HourlySales, Receipt, ReceiptItem, Venue


class GroupBy(str, Enum):
    """Grouping options for sales reports."""

    DAY = "day"
    WEEK = "week"
    MONTH = "month"


class CompareWith(str, Enum):
    """Comparison period options."""

    PREVIOUS = "previous"
    YEAR_AGO = "year_ago"


@dataclass
class SalesSummary:
    """Summary of sales for a period."""

    revenue: Decimal
    receipts_count: int
    avg_check: Decimal
    guests_count: int
    items_count: int
    items_per_receipt: Decimal
    revenue_per_guest: Decimal
    total_discount: Decimal


@dataclass
class SalesDataPoint:
    """Single data point for time series."""

    date: date
    revenue: Decimal
    receipts_count: int
    avg_check: Decimal
    guests_count: int


@dataclass
class SalesComparison:
    """Comparison between two periods."""

    current: SalesSummary
    previous: SalesSummary
    revenue_diff: Decimal
    revenue_diff_percent: Decimal
    receipts_diff: int
    receipts_diff_percent: Decimal
    avg_check_diff: Decimal
    avg_check_diff_percent: Decimal
    guests_diff: int
    guests_diff_percent: Decimal


@dataclass
class VenueSales:
    """Sales data for a single venue."""

    venue_id: uuid.UUID
    venue_name: str
    revenue: Decimal
    receipts_count: int
    avg_check: Decimal
    guests_count: int
    revenue_percent: Decimal  # % of total


@dataclass
class HourlySalesData:
    """Hourly sales breakdown."""

    hour: int  # 0-23
    revenue: Decimal
    receipts_count: int
    avg_revenue: Decimal  # average across selected days


class SalesReportService:
    """Service for generating sales reports."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> SalesSummary:
        """
        Get sales summary for specified venues and period.

        Args:
            venue_ids: List of venue UUIDs to include
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            SalesSummary with aggregated metrics
        """
        # Query from pre-aggregated daily_sales table
        query = select(
            func.coalesce(func.sum(DailySales.total_revenue), 0).label("revenue"),
            func.coalesce(func.sum(DailySales.total_receipts), 0).label("receipts_count"),
            func.coalesce(func.sum(DailySales.total_guests), 0).label("guests_count"),
            func.coalesce(func.sum(DailySales.total_items), 0).label("items_count"),
            func.coalesce(func.sum(DailySales.total_discount), 0).label("total_discount"),
        ).where(
            and_(
                DailySales.venue_id.in_(venue_ids),
                DailySales.date >= date_from,
                DailySales.date <= date_to,
            )
        )

        result = await self.db.execute(query)
        row = result.one()

        revenue = Decimal(str(row.revenue))
        receipts_count = int(row.receipts_count)
        guests_count = int(row.guests_count)
        items_count = int(row.items_count)
        total_discount = Decimal(str(row.total_discount))

        # Calculate derived metrics
        avg_check = revenue / receipts_count if receipts_count > 0 else Decimal("0")
        items_per_receipt = (
            Decimal(str(items_count)) / receipts_count if receipts_count > 0 else Decimal("0")
        )
        revenue_per_guest = revenue / guests_count if guests_count > 0 else Decimal("0")

        return SalesSummary(
            revenue=revenue,
            receipts_count=receipts_count,
            avg_check=round(avg_check, 2),
            guests_count=guests_count,
            items_count=items_count,
            items_per_receipt=round(items_per_receipt, 2),
            revenue_per_guest=round(revenue_per_guest, 2),
            total_discount=total_discount,
        )

    async def get_daily(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[SalesDataPoint]:
        """
        Get daily sales breakdown.

        Args:
            venue_ids: List of venue UUIDs to include
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of SalesDataPoint for each day
        """
        query = (
            select(
                DailySales.date,
                func.sum(DailySales.total_revenue).label("revenue"),
                func.sum(DailySales.total_receipts).label("receipts_count"),
                func.sum(DailySales.total_guests).label("guests_count"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                    DailySales.date <= date_to,
                )
            )
            .group_by(DailySales.date)
            .order_by(DailySales.date)
        )

        result = await self.db.execute(query)
        rows = result.all()

        data_points = []
        for row in rows:
            revenue = Decimal(str(row.revenue))
            receipts_count = int(row.receipts_count)
            avg_check = revenue / receipts_count if receipts_count > 0 else Decimal("0")

            data_points.append(
                SalesDataPoint(
                    date=row.date,
                    revenue=revenue,
                    receipts_count=receipts_count,
                    avg_check=round(avg_check, 2),
                    guests_count=int(row.guests_count),
                )
            )

        return data_points

    async def get_comparison(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        compare_with: CompareWith = CompareWith.PREVIOUS,
    ) -> SalesComparison:
        """
        Compare sales between current period and previous period.

        Args:
            venue_ids: List of venue UUIDs to include
            date_from: Start date of current period
            date_to: End date of current period
            compare_with: How to determine comparison period

        Returns:
            SalesComparison with current, previous and diff metrics
        """
        # Calculate comparison period
        period_days = (date_to - date_from).days + 1

        if compare_with == CompareWith.YEAR_AGO:
            prev_date_from = date_from.replace(year=date_from.year - 1)
            prev_date_to = date_to.replace(year=date_to.year - 1)
        else:  # PREVIOUS
            prev_date_to = date_from - timedelta(days=1)
            prev_date_from = prev_date_to - timedelta(days=period_days - 1)

        # Get summaries for both periods
        current = await self.get_summary(venue_ids, date_from, date_to)
        previous = await self.get_summary(venue_ids, prev_date_from, prev_date_to)

        # Calculate diffs
        revenue_diff = current.revenue - previous.revenue
        revenue_diff_percent = (
            (revenue_diff / previous.revenue * 100) if previous.revenue > 0 else Decimal("0")
        )

        receipts_diff = current.receipts_count - previous.receipts_count
        receipts_diff_percent = (
            Decimal(str(receipts_diff)) / previous.receipts_count * 100
            if previous.receipts_count > 0
            else Decimal("0")
        )

        avg_check_diff = current.avg_check - previous.avg_check
        avg_check_diff_percent = (
            (avg_check_diff / previous.avg_check * 100) if previous.avg_check > 0 else Decimal("0")
        )

        guests_diff = current.guests_count - previous.guests_count
        guests_diff_percent = (
            Decimal(str(guests_diff)) / previous.guests_count * 100
            if previous.guests_count > 0
            else Decimal("0")
        )

        return SalesComparison(
            current=current,
            previous=previous,
            revenue_diff=revenue_diff,
            revenue_diff_percent=round(revenue_diff_percent, 2),
            receipts_diff=receipts_diff,
            receipts_diff_percent=round(receipts_diff_percent, 2),
            avg_check_diff=avg_check_diff,
            avg_check_diff_percent=round(avg_check_diff_percent, 2),
            guests_diff=guests_diff,
            guests_diff_percent=round(guests_diff_percent, 2),
        )

    async def get_by_venue(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[VenueSales]:
        """
        Get sales breakdown by venue.

        Args:
            venue_ids: List of venue UUIDs to include
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of VenueSales sorted by revenue descending
        """
        query = (
            select(
                DailySales.venue_id,
                Venue.name.label("venue_name"),
                func.sum(DailySales.total_revenue).label("revenue"),
                func.sum(DailySales.total_receipts).label("receipts_count"),
                func.sum(DailySales.total_guests).label("guests_count"),
            )
            .join(Venue, Venue.id == DailySales.venue_id)
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                    DailySales.date <= date_to,
                )
            )
            .group_by(DailySales.venue_id, Venue.name)
            .order_by(func.sum(DailySales.total_revenue).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Calculate total revenue for percentage
        total_revenue = sum(Decimal(str(row.revenue)) for row in rows)

        venue_sales = []
        for row in rows:
            revenue = Decimal(str(row.revenue))
            receipts_count = int(row.receipts_count)
            avg_check = revenue / receipts_count if receipts_count > 0 else Decimal("0")
            revenue_percent = (revenue / total_revenue * 100) if total_revenue > 0 else Decimal("0")

            venue_sales.append(
                VenueSales(
                    venue_id=row.venue_id,
                    venue_name=row.venue_name,
                    revenue=revenue,
                    receipts_count=receipts_count,
                    avg_check=round(avg_check, 2),
                    guests_count=int(row.guests_count),
                    revenue_percent=round(revenue_percent, 2),
                )
            )

        return venue_sales

    async def get_hourly(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[HourlySalesData]:
        """
        Get hourly sales breakdown (averaged across days).

        Args:
            venue_ids: List of venue UUIDs to include
            date_from: Start date (inclusive)
            date_to: End date (inclusive)

        Returns:
            List of HourlySalesData for hours 0-23
        """
        period_days = (date_to - date_from).days + 1

        query = (
            select(
                HourlySales.hour,
                func.sum(HourlySales.total_revenue).label("revenue"),
                func.sum(HourlySales.total_receipts).label("receipts_count"),
            )
            .where(
                and_(
                    HourlySales.venue_id.in_(venue_ids),
                    HourlySales.date >= date_from,
                    HourlySales.date <= date_to,
                )
            )
            .group_by(HourlySales.hour)
            .order_by(HourlySales.hour)
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Create a dict for easy lookup
        hourly_data = {row.hour: row for row in rows}

        hourly_sales = []
        for hour in range(24):
            if hour in hourly_data:
                row = hourly_data[hour]
                revenue = Decimal(str(row.revenue))
                receipts_count = int(row.receipts_count)
                avg_revenue = revenue / period_days
            else:
                revenue = Decimal("0")
                receipts_count = 0
                avg_revenue = Decimal("0")

            hourly_sales.append(
                HourlySalesData(
                    hour=hour,
                    revenue=revenue,
                    receipts_count=receipts_count,
                    avg_revenue=round(avg_revenue, 2),
                )
            )

        return hourly_sales

    async def get_plan_fact(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        target_revenue: Optional[Decimal] = None,
    ) -> dict:
        """
        Get plan/fact comparison for revenue.

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date
            target_revenue: Target revenue for the period (optional)

        Returns:
            Dict with actual, target, completion percentage
        """
        summary = await self.get_summary(venue_ids, date_from, date_to)

        # If no target provided, calculate based on previous period
        if target_revenue is None:
            period_days = (date_to - date_from).days + 1
            prev_date_to = date_from - timedelta(days=1)
            prev_date_from = prev_date_to - timedelta(days=period_days - 1)
            prev_summary = await self.get_summary(venue_ids, prev_date_from, prev_date_to)
            target_revenue = prev_summary.revenue

        completion_percent = (
            (summary.revenue / target_revenue * 100) if target_revenue > 0 else Decimal("0")
        )

        return {
            "actual_revenue": summary.revenue,
            "target_revenue": target_revenue,
            "completion_percent": round(completion_percent, 2),
            "remaining": max(target_revenue - summary.revenue, Decimal("0")),
            "receipts_count": summary.receipts_count,
            "avg_check": summary.avg_check,
        }

    async def get_top_days(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        limit: int = 10,
    ) -> List[SalesDataPoint]:
        """
        Get top N days by revenue.

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date
            limit: Number of days to return

        Returns:
            List of SalesDataPoint sorted by revenue descending
        """
        query = (
            select(
                DailySales.date,
                func.sum(DailySales.total_revenue).label("revenue"),
                func.sum(DailySales.total_receipts).label("receipts_count"),
                func.sum(DailySales.total_guests).label("guests_count"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                    DailySales.date <= date_to,
                )
            )
            .group_by(DailySales.date)
            .order_by(func.sum(DailySales.total_revenue).desc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        rows = result.all()

        data_points = []
        for row in rows:
            revenue = Decimal(str(row.revenue))
            receipts_count = int(row.receipts_count)
            avg_check = revenue / receipts_count if receipts_count > 0 else Decimal("0")

            data_points.append(
                SalesDataPoint(
                    date=row.date,
                    revenue=revenue,
                    receipts_count=receipts_count,
                    avg_check=round(avg_check, 2),
                    guests_count=int(row.guests_count),
                )
            )

        return data_points

    async def get_weekday_analysis(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> dict:
        """
        Get average sales by day of week.

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date

        Returns:
            Dict with weekday name -> average metrics
        """
        # Use extract for weekday (0=Monday in PostgreSQL)
        query = (
            select(
                func.extract("dow", DailySales.date).label("weekday"),
                func.avg(DailySales.total_revenue).label("avg_revenue"),
                func.avg(DailySales.total_receipts).label("avg_receipts"),
                func.avg(DailySales.avg_receipt).label("avg_check"),
                func.count(DailySales.date).label("days_count"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                    DailySales.date <= date_to,
                )
            )
            .group_by(func.extract("dow", DailySales.date))
            .order_by(func.extract("dow", DailySales.date))
        )

        result = await self.db.execute(query)
        rows = result.all()

        weekday_names = [
            "Sunday",
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
        ]

        weekday_data = {}
        for row in rows:
            weekday_idx = int(row.weekday)
            weekday_name = weekday_names[weekday_idx]
            weekday_data[weekday_name] = {
                "avg_revenue": round(Decimal(str(row.avg_revenue)), 2),
                "avg_receipts": round(float(row.avg_receipts), 1),
                "avg_check": round(Decimal(str(row.avg_check)), 2),
                "days_count": int(row.days_count),
            }

        return weekday_data
