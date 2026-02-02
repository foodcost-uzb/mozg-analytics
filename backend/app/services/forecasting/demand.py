"""Product Demand Forecasting service for MOZG Analytics."""

import uuid
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from prophet import Prophet
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Product, Receipt, ReceiptItem, Category

logger = logging.getLogger(__name__)


@dataclass
class ProductForecastPoint:
    """Single product demand forecast point."""

    date: date
    quantity: Decimal
    lower_bound: Decimal
    upper_bound: Decimal


@dataclass
class ProductDemandForecast:
    """Demand forecast for a single product."""

    product_id: uuid.UUID
    product_name: str
    category_name: Optional[str]

    # Forecast
    forecast: List[ProductForecastPoint]
    total_forecast: Decimal
    avg_daily_forecast: Decimal

    # Historical
    historical_avg: Decimal
    historical_total: Decimal

    # Trend
    trend: str  # "up", "down", "stable"
    trend_percent: Decimal

    # Confidence
    confidence_score: Decimal  # 0-100


@dataclass
class CategoryDemandForecast:
    """Demand forecast aggregated by category."""

    category_id: Optional[uuid.UUID]
    category_name: str
    products: List[ProductDemandForecast]
    total_forecast: Decimal
    growth_percent: Decimal


@dataclass
class DemandForecastReport:
    """Complete demand forecast report."""

    venue_ids: List[uuid.UUID]
    forecast_start: date
    forecast_end: date
    horizon_days: int

    # Product forecasts
    product_forecasts: List[ProductDemandForecast]

    # Category summaries
    category_forecasts: List[CategoryDemandForecast]

    # Top movers
    top_growing: List[ProductDemandForecast]
    top_declining: List[ProductDemandForecast]

    # Recommendations
    insights: List[str] = field(default_factory=list)


