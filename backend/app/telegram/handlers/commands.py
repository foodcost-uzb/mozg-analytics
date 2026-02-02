"""Telegram bot command handlers."""

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional
import uuid

from telegram import Update
from telegram.ext import ContextTypes

from app.telegram.keyboards import (
    get_main_menu_keyboard,
    get_period_keyboard,
    get_report_keyboard,
    get_settings_keyboard,
    get_venues_keyboard,
)
from app.telegram.formatters import (
    format_anomaly_alert,
    format_currency,
    format_forecast_message,
    format_percent,
    format_sales_summary,
    format_venue_list,
)
from app.telegram.services import TelegramUserService


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command - welcome message."""
    user = update.effective_user

    welcome_text = f"""
👋 Привет, <b>{user.first_name}</b>!

Я бот <b>MOZG Analytics</b> - твой персональный помощник для аналитики ресторанного бизнеса.

🔧 <b>Что я умею:</b>
• 📊 Показывать продажи за период
• 📈 Прогнозировать выручку
• 🚨 Отслеживать аномалии
• 📋 Генерировать отчеты

Используй кнопки меню ниже или команды:
/sales - быстрая сводка продаж
/today - продажи за сегодня
/week - продажи за неделю
/forecast - прогноз выручки
/alerts - последние аномалии
/venues - список заведений
/report - детальный отчет
/settings - настройки уведомлений
/help - справка по командам

🔗 Для привязки аккаунта используй /link
"""

    # Check if user is linked
    service = TelegramUserService()
    linked_user = await service.get_user_by_telegram_id(user.id)

    if linked_user:
        welcome_text += f"\n✅ <b>Аккаунт привязан:</b> {linked_user.email or linked_user.first_name}"
    else:
        welcome_text += "\n⚠️ <b>Аккаунт не привязан.</b> Используй /link для привязки."

    await update.message.reply_text(
        welcome_text,
        parse_mode="HTML",
        reply_markup=get_main_menu_keyboard(),
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command - show help."""
    help_text = """
📚 <b>Справка по командам MOZG Analytics</b>

<b>Продажи:</b>
/sales - быстрая сводка продаж
/today - продажи за сегодня
/week - продажи за текущую неделю
/month - продажи за текущий месяц

<b>Аналитика:</b>
/forecast - прогноз выручки на 7 дней
/alerts - последние аномалии и отклонения

<b>Отчеты:</b>
/report - выбор детального отчета
/venues - список заведений

<b>Настройки:</b>
/settings - настройки уведомлений
/link - привязка аккаунта

<b>Уведомления:</b>
• 🌅 Утренний отчет (9:00)
• 🌙 Вечерний отчет (22:00)
• 🚨 Алерты об аномалиях
• 🎯 Достижение целей

Для управления уведомлениями: /settings
"""

    await update.message.reply_text(help_text, parse_mode="HTML")


async def sales_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /sales command - quick sales summary."""
    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        "📊 <b>Выбери период:</b>",
        parse_mode="HTML",
        reply_markup=get_period_keyboard("sales"),
    )


async def today_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /today command - today's sales."""
    await _send_sales_report(update, context, period="today")


async def week_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /week command - this week's sales."""
    await _send_sales_report(update, context, period="week")


async def month_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /month command - this month's sales."""
    await _send_sales_report(update, context, period="month")


async def _send_sales_report(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    period: str,
    venue_id: Optional[str] = None,
) -> None:
    """Send sales report for specified period."""
    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    # Calculate date range
    today = date.today()
    if period == "today":
        start_date = today
        end_date = today
        period_name = "сегодня"
    elif period == "yesterday":
        start_date = today - timedelta(days=1)
        end_date = start_date
        period_name = "вчера"
    elif period == "week":
        start_date = today - timedelta(days=today.weekday())
        end_date = today
        period_name = "эту неделю"
    elif period == "month":
        start_date = today.replace(day=1)
        end_date = today
        period_name = "этот месяц"
    else:
        start_date = today - timedelta(days=7)
        end_date = today
        period_name = "последние 7 дней"

    # Get sales data
    await update.message.reply_text("⏳ Загружаю данные...")

    try:
        sales_data = await service.get_sales_summary(
            user=user,
            start_date=start_date,
            end_date=end_date,
            venue_id=uuid.UUID(venue_id) if venue_id else None,
        )

        message = format_sales_summary(sales_data, period_name)
        await update.message.reply_text(message, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка загрузки данных: {str(e)}",
            parse_mode="HTML",
        )


