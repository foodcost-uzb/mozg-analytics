"""API endpoints for advanced analytics (Phase 4)."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db, get_user_venue_ids
from app.db.models import User
from app.services.analytics import (
    MotiveMarketingService,
    PnLReportService,
    HRAnalyticsService,
    BasketAnalysisService,
)


router = APIRouter()


# ==================== Pydantic Schemas ====================


class FactorImpactResponse(BaseModel):
    """Factor impact response."""

    factor: str
    impact_level: str
    impact_percent: float
    description: str
    recommendation: str


class WeekdayAnalysisResponse(BaseModel):
    """Weekday analysis response."""

    day: int
    day_name: str
    avg_revenue: float
    avg_receipts: int
    avg_check: float
    index: float
    best_hours: List[int]


class SeasonalityResponse(BaseModel):
    """Seasonality analysis response."""

    month: int
    month_name: str
    avg_revenue: float
    index: float
    trend: str
    year_over_year: Optional[float]


class EventImpactResponse(BaseModel):
    """Event impact response."""

    event_name: str
    event_date: date
    actual_revenue: float
    expected_revenue: float
    impact_percent: float
    impact_level: str


class PricingImpactResponse(BaseModel):
    """Pricing impact response."""

    product_name: str
    old_price: float
    new_price: float
    price_change_percent: float
    quantity_before: int
    quantity_after: int
    quantity_change_percent: float
    revenue_impact: float
    elasticity: float


class MotiveReportResponse(BaseModel):
    """Complete Motive Marketing report response."""

    period_start: date
    period_end: date
    total_revenue: float
    avg_daily_revenue: float
    weekday_analysis: List[WeekdayAnalysisResponse]
    seasonality_analysis: List[SeasonalityResponse]
    event_impacts: List[EventImpactResponse]
    pricing_impacts: List[PricingImpactResponse]
    factor_summary: List[FactorImpactResponse]
    top_recommendations: List[str]


class PnLSummaryResponse(BaseModel):
    """P&L summary response."""

    gross_revenue: float
    discounts: float
    net_revenue: float
    cogs: float
    cogs_percent: float
    gross_profit: float
    gross_margin_percent: float
    labor_cost: float
    labor_percent: float
    rent_cost: float
    rent_percent: float
    marketing_cost: float
    marketing_percent: float
    other_operating: float
    total_operating: float
    operating_percent: float
    ebitda: float
    ebitda_percent: float
    depreciation: float
    taxes: float
    net_profit: float
    net_margin_percent: float


class RevenueBreakdownResponse(BaseModel):
    """Revenue breakdown by category."""

    category_id: Optional[str]
    category_name: str
    revenue: float
    cost: float
    gross_profit: float
    margin_percent: float
    revenue_percent: float


class CostLineResponse(BaseModel):
    """Cost line item."""

    category: str
    name: str
    amount: float
    percent_of_revenue: float
    notes: Optional[str]


class DailyPnLResponse(BaseModel):
    """Daily P&L response."""

    date: date
    revenue: float
    cogs: float
    gross_profit: float
    gross_margin_percent: float


class PnLComparisonResponse(BaseModel):
    """P&L comparison response."""

    revenue_change: float
    revenue_change_percent: float
    gross_profit_change: float
    gross_profit_change_percent: float
    net_profit_change: float
    net_profit_change_percent: float


class PnLReportResponse(BaseModel):
    """Complete P&L report response."""

    period_start: date
    period_end: date
    summary: PnLSummaryResponse
    revenue_by_category: List[RevenueBreakdownResponse]
    cost_lines: List[CostLineResponse]
    daily_trend: List[DailyPnLResponse]
    comparison: Optional[PnLComparisonResponse]
    industry_benchmarks: Dict[str, float]


class EmployeeMetricsResponse(BaseModel):
    """Employee metrics response."""

    employee_id: str
    employee_name: str
    role: Optional[str]
    total_revenue: float
    total_receipts: int
    total_items: int
    avg_check: float
    items_per_receipt: float
    revenue_per_hour: float
    avg_discount_percent: float
    return_rate: float
    performance_level: str
    rank: int
    percentile: float


class EmployeeComparisonResponse(BaseModel):
    """Employee comparison response."""

    employee_id: str
    employee_name: str
    revenue_vs_avg: float
    avg_check_vs_avg: float
    items_per_receipt_vs_avg: float
    strengths: List[str]
    improvements: List[str]


class ShiftAnalysisResponse(BaseModel):
    """Shift analysis response."""

    shift: str
    shift_name: str
    hours: str
    total_revenue: float
    total_receipts: int
    avg_check: float
    revenue_percent: float
    top_employees: List[str]


class HourlyProductivityResponse(BaseModel):
    """Hourly productivity response."""

    hour: int
    avg_revenue: float
    avg_receipts: int
    avg_items: int
    efficiency_index: float


class TeamMetricsResponse(BaseModel):
    """Team metrics response."""

    total_employees: int
    active_employees: int
    avg_revenue_per_employee: float
    avg_receipts_per_employee: float
    avg_check: float
    avg_items_per_receipt: float
    top_performers_count: int
    avg_performers_count: int
    low_performers_count: int
    revenue_per_labor_hour: float
    receipts_per_labor_hour: float


class HRReportResponse(BaseModel):
    """Complete HR report response."""

    period_start: date
    period_end: date
    team_metrics: TeamMetricsResponse
    employee_rankings: List[EmployeeMetricsResponse]
    employee_comparisons: List[EmployeeComparisonResponse]
    shift_analysis: List[ShiftAnalysisResponse]
    hourly_productivity: List[HourlyProductivityResponse]
    recommendations: List[str]


class ProductPairResponse(BaseModel):
    """Product pair response."""

    product_a_id: str
    product_a_name: str
    product_b_id: str
    product_b_name: str
    co_occurrence_count: int
    support: float
    confidence_a_to_b: float
    confidence_b_to_a: float
    lift: float


class CrossSellResponse(BaseModel):
    """Cross-sell recommendation response."""

    trigger_product_id: str
    trigger_product_name: str
    recommended_product_id: str
    recommended_product_name: str
    confidence: float
    lift: float
    potential_revenue: float
    recommendation_text: str


class CategoryAffinityResponse(BaseModel):
    """Category affinity response."""

    category_a_id: Optional[str]
    category_a_name: str
    category_b_id: Optional[str]
    category_b_name: str
    affinity_score: float
    avg_basket_value: float


class BasketProfileResponse(BaseModel):
    """Basket profile response."""

    avg_items: float
    avg_value: float
    avg_categories: float
    single_item_percent: float
    small_basket_percent: float
    medium_basket_percent: float
    large_basket_percent: float


class BasketReportResponse(BaseModel):
    """Complete basket report response."""

    period_start: date
    period_end: date
    basket_profile: BasketProfileResponse
    top_product_pairs: List[ProductPairResponse]
    cross_sell_recommendations: List[CrossSellResponse]
    category_affinities: List[CategoryAffinityResponse]
    insights: List[str]


# ==================== Motive Marketing Endpoints ====================


@router.get("/motive/report", response_model=MotiveReportResponse)
async def get_motive_report(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Get complete Motive Marketing analysis report.

    Analyzes 6 factors affecting sales:
    - Weekday patterns
    - Seasonality
    - Events/holidays
    - Pricing changes
    - (Weather - requires external data)
    - (Marketing - requires campaign data)
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = MotiveMarketingService(db)
    report = await service.get_full_report(venue_ids, date_from, date_to)

    return MotiveReportResponse(
        period_start=report.period_start,
        period_end=report.period_end,
        total_revenue=float(report.total_revenue),
        avg_daily_revenue=float(report.avg_daily_revenue),
        weekday_analysis=[
            WeekdayAnalysisResponse(
                day=w.day,
                day_name=w.day_name,
                avg_revenue=float(w.avg_revenue),
                avg_receipts=w.avg_receipts,
                avg_check=float(w.avg_check),
                index=float(w.index),
                best_hours=w.best_hours,
            )
            for w in report.weekday_analysis
        ],
        seasonality_analysis=[
            SeasonalityResponse(
                month=s.month,
                month_name=s.month_name,
                avg_revenue=float(s.avg_revenue),
                index=float(s.index),
                trend=s.trend,
                year_over_year=float(s.year_over_year) if s.year_over_year else None,
            )
            for s in report.seasonality_analysis
        ],
        event_impacts=[
            EventImpactResponse(
                event_name=e.event_name,
                event_date=e.event_date,
                actual_revenue=float(e.actual_revenue),
                expected_revenue=float(e.expected_revenue),
                impact_percent=float(e.impact_percent),
                impact_level=e.impact_level.value,
            )
            for e in report.event_impacts
        ],
        pricing_impacts=[
            PricingImpactResponse(
                product_name=p.product_name,
                old_price=float(p.old_price),
                new_price=float(p.new_price),
                price_change_percent=float(p.price_change_percent),
                quantity_before=p.quantity_before,
                quantity_after=p.quantity_after,
                quantity_change_percent=float(p.quantity_change_percent),
                revenue_impact=float(p.revenue_impact),
                elasticity=float(p.elasticity),
            )
            for p in report.pricing_impacts
        ],
        factor_summary=[
            FactorImpactResponse(
                factor=f.factor.value,
                impact_level=f.impact_level.value,
                impact_percent=float(f.impact_percent),
                description=f.description,
                recommendation=f.recommendation,
            )
            for f in report.factor_summary
        ],
        top_recommendations=report.top_recommendations,
    )


@router.get("/motive/weekdays", response_model=List[WeekdayAnalysisResponse])
async def get_weekday_analysis(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """Get sales analysis by day of week."""
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = MotiveMarketingService(db)
    analysis = await service.analyze_weekdays(venue_ids, date_from, date_to)

    return [
        WeekdayAnalysisResponse(
            day=w.day,
            day_name=w.day_name,
            avg_revenue=float(w.avg_revenue),
            avg_receipts=w.avg_receipts,
            avg_check=float(w.avg_check),
            index=float(w.index),
            best_hours=w.best_hours,
        )
        for w in analysis
    ]


@router.get("/motive/seasonality", response_model=List[SeasonalityResponse])
async def get_seasonality_analysis(
    months: int = Query(12, ge=3, le=24, description="Number of months to analyze"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """Get monthly seasonality analysis."""
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = MotiveMarketingService(db)
    analysis = await service.analyze_seasonality(venue_ids, months)

    return [
        SeasonalityResponse(
            month=s.month,
            month_name=s.month_name,
            avg_revenue=float(s.avg_revenue),
            index=float(s.index),
            trend=s.trend,
            year_over_year=float(s.year_over_year) if s.year_over_year else None,
        )
        for s in analysis
    ]


# ==================== P&L Report Endpoints ====================


@router.get("/pnl/report", response_model=PnLReportResponse)
async def get_pnl_report(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    labor_cost: Optional[float] = Query(None, description="Override labor cost"),
    rent_cost: Optional[float] = Query(None, description="Override rent cost"),
    marketing_cost: Optional[float] = Query(None, description="Override marketing cost"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Get complete P&L (Profit & Loss) report.

    Includes:
    - Revenue breakdown
    - Cost of Goods Sold (calculated from data)
    - Operating expenses (estimated or provided)
    - Profit margins
    - Period comparison
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = PnLReportService(db)
    report = await service.generate_report(
        venue_ids=venue_ids,
        date_from=date_from,
        date_to=date_to,
        labor_cost=Decimal(str(labor_cost)) if labor_cost else None,
        rent_cost=Decimal(str(rent_cost)) if rent_cost else None,
        marketing_cost=Decimal(str(marketing_cost)) if marketing_cost else None,
    )

    comparison = None
    if report.comparison:
        comparison = PnLComparisonResponse(
            revenue_change=float(report.comparison.revenue_change),
            revenue_change_percent=float(report.comparison.revenue_change_percent),
            gross_profit_change=float(report.comparison.gross_profit_change),
            gross_profit_change_percent=float(report.comparison.gross_profit_change_percent),
            net_profit_change=float(report.comparison.net_profit_change),
            net_profit_change_percent=float(report.comparison.net_profit_change_percent),
        )

    return PnLReportResponse(
        period_start=report.period_start,
        period_end=report.period_end,
        summary=PnLSummaryResponse(
            gross_revenue=float(report.summary.gross_revenue),
            discounts=float(report.summary.discounts),
            net_revenue=float(report.summary.net_revenue),
            cogs=float(report.summary.cogs),
            cogs_percent=float(report.summary.cogs_percent),
            gross_profit=float(report.summary.gross_profit),
            gross_margin_percent=float(report.summary.gross_margin_percent),
            labor_cost=float(report.summary.labor_cost),
            labor_percent=float(report.summary.labor_percent),
            rent_cost=float(report.summary.rent_cost),
            rent_percent=float(report.summary.rent_percent),
            marketing_cost=float(report.summary.marketing_cost),
            marketing_percent=float(report.summary.marketing_percent),
            other_operating=float(report.summary.other_operating),
            total_operating=float(report.summary.total_operating),
            operating_percent=float(report.summary.operating_percent),
            ebitda=float(report.summary.ebitda),
            ebitda_percent=float(report.summary.ebitda_percent),
            depreciation=float(report.summary.depreciation),
            taxes=float(report.summary.taxes),
            net_profit=float(report.summary.net_profit),
            net_margin_percent=float(report.summary.net_margin_percent),
        ),
        revenue_by_category=[
            RevenueBreakdownResponse(
                category_id=str(r.category_id) if r.category_id else None,
                category_name=r.category_name,
                revenue=float(r.revenue),
                cost=float(r.cost),
                gross_profit=float(r.gross_profit),
                margin_percent=float(r.margin_percent),
                revenue_percent=float(r.revenue_percent),
            )
            for r in report.revenue_by_category
        ],
        cost_lines=[
            CostLineResponse(
                category=c.category.value,
                name=c.name,
                amount=float(c.amount),
                percent_of_revenue=float(c.percent_of_revenue),
                notes=c.notes,
            )
            for c in report.cost_lines
        ],
        daily_trend=[
            DailyPnLResponse(
                date=d.date,
                revenue=float(d.revenue),
                cogs=float(d.cogs),
                gross_profit=float(d.gross_profit),
                gross_margin_percent=float(d.gross_margin_percent),
            )
            for d in report.daily_trend
        ],
        comparison=comparison,
        industry_benchmarks={k: float(v) for k, v in report.industry_benchmarks.items()},
    )


@router.get("/pnl/margin-trend")
async def get_margin_trend(
    months: int = Query(6, ge=1, le=12, description="Number of months"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """Get monthly gross margin trend."""
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = PnLReportService(db)
    trend = await service.get_margin_trend(venue_ids, months)

    return trend


# ==================== HR Analytics Endpoints ====================


@router.get("/hr/report", response_model=HRReportResponse)
async def get_hr_report(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Get complete HR analytics report.

    Includes:
    - Employee performance rankings
    - Team metrics
    - Shift analysis
    - Hourly productivity
    - Recommendations
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = HRAnalyticsService(db)
    report = await service.generate_report(venue_ids, date_from, date_to)

    return HRReportResponse(
        period_start=report.period_start,
        period_end=report.period_end,
        team_metrics=TeamMetricsResponse(
            total_employees=report.team_metrics.total_employees,
            active_employees=report.team_metrics.active_employees,
            avg_revenue_per_employee=float(report.team_metrics.avg_revenue_per_employee),
            avg_receipts_per_employee=float(report.team_metrics.avg_receipts_per_employee),
            avg_check=float(report.team_metrics.avg_check),
            avg_items_per_receipt=float(report.team_metrics.avg_items_per_receipt),
            top_performers_count=report.team_metrics.top_performers_count,
            avg_performers_count=report.team_metrics.avg_performers_count,
            low_performers_count=report.team_metrics.low_performers_count,
            revenue_per_labor_hour=float(report.team_metrics.revenue_per_labor_hour),
            receipts_per_labor_hour=float(report.team_metrics.receipts_per_labor_hour),
        ),
        employee_rankings=[
            EmployeeMetricsResponse(
                employee_id=str(e.employee_id),
                employee_name=e.employee_name,
                role=e.role,
                total_revenue=float(e.total_revenue),
                total_receipts=e.total_receipts,
                total_items=e.total_items,
                avg_check=float(e.avg_check),
                items_per_receipt=float(e.items_per_receipt),
                revenue_per_hour=float(e.revenue_per_hour),
                avg_discount_percent=float(e.avg_discount_percent),
                return_rate=float(e.return_rate),
                performance_level=e.performance_level.value,
                rank=e.rank,
                percentile=float(e.percentile),
            )
            for e in report.employee_rankings
        ],
        employee_comparisons=[
            EmployeeComparisonResponse(
                employee_id=str(c.employee_id),
                employee_name=c.employee_name,
                revenue_vs_avg=float(c.revenue_vs_avg),
                avg_check_vs_avg=float(c.avg_check_vs_avg),
                items_per_receipt_vs_avg=float(c.items_per_receipt_vs_avg),
                strengths=c.strengths,
                improvements=c.improvements,
            )
            for c in report.employee_comparisons
        ],
        shift_analysis=[
            ShiftAnalysisResponse(
                shift=s.shift.value,
                shift_name=s.shift_name,
                hours=s.hours,
                total_revenue=float(s.total_revenue),
                total_receipts=s.total_receipts,
                avg_check=float(s.avg_check),
                revenue_percent=float(s.revenue_percent),
                top_employees=s.top_employees,
            )
            for s in report.shift_analysis
        ],
        hourly_productivity=[
            HourlyProductivityResponse(
                hour=h.hour,
                avg_revenue=float(h.avg_revenue),
                avg_receipts=h.avg_receipts,
                avg_items=h.avg_items,
                efficiency_index=float(h.efficiency_index),
            )
            for h in report.hourly_productivity
        ],
        recommendations=report.recommendations,
    )


@router.get("/hr/rankings", response_model=List[EmployeeMetricsResponse])
async def get_employee_rankings(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """Get employee rankings by performance."""
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = HRAnalyticsService(db)
    metrics = await service.get_employee_metrics(venue_ids, date_from, date_to)

    return [
        EmployeeMetricsResponse(
            employee_id=str(e.employee_id),
            employee_name=e.employee_name,
            role=e.role,
            total_revenue=float(e.total_revenue),
            total_receipts=e.total_receipts,
            total_items=e.total_items,
            avg_check=float(e.avg_check),
            items_per_receipt=float(e.items_per_receipt),
            revenue_per_hour=float(e.revenue_per_hour),
            avg_discount_percent=float(e.avg_discount_percent),
            return_rate=float(e.return_rate),
            performance_level=e.performance_level.value,
            rank=e.rank,
            percentile=float(e.percentile),
        )
        for e in metrics[:limit]
    ]


# ==================== Basket Analysis Endpoints ====================


@router.get("/basket/report", response_model=BasketReportResponse)
async def get_basket_report(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """
    Get complete basket analysis report.

    Includes:
    - Basket profile (avg items, value, etc.)
    - Product pairs (frequently bought together)
    - Cross-sell recommendations
    - Category affinity
    - Actionable insights
    """
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = BasketAnalysisService(db)
    report = await service.generate_report(venue_ids, date_from, date_to)

    return BasketReportResponse(
        period_start=report.period_start,
        period_end=report.period_end,
        basket_profile=BasketProfileResponse(
            avg_items=float(report.basket_profile.avg_items),
            avg_value=float(report.basket_profile.avg_value),
            avg_categories=float(report.basket_profile.avg_categories),
            single_item_percent=float(report.basket_profile.single_item_percent),
            small_basket_percent=float(report.basket_profile.small_basket_percent),
            medium_basket_percent=float(report.basket_profile.medium_basket_percent),
            large_basket_percent=float(report.basket_profile.large_basket_percent),
        ),
        top_product_pairs=[
            ProductPairResponse(
                product_a_id=str(p.product_a_id),
                product_a_name=p.product_a_name,
                product_b_id=str(p.product_b_id),
                product_b_name=p.product_b_name,
                co_occurrence_count=p.co_occurrence_count,
                support=float(p.support),
                confidence_a_to_b=float(p.confidence_a_to_b),
                confidence_b_to_a=float(p.confidence_b_to_a),
                lift=float(p.lift),
            )
            for p in report.top_product_pairs
        ],
        cross_sell_recommendations=[
            CrossSellResponse(
                trigger_product_id=str(c.trigger_product_id),
                trigger_product_name=c.trigger_product_name,
                recommended_product_id=str(c.recommended_product_id),
                recommended_product_name=c.recommended_product_name,
                confidence=float(c.confidence),
                lift=float(c.lift),
                potential_revenue=float(c.potential_revenue),
                recommendation_text=c.recommendation_text,
            )
            for c in report.cross_sell_recommendations
        ],
        category_affinities=[
            CategoryAffinityResponse(
                category_a_id=str(a.category_a_id) if a.category_a_id else None,
                category_a_name=a.category_a_name,
                category_b_id=str(a.category_b_id) if a.category_b_id else None,
                category_b_name=a.category_b_name,
                affinity_score=float(a.affinity_score),
                avg_basket_value=float(a.avg_basket_value),
            )
            for a in report.category_affinities
        ],
        insights=report.insights,
    )


@router.get("/basket/product-pairs", response_model=List[ProductPairResponse])
async def get_product_pairs(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    min_support: float = Query(0.01, ge=0.001, le=0.5, description="Minimum support threshold"),
    limit: int = Query(50, ge=10, le=200, description="Max results"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """Get product pairs frequently bought together."""
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = BasketAnalysisService(db)
    pairs = await service.calculate_product_pairs(
        venue_ids, date_from, date_to,
        min_support=Decimal(str(min_support)),
        limit=limit,
    )

    return [
        ProductPairResponse(
            product_a_id=str(p.product_a_id),
            product_a_name=p.product_a_name,
            product_b_id=str(p.product_b_id),
            product_b_name=p.product_b_name,
            co_occurrence_count=p.co_occurrence_count,
            support=float(p.support),
            confidence_a_to_b=float(p.confidence_a_to_b),
            confidence_b_to_a=float(p.confidence_b_to_a),
            lift=float(p.lift),
        )
        for p in pairs
    ]


@router.get("/basket/cross-sell", response_model=List[CrossSellResponse])
async def get_cross_sell_recommendations(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_id: Optional[str] = Query(None, description="Filter by venue"),
    min_confidence: float = Query(0.1, ge=0.05, le=0.5, description="Min confidence"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    user_venue_ids: List[uuid.UUID] = Depends(get_user_venue_ids),
):
    """Get cross-sell recommendations based on basket analysis."""
    venue_ids = [uuid.UUID(venue_id)] if venue_id else user_venue_ids

    service = BasketAnalysisService(db)
    pairs = await service.calculate_product_pairs(venue_ids, date_from, date_to)
    recs = await service.generate_cross_sell_recommendations(
        pairs, venue_ids,
        min_confidence=Decimal(str(min_confidence)),
    )

    return [
        CrossSellResponse(
            trigger_product_id=str(c.trigger_product_id),
            trigger_product_name=c.trigger_product_name,
            recommended_product_id=str(c.recommended_product_id),
            recommended_product_name=c.recommended_product_name,
            confidence=float(c.confidence),
            lift=float(c.lift),
            potential_revenue=float(c.potential_revenue),
            recommendation_text=c.recommendation_text,
        )
        for c in recs
    ]
