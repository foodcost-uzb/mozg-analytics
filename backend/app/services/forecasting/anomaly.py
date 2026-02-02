"""Anomaly Detection service for MOZG Analytics."""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DailySales, HourlySales, Receipt, ReceiptItem, Product

logger = logging.getLogger(__name__)


class AnomalyType(str, Enum):
    """Types of anomalies."""

    REVENUE_SPIKE = "revenue_spike"
    REVENUE_DROP = "revenue_drop"
    TRAFFIC_SPIKE = "traffic_spike"
    TRAFFIC_DROP = "traffic_drop"
    AVG_CHECK_SPIKE = "avg_check_spike"
    AVG_CHECK_DROP = "avg_check_drop"
    PRODUCT_SPIKE = "product_spike"
    PRODUCT_DROP = "product_drop"
    HOURLY_ANOMALY = "hourly_anomaly"


class AnomalySeverity(str, Enum):
    """Severity level of anomaly."""

    LOW = "low"         # 2-3 standard deviations
    MEDIUM = "medium"   # 3-4 standard deviations
    HIGH = "high"       # 4+ standard deviations
    CRITICAL = "critical"  # 5+ standard deviations


@dataclass
class Anomaly:
    """Detected anomaly."""

    anomaly_type: AnomalyType
    severity: AnomalySeverity
    date: date
    hour: Optional[int]  # For hourly anomalies

    # Values
    actual_value: Decimal
    expected_value: Decimal
    deviation_percent: Decimal
    z_score: Decimal

    # Context
    metric_name: str
    description: str
    possible_causes: List[str]
    recommended_actions: List[str]

    # Related
    venue_id: Optional[uuid.UUID] = None
    product_id: Optional[uuid.UUID] = None
    product_name: Optional[str] = None


@dataclass
class AnomalyStats:
    """Statistics for anomaly detection."""

    total_anomalies: int
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    most_common_day: Optional[str]
    most_affected_metric: str


@dataclass
class AnomalyReport:
    """Complete anomaly detection report."""

    venue_ids: List[uuid.UUID]
    period_start: date
    period_end: date

    # Detected anomalies
    anomalies: List[Anomaly]

    # Statistics
    stats: AnomalyStats

    # Summary
    critical_count: int
    high_count: int
    requires_attention: bool

    # Insights
    insights: List[str] = field(default_factory=list)


