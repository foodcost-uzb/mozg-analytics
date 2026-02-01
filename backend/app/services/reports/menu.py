"""Menu analysis service for MOZG Analytics."""

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Category, Product, Receipt, ReceiptItem


class ABCCategory(str, Enum):
    """ABC analysis categories."""

    A = "A"  # Top 80% (high contribution)
    B = "B"  # Next 15% (medium contribution)
    C = "C"  # Remaining 5% (low contribution)


class XYZCategory(str, Enum):
    """XYZ analysis categories (demand stability)."""

    X = "X"  # CV < 10% - stable demand
    Y = "Y"  # CV 10-25% - variable demand
    Z = "Z"  # CV > 25% - unstable demand


class GoListCategory(str, Enum):
    """Go-List recommendation categories."""

    STARS = "stars"  # A + high margin - promote
    WORKHORSES = "workhorses"  # A + low margin - increase price
    PUZZLES = "puzzles"  # C + high margin - analyze why low sales
    DOGS = "dogs"  # C + low margin - consider removing
    POTENTIAL = "potential"  # B + high margin - increase sales
    STANDARD = "standard"  # B + low margin - standard items


@dataclass
class ProductABC:
    """ABC analysis result for a product."""

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
    abc_category: ABCCategory


@dataclass
class ProductXYZ:
    """XYZ analysis result for a product."""

    product_id: uuid.UUID
    product_name: str
    avg_daily_quantity: Decimal
    std_dev: Decimal
    coefficient_of_variation: Decimal
    xyz_category: XYZCategory


@dataclass
class ProductMargin:
    """Margin analysis for a product."""

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


@dataclass
class GoListItem:
    """Go-List recommendation for a product."""

    product_id: uuid.UUID
    product_name: str
    category_name: Optional[str]
    abc_category: ABCCategory
    margin_percent: Decimal
    go_list_category: GoListCategory
    recommendation: str
    revenue: Decimal
    profit: Decimal


@dataclass
class ABCAnalysisResult:
    """Complete ABC analysis result."""

    products: List[ProductABC]
    summary: Dict[ABCCategory, dict] = field(default_factory=dict)
    total_revenue: Decimal = Decimal("0")
    total_profit: Decimal = Decimal("0")


@dataclass
class GoListResult:
    """Complete Go-List analysis result."""

    items: List[GoListItem]
    summary: Dict[GoListCategory, dict] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


