"""Motive Marketing analysis service - 6 factors affecting sales."""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select, extract
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailySales, Receipt, ReceiptItem, Venue


class MotiveFactor(str, Enum):
    """Six factors that influence restaurant sales."""

    WEEKDAY = "weekday"           # Day of week patterns
    SEASONALITY = "seasonality"   # Monthly/seasonal trends
    WEATHER = "weather"           # Weather impact (requires external data)
    EVENTS = "events"             # Holidays, local events
    PRICING = "pricing"           # Menu price changes
    MARKETING = "marketing"       # Promotions, campaigns


class ImpactLevel(str, Enum):
    """Impact level of a factor."""

    VERY_POSITIVE = "very_positive"   # +15% or more
    POSITIVE = "positive"             # +5% to +15%
    NEUTRAL = "neutral"               # -5% to +5%
    NEGATIVE = "negative"             # -5% to -15%
    VERY_NEGATIVE = "very_negative"   # -15% or less


@dataclass
class FactorImpact:
    """Impact analysis of a single factor."""

    factor: MotiveFactor
    impact_level: ImpactLevel
    impact_percent: Decimal
    description: str
    recommendation: str


@dataclass
class WeekdayAnalysis:
    """Sales analysis by day of week."""

    day: int  # 0 = Monday, 6 = Sunday
    day_name: str
    avg_revenue: Decimal
    avg_receipts: int
    avg_check: Decimal
    index: Decimal  # 100 = average, >100 = above average
    best_hours: List[int]


@dataclass
class SeasonalityAnalysis:
    """Monthly seasonality analysis."""

    month: int
    month_name: str
    avg_revenue: Decimal
    index: Decimal  # 100 = average
    trend: str  # "up", "down", "stable"
    year_over_year: Optional[Decimal]  # % change vs last year


@dataclass
class EventImpact:
    """Impact of specific events/holidays."""

    event_name: str
    event_date: date
    actual_revenue: Decimal
    expected_revenue: Decimal
    impact_percent: Decimal
    impact_level: ImpactLevel


@dataclass
class PricingImpact:
    """Impact of pricing changes on sales."""

    product_name: str
    old_price: Decimal
    new_price: Decimal
    price_change_percent: Decimal
    quantity_before: int
    quantity_after: int
    quantity_change_percent: Decimal
    revenue_impact: Decimal
    elasticity: Decimal  # Price elasticity of demand


@dataclass
class MotiveReport:
    """Complete Motive Marketing report."""

    period_start: date
    period_end: date
    venue_ids: List[uuid.UUID]

    # Summary
    total_revenue: Decimal
    avg_daily_revenue: Decimal

    # Factor analyses
    weekday_analysis: List[WeekdayAnalysis]
    seasonality_analysis: List[SeasonalityAnalysis]
    event_impacts: List[EventImpact]
    pricing_impacts: List[PricingImpact]

    # Overall factor impacts
    factor_summary: List[FactorImpact]

    # Recommendations
    top_recommendations: List[str] = field(default_factory=list)