class AnomalyDetectionService:
    """
    Anomaly detection service using statistical methods.

    Methods:
    - Z-score based detection
    - IQR (Interquartile Range) method
    - Moving average deviation
    - Seasonal decomposition

    Detects anomalies in:
    - Daily revenue
    - Traffic (receipts count)
    - Average check
    - Product sales
    - Hourly patterns
    """

    # Thresholds for z-score
    Z_THRESHOLDS = {
        AnomalySeverity.LOW: 2.0,
        AnomalySeverity.MEDIUM: 3.0,
        AnomalySeverity.HIGH: 4.0,
        AnomalySeverity.CRITICAL: 5.0,
    }

    WEEKDAY_NAMES = {
        0: "Понедельник", 1: "Вторник", 2: "Среда",
        3: "Четверг", 4: "Пятница", 5: "Суббота", 6: "Воскресенье",
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    def _calculate_z_score(
        self,
        value: float,
        mean: float,
        std: float,
    ) -> float:
        """Calculate z-score."""
        if std == 0:
            return 0
        return (value - mean) / std

    def _get_severity(self, z_score: float) -> Optional[AnomalySeverity]:
        """Determine severity based on z-score."""
        abs_z = abs(z_score)

        if abs_z >= self.Z_THRESHOLDS[AnomalySeverity.CRITICAL]:
            return AnomalySeverity.CRITICAL
        elif abs_z >= self.Z_THRESHOLDS[AnomalySeverity.HIGH]:
            return AnomalySeverity.HIGH
        elif abs_z >= self.Z_THRESHOLDS[AnomalySeverity.MEDIUM]:
            return AnomalySeverity.MEDIUM
        elif abs_z >= self.Z_THRESHOLDS[AnomalySeverity.LOW]:
            return AnomalySeverity.LOW
        return None

    def _get_possible_causes(
        self,
        anomaly_type: AnomalyType,
        z_score: float,
        day_of_week: int,
    ) -> List[str]:
        """Generate possible causes for an anomaly."""

        causes = []

        is_positive = z_score > 0
        is_weekend = day_of_week >= 5

        if anomaly_type == AnomalyType.REVENUE_SPIKE:
            causes = [
                "Праздничный день или событие",
                "Успешная маркетинговая акция",
                "Большой корпоративный заказ",
                "Погодные условия (хорошая погода)",
            ]
        elif anomaly_type == AnomalyType.REVENUE_DROP:
            causes = [
                "Технические проблемы (POS, интернет)",
                "Погодные условия (плохая погода)",
                "Ремонтные работы рядом",
                "Конкурентная активность",
                "Отсутствие ключевых позиций меню",
            ]
        elif anomaly_type == AnomalyType.TRAFFIC_SPIKE:
            causes = [
                "Мероприятие в районе",
                "Вирусный пост в соцсетях",
                "Праздничный день",
                "Акция «приведи друга»",
            ]
        elif anomaly_type == AnomalyType.TRAFFIC_DROP:
            causes = [
                "Плохая погода",
                "Проблемы с доступностью",
                "Конкурент открыл акцию",
                "Технические проблемы",
            ]
        elif anomaly_type == AnomalyType.AVG_CHECK_SPIKE:
            causes = [
                "Корпоративный заказ",
                "Успешный апселл",
                "Премиум-клиенты",
                "Новое дорогое меню",
            ]
        elif anomaly_type == AnomalyType.AVG_CHECK_DROP:
            causes = [
                "Много мелких заказов (кофе с собой)",
                "Активная скидочная акция",
                "Изменение целевой аудитории",
            ]
        elif anomaly_type == AnomalyType.PRODUCT_SPIKE:
            causes = [
                "Вирусная популярность",
                "Акция на товар",
                "Сезонный спрос",
                "Рекомендации официантов",
            ]
        elif anomaly_type == AnomalyType.PRODUCT_DROP:
            causes = [
                "Отсутствие ингредиентов",
                "Изменение рецептуры",
                "Конец сезона",
                "Негативный отзыв",
            ]

        return causes[:4]

    def _get_recommended_actions(
        self,
        anomaly_type: AnomalyType,
        severity: AnomalySeverity,
        z_score: float,
    ) -> List[str]:
        """Generate recommended actions."""

        actions = []

        is_positive = z_score > 0
        is_critical = severity in [AnomalySeverity.HIGH, AnomalySeverity.CRITICAL]

        if anomaly_type in [AnomalyType.REVENUE_DROP, AnomalyType.TRAFFIC_DROP]:
            actions = [
                "Проверить технические системы",
                "Проанализировать отзывы за этот день",
                "Сравнить с конкурентами",
            ]
            if is_critical:
                actions.insert(0, "⚠️ Срочно выяснить причину!")

        elif anomaly_type in [AnomalyType.REVENUE_SPIKE, AnomalyType.TRAFFIC_SPIKE]:
            actions = [
                "Определить причину успеха",
                "Рассмотреть повторение стратегии",
                "Подготовить запасы на будущее",
            ]

        elif anomaly_type == AnomalyType.AVG_CHECK_DROP:
            actions = [
                "Обучить персонал техникам апселла",
                "Проверить эффективность акций",
                "Пересмотреть скидочную политику",
            ]

        elif anomaly_type == AnomalyType.PRODUCT_DROP:
            actions = [
                "Проверить наличие ингредиентов",
                "Проверить качество блюда",
                "Рассмотреть продвижение товара",
            ]

        elif anomaly_type == AnomalyType.PRODUCT_SPIKE:
            actions = [
                "Увеличить запасы ингредиентов",
                "Рассмотреть повышение цены",
                "Добавить в рекомендации",
            ]

        return actions[:3]

    async def get_daily_metrics(
        self,
        venue_ids: List[uuid.UUID],
        days: int = 90,
    ) -> pd.DataFrame:
        """Get daily metrics for anomaly detection."""

        date_from = date.today() - timedelta(days=days)

        query = (
            select(
                DailySales.date,
                func.sum(DailySales.total_revenue).label("revenue"),
                func.sum(DailySales.total_receipts).label("receipts"),
                func.avg(DailySales.avg_receipt).label("avg_check"),
            )
            .where(
                and_(
                    DailySales.venue_id.in_(venue_ids),
                    DailySales.date >= date_from,
                )
            )
            .group_by(DailySales.date)
            .order_by(DailySales.date)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return pd.DataFrame([
            {
                'date': row.date,
                'revenue': float(row.revenue or 0),
                'receipts': int(row.receipts or 0),
                'avg_check': float(row.avg_check or 0),
            }
            for row in rows
        ])

    def _detect_metric_anomalies(
        self,
        data: pd.DataFrame,
        metric: str,
        anomaly_type_positive: AnomalyType,
        anomaly_type_negative: AnomalyType,
        metric_name: str,
    ) -> List[Anomaly]:
        """Detect anomalies in a specific metric using z-score."""

        anomalies = []

        if len(data) < 14:
            return anomalies

        values = data[metric].values
        dates = data['date'].values

        # Calculate rolling statistics (14-day window)
        window = 14
        for i in range(window, len(values)):
            window_values = values[i-window:i]
            mean = np.mean(window_values)
            std = np.std(window_values)

            if std == 0:
                continue

            z_score = self._calculate_z_score(values[i], mean, std)
            severity = self._get_severity(z_score)

            if severity is None:
                continue

            current_date = pd.Timestamp(dates[i]).date()
            day_of_week = current_date.weekday()

            anomaly_type = anomaly_type_positive if z_score > 0 else anomaly_type_negative
            deviation_percent = ((values[i] - mean) / mean * 100) if mean != 0 else 0

            anomaly = Anomaly(
                anomaly_type=anomaly_type,
                severity=severity,
                date=current_date,
                hour=None,
                actual_value=Decimal(str(values[i])).quantize(Decimal("0.01")),
                expected_value=Decimal(str(mean)).quantize(Decimal("0.01")),
                deviation_percent=Decimal(str(deviation_percent)).quantize(Decimal("0.1")),
                z_score=Decimal(str(z_score)).quantize(Decimal("0.01")),
                metric_name=metric_name,
                description=f"{metric_name}: {'выше' if z_score > 0 else 'ниже'} нормы на {abs(deviation_percent):.1f}%",
                possible_causes=self._get_possible_causes(anomaly_type, z_score, day_of_week),
                recommended_actions=self._get_recommended_actions(anomaly_type, severity, z_score),
            )

            anomalies.append(anomaly)

        return anomalies

    async def detect_daily_anomalies(
        self,
        venue_ids: List[uuid.UUID],
        days: int = 90,
    ) -> List[Anomaly]:
        """Detect anomalies in daily metrics."""

        data = await self.get_daily_metrics(venue_ids, days)

        if len(data) < 14:
            return []

        anomalies = []

        # Revenue anomalies
        anomalies.extend(self._detect_metric_anomalies(
            data, 'revenue',
            AnomalyType.REVENUE_SPIKE, AnomalyType.REVENUE_DROP,
            "Выручка",
        ))

        # Traffic anomalies
        anomalies.extend(self._detect_metric_anomalies(
            data, 'receipts',
            AnomalyType.TRAFFIC_SPIKE, AnomalyType.TRAFFIC_DROP,
            "Количество чеков",
        ))

        # Average check anomalies
        anomalies.extend(self._detect_metric_anomalies(
            data, 'avg_check',
            AnomalyType.AVG_CHECK_SPIKE, AnomalyType.AVG_CHECK_DROP,
            "Средний чек",
        ))

        return anomalies

    async def detect_product_anomalies(
        self,
        venue_ids: List[uuid.UUID],
        days: int = 30,
        top_n: int = 20,
    ) -> List[Anomaly]:
        """Detect anomalies in product sales."""

        date_from = date.today() - timedelta(days=days)

        # Get top products
        top_products_query = (
            select(
                ReceiptItem.product_id,
                ReceiptItem.product_name,
                func.sum(ReceiptItem.quantity).label("total_qty"),
            )
            .select_from(ReceiptItem)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.is_deleted == False,
                    ReceiptItem.product_id.isnot(None),
                )
            )
            .group_by(ReceiptItem.product_id, ReceiptItem.product_name)
            .order_by(func.sum(ReceiptItem.quantity).desc())
            .limit(top_n)
        )

        result = await self.db.execute(top_products_query)
        top_products = result.all()

        anomalies = []

        for product in top_products:
            # Get daily sales for this product
            product_query = (
                select(
                    func.date(Receipt.opened_at).label("date"),
                    func.sum(ReceiptItem.quantity).label("quantity"),
                )
                .select_from(ReceiptItem)
                .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
                .where(
                    and_(
                        Receipt.venue_id.in_(venue_ids),
                        ReceiptItem.product_id == product.product_id,
                        Receipt.opened_at >= date_from,
                        Receipt.is_deleted == False,
                    )
                )
                .group_by(func.date(Receipt.opened_at))
                .order_by(func.date(Receipt.opened_at))
            )

            result = await self.db.execute(product_query)
            rows = result.all()

            if len(rows) < 7:
                continue

            data = pd.DataFrame([
                {'date': row.date, 'quantity': float(row.quantity)}
                for row in rows
            ])

            # Detect anomalies
            product_anomalies = self._detect_metric_anomalies(
                data, 'quantity',
                AnomalyType.PRODUCT_SPIKE, AnomalyType.PRODUCT_DROP,
                f"Продажи «{product.product_name[:30]}»",
            )

            # Add product info
            for anomaly in product_anomalies:
                anomaly.product_id = product.product_id
                anomaly.product_name = product.product_name

            anomalies.extend(product_anomalies)

        return anomalies

    async def detect_hourly_anomalies(
        self,
        venue_ids: List[uuid.UUID],
        days: int = 14,
    ) -> List[Anomaly]:
        """Detect anomalies in hourly patterns."""

        date_from = date.today() - timedelta(days=days)

        query = (
            select(
                HourlySales.date,
                HourlySales.hour,
                func.sum(HourlySales.total_revenue).label("revenue"),
            )
            .where(
                and_(
                    HourlySales.venue_id.in_(venue_ids),
                    HourlySales.date >= date_from,
                )
            )
            .group_by(HourlySales.date, HourlySales.hour)
            .order_by(HourlySales.date, HourlySales.hour)
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Group by hour to find typical patterns
        hourly_data: Dict[int, List[float]] = {h: [] for h in range(24)}
        for row in rows:
            hourly_data[row.hour].append(float(row.revenue or 0))

        anomalies = []

        # Check each hour's data
        for row in rows:
            hour = row.hour
            revenue = float(row.revenue or 0)
            typical_values = hourly_data[hour]

            if len(typical_values) < 5:
                continue

            mean = np.mean(typical_values)
            std = np.std(typical_values)

            if std == 0:
                continue

            z_score = self._calculate_z_score(revenue, mean, std)
            severity = self._get_severity(z_score)

            if severity is None:
                continue

            if abs(z_score) < 3:  # Only report significant hourly anomalies
                continue

            deviation_percent = ((revenue - mean) / mean * 100) if mean != 0 else 0

            anomaly = Anomaly(
                anomaly_type=AnomalyType.HOURLY_ANOMALY,
                severity=severity,
                date=row.date,
                hour=hour,
                actual_value=Decimal(str(revenue)).quantize(Decimal("0.01")),
                expected_value=Decimal(str(mean)).quantize(Decimal("0.01")),
                deviation_percent=Decimal(str(deviation_percent)).quantize(Decimal("0.1")),
                z_score=Decimal(str(z_score)).quantize(Decimal("0.01")),
                metric_name=f"Выручка в {hour}:00",
                description=f"Аномалия в {hour}:00: {'выше' if z_score > 0 else 'ниже'} нормы на {abs(deviation_percent):.1f}%",
                possible_causes=self._get_possible_causes(
                    AnomalyType.REVENUE_SPIKE if z_score > 0 else AnomalyType.REVENUE_DROP,
                    z_score,
                    row.date.weekday(),
                ),
                recommended_actions=[
                    "Проверить события в это время",
                    "Сравнить с другими днями",
                ],
            )

            anomalies.append(anomaly)

        return anomalies

    def _calculate_stats(
        self,
        anomalies: List[Anomaly],
    ) -> AnomalyStats:
        """Calculate anomaly statistics."""

        by_type: Dict[str, int] = {}
        by_severity: Dict[str, int] = {}
        by_day: Dict[int, int] = {}

        for a in anomalies:
            # By type
            type_key = a.anomaly_type.value
            by_type[type_key] = by_type.get(type_key, 0) + 1

            # By severity
            sev_key = a.severity.value
            by_severity[sev_key] = by_severity.get(sev_key, 0) + 1

            # By day
            dow = a.date.weekday()
            by_day[dow] = by_day.get(dow, 0) + 1

        most_common_day = None
        if by_day:
            max_day = max(by_day.items(), key=lambda x: x[1])
            most_common_day = self.WEEKDAY_NAMES[max_day[0]]

        most_affected_metric = "Выручка"
        if by_type:
            max_type = max(by_type.items(), key=lambda x: x[1])
            if "traffic" in max_type[0]:
                most_affected_metric = "Трафик"
            elif "avg_check" in max_type[0]:
                most_affected_metric = "Средний чек"
            elif "product" in max_type[0]:
                most_affected_metric = "Продукты"

        return AnomalyStats(
            total_anomalies=len(anomalies),
            by_type=by_type,
            by_severity=by_severity,
            most_common_day=most_common_day,
            most_affected_metric=most_affected_metric,
        )

    def _generate_insights(
        self,
        anomalies: List[Anomaly],
        stats: AnomalyStats,
    ) -> List[str]:
        """Generate insights from anomaly analysis."""

        insights = []

        critical = [a for a in anomalies if a.severity == AnomalySeverity.CRITICAL]
        if critical:
            insights.append(
                f"🚨 Обнаружено {len(critical)} критических аномалий — требуется срочное внимание!"
            )

        # Recent anomalies
        recent = [a for a in anomalies if (date.today() - a.date).days <= 7]
        if recent:
            insights.append(
                f"📊 За последнюю неделю: {len(recent)} аномалий"
            )

        # Revenue drops
        drops = [a for a in anomalies if a.anomaly_type == AnomalyType.REVENUE_DROP]
        if len(drops) > 3:
            insights.append(
                f"⚠️ Частые падения выручки ({len(drops)} раз) — проверить системные проблемы"
            )

        # Product anomalies
        product_anomalies = [a for a in anomalies if a.product_name]
        if product_anomalies:
            products = set(a.product_name for a in product_anomalies)
            insights.append(
                f"📦 Аномалии в продажах {len(products)} товаров"
            )

        # Day pattern
        if stats.most_common_day:
            insights.append(
                f"📅 Больше всего аномалий в {stats.most_common_day}"
            )

        return insights[:5]

    async def generate_report(
        self,
        venue_ids: List[uuid.UUID],
        days: int = 30,
        include_products: bool = True,
        include_hourly: bool = True,
    ) -> AnomalyReport:
        """
        Generate complete anomaly detection report.

        Args:
            venue_ids: Venues to analyze
            days: Days of history to analyze
            include_products: Include product-level anomalies
            include_hourly: Include hourly pattern anomalies
        """

        all_anomalies = []

        # Daily anomalies
        daily_anomalies = await self.detect_daily_anomalies(venue_ids, days)
        all_anomalies.extend(daily_anomalies)

        # Product anomalies
        if include_products:
            product_anomalies = await self.detect_product_anomalies(venue_ids, days)
            all_anomalies.extend(product_anomalies)

        # Hourly anomalies
        if include_hourly:
            hourly_anomalies = await self.detect_hourly_anomalies(venue_ids, min(days, 14))
            all_anomalies.extend(hourly_anomalies)

        # Sort by severity and date
        severity_order = {
            AnomalySeverity.CRITICAL: 0,
            AnomalySeverity.HIGH: 1,
            AnomalySeverity.MEDIUM: 2,
            AnomalySeverity.LOW: 3,
        }
        all_anomalies.sort(key=lambda x: (severity_order[x.severity], -x.date.toordinal()))

        # Calculate stats
        stats = self._calculate_stats(all_anomalies)

        # Count by severity
        critical_count = len([a for a in all_anomalies if a.severity == AnomalySeverity.CRITICAL])
        high_count = len([a for a in all_anomalies if a.severity == AnomalySeverity.HIGH])

        # Generate insights
        insights = self._generate_insights(all_anomalies, stats)

        return AnomalyReport(
            venue_ids=venue_ids,
            period_start=date.today() - timedelta(days=days),
            period_end=date.today(),
            anomalies=all_anomalies,
            stats=stats,
            critical_count=critical_count,
            high_count=high_count,
            requires_attention=critical_count > 0 or high_count > 2,
            insights=insights,
        )
