"""Tests for Phase 5 Forecasting services."""

from datetime import date, timedelta
from decimal import Decimal
import uuid

import numpy as np
import pandas as pd
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.forecasting.revenue import (
    RevenueForecastService,
    ForecastPoint,
    ForecastAccuracy,
    SeasonalComponent,
    TrendComponent,
    RevenueForecast,
)
from app.services.forecasting.demand import (
    DemandForecastService,
    ProductDemandForecast,
    CategoryDemandForecast,
    DemandForecastReport,
)
from app.services.forecasting.anomaly import (
    AnomalyDetectionService,
    AnomalyType,
    AnomalySeverity,
    Anomaly,
    AnomalyStats,
    AnomalyReport,
)


class TestRevenueForecastService:
    """Tests for Revenue Forecast service."""

    def test_holidays_dataframe(self):
        """Test holiday dataframe preparation."""
        service = RevenueForecastService(MagicMock())

        holidays = service._prepare_holidays([2025, 2026])

        assert len(holidays) > 0
        assert 'holiday' in holidays.columns
        assert 'ds' in holidays.columns

        # Check for New Year
        new_year = holidays[holidays['holiday'] == 'new_year']
        assert len(new_year) >= 2  # At least one per year

    def test_calculate_accuracy(self):
        """Test accuracy metrics calculation."""
        service = RevenueForecastService(MagicMock())

        actual = pd.Series([100, 110, 120, 130, 140])
        predicted = pd.Series([105, 108, 125, 128, 145])

        accuracy = service._calculate_accuracy(actual, predicted)

        assert accuracy.mape >= 0
        assert accuracy.rmse >= 0
        assert accuracy.mae >= 0
        assert accuracy.r_squared >= 0
        assert accuracy.r_squared <= 1

    def test_calculate_accuracy_perfect(self):
        """Test accuracy with perfect predictions."""
        service = RevenueForecastService(MagicMock())

        actual = pd.Series([100, 110, 120])
        predicted = pd.Series([100, 110, 120])

        accuracy = service._calculate_accuracy(actual, predicted)

        assert accuracy.mape == Decimal("0")
        assert accuracy.rmse == Decimal("0")
        assert accuracy.mae == Decimal("0")
        assert accuracy.r_squared == Decimal("1.000")

    def test_generate_insights(self):
        """Test insight generation."""
        service = RevenueForecastService(MagicMock())

        forecast = RevenueForecast(
            venue_ids=[uuid.uuid4()],
            forecast_start=date.today(),
            forecast_end=date.today() + timedelta(days=30),
            horizon_days=30,
            historical=[],
            forecast=[],
            accuracy=ForecastAccuracy(
                mape=Decimal("8.5"),
                rmse=Decimal("1000"),
                mae=Decimal("800"),
                r_squared=Decimal("0.92"),
            ),
            seasonality=[
                SeasonalComponent(
                    name="weekly",
                    strength=Decimal("0.3"),
                    pattern={
                        "Monday": Decimal("0.85"),
                        "Saturday": Decimal("1.25"),
                    },
                ),
            ],
            trend=TrendComponent(
                direction="up",
                slope=Decimal("150"),
                change_points=[],
            ),
            total_forecast=Decimal("300000"),
            avg_daily_forecast=Decimal("10000"),
            growth_percent=Decimal("15.5"),
        )

        data = pd.DataFrame({'y': [10000] * 30})

        insights = service._generate_insights(forecast, data)

        assert len(insights) > 0
        # Should mention growth
        has_growth = any("рост" in i.lower() for i in insights)
        assert has_growth