class MenuAnalysisService:
    """Service for menu analysis reports."""

    # ABC thresholds
    ABC_A_THRESHOLD = Decimal("80")  # Top 80%
    ABC_B_THRESHOLD = Decimal("95")  # Next 15%

    # XYZ thresholds (coefficient of variation)
    XYZ_X_THRESHOLD = Decimal("10")  # CV < 10%
    XYZ_Y_THRESHOLD = Decimal("25")  # CV < 25%

    # Margin threshold for Go-List (median is usually used, but we use fixed)
    MARGIN_THRESHOLD = Decimal("30")  # 30% margin threshold

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_product_sales(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[dict]:
        """
        Get aggregated product sales data.

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date

        Returns:
            List of product sales data
        """
        query = (
            select(
                ReceiptItem.product_id,
                Product.name.label("product_name"),
                Category.name.label("category_name"),
                func.sum(ReceiptItem.quantity).label("quantity"),
                func.sum(ReceiptItem.total).label("revenue"),
                func.sum(
                    ReceiptItem.quantity
                    * func.coalesce(ReceiptItem.cost_price, Product.cost_price, 0)
                ).label("cost"),
            )
            .join(Receipt, Receipt.id == ReceiptItem.receipt_id)
            .outerjoin(Product, Product.id == ReceiptItem.product_id)
            .outerjoin(Category, Category.id == Product.category_id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.closed_at >= date_from,
                    Receipt.closed_at < date_to,
                    Receipt.is_deleted == False,
                    ReceiptItem.product_id.isnot(None),
                )
            )
            .group_by(
                ReceiptItem.product_id,
                Product.name,
                Category.name,
            )
            .order_by(func.sum(ReceiptItem.total).desc())
        )

        result = await self.db.execute(query)
        return [dict(row._mapping) for row in result.all()]

    async def abc_analysis(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        metric: str = "revenue",  # revenue, profit, quantity
    ) -> ABCAnalysisResult:
        """
        Perform ABC analysis on products.

        ABC analysis classifies products into 3 categories:
        - A: Top products contributing to 80% of chosen metric
        - B: Products contributing to next 15%
        - C: Products contributing to remaining 5%

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date
            metric: Metric to analyze (revenue, profit, quantity)

        Returns:
            ABCAnalysisResult with classified products
        """
        sales_data = await self.get_product_sales(venue_ids, date_from, date_to)

        if not sales_data:
            return ABCAnalysisResult(products=[], summary={})

        products_abc = []
        total_revenue = Decimal("0")
        total_profit = Decimal("0")

        # Calculate profit and totals
        for item in sales_data:
            revenue = Decimal(str(item["revenue"]))
            cost = Decimal(str(item["cost"])) if item["cost"] else Decimal("0")
            profit = revenue - cost
            item["profit"] = profit

            total_revenue += revenue
            total_profit += profit

        # Sort by chosen metric
        if metric == "profit":
            sales_data.sort(key=lambda x: x["profit"], reverse=True)
            total_metric = total_profit
            metric_key = "profit"
        elif metric == "quantity":
            sales_data.sort(key=lambda x: Decimal(str(x["quantity"])), reverse=True)
            total_metric = sum(Decimal(str(item["quantity"])) for item in sales_data)
            metric_key = "quantity"
        else:  # revenue
            # Already sorted by revenue
            total_metric = total_revenue
            metric_key = "revenue"

        # Calculate cumulative percentages and assign categories
        cumulative = Decimal("0")
        for item in sales_data:
            metric_value = Decimal(str(item[metric_key]))
            metric_percent = (metric_value / total_metric * 100) if total_metric > 0 else Decimal("0")
            cumulative += metric_percent

            # Determine ABC category
            if cumulative <= self.ABC_A_THRESHOLD:
                abc_cat = ABCCategory.A
            elif cumulative <= self.ABC_B_THRESHOLD:
                abc_cat = ABCCategory.B
            else:
                abc_cat = ABCCategory.C

            revenue = Decimal(str(item["revenue"]))
            cost = Decimal(str(item["cost"])) if item["cost"] else Decimal("0")
            profit = item["profit"]
            quantity = Decimal(str(item["quantity"]))
            margin_percent = (profit / revenue * 100) if revenue > 0 else Decimal("0")

            products_abc.append(
                ProductABC(
                    product_id=item["product_id"],
                    product_name=item["product_name"] or "Unknown",
                    category_name=item["category_name"],
                    quantity=quantity,
                    revenue=revenue,
                    cost=cost,
                    profit=profit,
                    margin_percent=round(margin_percent, 2),
                    revenue_percent=round(
                        (revenue / total_revenue * 100) if total_revenue > 0 else Decimal("0"), 2
                    ),
                    cumulative_percent=round(cumulative, 2),
                    abc_category=abc_cat,
                )
            )

        # Calculate summary by category
        summary = {}
        for cat in ABCCategory:
            cat_products = [p for p in products_abc if p.abc_category == cat]
            cat_revenue = sum(p.revenue for p in cat_products)
            cat_profit = sum(p.profit for p in cat_products)
            summary[cat] = {
                "count": len(cat_products),
                "revenue": cat_revenue,
                "profit": cat_profit,
                "revenue_percent": round(
                    (cat_revenue / total_revenue * 100) if total_revenue > 0 else Decimal("0"), 2
                ),
            }

        return ABCAnalysisResult(
            products=products_abc,
            summary=summary,
            total_revenue=total_revenue,
            total_profit=total_profit,
        )

    async def xyz_analysis(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[ProductXYZ]:
        """
        Perform XYZ analysis on products.

        XYZ analysis classifies products by demand stability:
        - X: Stable demand (CV < 10%)
        - Y: Variable demand (CV 10-25%)
        - Z: Unstable demand (CV > 25%)

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date

        Returns:
            List of ProductXYZ with demand stability classification
        """
        # Get daily sales for each product
        query = (
            select(
                ReceiptItem.product_id,
                Product.name.label("product_name"),
                func.date(Receipt.closed_at).label("sale_date"),
                func.sum(ReceiptItem.quantity).label("daily_quantity"),
            )
            .join(Receipt, Receipt.id == ReceiptItem.receipt_id)
            .outerjoin(Product, Product.id == ReceiptItem.product_id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.closed_at >= date_from,
                    Receipt.closed_at < date_to,
                    Receipt.is_deleted == False,
                    ReceiptItem.product_id.isnot(None),
                )
            )
            .group_by(
                ReceiptItem.product_id,
                Product.name,
                func.date(Receipt.closed_at),
            )
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Group by product
        product_daily_sales: Dict[uuid.UUID, List[Tuple[str, float]]] = {}
        product_names: Dict[uuid.UUID, str] = {}

        for row in rows:
            product_id = row.product_id
            if product_id not in product_daily_sales:
                product_daily_sales[product_id] = []
                product_names[product_id] = row.product_name or "Unknown"
            product_daily_sales[product_id].append(float(row.daily_quantity))

        # Calculate XYZ for each product
        products_xyz = []
        for product_id, daily_quantities in product_daily_sales.items():
            quantities_array = np.array(daily_quantities)
            avg_quantity = np.mean(quantities_array)
            std_dev = np.std(quantities_array)
            cv = (std_dev / avg_quantity * 100) if avg_quantity > 0 else 0

            # Determine XYZ category
            if cv < float(self.XYZ_X_THRESHOLD):
                xyz_cat = XYZCategory.X
            elif cv < float(self.XYZ_Y_THRESHOLD):
                xyz_cat = XYZCategory.Y
            else:
                xyz_cat = XYZCategory.Z

            products_xyz.append(
                ProductXYZ(
                    product_id=product_id,
                    product_name=product_names[product_id],
                    avg_daily_quantity=Decimal(str(round(avg_quantity, 2))),
                    std_dev=Decimal(str(round(std_dev, 2))),
                    coefficient_of_variation=Decimal(str(round(cv, 2))),
                    xyz_category=xyz_cat,
                )
            )

        # Sort by CV ascending (most stable first)
        products_xyz.sort(key=lambda x: x.coefficient_of_variation)

        return products_xyz

    async def margin_analysis(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        min_quantity: int = 1,
    ) -> List[ProductMargin]:
        """
        Analyze margin by product.

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date
            min_quantity: Minimum quantity sold to include

        Returns:
            List of ProductMargin sorted by margin descending
        """
        sales_data = await self.get_product_sales(venue_ids, date_from, date_to)

        margins = []
        for item in sales_data:
            quantity = Decimal(str(item["quantity"]))
            if quantity < min_quantity:
                continue

            revenue = Decimal(str(item["revenue"]))
            cost = Decimal(str(item["cost"])) if item["cost"] else Decimal("0")
            profit = revenue - cost
            margin_percent = (profit / revenue * 100) if revenue > 0 else Decimal("0")
            avg_price = revenue / quantity if quantity > 0 else Decimal("0")
            avg_cost = cost / quantity if quantity > 0 else Decimal("0")

            margins.append(
                ProductMargin(
                    product_id=item["product_id"],
                    product_name=item["product_name"] or "Unknown",
                    category_name=item["category_name"],
                    quantity=quantity,
                    revenue=revenue,
                    cost=cost,
                    profit=profit,
                    margin_percent=round(margin_percent, 2),
                    avg_price=round(avg_price, 2),
                    avg_cost=round(avg_cost, 2),
                )
            )

        # Sort by margin descending
        margins.sort(key=lambda x: x.margin_percent, reverse=True)

        return margins

    async def go_list(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        margin_threshold: Optional[Decimal] = None,
    ) -> GoListResult:
        """
        Generate Go-List recommendations.

        Go-List combines ABC and margin analysis:
        | ABC | High Margin | Low Margin |
        |-----|-------------|------------|
        |  A  | STARS       | WORKHORSES |
        |  B  | POTENTIAL   | STANDARD   |
        |  C  | PUZZLES     | DOGS       |

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date
            margin_threshold: Threshold for high/low margin (uses median if not provided)

        Returns:
            GoListResult with recommendations
        """
        # Get ABC analysis
        abc_result = await self.abc_analysis(venue_ids, date_from, date_to)

        if not abc_result.products:
            return GoListResult(items=[], summary={})

        # Calculate margin threshold if not provided
        if margin_threshold is None:
            margins = [p.margin_percent for p in abc_result.products if p.margin_percent > 0]
            if margins:
                margin_threshold = Decimal(str(np.median([float(m) for m in margins])))
            else:
                margin_threshold = self.MARGIN_THRESHOLD

        go_list_items = []
        recommendations = {cat: [] for cat in GoListCategory}

        for product in abc_result.products:
            is_high_margin = product.margin_percent >= margin_threshold

            # Determine Go-List category
            if product.abc_category == ABCCategory.A:
                if is_high_margin:
                    go_cat = GoListCategory.STARS
                    rec = "Promote and feature prominently"
                else:
                    go_cat = GoListCategory.WORKHORSES
                    rec = "Consider increasing price or reducing cost"
            elif product.abc_category == ABCCategory.B:
                if is_high_margin:
                    go_cat = GoListCategory.POTENTIAL
                    rec = "Increase visibility and promotion"
                else:
                    go_cat = GoListCategory.STANDARD
                    rec = "Maintain current position"
            else:  # C
                if is_high_margin:
                    go_cat = GoListCategory.PUZZLES
                    rec = "Investigate why sales are low"
                else:
                    go_cat = GoListCategory.DOGS
                    rec = "Consider removing from menu"

            go_list_items.append(
                GoListItem(
                    product_id=product.product_id,
                    product_name=product.product_name,
                    category_name=product.category_name,
                    abc_category=product.abc_category,
                    margin_percent=product.margin_percent,
                    go_list_category=go_cat,
                    recommendation=rec,
                    revenue=product.revenue,
                    profit=product.profit,
                )
            )

        # Calculate summary
        summary = {}
        for cat in GoListCategory:
            cat_items = [i for i in go_list_items if i.go_list_category == cat]
            summary[cat] = {
                "count": len(cat_items),
                "revenue": sum(i.revenue for i in cat_items),
                "profit": sum(i.profit for i in cat_items),
            }

        # Generate top-level recommendations
        top_recommendations = []

        dogs_count = summary[GoListCategory.DOGS]["count"]
        if dogs_count > 0:
            top_recommendations.append(
                f"Review {dogs_count} 'Dogs' items for potential menu removal"
            )

        puzzles_count = summary[GoListCategory.PUZZLES]["count"]
        if puzzles_count > 0:
            top_recommendations.append(
                f"Investigate {puzzles_count} 'Puzzles' - high margin but low sales"
            )

        workhorses_count = summary[GoListCategory.WORKHORSES]["count"]
        if workhorses_count > 0:
            top_recommendations.append(
                f"Consider price optimization for {workhorses_count} 'Workhorses'"
            )

        stars_count = summary[GoListCategory.STARS]["count"]
        if stars_count > 0:
            top_recommendations.append(f"Feature {stars_count} 'Stars' items prominently")

        return GoListResult(
            items=go_list_items,
            summary=summary,
            recommendations=top_recommendations,
        )

    async def top_sellers(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        limit: int = 10,
        by: str = "revenue",  # revenue, quantity, profit
    ) -> List[ProductMargin]:
        """
        Get top selling products.

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date
            limit: Number of products to return
            by: Sort by revenue, quantity, or profit

        Returns:
            List of top products
        """
        margins = await self.margin_analysis(venue_ids, date_from, date_to)

        if by == "quantity":
            margins.sort(key=lambda x: x.quantity, reverse=True)
        elif by == "profit":
            margins.sort(key=lambda x: x.profit, reverse=True)
        else:  # revenue
            margins.sort(key=lambda x: x.revenue, reverse=True)

        return margins[:limit]

    async def worst_sellers(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        limit: int = 10,
        min_quantity: int = 5,
    ) -> List[ProductMargin]:
        """
        Get worst selling products (by revenue).

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date
            limit: Number of products to return
            min_quantity: Minimum quantity to consider

        Returns:
            List of worst performing products
        """
        margins = await self.margin_analysis(venue_ids, date_from, date_to, min_quantity)

        # Sort by revenue ascending (worst first)
        margins.sort(key=lambda x: x.revenue)

        return margins[:limit]

    async def category_analysis(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[dict]:
        """
        Analyze sales by product category.

        Args:
            venue_ids: List of venue UUIDs
            date_from: Start date
            date_to: End date

        Returns:
            List of category performance data
        """
        query = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                func.sum(ReceiptItem.quantity).label("quantity"),
                func.sum(ReceiptItem.total).label("revenue"),
                func.count(func.distinct(ReceiptItem.product_id)).label("products_count"),
                func.count(func.distinct(ReceiptItem.receipt_id)).label("receipts_count"),
            )
            .join(Product, Product.id == ReceiptItem.product_id)
            .join(Category, Category.id == Product.category_id)
            .join(Receipt, Receipt.id == ReceiptItem.receipt_id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.closed_at >= date_from,
                    Receipt.closed_at < date_to,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(Category.id, Category.name)
            .order_by(func.sum(ReceiptItem.total).desc())
        )

        result = await self.db.execute(query)
        rows = result.all()

        total_revenue = sum(Decimal(str(row.revenue)) for row in rows)

        categories = []
        for row in rows:
            revenue = Decimal(str(row.revenue))
            revenue_percent = (revenue / total_revenue * 100) if total_revenue > 0 else Decimal("0")

            categories.append(
                {
                    "category_id": row.category_id,
                    "category_name": row.category_name,
                    "quantity": Decimal(str(row.quantity)),
                    "revenue": revenue,
                    "revenue_percent": round(revenue_percent, 2),
                    "products_count": row.products_count,
                    "receipts_count": row.receipts_count,
                }
            )

        return categories
