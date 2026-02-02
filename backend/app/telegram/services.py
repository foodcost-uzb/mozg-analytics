"""Telegram bot service layer for database operations."""

from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
import secrets
import uuid

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.db.models import (
    DailySales,
    Organization,
    User,
    Venue,
)
from app.telegram.formatters import (
    ABCReportData,
    AnomalyData,
    ForecastData,
    SalesSummaryData,
)


class TelegramUserService:
    """Service for Telegram user operations."""

    def __init__(self):
        self._engine = None
        self._link_codes: Dict[str, Dict[str, Any]] = {}  # In-memory storage for link codes

    async def _get_session(self) -> AsyncSession:
        """Get database session."""
        if self._engine is None:
            self._engine = create_async_engine(settings.DATABASE_URL)

        from sqlalchemy.orm import sessionmaker

        async_session = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        return async_session()

    async def get_user_by_telegram_id(self, telegram_id: int) -> Optional[User]:
        """Get user by Telegram ID."""
        session = await self._get_session()
        try:
            result = await session.execute(
                select(User)
                .where(User.telegram_id == telegram_id)
                .options(selectinload(User.organization))
            )
            return result.scalar_one_or_none()
        finally:
            await session.close()

    async def get_user_venues(self, user: User) -> List[Venue]:
        """Get venues accessible to user."""
        session = await self._get_session()
        try:
            query = select(Venue).where(
                and_(
                    Venue.organization_id == user.organization_id,
                    Venue.is_active == True,
                )
            )

            # Filter by allowed venues if specified
            if user.allowed_venue_ids:
                venue_uuids = [uuid.UUID(v) for v in user.allowed_venue_ids]
                query = query.where(Venue.id.in_(venue_uuids))

            query = query.order_by(Venue.name)
            result = await session.execute(query)
            return list(result.scalars().all())
        finally:
            await session.close()

    async def get_venue_info(self, user: User, venue_id: uuid.UUID) -> Optional[Venue]:
        """Get venue details."""
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Venue).where(
                    and_(
                        Venue.id == venue_id,
                        Venue.organization_id == user.organization_id,
                    )
                )
            )
            return result.scalar_one_or_none()
        finally:
            await session.close()

    async def get_sales_summary(
        self,
        user: User,
        start_date: date,
        end_date: date,
        venue_id: Optional[uuid.UUID] = None,
    ) -> SalesSummaryData:
        """Get sales summary for period."""
        session = await self._get_session()
        try:
            # Get venue IDs
            if venue_id:
                venue_ids = [venue_id]
            else:
                venues = await self.get_user_venues(user)
                venue_ids = [v.id for v in venues]

            if not venue_ids:
                return SalesSummaryData(
                    total_revenue=Decimal("0"),
                    total_receipts=0,
                    avg_receipt=Decimal("0"),
                    total_guests=0,
                )

            # Get daily sales for period
            result = await session.execute(
                select(DailySales).where(
                    and_(
                        DailySales.venue_id.in_(venue_ids),
                        DailySales.date >= start_date,
                        DailySales.date <= end_date,
                    )
                )
            )
            daily_sales = list(result.scalars().all())

            if not daily_sales:
                return SalesSummaryData(
                    total_revenue=Decimal("0"),
                    total_receipts=0,
                    avg_receipt=Decimal("0"),
                    total_guests=0,
                )

            # Calculate totals
            total_revenue = sum(d.total_revenue for d in daily_sales)
            total_receipts = sum(d.total_receipts for d in daily_sales)
            total_guests = sum(d.total_guests for d in daily_sales)
            avg_receipt = total_revenue / total_receipts if total_receipts > 0 else Decimal("0")

            # Calculate previous period for comparison
            period_days = (end_date - start_date).days + 1
            prev_start = start_date - timedelta(days=period_days)
            prev_end = end_date - timedelta(days=period_days)

            prev_result = await session.execute(
                select(DailySales).where(
                    and_(
                        DailySales.venue_id.in_(venue_ids),
                        DailySales.date >= prev_start,
                        DailySales.date <= prev_end,
                    )
                )
            )
            prev_sales = list(prev_result.scalars().all())
            prev_revenue = sum(d.total_revenue for d in prev_sales)

            growth_percent = None
            if prev_revenue > 0:
                growth_percent = float((total_revenue - prev_revenue) / prev_revenue * 100)

            return SalesSummaryData(
                total_revenue=total_revenue,
                total_receipts=total_receipts,
                avg_receipt=avg_receipt,
                total_guests=total_guests,
                previous_revenue=prev_revenue if prev_revenue > 0 else None,
                growth_percent=growth_percent,
            )
        finally:
            await session.close()

    async def get_quick_forecast(
        self,
        user: User,
        days: int = 7,
    ) -> ForecastData:
        """Get quick revenue forecast."""
        session = await self._get_session()
        try:
            venues = await self.get_user_venues(user)
            venue_ids = [v.id for v in venues]

            if not venue_ids:
                return ForecastData(
                    total=Decimal("0"),
                    avg_daily=Decimal("0"),
                    days=days,
                )

            # Get historical data for simple forecast
            end_date = date.today() - timedelta(days=1)
            start_date = end_date - timedelta(days=30)

            result = await session.execute(
                select(DailySales).where(
                    and_(
                        DailySales.venue_id.in_(venue_ids),
                        DailySales.date >= start_date,
                        DailySales.date <= end_date,
                    )
                ).order_by(DailySales.date)
            )
            daily_sales = list(result.scalars().all())

            if not daily_sales:
                return ForecastData(
                    total=Decimal("0"),
                    avg_daily=Decimal("0"),
                    days=days,
                )

            # Simple average-based forecast
            avg_daily = sum(d.total_revenue for d in daily_sales) / len(daily_sales)
            total = avg_daily * days

            # Calculate growth trend
            first_half = daily_sales[: len(daily_sales) // 2]
            second_half = daily_sales[len(daily_sales) // 2 :]

            first_avg = sum(d.total_revenue for d in first_half) / len(first_half) if first_half else 0
            second_avg = sum(d.total_revenue for d in second_half) / len(second_half) if second_half else 0

            growth_percent = None
            if first_avg > 0:
                growth_percent = float((second_avg - first_avg) / first_avg * 100)

            # Generate daily forecast
            daily_forecast = []
            for i in range(days):
                forecast_date = date.today() + timedelta(days=i)
                daily_forecast.append({
                    "date": forecast_date,
                    "forecast": avg_daily,
                })

            return ForecastData(
                total=total,
                avg_daily=avg_daily,
                days=days,
                growth_percent=growth_percent,
                daily_forecast=daily_forecast,
            )
        finally:
            await session.close()

    async def get_recent_anomalies(
        self,
        user: User,
        days: int = 7,
        limit: int = 5,
    ) -> List[AnomalyData]:
        """Get recent anomalies."""
        session = await self._get_session()
        try:
            venues = await self.get_user_venues(user)
            venue_ids = [v.id for v in venues]

            if not venue_ids:
                return []

            # Get daily sales
            end_date = date.today()
            start_date = end_date - timedelta(days=days)

            result = await session.execute(
                select(DailySales).where(
                    and_(
                        DailySales.venue_id.in_(venue_ids),
                        DailySales.date >= start_date,
                        DailySales.date <= end_date,
                    )
                ).order_by(DailySales.date)
            )
            daily_sales = list(result.scalars().all())

            if len(daily_sales) < 7:
                return []

            # Simple anomaly detection using z-score
            revenues = [float(d.total_revenue) for d in daily_sales]
            mean_revenue = sum(revenues) / len(revenues)
            variance = sum((r - mean_revenue) ** 2 for r in revenues) / len(revenues)
            std_revenue = variance ** 0.5 if variance > 0 else 1

            anomalies = []
            for sales in daily_sales:
                z_score = (float(sales.total_revenue) - mean_revenue) / std_revenue if std_revenue > 0 else 0

                if abs(z_score) >= 2:  # 2 sigma threshold
                    severity = "low"
                    if abs(z_score) >= 3:
                        severity = "medium"
                    if abs(z_score) >= 4:
                        severity = "high"
                    if abs(z_score) >= 5:
                        severity = "critical"

                    anomaly_type = "revenue_spike" if z_score > 0 else "revenue_drop"
                    deviation_percent = (float(sales.total_revenue) - mean_revenue) / mean_revenue * 100

                    anomalies.append(
                        AnomalyData(
                            anomaly_type=anomaly_type,
                            severity=severity,
                            date=sales.date,
                            actual_value=sales.total_revenue,
                            expected_value=Decimal(str(mean_revenue)),
                            deviation_percent=deviation_percent,
                            metric_name="Выручка",
                            description=f"{'Всплеск' if z_score > 0 else 'Падение'} выручки",
                            possible_causes=[
                                "Специальная акция или событие" if z_score > 0 else "Внешние факторы",
                                "Изменение трафика",
                            ],
                        )
                    )

            # Sort by severity and date
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            anomalies.sort(key=lambda a: (severity_order.get(a.severity, 4), -a.date.toordinal()))

            return anomalies[:limit]
        finally:
            await session.close()

    async def get_abc_report(self, user: User) -> ABCReportData:
        """Get ABC analysis report."""
        # This is a simplified version - full implementation would use MenuAnalysisService
        return ABCReportData(
            a_products=[
                {"name": "Пицца Маргарита", "revenue": Decimal("150000")},
                {"name": "Бургер Классический", "revenue": Decimal("120000")},
                {"name": "Салат Цезарь", "revenue": Decimal("90000")},
            ],
            b_products=[
                {"name": "Паста Карбонара", "revenue": Decimal("50000")},
                {"name": "Суп дня", "revenue": Decimal("40000")},
            ],
            c_products=[
                {"name": "Десерт 1", "revenue": Decimal("10000")},
                {"name": "Десерт 2", "revenue": Decimal("8000")},
            ],
            a_percent=70,
            b_percent=20,
            c_percent=10,
        )

    async def generate_excel_report(self, user: User) -> Optional[bytes]:
        """Generate Excel report."""
        # Placeholder - would integrate with ExportService
        return None

    async def get_notification_settings(self, user: User) -> Dict[str, bool]:
        """Get user notification settings."""
        session = await self._get_session()
        try:
            # Get from organization settings or user settings
            result = await session.execute(
                select(Organization).where(Organization.id == user.organization_id)
            )
            org = result.scalar_one_or_none()

            if org and org.settings and "telegram_notifications" in org.settings:
                return org.settings["telegram_notifications"]

            # Default settings
            return {
                "morning_report": True,
                "evening_report": True,
                "anomaly_alerts": True,
                "goal_alerts": True,
            }
        finally:
            await session.close()

    async def toggle_notification_setting(
        self, user: User, setting_key: str
    ) -> Dict[str, bool]:
        """Toggle notification setting."""
        session = await self._get_session()
        try:
            result = await session.execute(
                select(Organization).where(Organization.id == user.organization_id)
            )
            org = result.scalar_one_or_none()

            if not org:
                return {}

            if org.settings is None:
                org.settings = {}

            if "telegram_notifications" not in org.settings:
                org.settings["telegram_notifications"] = {
                    "morning_report": True,
                    "evening_report": True,
                    "anomaly_alerts": True,
                    "goal_alerts": True,
                }

            # Toggle the setting
            current = org.settings["telegram_notifications"].get(setting_key, True)
            org.settings["telegram_notifications"][setting_key] = not current

            # Update in database
            org.settings = dict(org.settings)  # Force update
            await session.commit()

            return org.settings["telegram_notifications"]
        finally:
            await session.close()

    async def generate_link_code(
        self,
        telegram_id: int,
        telegram_username: Optional[str],
        first_name: str,
        last_name: Optional[str],
    ) -> str:
        """Generate account link code."""
        code = secrets.token_hex(4).upper()

        self._link_codes[code] = {
            "telegram_id": telegram_id,
            "telegram_username": telegram_username,
            "first_name": first_name,
            "last_name": last_name,
            "created_at": datetime.utcnow(),
        }

        return code

    async def verify_link_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Verify and consume link code."""
        if code not in self._link_codes:
            return None

        data = self._link_codes[code]

        # Check expiration (10 minutes)
        if datetime.utcnow() - data["created_at"] > timedelta(minutes=10):
            del self._link_codes[code]
            return None

        # Consume the code
        del self._link_codes[code]
        return data

    async def get_users_for_notification(
        self, notification_type: str
    ) -> List[Dict[str, Any]]:
        """Get users who should receive notification."""
        session = await self._get_session()
        try:
            # Get all users with telegram_id
            result = await session.execute(
                select(User)
                .where(
                    and_(
                        User.telegram_id.isnot(None),
                        User.is_active == True,
                    )
                )
                .options(selectinload(User.organization))
            )
            users = list(result.scalars().all())

            # Filter by notification settings
            notification_users = []
            for user in users:
                if user.organization and user.organization.settings:
                    settings = user.organization.settings.get("telegram_notifications", {})
                    if settings.get(notification_type, True):
                        notification_users.append({
                            "user": user,
                            "telegram_id": user.telegram_id,
                            "organization_id": user.organization_id,
                        })
                else:
                    # Default: send notifications
                    notification_users.append({
                        "user": user,
                        "telegram_id": user.telegram_id,
                        "organization_id": user.organization_id,
                    })

            return notification_users
        finally:
            await session.close()
