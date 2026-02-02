"""Tests for Phase 4 Advanced Analytics services."""

from datetime import date, timedelta
from decimal import Decimal
import uuid

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.analytics.motive import (
    MotiveMarketingService,
    MotiveFactor,
    ImpactLevel,
    WeekdayAnalysis,
    SeasonalityAnalysis,
    FactorImpact,
)
from app.services.analytics.pnl import (
    PnLReportService,
    CostCategory,
    PnLSummary,
    RevenueBreakdown,
)
from app.services.analytics.hr import (
    HRAnalyticsService,
    PerformanceLevel,
    Shift,
    EmployeeMetrics,
    TeamMetrics,
)
from app.services.analytics.basket import (
    BasketAnalysisService,
    ProductPair,
    CrossSellRecommendation,
    BasketProfile,
)


class TestMotiveMarketingService:
    """Tests for Motive Marketing analysis."""

    def test_weekday_names(self):
        """Test weekday name constants."""
        service = MotiveMarketingService(MagicMock())

        assert service.WEEKDAY_NAMES[0] == "Понедельник"
        assert service.WEEKDAY_NAMES[6] == "Воскресенье"
        assert len(service.WEEKDAY_NAMES) == 7

    def test_month_names(self):
        """Test month name constants."""
        service = MotiveMarketingService(MagicMock())

        assert service.MONTH_NAMES[1] == "Январь"
        assert service.MONTH_NAMES[12] == "Декабрь"
        assert len(service.MONTH_NAMES) == 12

    def test_holidays(self):
        """Test holiday definitions."""
        service = MotiveMarketingService(MagicMock())

        assert (1, 1) in service.HOLIDAYS
        assert service.HOLIDAYS[(1, 1)] == "Новый год"
        assert (3, 8) in service.HOLIDAYS
        assert service.HOLIDAYS[(3, 8)] == "Международный женский день"

    def test_calculate_factor_impact_weekday(self):
        """Test weekday factor impact calculation."""
        service = MotiveMarketingService(MagicMock())

        weekday_analysis = [
            WeekdayAnalysis(
                day=0, day_name="Понедельник", avg_revenue=Decimal("10000"),
                avg_receipts=100, avg_check=Decimal("100"), index=Decimal("80"),
                best_hours=[12, 13, 14]
            ),
            WeekdayAnalysis(
                day=5, day_name="Суббота", avg_revenue=Decimal("15000"),
                avg_receipts=150, avg_check=Decimal("100"), index=Decimal("120"),
                best_hours=[19, 20, 21]
            ),
        ]

        factors = service._calculate_factor_impact(weekday_analysis, [], [], [])

        assert len(factors) == 1
        assert factors[0].factor == MotiveFactor.WEEKDAY
        assert "Понедельник" in factors[0].description or "Суббота" in factors[0].description

    def test_generate_recommendations(self):
        """Test recommendation generation."""
        service = MotiveMarketingService(MagicMock())

        weekday_analysis = [
            WeekdayAnalysis(
                day=0, day_name="Понедельник", avg_revenue=Decimal("8000"),
                avg_receipts=80, avg_check=Decimal("100"), index=Decimal("70"),
                best_hours=[12, 13, 14]
            ),
            WeekdayAnalysis(
                day=5, day_name="Суббота", avg_revenue=Decimal("15000"),
                avg_receipts=150, avg_check=Decimal("100"), index=Decimal("130"),
                best_hours=[19, 20, 21]
            ),
        ]

        recommendations = service._generate_recommendations(
            weekday_analysis, [], [], []
        )

        assert len(recommendations) > 0
        # Should recommend action for weak day
        has_monday_recommendation = any(
            "Понедельник" in r for r in recommendations
        )
        assert has_monday_recommendation


