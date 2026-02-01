"""Unit tests for report services."""

import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Category,
    DailySales,
    Employee,
    HourlySales,
    Organization,
    POSType,
    Product,
    Receipt,
    ReceiptItem,
    User,
    UserRole,
    Venue,
)
from app.services.reports.sales import SalesReportService, CompareWith
from app.services.reports.menu import (
    MenuAnalysisService,
    ABCCategory,
    GoListCategory,
)


# ==================== Fixtures ====================


@pytest_asyncio.fixture
async def test_venue(db: AsyncSession, test_organization: Organization) -> Venue:
    """Create test venue."""
    venue = Venue(
        organization_id=test_organization.id,
        name="Test Restaurant",
        address="123 Test St",
        city="Test City",
        timezone="Europe/Moscow",
        pos_type=POSType.IIKO,
        pos_config={"organization_id": "test-org-id", "api_login": "test-login"},
    )
    db.add(venue)
    await db.flush()
    await db.refresh(venue)
    return venue


@pytest_asyncio.fixture
async def test_category(db: AsyncSession, test_venue: Venue) -> Category:
    """Create test category."""
    category = Category(
        venue_id=test_venue.id,
        external_id="cat-001",
        name="Main Dishes",
    )
    db.add(category)
    await db.flush()
    await db.refresh(category)
    return category


@pytest_asyncio.fixture
async def test_products(db: AsyncSession, test_venue: Venue, test_category: Category) -> list[Product]:
    """Create test products with varying prices and costs."""
    products_data = [
        {"name": "Pizza Margherita", "price": 500, "cost_price": 150},
        {"name": "Caesar Salad", "price": 400, "cost_price": 100},
        {"name": "Pasta Carbonara", "price": 450, "cost_price": 120},
        {"name": "Tiramisu", "price": 300, "cost_price": 80},
        {"name": "Espresso", "price": 100, "cost_price": 20},
    ]

    products = []
    for i, data in enumerate(products_data):
        product = Product(
            venue_id=test_venue.id,
            category_id=test_category.id,
            external_id=f"prod-{i:03d}",
            name=data["name"],
            price=Decimal(str(data["price"])),
            cost_price=Decimal(str(data["cost_price"])),
        )
        db.add(product)
        products.append(product)

    await db.flush()
    for p in products:
        await db.refresh(p)
    return products


@pytest_asyncio.fixture
async def test_employee(db: AsyncSession, test_venue: Venue) -> Employee:
    """Create test employee."""
    employee = Employee(
        venue_id=test_venue.id,
        external_id="emp-001",
        name="John Waiter",
        role="Waiter",
    )
    db.add(employee)
    await db.flush()
    await db.refresh(employee)
    return employee


@pytest_asyncio.fixture
async def test_receipts(
    db: AsyncSession,
    test_venue: Venue,
    test_products: list[Product],
    test_employee: Employee,
) -> list[Receipt]:
    """Create test receipts with items."""
    receipts = []
    today = date.today()

    # Create receipts for the last 7 days
    for day_offset in range(7):
        receipt_date = today - timedelta(days=day_offset)
        receipt_datetime = datetime.combine(receipt_date, datetime.min.time().replace(hour=12))

        # Create 3 receipts per day with different totals
        for receipt_num in range(3):
            receipt = Receipt(
                venue_id=test_venue.id,
                employee_id=test_employee.id,
                external_id=f"rcpt-{day_offset}-{receipt_num}",
                receipt_number=f"R{day_offset:02d}{receipt_num:02d}",
                opened_at=receipt_datetime + timedelta(hours=receipt_num),
                closed_at=receipt_datetime + timedelta(hours=receipt_num, minutes=30),
                guests_count=2 + receipt_num,
                is_paid=True,
            )
            db.add(receipt)
            await db.flush()

            # Add items to receipt
            total = Decimal("0")
            for i, product in enumerate(test_products[:3]):  # Add first 3 products
                quantity = Decimal(str(1 + (receipt_num % 2)))
                item_total = product.price * quantity

                item = ReceiptItem(
                    receipt_id=receipt.id,
                    product_id=product.id,
                    external_product_id=product.external_id,
                    product_name=product.name,
                    quantity=quantity,
                    unit_price=product.price,
                    cost_price=product.cost_price,
                    total=item_total,
                )
                db.add(item)
                total += item_total

            receipt.subtotal = total
            receipt.total = total
            receipts.append(receipt)

    await db.flush()
    for r in receipts:
        await db.refresh(r)
    return receipts