class TestDemandForecastService:
    """Tests for Demand Forecast service."""

    def test_calculate_trend_up(self):
        """Test trend calculation for increasing data."""
        service = DemandForecastService(MagicMock())

        # Increasing values
        data = pd.DataFrame({
            'y': [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36]
        })

        trend, percent = service._calculate_trend(data)

        assert trend == "up"
        assert percent > 0

    def test_calculate_trend_down(self):
        """Test trend calculation for decreasing data."""
        service = DemandForecastService(MagicMock())

        # Decreasing values
        data = pd.DataFrame({
            'y': [36, 34, 32, 30, 28, 26, 24, 22, 20, 18, 16, 14, 12, 10]
        })

        trend, percent = service._calculate_trend(data)

        assert trend == "down"
        assert percent < 0

    def test_calculate_trend_stable(self):
        """Test trend calculation for stable data."""
        service = DemandForecastService(MagicMock())

        # Stable values with minor fluctuation
        data = pd.DataFrame({
            'y': [20, 21, 19, 20, 21, 19, 20, 21, 19, 20, 21, 19, 20, 21]
        })

        trend, percent = service._calculate_trend(data)

        assert trend == "stable"
        assert abs(percent) < 10

    def test_calculate_trend_insufficient_data(self):
        """Test trend with insufficient data."""
        service = DemandForecastService(MagicMock())

        data = pd.DataFrame({'y': [10, 20]})  # Only 2 points

        trend, percent = service._calculate_trend(data)

        assert trend == "stable"
        assert percent == Decimal("0")

    def test_generate_insights(self):
        """Test insight generation for demand."""
        service = DemandForecastService(MagicMock())

        product_forecasts = [
            ProductDemandForecast(
                product_id=uuid.uuid4(),
                product_name="Product A",
                category_name="Category 1",
                forecast=[],
                total_forecast=Decimal("100"),
                avg_daily_forecast=Decimal("7"),
                historical_avg=Decimal("5"),
                historical_total=Decimal("70"),
                trend="up",
                trend_percent=Decimal("40"),
                confidence_score=Decimal("85"),
            ),
            ProductDemandForecast(
                product_id=uuid.uuid4(),
                product_name="Product B",
                category_name="Category 1",
                forecast=[],
                total_forecast=Decimal("50"),
                avg_daily_forecast=Decimal("3.5"),
                historical_avg=Decimal("5"),
                historical_total=Decimal("70"),
                trend="down",
                trend_percent=Decimal("-30"),
                confidence_score=Decimal("75"),
            ),
        ]

        category_forecasts = [
            CategoryDemandForecast(
                category_id=uuid.uuid4(),
                category_name="Category 1",
                products=product_forecasts,
                total_forecast=Decimal("150"),
                growth_percent=Decimal("10"),
            ),
        ]

        top_growing = [product_forecasts[0]]
        top_declining = [product_forecasts[1]]

        insights = service._generate_insights(
            product_forecasts, category_forecasts, top_growing, top_declining
        )

        assert len(insights) > 0
        # Should mention growing products
        has_growing = any("раст" in i.lower() for i in insights)
        assert has_growing


class TestAnomalyDetectionService:
    """Tests for Anomaly Detection service."""

    def test_z_thresholds(self):
        """Test z-score thresholds."""
        service = AnomalyDetectionService(MagicMock())

        assert service.Z_THRESHOLDS[AnomalySeverity.LOW] == 2.0
        assert service.Z_THRESHOLDS[AnomalySeverity.MEDIUM] == 3.0
        assert service.Z_THRESHOLDS[AnomalySeverity.HIGH] == 4.0
        assert service.Z_THRESHOLDS[AnomalySeverity.CRITICAL] == 5.0

    def test_calculate_z_score(self):
        """Test z-score calculation."""
        service = AnomalyDetectionService(MagicMock())

        # Normal case
        z = service._calculate_z_score(150, 100, 10)
        assert z == 5.0

        # Below mean
        z = service._calculate_z_score(80, 100, 10)
        assert z == -2.0

        # Zero std
        z = service._calculate_z_score(100, 100, 0)
        assert z == 0

    def test_get_severity(self):
        """Test severity determination."""
        service = AnomalyDetectionService(MagicMock())

        assert service._get_severity(1.5) is None
        assert service._get_severity(2.5) == AnomalySeverity.LOW
        assert service._get_severity(3.5) == AnomalySeverity.MEDIUM
        assert service._get_severity(4.5) == AnomalySeverity.HIGH
        assert service._get_severity(5.5) == AnomalySeverity.CRITICAL

        # Negative z-scores
        assert service._get_severity(-2.5) == AnomalySeverity.LOW
        assert service._get_severity(-5.5) == AnomalySeverity.CRITICAL

    def test_get_possible_causes(self):
        """Test cause generation."""
        service = AnomalyDetectionService(MagicMock())

        # Revenue spike
        causes = service._get_possible_causes(
            AnomalyType.REVENUE_SPIKE, 3.0, 5  # Saturday
        )
        assert len(causes) > 0
        assert all(isinstance(c, str) for c in causes)

        # Revenue drop
        causes = service._get_possible_causes(
            AnomalyType.REVENUE_DROP, -3.0, 0  # Monday
        )
        assert len(causes) > 0

    def test_get_recommended_actions(self):
        """Test action recommendation generation."""
        service = AnomalyDetectionService(MagicMock())

        # Critical revenue drop
        actions = service._get_recommended_actions(
            AnomalyType.REVENUE_DROP,
            AnomalySeverity.CRITICAL,
            -5.0,
        )
        assert len(actions) > 0
        assert any("срочно" in a.lower() for a in actions)

        # Normal product spike
        actions = service._get_recommended_actions(
            AnomalyType.PRODUCT_SPIKE,
            AnomalySeverity.LOW,
            2.5,
        )
        assert len(actions) > 0

    def test_calculate_stats(self):
        """Test statistics calculation."""
        service = AnomalyDetectionService(MagicMock())

        anomalies = [
            Anomaly(
                anomaly_type=AnomalyType.REVENUE_SPIKE,
                severity=AnomalySeverity.HIGH,
                date=date(2026, 1, 15),  # Wednesday
                hour=None,
                actual_value=Decimal("15000"),
                expected_value=Decimal("10000"),
                deviation_percent=Decimal("50"),
                z_score=Decimal("4.5"),
                metric_name="Выручка",
                description="Test",
                possible_causes=[],
                recommended_actions=[],
            ),
            Anomaly(
                anomaly_type=AnomalyType.REVENUE_DROP,
                severity=AnomalySeverity.MEDIUM,
                date=date(2026, 1, 15),  # Wednesday
                hour=None,
                actual_value=Decimal("5000"),
                expected_value=Decimal("10000"),
                deviation_percent=Decimal("-50"),
                z_score=Decimal("-3.5"),
                metric_name="Выручка",
                description="Test",
                possible_causes=[],
                recommended_actions=[],
            ),
        ]

        stats = service._calculate_stats(anomalies)

        assert stats.total_anomalies == 2
        assert "revenue_spike" in stats.by_type
        assert "revenue_drop" in stats.by_type
        assert "high" in stats.by_severity
        assert "medium" in stats.by_severity
        assert stats.most_common_day == "Среда"

    def test_generate_insights(self):
        """Test insight generation."""
        service = AnomalyDetectionService(MagicMock())

        anomalies = [
            Anomaly(
                anomaly_type=AnomalyType.REVENUE_DROP,
                severity=AnomalySeverity.CRITICAL,
                date=date.today() - timedelta(days=2),
                hour=None,
                actual_value=Decimal("5000"),
                expected_value=Decimal("15000"),
                deviation_percent=Decimal("-66"),
                z_score=Decimal("-5.5"),
                metric_name="Выручка",
                description="Test",
                possible_causes=[],
                recommended_actions=[],
            ),
        ]

        stats = AnomalyStats(
            total_anomalies=1,
            by_type={"revenue_drop": 1},
            by_severity={"critical": 1},
            most_common_day="Понедельник",
            most_affected_metric="Выручка",
        )

        insights = service._generate_insights(anomalies, stats)

        assert len(insights) > 0
        # Should mention critical anomalies
        has_critical = any("критич" in i.lower() for i in insights)
        assert has_critical


