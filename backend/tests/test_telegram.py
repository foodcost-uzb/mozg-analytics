"""Tests for Phase 6 Telegram integration."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest

from app.telegram.formatters import (
    ABCReportData,
    AnomalyData,
    ForecastData,
    SalesSummaryData,
    format_abc_report,
    format_anomaly_alert,
    format_currency,
    format_daily_report,
    format_evening_report,
    format_forecast_message,
    format_morning_report,
    format_number,
    format_percent,
    format_sales_summary,
    format_severity_emoji,
    format_trend_emoji,
    format_venue_list,
)
from app.telegram.keyboards import (
    get_anomaly_alert_keyboard,
    get_daily_report_keyboard,
    get_main_menu_keyboard,
    get_period_keyboard,
    get_report_keyboard,
    get_settings_keyboard,
    get_venues_keyboard,
)


class TestFormatters:
    """Tests for message formatters."""

    def test_format_currency(self):
        """Test currency formatting."""
        assert format_currency(Decimal("1000")) == "1 000 ₽"
        assert format_currency(1500.5) == "1 500 ₽"
        assert format_currency(Decimal("1234567")) == "1 234 567 ₽"
        assert format_currency(100, symbol="$") == "100 $"

    def test_format_percent(self):
        """Test percent formatting."""
        assert format_percent(15.5) == "+15.5%"
        assert format_percent(-10.2) == "-10.2%"
        assert format_percent(0) == "0.0%"
        assert format_percent(5.0, show_sign=False) == "5.0%"

    def test_format_number(self):
        """Test number formatting."""
        assert format_number(1000) == "1 000"
        assert format_number(1234567) == "1 234 567"
        assert format_number(99.5) == "99.5"

    def test_format_trend_emoji(self):
        """Test trend emoji selection."""
        assert format_trend_emoji(15) == "📈"
        assert format_trend_emoji(5) == "↗️"
        assert format_trend_emoji(-15) == "📉"
        assert format_trend_emoji(-5) == "↘️"
        assert format_trend_emoji(0) == "➡️"

    def test_format_severity_emoji(self):
        """Test severity emoji selection."""
        assert format_severity_emoji("critical") == "🔴"
        assert format_severity_emoji("high") == "🟠"
        assert format_severity_emoji("medium") == "🟡"
        assert format_severity_emoji("low") == "🟢"
        assert format_severity_emoji("unknown") == "⚪"

    def test_format_sales_summary(self):
        """Test sales summary formatting."""
        data = SalesSummaryData(
            total_revenue=Decimal("150000"),
            total_receipts=300,
            avg_receipt=Decimal("500"),
            total_guests=450,
            previous_revenue=Decimal("120000"),
            growth_percent=25.0,
        )

        result = format_sales_summary(data, "сегодня")

        assert "сегодня" in result
        assert "150 000 ₽" in result
        assert "300" in result
        assert "500 ₽" in result
        assert "+25.0%" in result

    def test_format_sales_summary_with_top_products(self):
        """Test sales summary with top products."""
        data = SalesSummaryData(
            total_revenue=Decimal("150000"),
            total_receipts=300,
            avg_receipt=Decimal("500"),
            total_guests=450,
            top_products=[
                {"name": "Пицца", "revenue": Decimal("50000")},
                {"name": "Бургер", "revenue": Decimal("30000")},
            ],
        )

        result = format_sales_summary(data, "неделю")

        assert "Топ-3 товаров" in result
        assert "Пицца" in result
        assert "Бургер" in result

    def test_format_forecast_message(self):
        """Test forecast message formatting."""
        data = ForecastData(
            total=Decimal("700000"),
            avg_daily=Decimal("100000"),
            days=7,
            growth_percent=10.5,
        )

        result = format_forecast_message(data)

        assert "7 дней" in result
        assert "700 000 ₽" in result
        assert "100 000 ₽" in result
        assert "+10.5%" in result

    def test_format_forecast_with_daily(self):
        """Test forecast with daily breakdown."""
        data = ForecastData(
            total=Decimal("700000"),
            avg_daily=Decimal("100000"),
            days=3,
            daily_forecast=[
                {"date": date(2026, 2, 2), "forecast": Decimal("95000")},
                {"date": date(2026, 2, 3), "forecast": Decimal("100000")},
                {"date": date(2026, 2, 4), "forecast": Decimal("105000")},
            ],
        )

        result = format_forecast_message(data)

        assert "По дням" in result

    def test_format_anomaly_alert(self):
        """Test anomaly alert formatting."""
        data = AnomalyData(
            anomaly_type="revenue_spike",
            severity="high",
            date=date(2026, 2, 1),
            actual_value=Decimal("200000"),
            expected_value=Decimal("100000"),
            deviation_percent=100.0,
            metric_name="Выручка",
            description="Всплеск выручки",
            possible_causes=["Акция", "Праздник"],
        )

        result = format_anomaly_alert(data)

        assert "Всплеск выручки" in result
        assert "🟠" in result  # high severity
        assert "200 000 ₽" in result
        assert "+100.0%" in result
        assert "Акция" in result

    def test_format_abc_report(self):
        """Test ABC report formatting."""
        data = ABCReportData(
            a_products=[
                {"name": "Товар A1", "revenue": Decimal("100000")},
                {"name": "Товар A2", "revenue": Decimal("80000")},
            ],
            b_products=[
                {"name": "Товар B1", "revenue": Decimal("30000")},
            ],
            c_products=[
                {"name": "Товар C1", "revenue": Decimal("5000")},
            ],
            a_percent=70,
            b_percent=20,
            c_percent=10,
        )

        result = format_abc_report(data)

        assert "ABC-анализ" in result
        assert "Категория A" in result
        assert "70%" in result
        assert "Товар A1" in result

    def test_format_morning_report(self):
        """Test morning report formatting."""
        result = format_morning_report(
            yesterday_revenue=Decimal("150000"),
            yesterday_receipts=300,
            forecast_today=Decimal("100000"),
            forecast_week=Decimal("700000"),
            alerts_count=2,
        )

        assert "Доброе утро" in result
        assert "Вчера" in result
        assert "150 000 ₽" in result
        assert "Прогноз" in result
        assert "2 аномалии" in result

    def test_format_evening_report(self):
        """Test evening report formatting."""
        result = format_evening_report(
            today_revenue=Decimal("120000"),
            today_receipts=250,
            avg_check=Decimal("480"),
            vs_yesterday=5.5,
        )

        assert "Итоги дня" in result
        assert "120 000 ₽" in result
        assert "+5.5%" in result

    def test_format_daily_report(self):
        """Test daily report formatting."""
        result = format_daily_report(
            date_report=date(2026, 2, 1),
            revenue=Decimal("130000"),
            receipts=280,
            avg_check=Decimal("464"),
            guests=350,
            vs_yesterday=-3.5,
        )

        assert "01.02.2026" in result
        assert "130 000 ₽" in result
        assert "-3.5%" in result


class TestKeyboards:
    """Tests for inline keyboards."""

    def test_main_menu_keyboard(self):
        """Test main menu keyboard structure."""
        keyboard = get_main_menu_keyboard()

        assert keyboard is not None
        assert len(keyboard.inline_keyboard) > 0

        # Check for main buttons
        buttons_text = [
            btn.text for row in keyboard.inline_keyboard for btn in row
        ]
        assert any("Продажи" in t for t in buttons_text)
        assert any("Прогноз" in t for t in buttons_text)
        assert any("Настройки" in t for t in buttons_text)

    def test_period_keyboard(self):
        """Test period selection keyboard."""
        keyboard = get_period_keyboard("sales")

        assert keyboard is not None
        buttons = [btn for row in keyboard.inline_keyboard for btn in row]

        # Check for period buttons
        callback_data = [btn.callback_data for btn in buttons]
        assert any("today" in cd for cd in callback_data)
        assert any("week" in cd for cd in callback_data)
        assert any("month" in cd for cd in callback_data)

    def test_period_keyboard_with_venue(self):
        """Test period keyboard with venue ID."""
        venue_id = str(uuid.uuid4())
        keyboard = get_period_keyboard("sales", venue_id)

        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        callback_data = [btn.callback_data for btn in buttons]

        # Venue ID should be in callback data
        assert any(venue_id in cd for cd in callback_data if cd)

    def test_report_keyboard(self):
        """Test report type keyboard."""
        keyboard = get_report_keyboard()

        buttons_text = [
            btn.text for row in keyboard.inline_keyboard for btn in row
        ]
        assert any("Продажи" in t for t in buttons_text)
        assert any("ABC" in t for t in buttons_text)
        assert any("Прогноз" in t for t in buttons_text)
        assert any("Excel" in t for t in buttons_text)

    def test_settings_keyboard(self):
        """Test settings keyboard."""
        settings = {
            "morning_report": True,
            "evening_report": False,
            "anomaly_alerts": True,
            "goal_alerts": True,
        }

        keyboard = get_settings_keyboard(settings)

        buttons_text = [
            btn.text for row in keyboard.inline_keyboard for btn in row
        ]
        # Check for enabled/disabled indicators
        assert any("✅" in t and "Утренний" in t for t in buttons_text)
        assert any("❌" in t and "Вечерний" in t for t in buttons_text)

    def test_venues_keyboard(self):
        """Test venues keyboard."""
        # Create mock venues
        class MockVenue:
            def __init__(self, id, name):
                self.id = id
                self.name = name

        venues = [
            MockVenue(uuid.uuid4(), "Ресторан 1"),
            MockVenue(uuid.uuid4(), "Ресторан 2"),
        ]

        keyboard = get_venues_keyboard(venues)

        buttons_text = [
            btn.text for row in keyboard.inline_keyboard for btn in row
        ]
        assert any("Ресторан 1" in t for t in buttons_text)
        assert any("Ресторан 2" in t for t in buttons_text)

    def test_anomaly_alert_keyboard(self):
        """Test anomaly alert keyboard."""
        keyboard = get_anomaly_alert_keyboard("anomaly-123")

        buttons_text = [
            btn.text for row in keyboard.inline_keyboard for btn in row
        ]
        assert any("Подробнее" in t for t in buttons_text)
        assert any("Понятно" in t for t in buttons_text)

    def test_daily_report_keyboard(self):
        """Test daily report keyboard."""
        keyboard = get_daily_report_keyboard()

        buttons = [btn for row in keyboard.inline_keyboard for btn in row]
        callback_data = [btn.callback_data for btn in buttons]

        assert any("report:sales" in cd for cd in callback_data)
        assert any("report:forecast" in cd for cd in callback_data)


class TestTelegramUserService:
    """Tests for TelegramUserService."""

    @pytest.mark.asyncio
    async def test_format_venue_list(self):
        """Test venue list formatting."""

        class MockVenue:
            def __init__(self, name, is_active, last_sync_at):
                self.name = name
                self.is_active = is_active
                self.last_sync_at = last_sync_at

        from datetime import datetime

        venues = [
            MockVenue("Кафе Центральное", True, datetime(2026, 2, 1, 14, 30)),
            MockVenue("Ресторан Приморский", True, None),
            MockVenue("Закрытое заведение", False, None),
        ]

        result = format_venue_list(venues)

        assert "Ваши заведения" in result
        assert "Кафе Центральное" in result
        assert "🟢" in result  # Active
        assert "🔴" in result  # Inactive
        assert "01.02 14:30" in result  # Sync time


class TestNotificationMessages:
    """Tests for notification message content."""

    def test_morning_report_without_alerts(self):
        """Test morning report when no alerts."""
        result = format_morning_report(
            yesterday_revenue=Decimal("100000"),
            yesterday_receipts=200,
            forecast_today=Decimal("95000"),
            forecast_week=Decimal("665000"),
            alerts_count=0,
        )

        assert "аномали" not in result
        assert "Успешного дня" in result

    def test_evening_report_with_plan(self):
        """Test evening report with plan comparison."""
        result = format_evening_report(
            today_revenue=Decimal("105000"),
            today_receipts=210,
            avg_check=Decimal("500"),
            vs_plan=5.0,
            vs_yesterday=2.5,
        )

        assert "К плану" in result
        assert "+5.0%" in result

    def test_anomaly_drop_formatting(self):
        """Test anomaly drop message."""
        data = AnomalyData(
            anomaly_type="revenue_drop",
            severity="critical",
            date=date(2026, 2, 1),
            actual_value=Decimal("50000"),
            expected_value=Decimal("100000"),
            deviation_percent=-50.0,
            metric_name="Выручка",
            description="Падение выручки",
        )

        result = format_anomaly_alert(data)

        assert "Падение" in result
        assert "🔴" in result  # critical severity
        assert "-50.0%" in result


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_sales_data(self):
        """Test formatting with zero values."""
        data = SalesSummaryData(
            total_revenue=Decimal("0"),
            total_receipts=0,
            avg_receipt=Decimal("0"),
            total_guests=0,
        )

        result = format_sales_summary(data, "сегодня")

        assert "0 ₽" in result

    def test_large_numbers(self):
        """Test formatting with large numbers."""
        assert format_currency(Decimal("999999999")) == "999 999 999 ₽"
        assert format_number(1000000000) == "1 000 000 000"

    def test_negative_growth(self):
        """Test negative growth formatting."""
        data = SalesSummaryData(
            total_revenue=Decimal("80000"),
            total_receipts=150,
            avg_receipt=Decimal("533"),
            total_guests=200,
            previous_revenue=Decimal("100000"),
            growth_percent=-20.0,
        )

        result = format_sales_summary(data, "неделю")

        assert "-20.0%" in result
        assert "📉" in result or "↘️" in result

    def test_special_characters_in_venue_name(self):
        """Test venue name with special characters."""

        class MockVenue:
            def __init__(self):
                self.name = "Кафе <Звезда> & Bar"
                self.is_active = True
                self.last_sync_at = None

        venues = [MockVenue()]
        result = format_venue_list(venues)

        # Should handle special chars (HTML entities would be handled by Telegram)
        assert "Звезда" in result
