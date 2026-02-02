"""Telegram message formatters."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union


def format_currency(amount: Union[Decimal, float], symbol: str = "₽") -> str:
    """Format currency amount."""
    if isinstance(amount, Decimal):
        amount = float(amount)
    return f"{amount:,.0f} {symbol}".replace(",", " ")


def format_percent(value: Union[Decimal, float], show_sign: bool = True) -> str:
    """Format percentage value."""
    if isinstance(value, Decimal):
        value = float(value)
    sign = "+" if show_sign and value > 0 else ""
    return f"{sign}{value:.1f}%"


def format_number(value: Union[int, float]) -> str:
    """Format large number with spaces."""
    if isinstance(value, float):
        return f"{value:,.1f}".replace(",", " ")
    return f"{value:,}".replace(",", " ")


def format_trend_emoji(value: float) -> str:
    """Get trend emoji based on value."""
    if value > 10:
        return "📈"
    elif value > 0:
        return "↗️"
    elif value < -10:
        return "📉"
    elif value < 0:
        return "↘️"
    return "➡️"


def format_severity_emoji(severity: str) -> str:
    """Get severity emoji."""
    mapping = {
        "critical": "🔴",
        "high": "🟠",
        "medium": "🟡",
        "low": "🟢",
    }
    return mapping.get(severity.lower(), "⚪")


@dataclass
class SalesSummaryData:
    """Sales summary data for formatting."""

    total_revenue: Decimal
    total_receipts: int
    avg_receipt: Decimal
    total_guests: int
    previous_revenue: Optional[Decimal] = None
    growth_percent: Optional[float] = None
    top_products: Optional[List[Dict]] = None
    by_venue: Optional[List[Dict]] = None


def format_sales_summary(data: SalesSummaryData, period_name: str) -> str:
    """Format sales summary message."""
    # Growth indicator
    growth_text = ""
    if data.growth_percent is not None:
        emoji = format_trend_emoji(data.growth_percent)
        growth_text = f"\n{emoji} <b>{format_percent(data.growth_percent)}</b> к прошлому периоду"
        if data.previous_revenue:
            growth_text += f" ({format_currency(data.previous_revenue)})"

    message = f"""
📊 <b>Продажи за {period_name}</b>
{growth_text}

💰 <b>Выручка:</b> {format_currency(data.total_revenue)}
🧾 <b>Чеков:</b> {format_number(data.total_receipts)}
💵 <b>Средний чек:</b> {format_currency(data.avg_receipt)}
👥 <b>Гостей:</b> {format_number(data.total_guests)}
"""

    # Top products
    if data.top_products:
        message += "\n🏆 <b>Топ-3 товаров:</b>\n"
        for i, product in enumerate(data.top_products[:3], 1):
            message += f"{i}. {product['name']} — {format_currency(product['revenue'])}\n"

    # By venue breakdown
    if data.by_venue and len(data.by_venue) > 1:
        message += "\n📍 <b>По заведениям:</b>\n"
        for venue in data.by_venue[:5]:
            message += f"• {venue['name']}: {format_currency(venue['revenue'])}\n"

    return message


@dataclass
class ForecastData:
    """Forecast data for formatting."""

    total: Decimal
    avg_daily: Decimal
    days: int
    growth_percent: Optional[float] = None
    daily_forecast: Optional[List[Dict]] = None


def format_forecast_message(data: ForecastData) -> str:
    """Format forecast message."""
    growth_text = ""
    if data.growth_percent is not None:
        emoji = format_trend_emoji(data.growth_percent)
        growth_text = f"\n{emoji} Ожидаемый рост: <b>{format_percent(data.growth_percent)}</b>"

    message = f"""
📈 <b>Прогноз на {data.days} дней</b>
{growth_text}

💰 <b>Прогноз выручки:</b> {format_currency(data.total)}
📊 <b>В среднем в день:</b> {format_currency(data.avg_daily)}
"""

    # Daily breakdown (if short forecast)
    if data.daily_forecast and len(data.daily_forecast) <= 7:
        message += "\n📅 <b>По дням:</b>\n"
        weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for day in data.daily_forecast:
            d = day["date"]
            if isinstance(d, str):
                d = date.fromisoformat(d)
            weekday = weekdays[d.weekday()]
            message += f"• {weekday} {d.day:02d}: {format_currency(day['forecast'])}\n"

    return message


@dataclass
class AnomalyData:
    """Anomaly data for formatting."""

    anomaly_type: str
    severity: str
    date: date
    actual_value: Decimal
    expected_value: Decimal
    deviation_percent: float
    metric_name: str
    description: str
    possible_causes: List[str] = None
    recommended_actions: List[str] = None
    product_name: Optional[str] = None


def format_anomaly_alert(data: AnomalyData) -> str:
    """Format anomaly alert message."""
    severity_emoji = format_severity_emoji(data.severity)
    trend_emoji = "📈" if data.deviation_percent > 0 else "📉"

    type_names = {
        "revenue_spike": "Всплеск выручки",
        "revenue_drop": "Падение выручки",
        "traffic_spike": "Всплеск трафика",
        "traffic_drop": "Падение трафика",
        "avg_check_spike": "Рост среднего чека",
        "avg_check_drop": "Падение среднего чека",
        "product_spike": "Всплеск продаж товара",
        "product_drop": "Падение продаж товара",
    }
    type_name = type_names.get(data.anomaly_type, data.anomaly_type)

    message = f"""
{severity_emoji} <b>{type_name}</b>
📅 {data.date.strftime('%d.%m.%Y')}

