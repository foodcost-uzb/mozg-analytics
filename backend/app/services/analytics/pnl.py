"""P&L (Profit & Loss) Report service for MOZG Analytics."""

import uuid
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    DailySales,
    Receipt,
    ReceiptItem,
    Product,
    Category,
    Venue,
)


class CostCategory(str, Enum):
    """Categories of costs in P&L."""

    COGS = "cogs"                    # Cost of Goods Sold (food cost)
    LABOR = "labor"                  # Labor costs
    RENT = "rent"                    # Rent and utilities
    MARKETING = "marketing"          # Marketing expenses
    OPERATIONS = "operations"        # Operating expenses
    DEPRECIATION = "depreciation"    # Depreciation
    OTHER = "other"                  # Other expenses


@dataclass
class RevenueBreakdown:
    """Revenue breakdown by category."""

    category_id: Optional[uuid.UUID]
    category_name: str
    revenue: Decimal
    cost: Decimal
    gross_profit: Decimal
    margin_percent: Decimal
    revenue_percent: Decimal  # % of total revenue


@dataclass
class CostLine:
    """Single line item in P&L costs."""

    category: CostCategory
    name: str
    amount: Decimal
    percent_of_revenue: Decimal
    notes: Optional[str] = None


@dataclass
class PnLSummary:
    """P&L Summary metrics."""

    # Revenue
    gross_revenue: Decimal
    discounts: Decimal
    net_revenue: Decimal

    # Cost of Goods Sold
    cogs: Decimal
    cogs_percent: Decimal

    # Gross Profit
    gross_profit: Decimal
    gross_margin_percent: Decimal

    # Operating Expenses
    labor_cost: Decimal
    labor_percent: Decimal
    rent_cost: Decimal
    rent_percent: Decimal
    marketing_cost: Decimal
    marketing_percent: Decimal
    other_operating: Decimal
    total_operating: Decimal
    operating_percent: Decimal

    # Operating Profit (EBITDA)
    ebitda: Decimal
    ebitda_percent: Decimal

    # Net Profit
    depreciation: Decimal
    taxes: Decimal
    net_profit: Decimal
    net_margin_percent: Decimal


@dataclass
class PnLComparison:
    """Comparison between two periods."""

    current: PnLSummary
    previous: PnLSummary

    revenue_change: Decimal
    revenue_change_percent: Decimal
    gross_profit_change: Decimal
    gross_profit_change_percent: Decimal
    net_profit_change: Decimal
    net_profit_change_percent: Decimal


@dataclass
class DailyPnL:
    """Daily P&L data point."""

    date: date
    revenue: Decimal
    cogs: Decimal
    gross_profit: Decimal
    gross_margin_percent: Decimal


@dataclass
class PnLReport:
    """Complete P&L Report."""

    period_start: date
    period_end: date
    venue_ids: List[uuid.UUID]

    # Summary
    summary: PnLSummary

    # Revenue breakdown
    revenue_by_category: List[RevenueBreakdown]

    # Cost breakdown
    cost_lines: List[CostLine]

    # Daily trend
    daily_trend: List[DailyPnL]

    # Comparison with previous period
    comparison: Optional[PnLComparison] = None

    # Benchmarks
    industry_benchmarks: Dict[str, Decimal] = field(default_factory=dict)


