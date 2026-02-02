"""API endpoints for forecasting services (Phase 5)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_user_venue_ids
from app.db.models import User
from app.services.forecasting import (
    RevenueForecastService,
    DemandForecastService,
    AnomalyDetectionService,
)

router = APIRouter()


# ==================== Pydantic Schemas ====================


class ForecastPointResponse(BaseModel):
    """Single forecast point."""

    date: date
    forecast: float
    lower_bound: float
    upper_bound: float
    is_actual: bool = False


class ForecastAccuracyResponse(BaseModel):
    """Forecast accuracy metrics."""

    mape: float
    rmse: float
    mae: float
    r_squared: float


class SeasonalComponentResponse(BaseModel):
    """Seasonal component."""

    name: str
    strength: float
    pattern: Dict[str, float]


class TrendComponentResponse(BaseModel):
    """Trend component."""

    direction: str
    slope: float
    change_points: List[date]


class RevenueForecastResponse(BaseModel):
    """Complete revenue forecast response."""

    forecast_start: date
    forecast_end: date
    horizon_days: int

    historical: List[ForecastPointResponse]
    forecast: List[ForecastPointResponse]

    accuracy: Optional[ForecastAccuracyResponse]
    seasonality: List[SeasonalComponentResponse]
    trend: TrendComponentResponse

    total_forecast: float
    avg_daily_forecast: float
    growth_percent: float

    insights: List[str]


class QuickForecastResponse(BaseModel):
    """Quick forecast for dashboard."""

    forecast: List[ForecastPointResponse]
    total: float
    avg_daily: float


class ProductForecastPointResponse(BaseModel):
    """Product demand forecast point."""

    date: date
    quantity: float
    lower_bound: float
    upper_bound: float


class ProductDemandResponse(BaseModel):
    """Product demand forecast."""

    product_id: str
    product_name: str
    category_name: Optional[str]

    forecast: List[ProductForecastPointResponse]
    total_forecast: float
    avg_daily_forecast: float

    historical_avg: float
    historical_total: float

    trend: str
    trend_percent: float
    confidence_score: float


class CategoryDemandResponse(BaseModel):
    """Category demand forecast."""

    category_name: str
    total_forecast: float
    growth_percent: float
    product_count: int


class DemandForecastResponse(BaseModel):
    """Complete demand forecast response."""

    forecast_start: date
    forecast_end: date
    horizon_days: int

    product_forecasts: List[ProductDemandResponse]
    category_forecasts: List[CategoryDemandResponse]

    top_growing: List[ProductDemandResponse]
    top_declining: List[ProductDemandResponse]

    insights: List[str]


class AnomalyResponse(BaseModel):
    """Single anomaly."""

    anomaly_type: str
    severity: str
    date: date
    hour: Optional[int]

    actual_value: float
    expected_value: float
    deviation_percent: float
    z_score: float

    metric_name: str
    description: str
    possible_causes: List[str]
    recommended_actions: List[str]

    product_id: Optional[str]
    product_name: Optional[str]


class AnomalyStatsResponse(BaseModel):
    """Anomaly statistics."""

    total_anomalies: int
    by_type: Dict[str, int]
    by_severity: Dict[str, int]
    most_common_day: Optional[str]
    most_affected_metric: str


class AnomalyReportResponse(BaseModel):
    """Complete anomaly report response."""

    period_start: date
    period_end: date

    anomalies: List[AnomalyResponse]
    stats: AnomalyStatsResponse

    critical_count: int
    high_count: int
    requires_attention: bool

    insights: List[str]


# ==================== Revenue Forecast Endpoints ====================


@router.get("/revenue/forecast", response_model=RevenueForecastResponse)
async def get_revenue_forecast(
    horizon_days: int = Query(30, ge=7, le=90, description="Days to forecast"),
    history_days: int = Query(365, ge=30, le=730, description="Historical days to use"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Generate revenue forecast using Prophet.

    Returns:
    - Time series forecast with confidence intervals
    - Seasonality analysis (weekly, yearly)
    - Trend detection
    - Accuracy metrics (backtesting)
    - Actionable insights
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = RevenueForecastService(db)

    try:
        result = await service.forecast_revenue(
            venue_ids=venue_ids,
            horizon_days=horizon_days,
            history_days=history_days,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    accuracy = None
    if result.accuracy:
        accuracy = ForecastAccuracyResponse(
            mape=float(result.accuracy.mape),
            rmse=float(result.accuracy.rmse),
            mae=float(result.accuracy.mae),
            r_squared=float(result.accuracy.r_squared),
        )

    return RevenueForecastResponse(
        forecast_start=result.forecast_start,
        forecast_end=result.forecast_end,
        horizon_days=result.horizon_days,
        historical=[
            ForecastPointResponse(
                date=p.date,
                forecast=float(p.forecast),
                lower_bound=float(p.lower_bound),
                upper_bound=float(p.upper_bound),
                is_actual=p.is_actual,
            )
            for p in result.historical
        ],
        forecast=[
            ForecastPointResponse(
                date=p.date,
                forecast=float(p.forecast),
                lower_bound=float(p.lower_bound),
                upper_bound=float(p.upper_bound),
            )
            for p in result.forecast
        ],
        accuracy=accuracy,
        seasonality=[
            SeasonalComponentResponse(
                name=s.name,
                strength=float(s.strength),
                pattern={k: float(v) for k, v in s.pattern.items()},
            )
            for s in result.seasonality
        ],
        trend=TrendComponentResponse(
            direction=result.trend.direction,
            slope=float(result.trend.slope),
            change_points=result.trend.change_points,
        ),
        total_forecast=float(result.total_forecast),
        avg_daily_forecast=float(result.avg_daily_forecast),
        growth_percent=float(result.growth_percent),
        insights=result.insights,
    )


@router.get("/revenue/quick", response_model=QuickForecastResponse)
async def get_quick_revenue_forecast(
    days: int = Query(7, ge=1, le=14, description="Days to forecast"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Quick revenue forecast for dashboard widgets.

    Faster than full forecast, suitable for real-time display.
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = RevenueForecastService(db)
    result = await service.quick_forecast(venue_ids, days)

    total = sum(p.forecast for p in result)
    avg_daily = total / len(result) if result else Decimal("0")

    return QuickForecastResponse(
        forecast=[
            ForecastPointResponse(
                date=p.date,
                forecast=float(p.forecast),
                lower_bound=float(p.lower_bound),
                upper_bound=float(p.upper_bound),
            )
            for p in result
        ],
        total=float(total),
        avg_daily=float(avg_daily),
    )


# ==================== Demand Forecast Endpoints ====================


@router.get("/demand/forecast", response_model=DemandForecastResponse)
async def get_demand_forecast(
    horizon_days: int = Query(14, ge=7, le=30, description="Days to forecast"),
    top_n: int = Query(30, ge=10, le=100, description="Number of products to forecast"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Generate product demand forecast.

    Returns:
    - Individual product forecasts
    - Category aggregations
    - Trending products (growing/declining)
    - Stock recommendations
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = DemandForecastService(db)
    result = await service.forecast_all_products(
        venue_ids=venue_ids,
        horizon_days=horizon_days,
        top_n=top_n,
    )

    def convert_product(p) -> ProductDemandResponse:
        return ProductDemandResponse(
            product_id=str(p.product_id),
            product_name=p.product_name,
            category_name=p.category_name,
            forecast=[
                ProductForecastPointResponse(
                    date=f.date,
                    quantity=float(f.quantity),
                    lower_bound=float(f.lower_bound),
                    upper_bound=float(f.upper_bound),
                )
                for f in p.forecast
            ],
            total_forecast=float(p.total_forecast),
            avg_daily_forecast=float(p.avg_daily_forecast),
            historical_avg=float(p.historical_avg),
            historical_total=float(p.historical_total),
            trend=p.trend,
            trend_percent=float(p.trend_percent),
            confidence_score=float(p.confidence_score),
        )

    return DemandForecastResponse(
        forecast_start=result.forecast_start,
        forecast_end=result.forecast_end,
        horizon_days=result.horizon_days,
        product_forecasts=[convert_product(p) for p in result.product_forecasts],
        category_forecasts=[
            CategoryDemandResponse(
                category_name=c.category_name,
                total_forecast=float(c.total_forecast),
                growth_percent=float(c.growth_percent),
                product_count=len(c.products),
            )
            for c in result.category_forecasts
        ],
        top_growing=[convert_product(p) for p in result.top_growing],
        top_declining=[convert_product(p) for p in result.top_declining],
        insights=result.insights,
    )


@router.get("/demand/product/{product_id}", response_model=ProductDemandResponse)
async def get_product_demand_forecast(
    product_id: str,
    horizon_days: int = Query(14, ge=7, le=30, description="Days to forecast"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Get demand forecast for a specific product.
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = DemandForecastService(db)

    try:
        result = await service.forecast_product_demand(
            venue_ids=venue_ids,
            product_id=uuid.UUID(product_id),
            horizon_days=horizon_days,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    return ProductDemandResponse(
        product_id=str(result.product_id),
        product_name=result.product_name,
        category_name=result.category_name,
        forecast=[
            ProductForecastPointResponse(
                date=f.date,
                quantity=float(f.quantity),
                lower_bound=float(f.lower_bound),
                upper_bound=float(f.upper_bound),
            )
            for f in result.forecast
        ],
        total_forecast=float(result.total_forecast),
        avg_daily_forecast=float(result.avg_daily_forecast),
        historical_avg=float(result.historical_avg),
        historical_total=float(result.historical_total),
        trend=result.trend,
        trend_percent=float(result.trend_percent),
        confidence_score=float(result.confidence_score),
    )


# ==================== Anomaly Detection Endpoints ====================


@router.get("/anomalies/report", response_model=AnomalyReportResponse)
async def get_anomaly_report(
    days: int = Query(30, ge=7, le=90, description="Days to analyze"),
    include_products: bool = Query(True, description="Include product anomalies"),
    include_hourly: bool = Query(True, description="Include hourly anomalies"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Generate anomaly detection report.

    Detects anomalies in:
    - Daily revenue, traffic, average check
    - Product sales patterns
    - Hourly revenue patterns

    Returns anomalies with:
    - Severity levels (low, medium, high, critical)
    - Possible causes
    - Recommended actions
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = AnomalyDetectionService(db)
    result = await service.generate_report(
        venue_ids=venue_ids,
        days=days,
        include_products=include_products,
        include_hourly=include_hourly,
    )

    return AnomalyReportResponse(
        period_start=result.period_start,
        period_end=result.period_end,
        anomalies=[
            AnomalyResponse(
                anomaly_type=a.anomaly_type.value,
                severity=a.severity.value,
                date=a.date,
                hour=a.hour,
                actual_value=float(a.actual_value),
                expected_value=float(a.expected_value),
                deviation_percent=float(a.deviation_percent),
                z_score=float(a.z_score),
                metric_name=a.metric_name,
                description=a.description,
                possible_causes=a.possible_causes,
                recommended_actions=a.recommended_actions,
                product_id=str(a.product_id) if a.product_id else None,
                product_name=a.product_name,
            )
            for a in result.anomalies
        ],
        stats=AnomalyStatsResponse(
            total_anomalies=result.stats.total_anomalies,
            by_type=result.stats.by_type,
            by_severity=result.stats.by_severity,
            most_common_day=result.stats.most_common_day,
            most_affected_metric=result.stats.most_affected_metric,
        ),
        critical_count=result.critical_count,
        high_count=result.high_count,
        requires_attention=result.requires_attention,
        insights=result.insights,
    )


@router.get("/anomalies/recent", response_model=List[AnomalyResponse])
async def get_recent_anomalies(
    days: int = Query(7, ge=1, le=30, description="Days to check"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    limit: int = Query(10, ge=1, le=50, description="Max results"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Get recent anomalies for alerts/notifications.
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = AnomalyDetectionService(db)
    result = await service.generate_report(
        venue_ids=venue_ids,
        days=days,
        include_products=True,
        include_hourly=False,  # Skip hourly for quick check
    )

    anomalies = result.anomalies

    # Filter by severity if specified
    if severity:
        anomalies = [a for a in anomalies if a.severity.value == severity]

    # Limit results
    anomalies = anomalies[:limit]

    return [
        AnomalyResponse(
            anomaly_type=a.anomaly_type.value,
            severity=a.severity.value,
            date=a.date,
            hour=a.hour,
            actual_value=float(a.actual_value),
            expected_value=float(a.expected_value),
            deviation_percent=float(a.deviation_percent),
            z_score=float(a.z_score),
            metric_name=a.metric_name,
            description=a.description,
            possible_causes=a.possible_causes,
            recommended_actions=a.recommended_actions,
            product_id=str(a.product_id) if a.product_id else None,
            product_name=a.product_name,
        )
        for a in anomalies
    ]