@pytest_asyncio.fixture
async def test_daily_sales(db: AsyncSession, test_venue: Venue) -> list[DailySales]:
    """Create test daily sales aggregates."""
    daily_sales = []
    today = date.today()

    for day_offset in range(14):
        ds_date = today - timedelta(days=day_offset)
        ds = DailySales(
            venue_id=test_venue.id,
            date=ds_date,
            total_revenue=Decimal("10000") + Decimal(str(day_offset * 500)),
            total_receipts=50 + day_offset * 2,
            total_items=150 + day_offset * 5,
            total_guests=80 + day_offset * 3,
            avg_receipt=Decimal("200") + Decimal(str(day_offset * 5)),
            avg_guest_check=Decimal("125") + Decimal(str(day_offset * 3)),
            total_discount=Decimal("500") + Decimal(str(day_offset * 20)),
        )
        db.add(ds)
        daily_sales.append(ds)

    await db.flush()
    return daily_sales


@pytest_asyncio.fixture
async def test_hourly_sales(db: AsyncSession, test_venue: Venue) -> list[HourlySales]:
    """Create test hourly sales aggregates."""
    hourly_sales = []
    today = date.today()

    for day_offset in range(7):
        hs_date = today - timedelta(days=day_offset)
        for hour in range(10, 22):  # 10:00 to 21:00
            # Peak hours have more revenue
            is_peak = hour in [12, 13, 19, 20]
            base_revenue = Decimal("500") if is_peak else Decimal("200")

            hs = HourlySales(
                venue_id=test_venue.id,
                date=hs_date,
                hour=hour,
                total_revenue=base_revenue + Decimal(str(day_offset * 10)),
                total_receipts=5 if is_peak else 2,
                total_items=15 if is_peak else 6,
                total_guests=8 if is_peak else 3,
            )
            db.add(hs)
            hourly_sales.append(hs)

    await db.flush()
    return hourly_sales


# ==================== Sales Report Tests ====================


