"""Telegram bot inline keyboards."""

from typing import Dict, List, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Get main menu inline keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Продажи", callback_data="period:sales:today"),
            InlineKeyboardButton("📈 Прогноз", callback_data="report:forecast"),
        ],
        [
            InlineKeyboardButton("🚨 Аномалии", callback_data="report:anomalies"),
            InlineKeyboardButton("📋 Отчеты", callback_data="back:reports"),
        ],
        [
            InlineKeyboardButton("📍 Заведения", callback_data="back:venues"),
            InlineKeyboardButton("⚙️ Настройки", callback_data="settings:show"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_period_keyboard(action: str, venue_id: Optional[str] = None) -> InlineKeyboardMarkup:
    """Get period selection keyboard."""
    suffix = f":{venue_id}" if venue_id else ""

    keyboard = [
        [
            InlineKeyboardButton("📆 Сегодня", callback_data=f"period:{action}:today{suffix}"),
            InlineKeyboardButton("📆 Вчера", callback_data=f"period:{action}:yesterday{suffix}"),
        ],
        [
            InlineKeyboardButton("📅 Эта неделя", callback_data=f"period:{action}:week{suffix}"),
            InlineKeyboardButton("📅 Этот месяц", callback_data=f"period:{action}:month{suffix}"),
        ],
        [
            InlineKeyboardButton("📅 7 дней", callback_data=f"period:{action}:last7{suffix}"),
            InlineKeyboardButton("📅 30 дней", callback_data=f"period:{action}:last30{suffix}"),
        ],
        [
            InlineKeyboardButton("« Назад", callback_data="back:main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_report_keyboard() -> InlineKeyboardMarkup:
    """Get report type selection keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Продажи", callback_data="report:sales"),
            InlineKeyboardButton("🔤 ABC-анализ", callback_data="report:abc"),
        ],
        [
            InlineKeyboardButton("📈 Прогноз", callback_data="report:forecast"),
            InlineKeyboardButton("🚨 Аномалии", callback_data="report:anomalies"),
        ],
        [
            InlineKeyboardButton("📥 Excel отчет", callback_data="report:excel"),
        ],
        [
            InlineKeyboardButton("« Назад", callback_data="back:main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_venues_keyboard(venues: List) -> InlineKeyboardMarkup:
    """Get venues list keyboard."""
    keyboard = []

    for venue in venues[:10]:  # Limit to 10 venues
        keyboard.append([
            InlineKeyboardButton(
                f"📍 {venue.name}",
                callback_data=f"venue:{venue.id}:sales",
            ),
            InlineKeyboardButton(
                "ℹ️",
                callback_data=f"venue:{venue.id}:info",
            ),
        ])

    keyboard.append([
        InlineKeyboardButton("« Назад", callback_data="back:main"),
    ])

    return InlineKeyboardMarkup(keyboard)


def get_settings_keyboard(settings: Dict[str, bool]) -> InlineKeyboardMarkup:
    """Get notification settings keyboard."""
    keyboard = [
        [
            InlineKeyboardButton(
                f"{'✅' if settings.get('morning_report', True) else '❌'} Утренний отчет",
                callback_data="settings:morning_report",
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if settings.get('evening_report', True) else '❌'} Вечерний отчет",
                callback_data="settings:evening_report",
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if settings.get('anomaly_alerts', True) else '❌'} Алерты об аномалиях",
                callback_data="settings:anomaly_alerts",
            ),
        ],
        [
            InlineKeyboardButton(
                f"{'✅' if settings.get('goal_alerts', True) else '❌'} Достижение целей",
                callback_data="settings:goal_alerts",
            ),
        ],
        [
            InlineKeyboardButton("« Назад", callback_data="back:main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_anomaly_alert_keyboard(anomaly_id: str = None) -> InlineKeyboardMarkup:
    """Get anomaly alert action keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Подробнее", callback_data=f"notify:details:{anomaly_id or 'none'}"),
            InlineKeyboardButton("✓ Понятно", callback_data="notify:dismiss"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_daily_report_keyboard() -> InlineKeyboardMarkup:
    """Get daily report keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("📊 Детальный отчет", callback_data="report:sales"),
            InlineKeyboardButton("📈 Прогноз", callback_data="report:forecast"),
        ],
        [
            InlineKeyboardButton("🚨 Аномалии", callback_data="report:anomalies"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_confirmation_keyboard(action: str, item_id: str) -> InlineKeyboardMarkup:
    """Get confirmation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да", callback_data=f"confirm:{action}:{item_id}"),
            InlineKeyboardButton("❌ Нет", callback_data="back:main"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