class TestPnLReportService:
    """Tests for P&L Report analysis."""

    def test_benchmarks(self):
        """Test industry benchmark constants."""
        service = PnLReportService(MagicMock())

        assert service.BENCHMARKS["cogs_percent"] == Decimal("30")
        assert service.BENCHMARKS["gross_margin_percent"] == Decimal("70")
        assert service.BENCHMARKS["net_margin_percent"] == Decimal("10")

    def test_calculate_summary(self):
        """Test P&L summary calculation."""
        service = PnLReportService(MagicMock())

        summary = service.calculate_summary(
            gross_revenue=Decimal("110000"),
            discounts=Decimal("10000"),
            net_revenue=Decimal("100000"),
            cogs=Decimal("30000"),
            labor_cost=Decimal("25000"),
            rent_cost=Decimal("10000"),
            marketing_cost=Decimal("3000"),
            other_operating=Decimal("7000"),
            depreciation=Decimal("2000"),
            taxes=Decimal("0"),
        )

        # Verify calculations
        assert summary.gross_revenue == Decimal("110000.00")
        assert summary.net_revenue == Decimal("100000.00")
        assert summary.cogs == Decimal("30000.00")
        assert summary.cogs_percent == Decimal("30.0")

        # Gross profit = 100000 - 30000 = 70000
        assert summary.gross_profit == Decimal("70000.00")
        assert summary.gross_margin_percent == Decimal("70.0")

        # Total operating = 25000 + 10000 + 3000 + 7000 = 45000
        assert summary.total_operating == Decimal("45000.00")

        # EBITDA = 70000 - 45000 = 25000
        assert summary.ebitda == Decimal("25000.00")

        # Net profit = 25000 - 2000 - 0 = 23000
        assert summary.net_profit == Decimal("23000.00")

    def test_calculate_summary_with_defaults(self):
        """Test P&L summary with default operating costs."""
        service = PnLReportService(MagicMock())

        summary = service.calculate_summary(
            gross_revenue=Decimal("100000"),
            discounts=Decimal("0"),
            net_revenue=Decimal("100000"),
            cogs=Decimal("30000"),
            # No operating costs provided - should use defaults
        )

        # Should use 25% for labor, 10% for rent, etc.
        assert summary.labor_cost == Decimal("25000.00")  # 25% of 100000
        assert summary.rent_cost == Decimal("10000.00")   # 10% of 100000

    def test_build_cost_lines(self):
        """Test cost lines generation."""
        service = PnLReportService(MagicMock())

        summary = service.calculate_summary(
            gross_revenue=Decimal("100000"),
            discounts=Decimal("0"),
            net_revenue=Decimal("100000"),
            cogs=Decimal("30000"),
        )

        cost_lines = service.build_cost_lines(summary)

        assert len(cost_lines) >= 6

        categories = [c.category for c in cost_lines]
        assert CostCategory.COGS in categories
        assert CostCategory.LABOR in categories
        assert CostCategory.RENT in categories
        assert CostCategory.MARKETING in categories


class TestHRAnalyticsService:
    """Tests for HR Analytics."""

    def test_shift_hours(self):
        """Test shift hour definitions."""
        service = HRAnalyticsService(MagicMock())

        morning = service.SHIFT_HOURS[Shift.MORNING]
        assert morning[0] == 6   # start
        assert morning[1] == 14  # end

        afternoon = service.SHIFT_HOURS[Shift.AFTERNOON]
        assert afternoon[0] == 14
        assert afternoon[1] == 22

        evening = service.SHIFT_HOURS[Shift.EVENING]
        assert evening[0] == 22
        assert evening[1] == 6  # crosses midnight

    def test_calculate_team_metrics_empty(self):
        """Test team metrics with no employees."""
        service = HRAnalyticsService(MagicMock())

        metrics = service.calculate_team_metrics([])

        assert metrics.total_employees == 0
        assert metrics.avg_revenue_per_employee == Decimal("0")

    def test_calculate_team_metrics(self):
        """Test team metrics calculation."""
        service = HRAnalyticsService(MagicMock())

        employee_metrics = [
            EmployeeMetrics(
                employee_id=uuid.uuid4(),
                employee_name="Alice",
                role="waiter",
                total_revenue=Decimal("50000"),
                total_receipts=100,
                total_items=300,
                avg_check=Decimal("500"),
                items_per_receipt=Decimal("3"),
                revenue_per_hour=Decimal("300"),
                avg_discount_percent=Decimal("5"),
                return_rate=Decimal("0"),
                performance_level=PerformanceLevel.TOP,
                rank=1,
                percentile=Decimal("90"),
            ),
            EmployeeMetrics(
                employee_id=uuid.uuid4(),
                employee_name="Bob",
                role="waiter",
                total_revenue=Decimal("30000"),
                total_receipts=80,
                total_items=200,
                avg_check=Decimal("375"),
                items_per_receipt=Decimal("2.5"),
                revenue_per_hour=Decimal("200"),
                avg_discount_percent=Decimal("8"),
                return_rate=Decimal("0"),
                performance_level=PerformanceLevel.AVERAGE,
                rank=2,
                percentile=Decimal("50"),
            ),
        ]

        team_metrics = service.calculate_team_metrics(employee_metrics)

        assert team_metrics.total_employees == 2
        assert team_metrics.active_employees == 2
        assert team_metrics.avg_revenue_per_employee == Decimal("40000.00")  # (50000+30000)/2
        assert team_metrics.top_performers_count == 1
        assert team_metrics.avg_performers_count == 1

    def test_generate_recommendations(self):
        """Test HR recommendations generation."""
        service = HRAnalyticsService(MagicMock())

        team_metrics = TeamMetrics(
            total_employees=10,
            active_employees=10,
            avg_revenue_per_employee=Decimal("40000"),
            avg_receipts_per_employee=Decimal("100"),
            avg_check=Decimal("400"),
            avg_items_per_receipt=Decimal("3"),
            top_performers_count=1,  # Only 10%, should trigger recommendation
            avg_performers_count=5,
            low_performers_count=4,  # 40%, should trigger recommendation
            revenue_per_labor_hour=Decimal("250"),
            receipts_per_labor_hour=Decimal("0.6"),
        )

        recommendations = service.generate_recommendations(team_metrics, [], [])

        assert len(recommendations) > 0
        # Should recommend training due to high low performers
        has_training_rec = any("обучен" in r.lower() for r in recommendations)
        assert has_training_rec


