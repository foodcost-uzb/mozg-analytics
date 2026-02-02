"""Basket Analysis service for MOZG Analytics."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Category,
    Product,
    Receipt,
    ReceiptItem,
)


@dataclass
class ProductPair:
    """A pair of products frequently bought together."""

    product_a_id: uuid.UUID
    product_a_name: str
    product_b_id: uuid.UUID
    product_b_name: str

    # Frequency metrics
    co_occurrence_count: int      # Times bought together
    product_a_count: int          # Times product A was bought
    product_b_count: int          # Times product B was bought
    total_receipts: int           # Total receipts in period

    # Association metrics
    support: Decimal              # co_occurrence / total_receipts
    confidence_a_to_b: Decimal    # P(B|A) = co_occurrence / product_a_count
    confidence_b_to_a: Decimal    # P(A|B) = co_occurrence / product_b_count
    lift: Decimal                 # How much more likely together than random


@dataclass
class CrossSellRecommendation:
    """Cross-sell recommendation for a product."""

    trigger_product_id: uuid.UUID
    trigger_product_name: str
    recommended_product_id: uuid.UUID
    recommended_product_name: str

    confidence: Decimal           # Probability of buying recommended if bought trigger
    lift: Decimal                 # Improvement over baseline
    potential_revenue: Decimal    # Estimated additional revenue

    recommendation_text: str


@dataclass
class CategoryAffinity:
    """Affinity between product categories."""

    category_a_id: Optional[uuid.UUID]
    category_a_name: str
    category_b_id: Optional[uuid.UUID]
    category_b_name: str

    affinity_score: Decimal       # How often bought together (0-1)
    avg_basket_value: Decimal     # Average basket value when both present


@dataclass
class BasketProfile:
    """Profile of a typical basket."""

    avg_items: Decimal
    avg_value: Decimal
    avg_categories: Decimal

    # Distribution
    single_item_percent: Decimal
    small_basket_percent: Decimal   # 2-3 items
    medium_basket_percent: Decimal  # 4-6 items
    large_basket_percent: Decimal   # 7+ items


@dataclass
class TimeBasedPattern:
    """Time-based purchasing patterns."""

    hour: int
    avg_basket_size: Decimal
    popular_combinations: List[Tuple[str, str]]
    avg_basket_value: Decimal


@dataclass
class BasketReport:
    """Complete Basket Analysis report."""

    period_start: date
    period_end: date
    venue_ids: List[uuid.UUID]

    # Basket profile
    basket_profile: BasketProfile

    # Top product pairs
    top_product_pairs: List[ProductPair]

    # Cross-sell recommendations
    cross_sell_recommendations: List[CrossSellRecommendation]

    # Category affinity
    category_affinities: List[CategoryAffinity]

    # Time patterns
    time_patterns: List[TimeBasedPattern]

    # Insights
    insights: List[str] = field(default_factory=list)


class BasketAnalysisService:
    """
    Basket Analysis service.

    Analyzes purchasing patterns including:
    - Product combinations (Market Basket Analysis)
    - Association rules (support, confidence, lift)
    - Cross-sell recommendations
    - Category affinity
    - Time-based patterns
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_receipt_items_data(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> Tuple[Dict[uuid.UUID, Set[uuid.UUID]], Dict[uuid.UUID, str], int]:
        """
        Get receipt-to-products mapping for analysis.

        Returns:
            - receipt_products: {receipt_id: set of product_ids}
            - product_names: {product_id: name}
            - total_receipts: count of receipts
        """

        query = (
            select(
                Receipt.id.label("receipt_id"),
                ReceiptItem.product_id,
                ReceiptItem.product_name,
            )
            .select_from(ReceiptItem)
            .join(Receipt, ReceiptItem.receipt_id == Receipt.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                    ReceiptItem.product_id.isnot(None),
                )
            )
        )

        result = await self.db.execute(query)
        rows = result.all()

        receipt_products: Dict[uuid.UUID, Set[uuid.UUID]] = defaultdict(set)
        product_names: Dict[uuid.UUID, str] = {}

        for row in rows:
            if row.product_id:
                receipt_products[row.receipt_id].add(row.product_id)
                product_names[row.product_id] = row.product_name

        total_receipts = len(receipt_products)

        return dict(receipt_products), product_names, total_receipts

    async def calculate_product_pairs(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        min_support: Decimal = Decimal("0.01"),
        min_occurrences: int = 5,
        limit: int = 50,
    ) -> List[ProductPair]:
        """
        Find frequently co-occurring product pairs.

        Uses Apriori-like algorithm for association rule mining.
        """

        receipt_products, product_names, total_receipts = await self.get_receipt_items_data(
            venue_ids, date_from, date_to
        )

        if total_receipts == 0:
            return []

        # Count individual product occurrences
        product_counts: Dict[uuid.UUID, int] = defaultdict(int)
        for products in receipt_products.values():
            for product_id in products:
                product_counts[product_id] += 1

        # Count co-occurrences
        pair_counts: Dict[Tuple[uuid.UUID, uuid.UUID], int] = defaultdict(int)

        for products in receipt_products.values():
            if len(products) < 2:
                continue

            # Generate all pairs within this receipt
            for pair in combinations(sorted(products), 2):
                pair_counts[pair] += 1

        # Filter and calculate metrics
        pairs = []
        min_support_count = int(total_receipts * float(min_support))

        for (prod_a, prod_b), co_count in pair_counts.items():
            if co_count < max(min_occurrences, min_support_count):
                continue

            count_a = product_counts[prod_a]
            count_b = product_counts[prod_b]

            support = Decimal(str(co_count / total_receipts))
            conf_a_to_b = Decimal(str(co_count / count_a)) if count_a > 0 else Decimal("0")
            conf_b_to_a = Decimal(str(co_count / count_b)) if count_b > 0 else Decimal("0")

            # Lift = P(A and B) / (P(A) * P(B))
            expected = (count_a / total_receipts) * (count_b / total_receipts) * total_receipts
            lift = Decimal(str(co_count / expected)) if expected > 0 else Decimal("1")

            pairs.append(ProductPair(
                product_a_id=prod_a,
                product_a_name=product_names.get(prod_a, "Unknown"),
                product_b_id=prod_b,
                product_b_name=product_names.get(prod_b, "Unknown"),
                co_occurrence_count=co_count,
                product_a_count=count_a,
                product_b_count=count_b,
                total_receipts=total_receipts,
                support=support.quantize(Decimal("0.0001")),
                confidence_a_to_b=conf_a_to_b.quantize(Decimal("0.001")),
                confidence_b_to_a=conf_b_to_a.quantize(Decimal("0.001")),
                lift=lift.quantize(Decimal("0.01")),
            ))

        # Sort by lift (most interesting associations first)
        pairs.sort(key=lambda x: x.lift, reverse=True)

        return pairs[:limit]

    async def generate_cross_sell_recommendations(
        self,
        product_pairs: List[ProductPair],
        venue_ids: List[uuid.UUID],
        min_confidence: Decimal = Decimal("0.1"),
        min_lift: Decimal = Decimal("1.2"),
    ) -> List[CrossSellRecommendation]:
        """Generate cross-sell recommendations from product pairs."""

        # Get product prices
        query = select(Product.id, Product.price).where(Product.venue_id.in_(venue_ids))
        result = await self.db.execute(query)
        prices = {row.id: row.price for row in result.all()}

        recommendations = []

        for pair in product_pairs:
            # Check A -> B direction
            if pair.confidence_a_to_b >= min_confidence and pair.lift >= min_lift:
                price_b = prices.get(pair.product_b_id, Decimal("0"))
                potential = price_b * pair.product_a_count * (1 - pair.confidence_a_to_b)

                recommendations.append(CrossSellRecommendation(
                    trigger_product_id=pair.product_a_id,
                    trigger_product_name=pair.product_a_name,
                    recommended_product_id=pair.product_b_id,
                    recommended_product_name=pair.product_b_name,
                    confidence=pair.confidence_a_to_b,
                    lift=pair.lift,
                    potential_revenue=potential.quantize(Decimal("0.01")),
                    recommendation_text=f"Предложите «{pair.product_b_name}» при заказе «{pair.product_a_name}» (вероятность {pair.confidence_a_to_b*100:.0f}%)",
                ))

            # Check B -> A direction
            if pair.confidence_b_to_a >= min_confidence and pair.lift >= min_lift:
                price_a = prices.get(pair.product_a_id, Decimal("0"))
                potential = price_a * pair.product_b_count * (1 - pair.confidence_b_to_a)

                recommendations.append(CrossSellRecommendation(
                    trigger_product_id=pair.product_b_id,
                    trigger_product_name=pair.product_b_name,
                    recommended_product_id=pair.product_a_id,
                    recommended_product_name=pair.product_a_name,
                    confidence=pair.confidence_b_to_a,
                    lift=pair.lift,
                    potential_revenue=potential.quantize(Decimal("0.01")),
                    recommendation_text=f"Предложите «{pair.product_a_name}» при заказе «{pair.product_b_name}» (вероятность {pair.confidence_b_to_a*100:.0f}%)",
                ))

        # Sort by potential revenue
        recommendations.sort(key=lambda x: x.potential_revenue, reverse=True)

        # Deduplicate (keep higher potential)
        seen = set()
        unique_recs = []
        for rec in recommendations:
            key = (rec.trigger_product_id, rec.recommended_product_id)
            if key not in seen:
                seen.add(key)
                unique_recs.append(rec)

        return unique_recs[:20]

    async def calculate_category_affinity(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> List[CategoryAffinity]:
        """Calculate affinity between product categories."""

        # Get receipt items with categories
        query = (
            select(
                Receipt.id.label("receipt_id"),
                Receipt.total.label("receipt_total"),
                Category.id.label("category_id"),
                Category.name.label("category_name"),
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
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Group categories by receipt
        receipt_categories: Dict[uuid.UUID, Set[Tuple[uuid.UUID, str]]] = defaultdict(set)
        receipt_totals: Dict[uuid.UUID, Decimal] = {}
        category_counts: Dict[uuid.UUID, int] = defaultdict(int)

        for row in rows:
            cat_id = row.category_id
            cat_name = row.category_name or "Без категории"

            receipt_categories[row.receipt_id].add((cat_id, cat_name))
            receipt_totals[row.receipt_id] = Decimal(str(row.receipt_total or 0))

            if cat_id:
                category_counts[cat_id] += 1

        total_receipts = len(receipt_categories)
        if total_receipts == 0:
            return []

        # Count category co-occurrences
        pair_data: Dict[Tuple, Dict] = defaultdict(lambda: {"count": 0, "total_value": Decimal("0")})

        for receipt_id, categories in receipt_categories.items():
            if len(categories) < 2:
                continue

            receipt_value = receipt_totals.get(receipt_id, Decimal("0"))

            for cat_pair in combinations(sorted(categories, key=lambda x: str(x[0])), 2):
                key = (cat_pair[0][0], cat_pair[0][1], cat_pair[1][0], cat_pair[1][1])
                pair_data[key]["count"] += 1
                pair_data[key]["total_value"] += receipt_value

        affinities = []
        for (cat_a_id, cat_a_name, cat_b_id, cat_b_name), data in pair_data.items():
            count = data["count"]
            if count < 5:
                continue

            affinity_score = Decimal(str(count / total_receipts))
            avg_value = data["total_value"] / count if count > 0 else Decimal("0")

            affinities.append(CategoryAffinity(
                category_a_id=cat_a_id,
                category_a_name=cat_a_name,
                category_b_id=cat_b_id,
                category_b_name=cat_b_name,
                affinity_score=affinity_score.quantize(Decimal("0.001")),
                avg_basket_value=avg_value.quantize(Decimal("0.01")),
            ))

        # Sort by affinity score
        affinities.sort(key=lambda x: x.affinity_score, reverse=True)

        return affinities[:20]

    async def calculate_basket_profile(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> BasketProfile:
        """Calculate typical basket profile metrics."""

        # Get basket sizes
        query = (
            select(
                Receipt.id,
                Receipt.total,
                func.count(ReceiptItem.id).label("item_count"),
                func.count(func.distinct(Product.category_id)).label("category_count"),
            )
            .select_from(Receipt)
            .join(ReceiptItem, Receipt.id == ReceiptItem.receipt_id)
            .outerjoin(Product, ReceiptItem.product_id == Product.id)
            .where(
                and_(
                    Receipt.venue_id.in_(venue_ids),
                    Receipt.opened_at >= date_from,
                    Receipt.opened_at <= date_to,
                    Receipt.is_deleted == False,
                )
            )
            .group_by(Receipt.id, Receipt.total)
        )

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return BasketProfile(
                avg_items=Decimal("0"),
                avg_value=Decimal("0"),
                avg_categories=Decimal("0"),
                single_item_percent=Decimal("0"),
                small_basket_percent=Decimal("0"),
                medium_basket_percent=Decimal("0"),
                large_basket_percent=Decimal("0"),
            )

        total_baskets = len(rows)
        total_items = sum(r.item_count for r in rows)
        total_value = sum(Decimal(str(r.total or 0)) for r in rows)
        total_categories = sum(r.category_count for r in rows)

        # Count by size
        single = sum(1 for r in rows if r.item_count == 1)
        small = sum(1 for r in rows if 2 <= r.item_count <= 3)
        medium = sum(1 for r in rows if 4 <= r.item_count <= 6)
        large = sum(1 for r in rows if r.item_count >= 7)

        return BasketProfile(
            avg_items=(Decimal(str(total_items)) / total_baskets).quantize(Decimal("0.1")),
            avg_value=(total_value / total_baskets).quantize(Decimal("0.01")),
            avg_categories=(Decimal(str(total_categories)) / total_baskets).quantize(Decimal("0.1")),
            single_item_percent=(Decimal(str(single / total_baskets * 100))).quantize(Decimal("0.1")),
            small_basket_percent=(Decimal(str(small / total_baskets * 100))).quantize(Decimal("0.1")),
            medium_basket_percent=(Decimal(str(medium / total_baskets * 100))).quantize(Decimal("0.1")),
            large_basket_percent=(Decimal(str(large / total_baskets * 100))).quantize(Decimal("0.1")),
        )

    async def analyze_time_patterns(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
        product_pairs: List[ProductPair],
    ) -> List[TimeBasedPattern]:
        """Analyze basket patterns by time of day."""

        query = (
            select(
                func.extract("hour", Receipt.opened_at).label("hour"),
                func.avg(Receipt.total).label("avg_value"),
                func.avg(func.count(ReceiptItem.id).over(partition_by=Receipt.id)).label("avg_size"),
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
            .group_by(func.extract("hour", Receipt.opened_at))
            .order_by(func.extract("hour", Receipt.opened_at))
        )

        result = await self.db.execute(query)
        rows = result.all()

        # Get top pairs for reference
        top_combos = [(p.product_a_name, p.product_b_name) for p in product_pairs[:5]]

        patterns = []
        for row in rows:
            patterns.append(TimeBasedPattern(
                hour=int(row.hour),
                avg_basket_size=Decimal(str(row.avg_size or 0)).quantize(Decimal("0.1")),
                popular_combinations=top_combos,  # Simplified - could be hour-specific
                avg_basket_value=Decimal(str(row.avg_value or 0)).quantize(Decimal("0.01")),
            ))

        return patterns

    def generate_insights(
        self,
        basket_profile: BasketProfile,
        product_pairs: List[ProductPair],
        cross_sell_recs: List[CrossSellRecommendation],
        category_affinities: List[CategoryAffinity],
    ) -> List[str]:
        """Generate actionable insights from basket analysis."""

        insights = []

        # Basket size insights
        if basket_profile.single_item_percent > 40:
            insights.append(
                f"⚠️ {basket_profile.single_item_percent}% чеков содержат только 1 позицию — "
                "большой потенциал для допродаж"
            )

        if basket_profile.avg_items < 2:
            insights.append(
                "📊 Средний чек содержит менее 2 позиций — внедрить комбо-предложения"
            )

        # Product pair insights
        if product_pairs:
            top_pair = product_pairs[0]
            if top_pair.lift > 2:
                insights.append(
                    f"🔥 «{top_pair.product_a_name}» + «{top_pair.product_b_name}» — "
                    f"покупают вместе в {top_pair.lift:.1f}x чаще (создать комбо)"
                )

            high_lift_pairs = [p for p in product_pairs if p.lift > 1.5]
            if len(high_lift_pairs) > 5:
                insights.append(
                    f"💡 Найдено {len(high_lift_pairs)} сильных связей между товарами — "
                    "использовать для выкладки и предложений"
                )

        # Cross-sell insights
        if cross_sell_recs:
            total_potential = sum(r.potential_revenue for r in cross_sell_recs)
            insights.append(
                f"💰 Потенциал допродаж: до {total_potential:,.0f} ₽ при правильных рекомендациях"
            )

            top_rec = cross_sell_recs[0]
            insights.append(
                f"🎯 Лучшая рекомендация: {top_rec.recommendation_text}"
            )

        # Category insights
        if category_affinities:
            top_cat = category_affinities[0]
            insights.append(
                f"📦 Категории «{top_cat.category_a_name}» и «{top_cat.category_b_name}» "
                f"часто покупают вместе — разместить рядом"
            )

        return insights[:6]

    async def generate_report(
        self,
        venue_ids: List[uuid.UUID],
        date_from: date,
        date_to: date,
    ) -> BasketReport:
        """Generate complete basket analysis report."""

        # Calculate basket profile
        basket_profile = await self.calculate_basket_profile(venue_ids, date_from, date_to)

        # Calculate product pairs
        product_pairs = await self.calculate_product_pairs(
            venue_ids, date_from, date_to,
            min_support=Decimal("0.005"),
            min_occurrences=3,
        )

        # Generate cross-sell recommendations
        cross_sell_recs = await self.generate_cross_sell_recommendations(
            product_pairs, venue_ids
        )

        # Calculate category affinity
        category_affinities = await self.calculate_category_affinity(
            venue_ids, date_from, date_to
        )

        # Analyze time patterns
        time_patterns = await self.analyze_time_patterns(
            venue_ids, date_from, date_to, product_pairs
        )

        # Generate insights
        insights = self.generate_insights(
            basket_profile, product_pairs, cross_sell_recs, category_affinities
        )

        return BasketReport(
            period_start=date_from,
            period_end=date_to,
            venue_ids=venue_ids,
            basket_profile=basket_profile,
            top_product_pairs=product_pairs,
            cross_sell_recommendations=cross_sell_recs,
            category_affinities=category_affinities,
            time_patterns=time_patterns,
            insights=insights,
        )
