"""Telegram bot callback query handlers."""

from datetime import date, timedelta
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
    format_abc_report,
    format_anomaly_alert,
    format_forecast_message,
    format_sales_summary,
)
from app.telegram.services import TelegramUserService


async def venue_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle venue selection callback."""
    query = update.callback_query
    await query.answer()

    # Parse callback data: venue:{venue_id}:{action}
    parts = query.data.split(":")
    if len(parts) < 2:
        return

    venue_id = parts[1]
    action = parts[2] if len(parts) > 2 else "sales"

    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await query.edit_message_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    if action == "sales":
        await query.edit_message_text(
            f"📊 <b>Выбери период для заведения:</b>",
            parse_mode="HTML",
            reply_markup=get_period_keyboard(f"venue_sales:{venue_id}"),
        )
    elif action == "info":
        venue = await service.get_venue_info(user, uuid.UUID(venue_id))
        if venue:
            await query.edit_message_text(
                f"📍 <b>{venue.name}</b>\n\n"
                f"Адрес: {venue.address or 'Не указан'}\n"
                f"Город: {venue.city or 'Не указан'}\n"
                f"POS: {venue.pos_type.value}\n"
                f"Последняя синхронизация: {venue.last_sync_at or 'Нет данных'}",
                parse_mode="HTML",
            )


async def period_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle period selection callback."""
    query = update.callback_query
    await query.answer()

    # Parse callback data: period:{action}:{period}[:venue_id]
    parts = query.data.split(":")
    if len(parts) < 3:
        return

    action = parts[1]
    period = parts[2]
    venue_id = parts[3] if len(parts) > 3 else None

    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await query.edit_message_text(
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
    elif period == "last7":
        start_date = today - timedelta(days=7)
        end_date = today
        period_name = "последние 7 дней"
    elif period == "last30":
        start_date = today - timedelta(days=30)
        end_date = today
        period_name = "последние 30 дней"
    else:
        start_date = today - timedelta(days=7)
        end_date = today
        period_name = "7 дней"

    await query.edit_message_text("⏳ Загружаю данные...")

    try:
        if action == "sales" or action.startswith("venue_sales"):
            sales_data = await service.get_sales_summary(
                user=user,
                start_date=start_date,
                end_date=end_date,
                venue_id=uuid.UUID(venue_id) if venue_id else None,
            )
            message = format_sales_summary(sales_data, period_name)

        elif action == "forecast":
            days = 7 if period == "week" else 30
            forecast_data = await service.get_quick_forecast(user=user, days=days)
            message = format_forecast_message(forecast_data)

        else:
            message = "❌ Неизвестное действие"

        await query.edit_message_text(message, parse_mode="HTML")

    except Exception as e:
        await query.edit_message_text(
            f"❌ Ошибка: {str(e)}",
            parse_mode="HTML",
        )


async def report_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle report type selection callback."""
    query = update.callback_query
    await query.answer()

    # Parse callback data: report:{report_type}
    parts = query.data.split(":")
    if len(parts) < 2:
        return

    report_type = parts[1]

    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await query.edit_message_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    await query.edit_message_text("⏳ Генерирую отчет...")

    try:
        if report_type == "sales":
            # Show period selection
            await query.edit_message_text(
                "📊 <b>Выбери период для отчета продаж:</b>",
                parse_mode="HTML",
                reply_markup=get_period_keyboard("sales"),
            )
            return

        elif report_type == "abc":
            report_data = await service.get_abc_report(user)
            message = format_abc_report(report_data)

        elif report_type == "forecast":
            forecast_data = await service.get_quick_forecast(user=user, days=7)
            message = format_forecast_message(forecast_data)

        elif report_type == "anomalies":
            anomalies = await service.get_recent_anomalies(user=user, days=30, limit=10)
            if not anomalies:
                message = "✅ <b>Аномалий не обнаружено</b>\n\nЗа последние 30 дней все показатели в норме."
            else:
                message = "🚨 <b>Аномалии за 30 дней</b>\n\n"
                for anomaly in anomalies:
                    message += format_anomaly_alert(anomaly) + "\n\n"

        elif report_type == "excel":
            # Generate and send Excel report
            excel_file = await service.generate_excel_report(user)
            if excel_file:
                await query.delete_message()
                from app.telegram.bot import get_bot

                bot = get_bot()
                if bot:
                    await bot.send_document(
                        chat_id=update.effective_user.id,
                        document=excel_file,
                        filename=f"mozg_report_{date.today().isoformat()}.xlsx",
                        caption="📊 <b>Отчет MOZG Analytics</b>",
                    )
                return
            else:
                message = "❌ Не удалось сгенерировать Excel отчет"

        else:
            message = "❌ Неизвестный тип отчета"

        await query.edit_message_text(message, parse_mode="HTML")

    except Exception as e:
        await query.edit_message_text(
            f"❌ Ошибка генерации отчета: {str(e)}",
            parse_mode="HTML",
        )


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle settings callback."""
    query = update.callback_query
    await query.answer()

    # Parse callback data: settings:{setting_key}
    parts = query.data.split(":")
    if len(parts) < 2:
        return

    setting_key = parts[1]

    service = TelegramUserService()
    user = await service.get_user_by_telegram_id(update.effective_user.id)

    if not user:
        await query.edit_message_text(
            "⚠️ Аккаунт не привязан. Используй /link для привязки.",
            parse_mode="HTML",
        )
        return

    # Toggle setting
    settings = await service.toggle_notification_setting(user, setting_key)

    settings_text = f"""
⚙️ <b>Настройки уведомлений</b>

🌅 Утренний отчет (9:00): {'✅' if settings.get('morning_report', True) else '❌'}
🌙 Вечерний отчет (22:00): {'✅' if settings.get('evening_report', True) else '❌'}
🚨 Алерты об аномалиях: {'✅' if settings.get('anomaly_alerts', True) else '❌'}
🎯 Достижение целей: {'✅' if settings.get('goal_alerts', True) else '❌'}

Нажми кнопку для переключения:
"""

    await query.edit_message_text(
        settings_text,
        parse_mode="HTML",
        reply_markup=get_settings_keyboard(settings),
    )


async def notification_callback(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Handle notification action callback."""
    query = update.callback_query
    await query.answer()

    # Parse callback data: notify:{action}
    parts = query.data.split(":")
    if len(parts) < 2:
        return

    action = parts[1]

    if action == "dismiss":
        # Just acknowledge and remove keyboard
        await query.edit_message_reply_markup(reply_markup=None)
    elif action == "details":
        # Would show more details - implementation depends on context
        await query.answer("Подробности доступны в веб-интерфейсе")


async def back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle back button callback."""
    query = update.callback_query
    await query.answer()

    # Parse callback data: back:{destination}
    parts = query.data.split(":")
    if len(parts) < 2:
        await query.edit_message_text(
            "📊 <b>Главное меню</b>\n\nВыбери действие:",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
        return

    destination = parts[1]

    if destination == "main":
        await query.edit_message_text(
            "📊 <b>Главное меню</b>\n\nВыбери действие:",
            parse_mode="HTML",
            reply_markup=get_main_menu_keyboard(),
        )
    elif destination == "reports":
        await query.edit_message_text(
            "📋 <b>Выбери тип отчета:</b>",
            parse_mode="HTML",
            reply_markup=get_report_keyboard(),
        )
    elif destination == "venues":
        service = TelegramUserService()
        user = await service.get_user_by_telegram_id(update.effective_user.id)
        if user:
            venues = await service.get_user_venues(user)
            await query.edit_message_text(
                "📍 <b>Ваши заведения:</b>",
                parse_mode="HTML",
                reply_markup=get_venues_keyboard(venues),
            )