class PnLReportService:
    """
    Profit & Loss Report service.

    Generates detailed P&L reports including:
    - Revenue breakdown by category
    - Cost of Goods Sold (food cost)
    - Operating expenses
    - Profit margins
    - Period comparisons
    """

    # Industry benchmarks for restaurants (Russia)
    BENCHMARKS = {
        "cogs_percent": Decimal("30"),           # 25-35%
        "labor_percent": Decimal("25"),          # 20-30%
        "rent_percent": Decimal("10"),           # 8-15%
        "marketing_percent": Decimal("3"),       # 2-5%
        "operating_percent": Decimal("40"),      # 35-45%
        "gross_margin_percent": Decimal("70"),   # 65-75%
        "net_margin_percent": Decimal("10"),     # 5-15%
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_revenue_breakdown(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[RevenueBreakdown]:
        """Calculate revenue and profit breakdown by category."""

        query = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                func.sum(ReceiptItem.total).label("revenue"),
                func.sum(
                    ReceiptItem.cost_price * ReceiptItem.quantity
                ).label("cost"),
            )
            .select_from(ReceiptItem)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .outerjoin(Product, ReceiptItem.product_id == Product.id)
            .outerjoin(Category, Product.category_id == Category.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(Category.id, Category.name)
            .order_by(func.sum(ReceiptItem.total).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        # Calculate totals
        total_revenue = sum(Decimal(str(r.revenue or 0)) for r in rows)

        breakdowns = []
        for row in rows:
            revenue = Decimal(str(row.revenue or 0))
            cost = Decimal(str(row.cost or 0))
            gross_profit = revenue - cost
            margin_percent = (gross_profit / revenue * 100) if revenue > 0 else Decimal("0")
            revenue_percent = (revenue / total_revenue * 100) if total_revenue > 0 else Decimal("0")

            breakdowns.append(RevenueBreakdown(
                category_id=row.category_id,
                category_name=row.category_name or "Без категории",
                revenue=revenue.quantize(Decimal("0.01")),
                cost=cost.quantize(Decimal("0.01")),
                gross_profit=gross_profit.quantize(Decimal("0.01")),
                margin_percent=margin_percent.quantize(Decimal("0.1")),
                revenue_percent=revenue_percent.quantize(Decimal("0.1")),
            ))

        return breakdowns

    async def calculate_cogs(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> Decimal:
        """Calculate total Cost of Goods Sold."""

        query = (
            select(
                func.sum(
                    func.coalesce(ReceiptItem.cost_price, Decimal("0")) * ReceiptItem.quantity
                ).label("total_cost"),
            )
            .select_from(ReceiptItem)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                )
            )
        )

        result = await self.db.execute(query)
        row = result.first()

        return Decimal(str(row.total_cost)) if row and row.total_cost else Decimal("0")

    async def get_revenue_and_discounts(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> tuple[Decimal, Decimal, Decimal]:
        """Get gross revenue, discounts, and net revenue."""

        query = (
            select(
                func.sum(Receipt.subtotal).label("gross_revenue"),
                func.sum(Receipt.discount_amount).label("discounts"),
                func.sum(Receipt.total).label("net_revenue"),
            )
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                    Receipt.is_paid == True,
                )
            )
        )

        result = await self.db.execute(query)
        row = result.first()

        gross = Decimal(str(row.gross_revenue)) if row and row.gross_revenue else Decimal("0")
        discounts = Decimal(str(row.discounts)) if row and row.discounts else Decimal("0")
        net = Decimal(str(row.net_revenue)) if row and row.net_revenue else Decimal("0")

        return gross, discounts, net

    async def get_daily_pnl(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[DailyPnL]:
        """Get daily P&L trend."""

        query = (
            select(
                func.date(Receipt.opened_at).label("date"),
                func.sum(Receipt.total).label("revenue"),
                func.sum(
                    func.coalesce(ReceiptItem.cost_price, Decimal("0")) * ReceiptItem.quantity
                ).label("cogs"),
            )
            .select_from(Receipt)
            .join(ReceiptItem, Receipt.id == ReceiptItem.receipt_id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(func.date(Receipt.opened_at))
            .order_by(func.date(Receipt.opened_at))
        )

        result = await self.db.execute(query)
        rows = result.all()

        daily_data = []
        for row in rows:
            revenue = Decimal(str(row.revenue or 0))
            cogs = Decimal(str(row.cogs or 0))
            gross_profit = revenue - cogs
            margin = (gross_profit / revenue * 100) if revenue > 0 else Decimal("0")

            daily_data.append(DailyPnL(
                date=row.date,
                revenue=revenue.quantize(Decimal("0.01")),
                cogs=cogs.quantize(Decimal("0.01")),
                gross_profit=gross_profit.quantize(Decimal("0.01")),
                gross_margin_percent=margin.quantize(Decimal("0.1")),
            ))

        return daily_data

    def calculate_summary(
        self,
        gross_revenue: Decimal,
        discounts: Decimal,
        net_revenue: Decimal,
        cogs: Decimal,
        labor_cost: Optional[Decimal] = None,
        rent_cost: Optional[Decimal] = None,
        marketing_cost: Optional[Decimal] = None,
        other_operating: Optional[Decimal] = None,
        depreciation: Optional[Decimal] = None,
        taxes: Optional[Decimal] = None,
    ) -> PnLSummary:
        """Calculate complete P&L summary."""

        # Use estimates based on industry benchmarks if not provided
        if labor_cost is None:
            labor_cost = net_revenue * Decimal("0.25")  # 25%
        if rent_cost is None:
            rent_cost = net_revenue * Decimal("0.10")   # 10%
        if marketing_cost is None:
            marketing_cost = net_revenue * Decimal("0.03")  # 3%
        if other_operating is None:
            other_operating = net_revenue * Decimal("0.07")  # 7%
        if depreciation is None:
            depreciation = net_revenue * Decimal("0.02")  # 2%
        if taxes is None:
            taxes = Decimal("0")  # Calculated separately

        # Gross Profit
        gross_profit = net_revenue - cogs
        gross_margin = (gross_profit / net_revenue * 100) if net_revenue > 0 else Decimal("0")

        # Operating Expenses
        total_operating = labor_cost + rent_cost + marketing_cost + other_operating

        # EBITDA
        ebitda = gross_profit - total_operating
        ebitda_percent = (ebitda / net_revenue * 100) if net_revenue > 0 else Decimal("0")

        # Net Profit
        net_profit = ebitda - depreciation - taxes
        net_margin = (net_profit / net_revenue * 100) if net_revenue > 0 else Decimal("0")

        return PnLSummary(
            gross_revenue=gross_revenue.quantize(Decimal("0.01")),
            discounts=discounts.quantize(Decimal("0.01")),
            net_revenue=net_revenue.quantize(Decimal("0.01")),
            cogs=cogs.quantize(Decimal("0.01")),
            cogs_percent=((cogs / net_revenue * 100) if net_revenue > 0 else Decimal("0")).quantize(Decimal("0.1")),
            gross_profit=gross_profit.quantize(Decimal("0.01")),
            gross_margin_percent=gross_margin.quantize(Decimal("0.1")),
            labor_cost=labor_cost.quantize(Decimal("0.01")),
            labor_percent=((labor_cost / net_revenue * 100) if net_revenue > 0 else Decimal("0")).quantize(Decimal("0.1")),
            rent_cost=rent_cost.quantize(Decimal("0.01")),
            rent_percent=((rent_cost / net_revenue * 100) if net_revenue > 0 else Decimal("0")).quantize(Decimal("0.1")),
            marketing_cost=marketing_cost.quantize(Decimal("0.01")),
            marketing_percent=((marketing_cost / net_revenue * 100) if net_revenue > 0 else Decimal("0")).quantize(Decimal("0.1")),
            other_operating=other_operating.quantize(Decimal("0.01")),
            total_operating=total_operating.quantize(Decimal("0.01")),
            operating_percent=((total_operating / net_revenue * 100) if net_revenue > 0 else Decimal("0")).quantize(Decimal("0.1")),
            ebitda=ebitda.quantize(Decimal("0.01")),
            ebitda_percent=ebitda_percent.quantize(Decimal("0.1")),
            depreciation=depreciation.quantize(Decimal("0.01")),
            taxes=taxes.quantize(Decimal("0.01")),
            net_profit=net_profit.quantize(Decimal("0.01")),
            net_margin_percent=net_margin.quantize(Decimal("0.1")),
        )

    def build_cost_lines(self, summary: PnLSummary) -> List[CostLine]:
        """Build detailed cost lines for the report."""

        return [
            CostLine(
                category=CostCategory.COGS,
                name="Себестоимость продукции (Food Cost)",
                amount=summary.cogs,
                percent_of_revenue=summary.cogs_percent,
                notes="Включает стоимость продуктов и напитков",
            ),
            CostLine(
                category=CostCategory.LABOR,
                name="Затраты на персонал",
                amount=summary.labor_cost,
                percent_of_revenue=summary.labor_percent,
                notes="Зарплаты, налоги, бонусы",
            ),
            CostLine(
                category=CostCategory.RENT,
                name="Аренда и коммунальные услуги",
                amount=summary.rent_cost,
                percent_of_revenue=summary.rent_percent,
                notes="Аренда, электричество, вода, интернет",
            ),
            CostLine(
                category=CostCategory.MARKETING,
                name="Маркетинг и реклама",
                amount=summary.marketing_cost,
                percent_of_revenue=summary.marketing_percent,
                notes="Реклама, SMM, акции",
            ),
            CostLine(
                category=CostCategory.OPERATIONS,
                name="Прочие операционные расходы",
                amount=summary.other_operating,
                percent_of_revenue=((summary.other_operating / summary.net_revenue * 100) if summary.net_revenue > 0 else Decimal("0")).quantize(Decimal("0.1")),
                notes="Инвентарь, обслуживание, расходные материалы",
            ),
            CostLine(
                category=CostCategory.DEPRECIATION,
                name="Амортизация",
                amount=summary.depreciation,
                percent_of_revenue=((summary.depreciation / summary.net_revenue * 100) if summary.net_revenue > 0 else Decimal("0")).quantize(Decimal("0.1")),
                notes="Оборудование, ремонт",
            ),
        ]

    async def generate_report(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        include_comparison: bool = True,
        labor_cost: Optional[Decimal] = None,
        rent_cost: Optional[Decimal] = None,
        marketing_cost: Optional[Decimal] = None,
    ) -> PnLReport:
        """Generate complete P&L report."""

        # Get revenue data
        gross_revenue, discounts, net_revenue = await self.get_revenue_and_discounts(
            venue_ids, date_from, date_to
        )

        # Get COGS
        cogs = await self.calculate_cogs(venue_ids, date_from, date_to)

        # Calculate summary
        summary = self.calculate_summary(
            gross_revenue=gross_revenue,
            discounts=discounts,
            net_revenue=net_revenue,
            cogs=cogs,
            labor_cost=labor_cost,
            rent_cost=rent_cost,
            marketing_cost=marketing_cost,
        )

        # Get revenue breakdown
        revenue_by_category = await self.calculate_revenue_breakdown(
            venue_ids, date_from, date_to
        )

        # Build cost lines
        cost_lines = self.build_cost_lines(summary)

        # Get daily trend
        daily_trend = await self.get_daily_pnl(venue_ids, date_from, date_to)

        # Comparison with previous period
        comparison = None
        if include_comparison:
            period_days = (date_to - date_from).days + 1
            prev_date_to = date_from - timedelta(days=1)
            prev_date_from = prev_date_to - timedelta(days=period_days - 1)

            prev_gross, prev_discounts, prev_net = await self.get_revenue_and_discounts(
                venue_ids, prev_date_from, prev_date_to
            )
            prev_cogs = await self.calculate_cogs(venue_ids, prev_date_from, prev_date_to)

            if prev_net > 0:
                prev_summary = self.calculate_summary(
                    gross_revenue=prev_gross,
                    discounts=prev_discounts,
                    net_revenue=prev_net,
                    cogs=prev_cogs,
                )

                revenue_change = summary.net_revenue - prev_summary.net_revenue
                revenue_change_pct = (revenue_change / prev_summary.net_revenue * 100) if prev_summary.net_revenue > 0 else Decimal("0")

                gp_change = summary.gross_profit - prev_summary.gross_profit
                gp_change_pct = (gp_change / prev_summary.gross_profit * 100) if prev_summary.gross_profit > 0 else Decimal("0")

                np_change = summary.net_profit - prev_summary.net_profit
                np_change_pct = (np_change / abs(prev_summary.net_profit) * 100) if prev_summary.net_profit != 0 else Decimal("0")

                comparison = PnLComparison(
                    current=summary,
                    previous=prev_summary,
                    revenue_change=revenue_change.quantize(Decimal("0.01")),
                    revenue_change_percent=revenue_change_pct.quantize(Decimal("0.1")),
                    gross_profit_change=gp_change.quantize(Decimal("0.01")),
                    gross_profit_change_percent=gp_change_pct.quantize(Decimal("0.1")),
                    net_profit_change=np_change.quantize(Decimal("0.01")),
                    net_profit_change_percent=np_change_pct.quantize(Decimal("0.1")),
                )

        return PnLReport(
            period_start=date_from,
            period_end=date_to,
            venue_ids=venue_ids,
            summary=summary,
            revenue_by_category=revenue_by_category,
            cost_lines=cost_lines,
            daily_trend=daily_trend,
            comparison=comparison,
            industry_benchmarks=self.BENCHMARKS,
        )

    async def get_margin_trend(
        self,
        venue_ids: List[uuid.UUID],
        months: int = 6,
    ) -> List[Dict]:
        """Get monthly gross margin trend."""

        date_to = date.today()
        date_from = date_to - timedelta(days=months * 31)

        query = (
            select(
                func.date_trunc("month", Receipt.opened_at).label("month"),
                func.sum(Receipt.total).label("revenue"),
                func.sum(
                    func.coalesce(ReceiptItem.cost_price, Decimal("0")) * ReceiptItem.quantity
                ).label("cogs"),
            )
            .select_from(Receipt)
            .join(ReceiptItem, Receipt.id == ReceiptItem.receipt_id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(func.date_trunc("month", Receipt.opened_at))
            .order_by(func.date_trunc("month", Receipt.opened_at))
        )

        result = await self.db.execute(query)
        rows = result.all()

        trend = []
        for row in rows:
            revenue = Decimal(str(row.revenue or 0))
            cogs = Decimal(str(row.cogs or 0))
            margin = ((revenue - cogs) / revenue * 100) if revenue > 0 else Decimal("0")

            trend.append({
                "month": row.month.strftime("%Y-%m"),
                "revenue": float(revenue),
                "cogs": float(cogs),
                "gross_margin_percent": float(margin.quantize(Decimal("0.1"))),
            })

        return trend