class DemandForecastService:
    """
    Product demand forecasting service.

    Features:
    - Individual product demand forecasting
    - Category-level aggregation
    - Trend analysis
    - Stock recommendations
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_product_sales_history(
        self,
        venue_ids: List[uuid.UUID],
        product_id: uuid.UUID,
        days: int = 90,
    ) -> pd.DataFrame:
        """Get daily sales history for a product."""

        date_from = date.today() - timedelta(days=days)

        query = (
            select(
                func.date(Receipt.opened_at).label("date"),
                func.sum(ReceiptItem.quantity).label("quantity"),
            )
            .select_from(ReceiptItem)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    ReceiptItem.product_id == product_id,
                    Receipt.opened_at >= date_from,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(func.date(Receipt.opened_at))
            .order_by(func.date(Receipt.opened_at))
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return pd.DataFrame(columns=['ds', 'y'])

        # Create full date range and fill missing days with 0
        data = pd.DataFrame([
            {'ds': row.date, 'y': float(row.quantity)}
            for row in rows
        ])

        # Fill missing dates
        full_range = pd.date_range(start=date_from, end=date.today(), freq='D')
        full_df = pd.DataFrame({'ds': full_range})
        data['ds'] = pd.to_datetime(data['ds'])
        data = full_df.merge(data, on='ds', how='left').fillna(0)

        return data

    async def get_top_products(
        self,
        venue_ids: List[uuid.UUID],
        limit: int = 50,
        days: int = 30,
    ) -> List[Tuple[uuid.UUID, str, str, Decimal]]:
        """Get top selling products by quantity."""

        date_from = date.today() - timedelta(days=days)

        query = (
            select(
                ReceiptItem.product_id,
                ReceiptItem.product_name,
                Category.name.label("category_name"),
                func.sum(ReceiptItem.quantity).label("total_qty"),
            )
            .select_from(ReceiptItem)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .outerjoin(Product, ReceiptItem.product_id == Product.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.is_deleted == False,
                    ReceiptItem.product_id.isnot(None),
                )
            )
            .group_by(
                ReceiptItem.product_id,
                ReceiptItem.product_name,
                Category.name,
            )
            .order_by(func.sum(ReceiptItem.quantity).desc())
            .limit(limit)
        )

        result = await self.db.execute(query)
        rows = result.all()

        return [
            (row.product_id, row.product_name, row.category_name or "Без категории", Decimal(str(row.total_qty)))
            for row in rows
        ]

    def _forecast_product(
        self,
        data: pd.DataFrame,
        horizon_days: int,
    ) -> Tuple[List[ProductForecastPoint], Decimal]:
        """Forecast demand for a single product."""

        if len(data) < 14:
            # Not enough data - use simple average
            avg = Decimal(str(data['y'].mean())) if len(data) > 0 else Decimal("0")
            return [
                ProductForecastPoint(
                    date=date.today() + timedelta(days=i),
                    quantity=avg,
                    lower_bound=max(Decimal("0"), avg * Decimal("0.5")),
                    upper_bound=avg * Decimal("1.5"),
                )
                for i in range(1, horizon_days + 1)
            ], Decimal("50")  # Low confidence

        # Use Prophet for forecasting
        model = Prophet(
            yearly_seasonality=False,
            weekly_seasonality=True,
            daily_seasonality=False,
            changepoint_prior_scale=0.1,
            seasonality_prior_scale=5.0,
        )

        import logging
        logging.getLogger('prophet').setLevel(logging.WARNING)
        logging.getLogger('cmdstanpy').setLevel(logging.WARNING)

        try:
            model.fit(data)
            future = model.make_future_dataframe(periods=horizon_days)
            forecast = model.predict(future)

            # Get forecast for future dates only
            future_forecast = forecast[forecast['ds'] > data['ds'].max()]

            points = [
                ProductForecastPoint(
                    date=row['ds'].date(),
                    quantity=Decimal(str(max(0, row['yhat']))).quantize(Decimal("0.01")),
                    lower_bound=Decimal(str(max(0, row['yhat_lower']))).quantize(Decimal("0.01")),
                    upper_bound=Decimal(str(max(0, row['yhat_upper']))).quantize(Decimal("0.01")),
                )
                for _, row in future_forecast.iterrows()
            ]

            # Calculate confidence based on data quality
            data_points = len(data)
            variance = data['y'].std() / data['y'].mean() if data['y'].mean() > 0 else 1
            confidence = min(100, max(30, 100 - variance * 50 + min(50, data_points)))

            return points, Decimal(str(confidence)).quantize(Decimal("0.1"))

        except Exception as e:
            logger.warning(f"Prophet forecast failed: {e}, falling back to average")
            avg = Decimal(str(data['y'].mean()))
            return [
                ProductForecastPoint(
                    date=date.today() + timedelta(days=i),
                    quantity=avg,
                    lower_bound=max(Decimal("0"), avg * Decimal("0.7")),
                    upper_bound=avg * Decimal("1.3"),
                )
                for i in range(1, horizon_days + 1)
            ], Decimal("40")

    def _calculate_trend(
        self,
        data: pd.DataFrame,
    ) -> Tuple[str, Decimal]:
        """Calculate trend from historical data."""

        if len(data) < 14:
            return "stable", Decimal("0")

        # Compare first half vs second half
        mid = len(data) // 2
        first_half_avg = data.iloc[:mid]['y'].mean()
        second_half_avg = data.iloc[mid:]['y'].mean()

        if first_half_avg == 0:
            return "stable", Decimal("0")

        change_percent = ((second_half_avg - first_half_avg) / first_half_avg * 100)

        if change_percent > 10:
            trend = "up"
        elif change_percent < -10:
            trend = "down"
        else:
            trend = "stable"

        return trend, Decimal(str(change_percent)).quantize(Decimal("0.1"))

    async def forecast_product_demand(
        self,
        venue_ids: List[uuid.UUID],
        product_id: uuid.UUID,
        horizon_days: int = 14,
    ) -> ProductDemandForecast:
        """Forecast demand for a single product."""

        # Get product info
        product_query = (
            select(Product.name, Category.name.label("category_name"))
            .outerjoin(Category, Product.category_id == Category.id)
            .where(Product.id == product_id)
        )
        result = await self.db.execute(product_query)
        product_info = result.first()

        product_name = product_info.name if product_info else "Unknown"
        category_name = product_info.category_name if product_info else None

        # Get historical data
        data = await self.get_product_sales_history(venue_ids, product_id, 90)

        # Calculate historical metrics
        historical_avg = Decimal(str(data['y'].mean())) if len(data) > 0 else Decimal("0")
        historical_total = Decimal(str(data['y'].sum())) if len(data) > 0 else Decimal("0")

        # Forecast
        forecast_points, confidence = self._forecast_product(data, horizon_days)

        # Calculate trend
        trend, trend_percent = self._calculate_trend(data)

        # Calculate totals
        total_forecast = sum(p.quantity for p in forecast_points)
        avg_daily = total_forecast / len(forecast_points) if forecast_points else Decimal("0")

        return ProductDemandForecast(
            product_id=product_id,
            product_name=product_name,
            category_name=category_name,
            forecast=forecast_points,
            total_forecast=total_forecast.quantize(Decimal("0.01")),
            avg_daily_forecast=avg_daily.quantize(Decimal("0.01")),
            historical_avg=historical_avg.quantize(Decimal("0.01")),
            historical_total=historical_total.quantize(Decimal("0.01")),
            trend=trend,
            trend_percent=trend_percent,
            confidence_score=confidence,
        )

    async def forecast_all_products(
        self,
        venue_ids: List[uuid.UUID],
        horizon_days: int = 14,
        top_n: int = 30,
    ) -> DemandForecastReport:
        """
        Generate demand forecast for top products.

        Args:
            venue_ids: Venues to analyze
            horizon_days: Days to forecast
            top_n: Number of top products to forecast
        """

        # Get top products
        top_products = await self.get_top_products(venue_ids, limit=top_n)

        if not top_products:
            return DemandForecastReport(
                venue_ids=venue_ids,
                forecast_start=date.today() + timedelta(days=1),
                forecast_end=date.today() + timedelta(days=horizon_days),
                horizon_days=horizon_days,
                product_forecasts=[],
                category_forecasts=[],
                top_growing=[],
                top_declining=[],
                insights=["Недостаточно данных для прогнозирования"],
            )

        # Forecast each product
        product_forecasts = []
        for product_id, product_name, category_name, _ in top_products:
            try:
                forecast = await self.forecast_product_demand(
                    venue_ids, product_id, horizon_days
                )
                product_forecasts.append(forecast)
            except Exception as e:
                logger.warning(f"Failed to forecast product {product_id}: {e}")
                continue

        # Aggregate by category
        category_map: Dict[str, List[ProductDemandForecast]] = {}
        for pf in product_forecasts:
            cat = pf.category_name or "Без категории"
            if cat not in category_map:
                category_map[cat] = []
            category_map[cat].append(pf)

        category_forecasts = []
        for cat_name, products in category_map.items():
            total = sum(p.total_forecast for p in products)
            hist_total = sum(p.historical_total for p in products)

            growth = (
                ((total - hist_total) / hist_total * 100)
                if hist_total > 0 else Decimal("0")
            )

            category_forecasts.append(CategoryDemandForecast(
                category_id=None,  # Would need to look up
                category_name=cat_name,
                products=products,
                total_forecast=total.quantize(Decimal("0.01")),
                growth_percent=growth.quantize(Decimal("0.1")),
            ))

        # Sort by forecast volume
        category_forecasts.sort(key=lambda x: x.total_forecast, reverse=True)

        # Find top growing and declining
        sorted_by_trend = sorted(
            product_forecasts,
            key=lambda x: x.trend_percent,
            reverse=True,
        )

        top_growing = [p for p in sorted_by_trend if p.trend == "up"][:5]
        top_declining = [p for p in sorted_by_trend if p.trend == "down"][-5:]
        top_declining.reverse()

        # Generate insights
        insights = self._generate_insights(
            product_forecasts, category_forecasts, top_growing, top_declining
        )

        return DemandForecastReport(
            venue_ids=venue_ids,
            forecast_start=date.today() + timedelta(days=1),
            forecast_end=date.today() + timedelta(days=horizon_days),
            horizon_days=horizon_days,
            product_forecasts=product_forecasts,
            category_forecasts=category_forecasts,
            top_growing=top_growing,
            top_declining=top_declining,
            insights=insights,
        )

    def _generate_insights(
        self,
        product_forecasts: List[ProductDemandForecast],
        category_forecasts: List[CategoryDemandForecast],
        top_growing: List[ProductDemandForecast],
        top_declining: List[ProductDemandForecast],
    ) -> List[str]:
        """Generate demand insights."""

        insights = []

        # Growing products
        if top_growing:
            names = ", ".join(p.product_name[:20] for p in top_growing[:3])
            insights.append(
                f"📈 Растущий спрос: {names} — увеличить запасы"
            )

        # Declining products
        if top_declining:
            names = ", ".join(p.product_name[:20] for p in top_declining[:3])
            insights.append(
                f"📉 Падающий спрос: {names} — рассмотреть акции или вывод"
            )

        # High confidence forecasts
        high_conf = [p for p in product_forecasts if p.confidence_score >= 80]
        if high_conf:
            insights.append(
                f"✅ Высокая точность прогноза для {len(high_conf)} из {len(product_forecasts)} товаров"
            )

        # Category insights
        if category_forecasts:
            top_cat = category_forecasts[0]
            insights.append(
                f"🏆 Топ категория: {top_cat.category_name} — "
                f"прогноз {top_cat.total_forecast:.0f} единиц"
            )

        # Stock recommendations
        high_demand = [p for p in product_forecasts if p.trend == "up" and p.avg_daily_forecast > 10]
        if high_demand:
            insights.append(
                f"📦 Рекомендуется увеличить запасы для {len(high_demand)} позиций с растущим спросом"
            )

        return insights[:5]