class TestBasketAnalysisService:
    """Tests for Basket Analysis."""

    def test_basket_profile_empty(self):
        """Test basket profile with no data."""
        service = BasketAnalysisService(MagicMock())

        # Empty case - should return zeros
        profile = BasketProfile(
            avg_items=Decimal("0"),
            avg_value=Decimal("0"),
            avg_categories=Decimal("0"),
            single_item_percent=Decimal("0"),
            small_basket_percent=Decimal("0"),
            medium_basket_percent=Decimal("0"),
            large_basket_percent=Decimal("0"),
        )

        assert profile.avg_items == Decimal("0")
        assert profile.single_item_percent == Decimal("0")

    def test_product_pair_metrics(self):
        """Test product pair metric calculations."""
        pair = ProductPair(
            product_a_id=uuid.uuid4(),
            product_a_name="Coffee",
            product_b_id=uuid.uuid4(),
            product_b_name="Croissant",
            co_occurrence_count=50,
            product_a_count=100,
            product_b_count=80,
            total_receipts=1000,
            support=Decimal("0.05"),        # 50/1000
            confidence_a_to_b=Decimal("0.5"),  # 50/100
            confidence_b_to_a=Decimal("0.625"),  # 50/80
            lift=Decimal("6.25"),            # 0.05 / (0.1 * 0.08)
        )

        # Verify metrics
        assert pair.support == Decimal("0.05")  # 5% of receipts have both
        assert pair.confidence_a_to_b == Decimal("0.5")  # 50% who buy A also buy B
        assert pair.lift > 1  # They are bought together more than random

    def test_generate_insights(self):
        """Test insight generation."""
        service = BasketAnalysisService(MagicMock())

        basket_profile = BasketProfile(
            avg_items=Decimal("1.5"),
            avg_value=Decimal("500"),
            avg_categories=Decimal("1.2"),
            single_item_percent=Decimal("50"),  # High - should trigger insight
            small_basket_percent=Decimal("30"),
            medium_basket_percent=Decimal("15"),
            large_basket_percent=Decimal("5"),
        )

        product_pairs = [
            ProductPair(
                product_a_id=uuid.uuid4(),
                product_a_name="Coffee",
                product_b_id=uuid.uuid4(),
                product_b_name="Croissant",
                co_occurrence_count=100,
                product_a_count=200,
                product_b_count=150,
                total_receipts=1000,
                support=Decimal("0.1"),
                confidence_a_to_b=Decimal("0.5"),
                confidence_b_to_a=Decimal("0.67"),
                lift=Decimal("3.33"),  # High lift
            )
        ]

        insights = service.generate_insights(
            basket_profile, product_pairs, [], []
        )

        assert len(insights) > 0
        # Should mention single-item receipts
        has_single_item_insight = any("1 позици" in i for i in insights)
        assert has_single_item_insight


class TestAnalyticsIntegration:
    """Integration tests for analytics services."""

    def test_impact_level_enum(self):
        """Test impact level enum values."""
        assert ImpactLevel.VERY_POSITIVE.value == "very_positive"
        assert ImpactLevel.NEUTRAL.value == "neutral"
        assert ImpactLevel.VERY_NEGATIVE.value == "very_negative"

    def test_performance_level_enum(self):
        """Test performance level enum values."""
        assert PerformanceLevel.TOP.value == "top"
        assert PerformanceLevel.AVERAGE.value == "average"
        assert PerformanceLevel.LOW.value == "low"

    def test_cost_category_enum(self):
        """Test cost category enum values."""
        assert CostCategory.COGS.value == "cogs"
        assert CostCategory.LABOR.value == "labor"
        assert CostCategory.RENT.value == "rent"

    def test_shift_enum(self):
        """Test shift enum values."""
        assert Shift.MORNING.value == "morning"
        assert Shift.AFTERNOON.value == "afternoon"
        assert Shift.EVENING.value == "evening"

    def test_motive_factor_enum(self):
        """Test motive factor enum values."""
        assert MotiveFactor.WEEKDAY.value == "weekday"
        assert MotiveFactor.SEASONALITY.value == "seasonality"
        assert MotiveFactor.PRICING.value == "pricing"
