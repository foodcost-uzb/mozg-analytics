"""Report API endpoints for MOZG Analytics."""

import io
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, require_analyst
from app.db.models import User, Venue
from app.db.session import get_db
from app.services.reports.sales import (
    CompareWith,
    SalesReportService,
)
from app.services.reports.menu import (
    ABCCategory,
    GoListCategory,
    MenuAnalysisService,
)
from app.services.export.excel import ExcelExportService

router = APIRouter(prefix="/reports", tags=["reports"])


# ==================== Request/Response Schemas ====================


class DateRangeParams(BaseModel):
    """Common date range parameters."""

    date_from: date
    date_to: date
    venue_ids: Optional[List[uuid.UUID]] = None


class SalesSummaryResponse(BaseModel):
    """Sales summary response."""

    revenue: Decimal
    receipts_count: int
    avg_check: Decimal
    guests_count: int
    items_count: int
    items_per_receipt: Decimal
    revenue_per_guest: Decimal
    total_discount: Decimal


class SalesDataPointResponse(BaseModel):
    """Daily sales data point."""

    date: date
    revenue: Decimal
    receipts_count: int
    avg_check: Decimal
    guests_count: int


class SalesComparisonResponse(BaseModel):
    """Sales comparison response."""

    current: SalesSummaryResponse
    previous: SalesSummaryResponse
    revenue_diff: Decimal
    revenue_diff_percent: Decimal
    receipts_diff: int
    receipts_diff_percent: Decimal
    avg_check_diff: Decimal
    avg_check_diff_percent: Decimal
    guests_diff: int
    guests_diff_percent: Decimal


class VenueSalesResponse(BaseModel):
    """Venue sales breakdown."""

    venue_id: uuid.UUID
    venue_name: str
    revenue: Decimal
    receipts_count: int
    avg_check: Decimal
    guests_count: int
    revenue_percent: Decimal


class HourlySalesResponse(BaseModel):
    """Hourly sales data."""

    hour: int
    revenue: Decimal
    receipts_count: int
    avg_revenue: Decimal


class ProductABCResponse(BaseModel):
    """ABC analysis product result."""

    product_id: uuid.UUID
    product_name: str
    category_name: Optional[str]
    quantity: Decimal
    revenue: Decimal
    cost: Decimal
    profit: Decimal
    margin_percent: Decimal
    revenue_percent: Decimal
    cumulative_percent: Decimal
    abc_category: str


class ABCSummaryResponse(BaseModel):
    """ABC category summary."""

    category: str
    count: int
    revenue: Decimal
    profit: Decimal
    revenue_percent: Decimal


class ABCAnalysisResponse(BaseModel):
    """Complete ABC analysis response."""

    products: List[ProductABCResponse]
    summary: List[ABCSummaryResponse]
    total_revenue: Decimal
    total_profit: Decimal


class ProductMarginResponse(BaseModel):
    """Product margin data."""

    product_id: uuid.UUID
    product_name: str
    category_name: Optional[str]
    quantity: Decimal
    revenue: Decimal
    cost: Decimal
    profit: Decimal
    margin_percent: Decimal
    avg_price: Decimal
    avg_cost: Decimal


class GoListItemResponse(BaseModel):
    """Go-List item response."""

    product_id: uuid.UUID
    product_name: str
    category_name: Optional[str]
    abc_category: str
    margin_percent: Decimal
    go_list_category: str
    recommendation: str
    revenue: Decimal
    profit: Decimal


class GoListSummaryResponse(BaseModel):
    """Go-List category summary."""

    category: str
    count: int
    revenue: Decimal
    profit: Decimal


class GoListResponse(BaseModel):
    """Complete Go-List response."""

    items: List[GoListItemResponse]
    summary: List[GoListSummaryResponse]
    recommendations: List[str]


class CategoryAnalysisResponse(BaseModel):
    """Category analysis response."""

    category_id: uuid.UUID
    category_name: str
    quantity: Decimal
    revenue: Decimal
    revenue_percent: Decimal
    products_count: int
    receipts_count: int


class PlanFactResponse(BaseModel):
    """Plan/fact comparison response."""

    actual_revenue: Decimal
    target_revenue: Decimal
    completion_percent: Decimal
    remaining: Decimal
    receipts_count: int
    avg_check: Decimal


# ==================== Helper Functions ====================