class TestAnomalyTypes:
    """Tests for anomaly type enums."""

    def test_anomaly_type_values(self):
        """Test anomaly type enum values."""
        assert AnomalyType.REVENUE_SPIKE.value == "revenue_spike"
        assert AnomalyType.REVENUE_DROP.value == "revenue_drop"
        assert AnomalyType.TRAFFIC_SPIKE.value == "traffic_spike"
        assert AnomalyType.PRODUCT_DROP.value == "product_drop"

    def test_severity_values(self):
        """Test severity enum values."""
        assert AnomalySeverity.LOW.value == "low"
        assert AnomalySeverity.MEDIUM.value == "medium"
        assert AnomalySeverity.HIGH.value == "high"
        assert AnomalySeverity.CRITICAL.value == "critical"


class TestForecastDataClasses:
    """Tests for forecast data classes."""

    def test_forecast_point(self):
        """Test ForecastPoint dataclass."""
        point = ForecastPoint(
            date=date.today(),
            forecast=Decimal("10000"),
            lower_bound=Decimal("8000"),
            upper_bound=Decimal("12000"),
            is_actual=False,
        )

        assert point.forecast == Decimal("10000")
        assert point.lower_bound < point.forecast < point.upper_bound

    def test_forecast_accuracy(self):
        """Test ForecastAccuracy dataclass."""
        accuracy = ForecastAccuracy(
            mape=Decimal("10.5"),
            rmse=Decimal("1500"),
            mae=Decimal("1200"),
            r_squared=Decimal("0.85"),
        )

        assert accuracy.mape == Decimal("10.5")
        assert accuracy.r_squared <= 1

    def test_seasonal_component(self):
        """Test SeasonalComponent dataclass."""
        component = SeasonalComponent(
            name="weekly",
            strength=Decimal("0.25"),
            pattern={
                "Monday": Decimal("0.9"),
                "Saturday": Decimal("1.2"),
            },
        )

        assert component.name == "weekly"
        assert "Monday" in component.pattern

    def test_trend_component(self):
        """Test TrendComponent dataclass."""
        trend = TrendComponent(
            direction="up",
            slope=Decimal("150"),
            change_points=[date(2026, 1, 15)],
        )

        assert trend.direction == "up"
        assert trend.slope > 0
        assert len(trend.change_points) == 1