async def forecast_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /forecast command - revenue forecast."""
    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text("⏳ Рассчитываю прогноз...")

    try:
        forecast_data = await service.get_quick_forecast(user=user, days=7)
        message = format_forecast_message(forecast_data)
        await update.message.reply_text(message, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка расчета прогноза: {str(e)}",
            parse_mode="HTML",
        )


async def alerts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /alerts command - recent anomalies."""
    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text("⏳ Проверяю аномалии...")

    try:
        anomalies = await service.get_recent_anomalies(user=user, days=7, limit=5)

        if not anomalies:
            await update.message.reply_text(
                "✅ <b>Аномалий не обнаружено</b>\n\n"
                "За последние 7 дней все показатели в норме.",
                parse_mode="HTML",
            )
            return

        message = "🚨 <b>Последние аномалии</b>\n\n"
        for anomaly in anomalies:
            message += format_anomaly_alert(anomaly) + "\n\n"

        await update.message.reply_text(message, parse_mode="HTML")

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка проверки аномалий: {str(e)}",
            parse_mode="HTML",
        )


async def venues_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /venues command - list venues."""
    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    try:
        venues = await service.get_user_venues(user)

        if not venues:
            await update.message.reply_text(
                "📍 У вас пока нет заведений.\n"
                "Добавьте заведение в веб-интерфейсе.",
                parse_mode="HTML",
            )
            return

        message = format_venue_list(venues)
        keyboard = get_venues_keyboard(venues)

        await update.message.reply_text(
            message,
            parse_mode="HTML",
            reply_markup=keyboard,
        )

    except Exception as e:
        await update.message.reply_text(
            f"❌ Ошибка загрузки заведений: {str(e)}",
            parse_mode="HTML",
        )


async def report_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /report command - choose report type."""
    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    await update.message.reply_text(
        "📋 <b>Выбери тип отчета:</b>",
        parse_mode="HTML",
        reply_markup=get_report_keyboard(),
    )


async def settings_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command - notification settings."""
    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await update.message.reply_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    # Get current settings
    settings = await service.get_notification_settings(user)

    settings_text = f"""
⚙️ <b>Настройки уведомлений</b>

🌅 Утренний отчет (9:00): {'✅' if settings.get('morning_report', True) else '❌'}
🌙 Вечерний отчет (22:00): {'✅' if settings.get('evening_report', True) else '❌'}
🚨 Алерты об аномалиях: {'✅' if settings.get('anomaly_alerts', True) else '❌'}
🎯 Достижение целей: {'✅' if settings.get('goal_alerts', True) else '❌'}

Нажми кнопку для переключения:
"""

    await update.message.reply_text(
        settings_text,
        parse_mode="HTML",
        reply_markup=get_settings_keyboard(settings),
    )


async def link_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /link command - link Telegram account."""
    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if user:
        await update.message.reply_text(
            f"✅ <b>Аккаунт уже привязан</b>\n\n"
            f"Пользователь: {user.email or user.first_name}\n"
            f"Организация: {user.organization.name}",
            parse_mode="HTML",
        )
        return

    # Generate link code
    tg_user = update.effective_user
    link_code = await service.generate_link_code(
        telegram_id=tg_user.id,
        telegram_username=tg_user.username,
        first_name=tg_user.first_name,
        last_name=tg_user.last_name,
    )

    await update.message.reply_text(
        f"🔗 <b>Привязка аккаунта</b>\n\n"
        f"Ваш код привязки:\n<code>{link_code}</code>\n\n"
        f"Введите этот код в веб-интерфейсе MOZG Analytics "
        f"в разделе Настройки → Telegram.\n\n"
        f"Код действителен 10 минут.",
        parse_mode="HTML",
    )