async def get_user_venue_ids(
    db: AsyncSession,
    user: User,
    requested_venue_ids: Optional[List[uuid.UUID]] = None,
) -> List[uuid.UUID]:
    """
    Get venue IDs that user has access to.

    If requested_venue_ids is provided, filter to only those the user can access.
    If user has allowed_venue_ids restriction, filter accordingly.
    """
    # Get all venues for user's organization
    query = select(Venue.id).where(
        Venue.organization_id == user.organization_id,
        Venue.is_active == True,
    )

    if requested_venue_ids:
        query = query.where(Venue.id.in_(requested_venue_ids))

    result = await db.execute(query)
    org_venue_ids = [row[0] for row in result.all()]

    # Filter by user's allowed venues if restricted
    if user.allowed_venue_ids:
        allowed = [uuid.UUID(v) for v in user.allowed_venue_ids]
        org_venue_ids = [v for v in org_venue_ids if v in allowed]

    if not org_venue_ids:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No venues found or accessible",
        )

    return org_venue_ids


# ==================== Sales Reports ====================


@router.get("/sales/summary", response_model=SalesSummaryResponse)
async def get_sales_summary(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get sales summary for specified period.

    Returns aggregated metrics: revenue, receipts, average check, guests, etc.
    """
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = SalesReportService(db)
    summary = await service.get_summary(user_venue_ids, date_from, date_to)

    return SalesSummaryResponse(
        revenue=summary.revenue,
        receipts_count=summary.receipts_count,
        avg_check=summary.avg_check,
        guests_count=summary.guests_count,
        items_count=summary.items_count,
        items_per_receipt=summary.items_per_receipt,
        revenue_per_guest=summary.revenue_per_guest,
        total_discount=summary.total_discount,
    )


@router.get("/sales/daily", response_model=List[SalesDataPointResponse])
async def get_sales_daily(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get daily sales breakdown."""
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = SalesReportService(db)
    data_points = await service.get_daily(user_venue_ids, date_from, date_to)

    return [
        SalesDataPointResponse(
            date=dp.date,
            revenue=dp.revenue,
            receipts_count=dp.receipts_count,
            avg_check=dp.avg_check,
            guests_count=dp.guests_count,
        )
        for dp in data_points
    ]


@router.get("/sales/comparison", response_model=SalesComparisonResponse)
async def get_sales_comparison(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    compare_with: str = Query("previous", description="previous or year_ago"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Compare sales with previous period.

    compare_with options:
    - previous: compare with immediately preceding period of same length
    - year_ago: compare with same period last year
    """
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = SalesReportService(db)

    compare = CompareWith.YEAR_AGO if compare_with == "year_ago" else CompareWith.PREVIOUS

    comparison = await service.get_comparison(
        user_venue_ids, date_from, date_to, compare
    )

    return SalesComparisonResponse(
        current=SalesSummaryResponse(
            revenue=comparison.current.revenue,
            receipts_count=comparison.current.receipts_count,
            avg_check=comparison.current.avg_check,
            guests_count=comparison.current.guests_count,
            items_count=comparison.current.items_count,
            items_per_receipt=comparison.current.items_per_receipt,
            revenue_per_guest=comparison.current.revenue_per_guest,
            total_discount=comparison.current.total_discount,
        ),
        previous=SalesSummaryResponse(
            revenue=comparison.previous.revenue,
            receipts_count=comparison.previous.receipts_count,
            avg_check=comparison.previous.avg_check,
            guests_count=comparison.previous.guests_count,
            items_count=comparison.previous.items_count,
            items_per_receipt=comparison.previous.items_per_receipt,
            revenue_per_guest=comparison.previous.revenue_per_guest,
            total_discount=comparison.previous.total_discount,
        ),
        revenue_diff=comparison.revenue_diff,
        revenue_diff_percent=comparison.revenue_diff_percent,
        receipts_diff=comparison.receipts_diff,
        receipts_diff_percent=comparison.receipts_diff_percent,
        avg_check_diff=comparison.avg_check_diff,
        avg_check_diff_percent=comparison.avg_check_diff_percent,
        guests_diff=comparison.guests_diff,
        guests_diff_percent=comparison.guests_diff_percent,
    )


@router.get("/sales/by-venue", response_model=List[VenueSalesResponse])
async def get_sales_by_venue(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get sales breakdown by venue."""
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = SalesReportService(db)
    venue_sales = await service.get_by_venue(user_venue_ids, date_from, date_to)

    return [
        VenueSalesResponse(
            venue_id=vs.venue_id,
            venue_name=vs.venue_name,
            revenue=vs.revenue,
            receipts_count=vs.receipts_count,
            avg_check=vs.avg_check,
            guests_count=vs.guests_count,
            revenue_percent=vs.revenue_percent,
        )
        for vs in venue_sales
    ]


@router.get("/sales/hourly", response_model=List[HourlySalesResponse])
async def get_sales_hourly(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get hourly sales breakdown (averaged across days)."""
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = SalesReportService(db)
    hourly = await service.get_hourly(user_venue_ids, date_from, date_to)

    return [
        HourlySalesResponse(
            hour=h.hour,
            revenue=h.revenue,
            receipts_count=h.receipts_count,
            avg_revenue=h.avg_revenue,
        )
        for h in hourly
    ]


@router.get("/sales/plan-fact", response_model=PlanFactResponse)
async def get_plan_fact(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    target_revenue: Optional[Decimal] = Query(None, description="Target revenue"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Get plan/fact comparison.

    If target_revenue is not provided, uses previous period revenue as target.
    """
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = SalesReportService(db)
    result = await service.get_plan_fact(
        user_venue_ids, date_from, date_to, target_revenue
    )

    return PlanFactResponse(**result)


@router.get("/sales/top-days", response_model=List[SalesDataPointResponse])
async def get_top_days(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    limit: int = Query(10, ge=1, le=100, description="Number of days to return"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get top N days by revenue."""
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = SalesReportService(db)
    top_days = await service.get_top_days(user_venue_ids, date_from, date_to, limit)

    return [
        SalesDataPointResponse(
            date=dp.date,
            revenue=dp.revenue,
            receipts_count=dp.receipts_count,
            avg_check=dp.avg_check,
            guests_count=dp.guests_count,
        )
        for dp in top_days
    ]


@router.get("/sales/weekday-analysis")
async def get_weekday_analysis(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get average sales by day of week."""
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = SalesReportService(db)
    weekday_data = await service.get_weekday_analysis(user_venue_ids, date_from, date_to)

    return weekday_data


# ==================== Menu Analysis Reports ====================


@router.get("/menu/abc", response_model=ABCAnalysisResponse)
async def get_abc_analysis(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    metric: str = Query("revenue", description="Metric: revenue, profit, or quantity"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Perform ABC analysis on products.

    Classifies products into A (80%), B (15%), C (5%) by chosen metric.
    """
    if metric not in ["revenue", "profit", "quantity"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metric must be one of: revenue, profit, quantity",
        )

    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = MenuAnalysisService(db)
    result = await service.abc_analysis(user_venue_ids, date_from, date_to, metric)

    products = [
        ProductABCResponse(
            product_id=p.product_id,
            product_name=p.product_name,
            category_name=p.category_name,
            quantity=p.quantity,
            revenue=p.revenue,
            cost=p.cost,
            profit=p.profit,
            margin_percent=p.margin_percent,
            revenue_percent=p.revenue_percent,
            cumulative_percent=p.cumulative_percent,
            abc_category=p.abc_category.value,
        )
        for p in result.products
    ]

    summary = [
        ABCSummaryResponse(
            category=cat.value,
            count=data["count"],
            revenue=data["revenue"],
            profit=data["profit"],
            revenue_percent=data["revenue_percent"],
        )
        for cat, data in result.summary.items()
    ]

    return ABCAnalysisResponse(
        products=products,
        summary=summary,
        total_revenue=result.total_revenue,
        total_profit=result.total_profit,
    )


@router.get("/menu/margin", response_model=List[ProductMarginResponse])
async def get_margin_analysis(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    min_quantity: int = Query(1, ge=1, description="Minimum quantity sold"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get margin analysis for all products."""
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = MenuAnalysisService(db)
    margins = await service.margin_analysis(
        user_venue_ids, date_from, date_to, min_quantity
    )

    return [
        ProductMarginResponse(
            product_id=m.product_id,
            product_name=m.product_name,
            category_name=m.category_name,
            quantity=m.quantity,
            revenue=m.revenue,
            cost=m.cost,
            profit=m.profit,
            margin_percent=m.margin_percent,
            avg_price=m.avg_price,
            avg_cost=m.avg_cost,
        )
        for m in margins
    ]


@router.get("/menu/go-list", response_model=GoListResponse)
async def get_go_list(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    margin_threshold: Optional[Decimal] = Query(
        None, description="Margin threshold (uses median if not provided)"
    ),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Generate Go-List recommendations.

    Combines ABC analysis with margin to provide actionable recommendations.
    """
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = MenuAnalysisService(db)
    result = await service.go_list(
        user_venue_ids, date_from, date_to, margin_threshold
    )

    items = [
        GoListItemResponse(
            product_id=i.product_id,
            product_name=i.product_name,
            category_name=i.category_name,
            abc_category=i.abc_category.value,
            margin_percent=i.margin_percent,
            go_list_category=i.go_list_category.value,
            recommendation=i.recommendation,
            revenue=i.revenue,
            profit=i.profit,
        )
        for i in result.items
    ]

    summary = [
        GoListSummaryResponse(
            category=cat.value,
            count=data["count"],
            revenue=data["revenue"],
            profit=data["profit"],
        )
        for cat, data in result.summary.items()
    ]

    return GoListResponse(
        items=items,
        summary=summary,
        recommendations=result.recommendations,
    )


@router.get("/menu/top-sellers", response_model=List[ProductMarginResponse])
async def get_top_sellers(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    limit: int = Query(10, ge=1, le=100, description="Number of products"),
    by: str = Query("revenue", description="Sort by: revenue, quantity, or profit"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get top selling products."""
    if by not in ["revenue", "quantity", "profit"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="by must be one of: revenue, quantity, profit",
        )

    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = MenuAnalysisService(db)
    products = await service.top_sellers(user_venue_ids, date_from, date_to, limit, by)

    return [
        ProductMarginResponse(
            product_id=p.product_id,
            product_name=p.product_name,
            category_name=p.category_name,
            quantity=p.quantity,
            revenue=p.revenue,
            cost=p.cost,
            profit=p.profit,
            margin_percent=p.margin_percent,
            avg_price=p.avg_price,
            avg_cost=p.avg_cost,
        )
        for p in products
    ]


@router.get("/menu/worst-sellers", response_model=List[ProductMarginResponse])
async def get_worst_sellers(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    limit: int = Query(10, ge=1, le=100, description="Number of products"),
    min_quantity: int = Query(5, ge=1, description="Minimum quantity sold"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get worst selling products."""
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = MenuAnalysisService(db)
    products = await service.worst_sellers(
        user_venue_ids, date_from, date_to, limit, min_quantity
    )

    return [
        ProductMarginResponse(
            product_id=p.product_id,
            product_name=p.product_name,
            category_name=p.category_name,
            quantity=p.quantity,
            revenue=p.revenue,
            cost=p.cost,
            profit=p.profit,
            margin_percent=p.margin_percent,
            avg_price=p.avg_price,
            avg_cost=p.avg_cost,
        )
        for p in products
    ]


@router.get("/menu/categories", response_model=List[CategoryAnalysisResponse])
async def get_category_analysis(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Get sales analysis by product category."""
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = MenuAnalysisService(db)
    categories = await service.category_analysis(user_venue_ids, date_from, date_to)

    return [
        CategoryAnalysisResponse(
            category_id=c["category_id"],
            category_name=c["category_name"],
            quantity=c["quantity"],
            revenue=c["revenue"],
            revenue_percent=c["revenue_percent"],
            products_count=c["products_count"],
            receipts_count=c["receipts_count"],
        )
        for c in categories
    ]


# ==================== Export Endpoints ====================


@router.get("/export/sales")
async def export_sales_excel(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    include_daily: bool = Query(True, description="Include daily breakdown"),
    include_hourly: bool = Query(True, description="Include hourly breakdown"),
    include_venues: bool = Query(True, description="Include venue comparison"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export sales report to Excel.

    Returns downloadable XLSX file with multiple sheets.
    """
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = ExcelExportService(db)

    excel_bytes = await service.export_sales_summary(
        venue_ids=user_venue_ids,
        date_from=date_from,
        date_to=date_to,
        include_daily=include_daily,
        include_hourly=include_hourly,
        include_venues=include_venues,
    )

    filename = f"sales_report_{date_from}_{date_to}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/abc")
async def export_abc_excel(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    metric: str = Query("revenue", description="Metric: revenue, profit, or quantity"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export ABC analysis to Excel.

    Returns downloadable XLSX file with ABC classification.
    """
    if metric not in ["revenue", "profit", "quantity"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="metric must be one of: revenue, profit, quantity",
        )

    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = ExcelExportService(db)

    excel_bytes = await service.export_abc_analysis(
        venue_ids=user_venue_ids,
        date_from=date_from,
        date_to=date_to,
        metric=metric,
    )

    filename = f"abc_analysis_{date_from}_{date_to}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/go-list")
async def export_go_list_excel(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    margin_threshold: Optional[Decimal] = Query(
        None, description="Margin threshold (uses median if not provided)"
    ),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export Go-List to Excel.

    Returns downloadable XLSX file with recommendations.
    """
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = ExcelExportService(db)

    excel_bytes = await service.export_go_list(
        venue_ids=user_venue_ids,
        date_from=date_from,
        date_to=date_to,
        margin_threshold=margin_threshold,
    )

    filename = f"go_list_{date_from}_{date_to}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/export/margin")
async def export_margin_excel(
    date_from: date = Query(..., description="Start date"),
    date_to: date = Query(..., description="End date"),
    min_quantity: int = Query(1, ge=1, description="Minimum quantity sold"),
    venue_ids: Optional[List[uuid.UUID]] = Query(None, description="Filter by venue IDs"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Export margin analysis to Excel.

    Returns downloadable XLSX file with product margins.
    """
    user_venue_ids = await get_user_venue_ids(db, current_user, venue_ids)
    service = ExcelExportService(db)

    excel_bytes = await service.export_margin_analysis(
        venue_ids=user_venue_ids,
        date_from=date_from,
        date_to=date_to,
        min_quantity=min_quantity,
    )

    filename = f"margin_analysis_{date_from}_{date_to}.xlsx"

    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