class TestSalesReportService:
    """Tests for SalesReportService."""

    @pytest.mark.asyncio
    async def test_get_summary(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_daily_sales: list[DailySales],
    ):
        """Test get_summary returns correct aggregates."""
        service = SalesReportService(db)
        today = date.today()
        date_from = today - timedelta(days=6)
        date_to = today

        summary = await service.get_summary([test_venue.id], date_from, date_to)

        assert summary.revenue > 0
        assert summary.receipts_count > 0
        assert summary.avg_check > 0
        assert summary.guests_count > 0

    @pytest.mark.asyncio
    async def test_get_summary_empty_period(
        self,
        db: AsyncSession,
        test_venue: Venue,
    ):
        """Test get_summary with no data returns zeros."""
        service = SalesReportService(db)
        # Query far in the future - no data
        date_from = date(2099, 1, 1)
        date_to = date(2099, 1, 31)

        summary = await service.get_summary([test_venue.id], date_from, date_to)

        assert summary.revenue == Decimal("0")
        assert summary.receipts_count == 0
        assert summary.avg_check == Decimal("0")

    @pytest.mark.asyncio
    async def test_get_daily(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_daily_sales: list[DailySales],
    ):
        """Test get_daily returns daily data points."""
        service = SalesReportService(db)
        today = date.today()
        date_from = today - timedelta(days=6)
        date_to = today

        daily_data = await service.get_daily([test_venue.id], date_from, date_to)

        assert len(daily_data) == 7
        # Check data is sorted by date
        dates = [dp.date for dp in daily_data]
        assert dates == sorted(dates)

    @pytest.mark.asyncio
    async def test_get_comparison_previous(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_daily_sales: list[DailySales],
    ):
        """Test get_comparison with previous period."""
        service = SalesReportService(db)
        today = date.today()
        date_from = today - timedelta(days=6)
        date_to = today

        comparison = await service.get_comparison(
            [test_venue.id], date_from, date_to, CompareWith.PREVIOUS
        )

        assert comparison.current is not None
        assert comparison.previous is not None
        # Revenue diff should be calculated
        assert comparison.revenue_diff == comparison.current.revenue - comparison.previous.revenue

    @pytest.mark.asyncio
    async def test_get_by_venue(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_daily_sales: list[DailySales],
    ):
        """Test get_by_venue returns venue breakdown."""
        service = SalesReportService(db)
        today = date.today()
        date_from = today - timedelta(days=6)
        date_to = today

        venue_sales = await service.get_by_venue([test_venue.id], date_from, date_to)

        assert len(venue_sales) == 1
        assert venue_sales[0].venue_id == test_venue.id
        assert venue_sales[0].venue_name == test_venue.name
        assert venue_sales[0].revenue_percent == Decimal("100.00")

    @pytest.mark.asyncio
    async def test_get_hourly(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_hourly_sales: list[HourlySales],
    ):
        """Test get_hourly returns 24 hour slots."""
        service = SalesReportService(db)
        today = date.today()
        date_from = today - timedelta(days=6)
        date_to = today

        hourly_data = await service.get_hourly([test_venue.id], date_from, date_to)

        assert len(hourly_data) == 24
        # Check hours are 0-23
        hours = [h.hour for h in hourly_data]
        assert hours == list(range(24))

    @pytest.mark.asyncio
    async def test_get_top_days(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_daily_sales: list[DailySales],
    ):
        """Test get_top_days returns sorted by revenue."""
        service = SalesReportService(db)
        today = date.today()
        date_from = today - timedelta(days=13)
        date_to = today

        top_days = await service.get_top_days([test_venue.id], date_from, date_to, limit=5)

        assert len(top_days) == 5
        # Check sorted by revenue descending
        revenues = [dp.revenue for dp in top_days]
        assert revenues == sorted(revenues, reverse=True)


# ==================== Menu Analysis Tests ====================