class MotiveMarketingService:
    """
    Motive Marketing analysis service.

    Analyzes 6 factors that influence restaurant sales:
    1. Weekday patterns
    2. Seasonality trends
    3. Weather impact
    4. Events/holidays
    5. Pricing changes
    6. Marketing campaigns
    """

    WEEKDAY_NAMES = {
        0: "Понедельник",
        1: "Вторник",
        2: "Среда",
        3: "Четверг",
        4: "Пятница",
        5: "Суббота",
        6: "Воскресенье",
    }

    MONTH_NAMES = {
        1: "Январь", 2: "Февраль", 3: "Март", 4: "Апрель",
        5: "Май", 6: "Июнь", 7: "Июль", 8: "Август",
        9: "Сентябрь", 10: "Октябрь", 11: "Ноябрь", 12: "Декабрь",
    }

    # Russian holidays (simplified)
    HOLIDAYS = {
        (1, 1): "Новый год",
        (1, 7): "Рождество",
        (2, 14): "День Святого Валентина",
        (2, 23): "День защитника Отечества",
        (3, 8): "Международный женский день",
        (5, 1): "Праздник весны и труда",
        (5, 9): "День Победы",
        (6, 12): "День России",
        (11, 4): "День народного единства",
        (12, 31): "Новогодняя ночь",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def analyze_weekdays(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[WeekdayAnalysis]:
        """Analyze sales patterns by day of week."""

        # Query daily sales with day of week
        query = (
            select(
                extract("dow", DailySales.date).label("dow"),
                func.avg(DailySales.total_revenue).label("avg_revenue"),
                func.avg(DailySales.total_receipts).label("avg_receipts"),
                func.avg(DailySales.avg_receipt).label("avg_check"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                    DailySales.date <= date_to,
                )
            )
            .group_by(extract("dow", DailySales.date))
            .order_by(extract("dow", DailySales.date))
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Calculate overall average for index
        total_avg = sum(r.avg_revenue for r in rows) / len(rows)

        analyses = []
        for row in rows:
            # PostgreSQL DOW: 0 = Sunday, 1 = Monday, etc.
            # Convert to Python: 0 = Monday
            python_dow = (int(row.dow) + 6) % 7

            index = (Decimal(str(row.avg_revenue)) / total_avg * 100) if total_avg > 0 else Decimal("100")

            # Get best hours for this day (would need hourly data join)
            best_hours = await self._get_best_hours_for_day(venue_ids, date_from, date_to, python_dow)

            analyses.append(WeekdayAnalysis(
                day=python_dow,
                day_name=self.WEEKDAY_NAMES[python_dow],
                avg_revenue=Decimal(str(row.avg_revenue)).quantize(Decimal("0.01")),
                avg_receipts=int(row.avg_receipts),
                avg_check=Decimal(str(row.avg_check)).quantize(Decimal("0.01")),
                index=index.quantize(Decimal("0.1")),
                best_hours=best_hours,
            ))

        return analyses

    async def _get_best_hours_for_day(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        dow: int,
    ) -> List[int]:
        """Get top 3 hours by revenue for a specific day of week."""
        from app.db.models import HourlySales

        # PostgreSQL DOW conversion
        pg_dow = (dow + 1) % 7

        query = (
            select(
                HourlySales.hour,
                func.avg(HourlySales.total_revenue).label("avg_revenue"),
            )
            .where(
                and_(
                    HourlySales.venue_id.in_(venue_ids),
                    HourlySales.date >= date_from,
                    HourlySales.date <= date_to,
                    extract("dow", HourlySales.date) == pg_dow,
                )
            )
            .group_by(HourlySales.hour)
            .order_by(func.avg(HourlySales.total_revenue).desc())
            .limit(3)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [row.hour for row in rows]

    async def analyze_seasonality(
        self,
        venue_ids: List[uuid.UUID],
        months: int = 12,
    ) -> List[SeasonalityAnalysis]:
        """Analyze monthly seasonality trends."""

        date_to = date.today()
        date_from = date_to - timedelta(days=months * 31)

        # Current period by month
        query = (
            select(
                extract("month", DailySales.date).label("month"),
                extract("year", DailySales.date).label("year"),
                func.sum(DailySales.total_revenue).label("total_revenue"),
                func.count(DailySales.id).label("days_count"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                    DailySales.date <= date_to,
                )
            )
            .group_by(
                extract("year", DailySales.date),
                extract("month", DailySales.date),
            )
            .order_by(
                extract("year", DailySales.date),
                extract("month", DailySales.date),
            )
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Group by month across years
        monthly_data: Dict[int, List[Tuple[int, Decimal]]] = {}
        for row in rows:
            month = int(row.month)
            year = int(row.year)
            avg_daily = Decimal(str(row.total_revenue)) / row.days_count if row.days_count > 0 else Decimal("0")

            if month not in monthly_data:
                monthly_data[month] = []
            monthly_data[month].append((year, avg_daily))

        # Calculate indices
        all_avgs = [avg for data in monthly_data.values() for _, avg in data]
        overall_avg = sum(all_avgs) / len(all_avgs) if all_avgs else Decimal("1")

        analyses = []
        for month in range(1, 13):
            if month not in monthly_data:
                continue

            data = monthly_data[month]
            current_avg = data[-1][1] if data else Decimal("0")

            # Year over year if we have data
            yoy = None
            if len(data) >= 2:
                prev_avg = data[-2][1]
                if prev_avg > 0:
                    yoy = ((current_avg - prev_avg) / prev_avg * 100).quantize(Decimal("0.1"))

            # Determine trend
            if len(data) >= 3:
                recent = sum(d[1] for d in data[-2:]) / 2
                earlier = sum(d[1] for d in data[:-2]) / len(data[:-2]) if len(data) > 2 else recent
                if recent > earlier * Decimal("1.05"):
                    trend = "up"
                elif recent < earlier * Decimal("0.95"):
                    trend = "down"
                else:
                    trend = "stable"
            else:
                trend = "stable"

            index = (current_avg / overall_avg * 100) if overall_avg > 0 else Decimal("100")

            analyses.append(SeasonalityAnalysis(
                month=month,
                month_name=self.MONTH_NAMES[month],
                avg_revenue=current_avg.quantize(Decimal("0.01")),
                index=index.quantize(Decimal("0.1")),
                trend=trend,
                year_over_year=yoy,
            ))

        return analyses

    async def analyze_events(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[EventImpact]:
        """Analyze impact of holidays and events on sales."""

        # Get daily sales data
        query = (
            select(
                DailySales.date,
                func.sum(DailySales.total_revenue).label("revenue"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                    DailySales.date <= date_to,
                )
            )
            .group_by(DailySales.date)
        )

        result = await self.db.execute(query)
        daily_data = {row.date: Decimal(str(row.revenue)) for row in result.all()}

        if not daily_data:
            return []

        # Calculate expected (average) revenue
        avg_revenue = sum(daily_data.values()) / len(daily_data)

        impacts = []
        for d, revenue in daily_data.items():
            # Check if this date is a holiday
            key = (d.month, d.day)
            if key in self.HOLIDAYS:
                impact_percent = ((revenue - avg_revenue) / avg_revenue * 100) if avg_revenue > 0 else Decimal("0")

                if impact_percent >= 15:
                    level = ImpactLevel.VERY_POSITIVE
                elif impact_percent >= 5:
                    level = ImpactLevel.POSITIVE
                elif impact_percent <= -15:
                    level = ImpactLevel.VERY_NEGATIVE
                elif impact_percent <= -5:
                    level = ImpactLevel.NEGATIVE
                else:
                    level = ImpactLevel.NEUTRAL

                impacts.append(EventImpact(
                    event_name=self.HOLIDAYS[key],
                    event_date=d,
                    actual_revenue=revenue.quantize(Decimal("0.01")),
                    expected_revenue=avg_revenue.quantize(Decimal("0.01")),
                    impact_percent=impact_percent.quantize(Decimal("0.1")),
                    impact_level=level,
                ))

        # Sort by impact
        impacts.sort(key=lambda x: abs(x.impact_percent), reverse=True)

        return impacts

    async def analyze_pricing(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        min_quantity: int = 10,
    ) -> List[PricingImpact]:
        """
        Analyze impact of pricing changes on product sales.

        Compares first half vs second half of period to detect price changes.
        """
        from app.db.models import Product

        mid_date = date_from + (date_to - date_from) / 2

        # Get sales in first half
        first_half_query = (
            select(
                ReceiptItem.product_id,
                ReceiptItem.product_name,
                func.avg(ReceiptItem.unit_price).label("avg_price"),
                func.sum(ReceiptItem.quantity).label("total_qty"),
            )
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at < mid_date,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(ReceiptItem.product_id, ReceiptItem.product_name)
            .having(func.sum(ReceiptItem.quantity) >= min_quantity)
        )

        # Get sales in second half
        second_half_query = (
            select(
                ReceiptItem.product_id,
                ReceiptItem.product_name,
                func.avg(ReceiptItem.unit_price).label("avg_price"),
                func.sum(ReceiptItem.quantity).label("total_qty"),
            )
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= mid_date,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(ReceiptItem.product_id, ReceiptItem.product_name)
            .having(func.sum(ReceiptItem.quantity) >= min_quantity)
        )

        first_result = await self.db.execute(first_half_query)
        first_data = {row.product_id: row for row in first_result.all()}

        second_result = await self.db.execute(second_half_query)
        second_data = {row.product_id: row for row in second_result.all()}

        impacts = []
        for product_id, second in second_data.items():
            if product_id not in first_data:
                continue

            first = first_data[product_id]

            old_price = Decimal(str(first.avg_price))
            new_price = Decimal(str(second.avg_price))

            # Only include if price changed by at least 3%
            if old_price == 0:
                continue

            price_change = ((new_price - old_price) / old_price * 100)
            if abs(price_change) < 3:
                continue

            qty_before = int(first.total_qty)
            qty_after = int(second.total_qty)

            qty_change = ((qty_after - qty_before) / qty_before * 100) if qty_before > 0 else Decimal("0")

            # Calculate price elasticity
            elasticity = (qty_change / price_change) if price_change != 0 else Decimal("0")

            # Revenue impact
            revenue_before = old_price * qty_before
            revenue_after = new_price * qty_after
            revenue_impact = revenue_after - revenue_before

            impacts.append(PricingImpact(
                product_name=second.product_name,
                old_price=old_price.quantize(Decimal("0.01")),
                new_price=new_price.quantize(Decimal("0.01")),
                price_change_percent=price_change.quantize(Decimal("0.1")),
                quantity_before=qty_before,
                quantity_after=qty_after,
                quantity_change_percent=qty_change.quantize(Decimal("0.1")),
                revenue_impact=revenue_impact.quantize(Decimal("0.01")),
                elasticity=elasticity.quantize(Decimal("0.01")),
            ))

        # Sort by absolute revenue impact
        impacts.sort(key=lambda x: abs(x.revenue_impact), reverse=True)

        return impacts[:20]  # Top 20

    def _calculate_factor_impact(
        self,
        weekday_analysis: List[WeekdayAnalysis],
        seasonality_analysis: List[SeasonalityAnalysis],
        event_impacts: List[EventImpact],
        pricing_impacts: List[PricingImpact],
    ) -> List[FactorImpact]:
        """Calculate overall impact summary for each factor."""

        factors = []

        # Weekday factor
        if weekday_analysis:
            max_idx = max(a.index for a in weekday_analysis)
            min_idx = min(a.index for a in weekday_analysis)
            variance = max_idx - min_idx

            if variance > 30:
                level = ImpactLevel.VERY_POSITIVE if max_idx > 120 else ImpactLevel.POSITIVE
                impact = variance / 2
            elif variance > 15:
                level = ImpactLevel.POSITIVE
                impact = variance / 2
            else:
                level = ImpactLevel.NEUTRAL
                impact = variance / 2

            best_day = max(weekday_analysis, key=lambda x: x.index)
            worst_day = min(weekday_analysis, key=lambda x: x.index)

            factors.append(FactorImpact(
                factor=MotiveFactor.WEEKDAY,
                impact_level=level,
                impact_percent=Decimal(str(impact)).quantize(Decimal("0.1")),
                description=f"Лучший день: {best_day.day_name} (индекс {best_day.index}), худший: {worst_day.day_name} (индекс {worst_day.index})",
                recommendation=f"Усилить маркетинг в {worst_day.day_name}, предложить акции",
            ))

        # Seasonality factor
        if seasonality_analysis:
            up_months = [a for a in seasonality_analysis if a.trend == "up"]
            down_months = [a for a in seasonality_analysis if a.trend == "down"]

            if len(up_months) > len(down_months):
                level = ImpactLevel.POSITIVE
                impact = Decimal("10")
            elif len(down_months) > len(up_months):
                level = ImpactLevel.NEGATIVE
                impact = Decimal("-10")
            else:
                level = ImpactLevel.NEUTRAL
                impact = Decimal("0")

            best_month = max(seasonality_analysis, key=lambda x: x.index)

            factors.append(FactorImpact(
                factor=MotiveFactor.SEASONALITY,
                impact_level=level,
                impact_percent=impact,
                description=f"Пиковый месяц: {best_month.month_name} (индекс {best_month.index})",
                recommendation="Планировать запасы и персонал с учётом сезонности",
            ))

        # Events factor
        if event_impacts:
            positive_events = [e for e in event_impacts if e.impact_percent > 5]
            negative_events = [e for e in event_impacts if e.impact_percent < -5]

            avg_positive = sum(e.impact_percent for e in positive_events) / len(positive_events) if positive_events else Decimal("0")

            if avg_positive > 20:
                level = ImpactLevel.VERY_POSITIVE
            elif avg_positive > 10:
                level = ImpactLevel.POSITIVE
            else:
                level = ImpactLevel.NEUTRAL

            factors.append(FactorImpact(
                factor=MotiveFactor.EVENTS,
                impact_level=level,
                impact_percent=avg_positive.quantize(Decimal("0.1")),
                description=f"Позитивных событий: {len(positive_events)}, негативных: {len(negative_events)}",
                recommendation="Создать специальные меню/акции для праздников",
            ))

        # Pricing factor
        if pricing_impacts:
            positive_impacts = [p for p in pricing_impacts if p.revenue_impact > 0]
            negative_impacts = [p for p in pricing_impacts if p.revenue_impact < 0]

            total_impact = sum(p.revenue_impact for p in pricing_impacts)

            if total_impact > 0:
                level = ImpactLevel.POSITIVE if total_impact > 1000 else ImpactLevel.NEUTRAL
            else:
                level = ImpactLevel.NEGATIVE if total_impact < -1000 else ImpactLevel.NEUTRAL

            avg_elasticity = sum(abs(p.elasticity) for p in pricing_impacts) / len(pricing_impacts)

            factors.append(FactorImpact(
                factor=MotiveFactor.PRICING,
                impact_level=level,
                impact_percent=Decimal(str(total_impact / 100)).quantize(Decimal("0.1")) if pricing_impacts else Decimal("0"),
                description=f"Средняя эластичность спроса: {avg_elasticity:.2f}",
                recommendation="Осторожно повышать цены на эластичные товары" if avg_elasticity > 1 else "Возможно повышение цен на неэластичные товары",
            ))

        return factors

    def _generate_recommendations(
        self,
        weekday_analysis: List[WeekdayAnalysis],
        seasonality_analysis: List[SeasonalityAnalysis],
        event_impacts: List[EventImpact],
        pricing_impacts: List[PricingImpact],
    ) -> List[str]:
        """Generate actionable recommendations based on analysis."""

        recommendations = []

        # Weekday recommendations
        if weekday_analysis:
            worst_day = min(weekday_analysis, key=lambda x: x.index)
            if worst_day.index < 80:
                recommendations.append(
                    f"🎯 Запустить акцию «Счастливый {worst_day.day_name}» — скидка 15% для увеличения трафика"
                )

            best_day = max(weekday_analysis, key=lambda x: x.index)
            recommendations.append(
                f"📈 В {best_day.day_name} (пиковый день) увеличить персонал и запасы"
            )

        # Seasonality recommendations
        if seasonality_analysis:
            upcoming_months = seasonality_analysis[-3:] if len(seasonality_analysis) >= 3 else seasonality_analysis
            down_trend = [m for m in upcoming_months if m.trend == "down"]
            if down_trend:
                recommendations.append(
                    f"⚠️ Ожидается спад в {', '.join(m.month_name for m in down_trend)} — подготовить маркетинговые акции"
                )

        # Event recommendations
        if event_impacts:
            top_events = [e for e in event_impacts if e.impact_percent > 15][:3]
            if top_events:
                recommendations.append(
                    f"🎉 Лучшие праздники: {', '.join(e.event_name for e in top_events)} — создать специальные предложения"
                )

        # Pricing recommendations
        if pricing_impacts:
            elastic_products = [p for p in pricing_impacts if abs(p.elasticity) > 1.5]
            if elastic_products:
                recommendations.append(
                    f"💰 Эластичные товары ({len(elastic_products)} шт.) — осторожно менять цены"
                )

            inelastic_profitable = [p for p in pricing_impacts if abs(p.elasticity) < 0.5 and p.revenue_impact > 0]
            if inelastic_profitable:
                recommendations.append(
                    f"📊 Можно повысить цены на {len(inelastic_profitable)} товаров с низкой эластичностью"
                )

        return recommendations[:5]  # Top 5 recommendations

    async def get_full_report(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> MotiveReport:
        """Generate complete Motive Marketing analysis report."""

        # Run all analyses
        weekday_analysis = await self.analyze_weekdays(venue_ids, date_from, date_to)
        seasonality_analysis = await self.analyze_seasonality(venue_ids, months=12)
        event_impacts = await self.analyze_events(venue_ids, date_from, date_to)
        pricing_impacts = await self.analyze_pricing(venue_ids, date_from, date_to)

        # Calculate factor summary
        factor_summary = self._calculate_factor_impact(
            weekday_analysis, seasonality_analysis, event_impacts, pricing_impacts
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            weekday_analysis, seasonality_analysis, event_impacts, pricing_impacts
        )

        # Get totals
        query = (
            select(
                func.sum(DailySales.total_revenue).label("total"),
                func.count(DailySales.id).label("days"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                    DailySales.date <= date_to,
                )
            )
        )
        result = await self.db.execute(query)
        row = result.first()

        total_revenue = Decimal(str(row.total)) if row and row.total else Decimal("0")
        days = row.days if row else 1
        avg_daily = total_revenue / days if days > 0 else Decimal("0")

        return MotiveReport(
            period_start=date_from,
            period_end=date_to,
            venue_ids=venue_ids,
            total_revenue=total_revenue.quantize(Decimal("0.01")),
            avg_daily_revenue=avg_daily.quantize(Decimal("0.01")),
            weekday_analysis=weekday_analysis,
            seasonality_analysis=seasonality_analysis,
            event_impacts=event_impacts,
            pricing_impacts=pricing_impacts,
            factor_summary=factor_summary,
            top_recommendations=recommendations,
        )