{trend_emoji} {data.metric_name}: {format_currency(data.actual_value)}
📊 Ожидалось: {format_currency(data.expected_value)}
📉 Отклонение: <b>{format_percent(data.deviation_percent)}</b>
"""

    if data.product_name:
        message += f"🏷 Товар: {data.product_name}\n"

    if data.possible_causes:
        message += "\n💡 <b>Возможные причины:</b>\n"
        for cause in data.possible_causes[:2]:
            message += f"• {cause}\n"

    return message


@dataclass
class ABCReportData:
    """ABC report data for formatting."""

    a_products: List[Dict]
    b_products: List[Dict]
    c_products: List[Dict]
    a_percent: float
    b_percent: float
    c_percent: float


def format_abc_report(data: ABCReportData) -> str:
    """Format ABC analysis report message."""
    message = f"""
🔤 <b>ABC-анализ меню</b>

<b>Категория A</b> ({data.a_percent:.0f}% выручки):
"""
    for product in data.a_products[:5]:
        message += f"• {product['name']} — {format_currency(product['revenue'])}\n"

    if len(data.a_products) > 5:
        message += f"<i>... и ещё {len(data.a_products) - 5} позиций</i>\n"

    message += f"\n<b>Категория B</b> ({data.b_percent:.0f}% выручки):\n"
    for product in data.b_products[:3]:
        message += f"• {product['name']} — {format_currency(product['revenue'])}\n"

    if len(data.b_products) > 3:
        message += f"<i>... и ещё {len(data.b_products) - 3} позиций</i>\n"

    message += f"\n<b>Категория C</b> ({data.c_percent:.0f}% выручки):\n"
    message += f"<i>{len(data.c_products)} позиций с низкой выручкой</i>\n"

    message += "\n💡 <b>Рекомендация:</b> Сфокусируйтесь на продвижении товаров категории A и оптимизируйте категорию C."

    return message


def format_venue_list(venues: List) -> str:
    """Format venue list message."""
    message = "📍 <b>Ваши заведения:</b>\n\n"

    for venue in venues:
        status = "🟢" if venue.is_active else "🔴"
        sync_status = ""
        if venue.last_sync_at:
            sync_status = f" (обновлено: {venue.last_sync_at.strftime('%d.%m %H:%M')})"
        message += f"{status} <b>{venue.name}</b>{sync_status}\n"

    message += "\nНажмите на заведение для просмотра статистики."

    return message


def format_daily_report(
    date_report: date,
    revenue: Decimal,
    receipts: int,
    avg_check: Decimal,
    guests: int,
    vs_yesterday: Optional[float] = None,
    vs_last_week: Optional[float] = None,
    anomalies: Optional[List[AnomalyData]] = None,
) -> str:
    """Format daily report notification."""
    message = f"""
📊 <b>Итоги дня {date_report.strftime('%d.%m.%Y')}</b>

💰 Выручка: {format_currency(revenue)}"""

    if vs_yesterday is not None:
        emoji = format_trend_emoji(vs_yesterday)
        message += f" {emoji} {format_percent(vs_yesterday)} к вчера"

    message += f"""

🧾 Чеков: {format_number(receipts)}
💵 Средний чек: {format_currency(avg_check)}
👥 Гостей: {format_number(guests)}
"""

    if vs_last_week is not None:
        emoji = format_trend_emoji(vs_last_week)
        message += f"\n📈 К прошлой неделе: {format_percent(vs_last_week)}"

    if anomalies:
        message += "\n\n⚠️ <b>Обнаружены аномалии:</b>\n"
        for anomaly in anomalies[:3]:
            severity_emoji = format_severity_emoji(anomaly.severity)
            message += f"{severity_emoji} {anomaly.description[:50]}...\n"

    return message


def format_morning_report(
    yesterday_revenue: Decimal,
    yesterday_receipts: int,
    forecast_today: Decimal,
    forecast_week: Decimal,
    alerts_count: int = 0,
) -> str:
    """Format morning report notification."""
    message = f"""
☀️ <b>Доброе утро! Сводка SMART CONTROL HUB</b>

📊 <b>Вчера:</b>
💰 Выручка: {format_currency(yesterday_revenue)}
🧾 Чеков: {format_number(yesterday_receipts)}

📈 <b>Прогноз:</b>
• На сегодня: {format_currency(forecast_today)}
• На неделю: {format_currency(forecast_week)}
"""

    if alerts_count > 0:
        message += f"\n⚠️ Требуют внимания: {alerts_count} аномали{'я' if alerts_count == 1 else ('и' if alerts_count < 5 else 'й')}"

    message += "\n\nУспешного дня! 🍀"

    return message


def format_evening_report(
    today_revenue: Decimal,
    today_receipts: int,
    avg_check: Decimal,
    vs_plan: Optional[float] = None,
    vs_yesterday: Optional[float] = None,
) -> str:
    """Format evening report notification."""
    message = f"""
🌙 <b>Итоги дня</b>

💰 Выручка: {format_currency(today_revenue)}
🧾 Чеков: {format_number(today_receipts)}
💵 Средний чек: {format_currency(avg_check)}
"""

    if vs_plan is not None:
        emoji = "✅" if vs_plan >= 0 else "⚠️"
        message += f"\n{emoji} К плану: {format_percent(vs_plan)}"

    if vs_yesterday is not None:
        emoji = format_trend_emoji(vs_yesterday)
        message += f"\n{emoji} К вчера: {format_percent(vs_yesterday)}"

    message += "\n\nОтличной ночи! 🌟"

    return message