class TestMenuAnalysisService:
    """Tests for MenuAnalysisService."""

    @pytest.mark.asyncio
    async def test_abc_analysis_by_revenue(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test ABC analysis classifies products correctly."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        result = await service.abc_analysis(
            [test_venue.id], date_from, date_to, metric="revenue"
        )

        assert len(result.products) > 0
        assert result.total_revenue > 0

        # Check ABC categories are assigned
        categories = set(p.abc_category for p in result.products)
        assert ABCCategory.A in categories or ABCCategory.B in categories or ABCCategory.C in categories

        # Check cumulative percentages
        cumulative = result.products[-1].cumulative_percent if result.products else Decimal("0")
        assert cumulative <= Decimal("100.01")  # Allow small rounding

    @pytest.mark.asyncio
    async def test_abc_analysis_summary(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test ABC analysis summary totals."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        result = await service.abc_analysis(
            [test_venue.id], date_from, date_to, metric="revenue"
        )

        # Summary should have all categories
        assert len(result.summary) == 3

        # Sum of category revenues should equal total
        summary_revenue = sum(data["revenue"] for data in result.summary.values())
        assert abs(summary_revenue - result.total_revenue) < Decimal("0.01")

    @pytest.mark.asyncio
    async def test_margin_analysis(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test margin analysis calculates margins correctly."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        margins = await service.margin_analysis([test_venue.id], date_from, date_to)

        assert len(margins) > 0

        for m in margins:
            assert m.quantity > 0
            assert m.revenue > 0
            # Margin = (revenue - cost) / revenue * 100
            expected_margin = (m.profit / m.revenue * 100) if m.revenue > 0 else Decimal("0")
            assert abs(m.margin_percent - expected_margin) < Decimal("0.1")

    @pytest.mark.asyncio
    async def test_margin_sorted_descending(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test margin analysis returns sorted by margin descending."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        margins = await service.margin_analysis([test_venue.id], date_from, date_to)

        # Check sorted by margin descending
        margin_percents = [m.margin_percent for m in margins]
        assert margin_percents == sorted(margin_percents, reverse=True)

    @pytest.mark.asyncio
    async def test_go_list(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test Go-List generates recommendations."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        result = await service.go_list([test_venue.id], date_from, date_to)

        assert len(result.items) > 0

        # Check all items have Go-List category and recommendation
        for item in result.items:
            assert item.go_list_category is not None
            assert item.recommendation != ""
            assert item.abc_category is not None

    @pytest.mark.asyncio
    async def test_go_list_categories(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test Go-List assigns correct categories based on ABC and margin."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        result = await service.go_list(
            [test_venue.id], date_from, date_to, margin_threshold=Decimal("30")
        )

        # Check category assignment logic
        for item in result.items:
            if item.abc_category == ABCCategory.A and item.margin_percent >= Decimal("30"):
                assert item.go_list_category == GoListCategory.STARS
            elif item.abc_category == ABCCategory.A and item.margin_percent < Decimal("30"):
                assert item.go_list_category == GoListCategory.WORKHORSES
            elif item.abc_category == ABCCategory.C and item.margin_percent >= Decimal("30"):
                assert item.go_list_category == GoListCategory.PUZZLES
            elif item.abc_category == ABCCategory.C and item.margin_percent < Decimal("30"):
                assert item.go_list_category == GoListCategory.DOGS

    @pytest.mark.asyncio
    async def test_top_sellers_by_revenue(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test top sellers returns products sorted by revenue."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        top = await service.top_sellers(
            [test_venue.id], date_from, date_to, limit=3, by="revenue"
        )

        assert len(top) <= 3
        revenues = [p.revenue for p in top]
        assert revenues == sorted(revenues, reverse=True)

    @pytest.mark.asyncio
    async def test_top_sellers_by_quantity(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test top sellers by quantity."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        top = await service.top_sellers(
            [test_venue.id], date_from, date_to, limit=3, by="quantity"
        )

        assert len(top) <= 3
        quantities = [p.quantity for p in top]
        assert quantities == sorted(quantities, reverse=True)

    @pytest.mark.asyncio
    async def test_worst_sellers(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test worst sellers returns products with lowest revenue."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        worst = await service.worst_sellers(
            [test_venue.id], date_from, date_to, limit=3, min_quantity=1
        )

        # Should be sorted by revenue ascending (worst first)
        revenues = [p.revenue for p in worst]
        assert revenues == sorted(revenues)

    @pytest.mark.asyncio
    async def test_category_analysis(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_receipts: list[Receipt],
    ):
        """Test category analysis groups by category."""
        service = MenuAnalysisService(db)
        today = date.today()
        date_from = today - timedelta(days=7)
        date_to = today + timedelta(days=1)

        categories = await service.category_analysis([test_venue.id], date_from, date_to)

        assert len(categories) >= 1

        for cat in categories:
            assert cat["category_name"] is not None
            assert cat["revenue"] > 0
            assert cat["products_count"] >= 1


# ==================== Edge Cases ====================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_venue_list(self, db: AsyncSession):
        """Test services handle empty venue list."""
        service = SalesReportService(db)
        today = date.today()

        # Empty list should return zero results
        summary = await service.get_summary([], today, today)
        assert summary.revenue == Decimal("0")

    @pytest.mark.asyncio
    async def test_future_dates(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_daily_sales: list[DailySales],
    ):
        """Test services handle future dates gracefully."""
        service = SalesReportService(db)
        future_date = date.today() + timedelta(days=365)

        summary = await service.get_summary(
            [test_venue.id], future_date, future_date
        )
        assert summary.revenue == Decimal("0")

    @pytest.mark.asyncio
    async def test_single_day_period(
        self,
        db: AsyncSession,
        test_venue: Venue,
        test_daily_sales: list[DailySales],
    ):
        """Test services work with single day period."""
        service = SalesReportService(db)
        today = date.today()

        summary = await service.get_summary([test_venue.id], today, today)
        assert summary is not None

    @pytest.mark.asyncio
    async def test_nonexistent_venue(self, db: AsyncSession):
        """Test services handle nonexistent venue ID."""
        service = SalesReportService(db)
        fake_venue_id = uuid.uuid4()
        today = date.today()

        summary = await service.get_summary([fake_venue_id], today, today)
        assert summary.revenue == Decimal("0")
