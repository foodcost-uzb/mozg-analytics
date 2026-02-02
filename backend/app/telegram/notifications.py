"""Telegram push notification service."""

import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional

from app.core.config import settings
from app.telegram.bot import get_bot
from app.telegram.formatters import (
    AnomalyData,
    format_anomaly_alert,
    format_daily_report,
    format_evening_report,
    format_morning_report,
)
from app.telegram.keyboards import (
    get_anomaly_alert_keyboard,
    get_daily_report_keyboard,
)
from app.telegram.services import TelegramUserService

logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending Telegram notifications."""

    def __init__(self):
        self.bot = get_bot()
        self.user_service = TelegramUserService()

    async def send_morning_report(self) -> int:
        """
        Send morning report to all subscribed users.

        Returns number of successfully sent messages.
        """
        if not self.bot:
            logger.warning("Telegram bot not configured")
            return 0

        users = await self.user_service.get_users_for_notification("morning_report")
        sent_count = 0

        for user_data in users:
            try:
                user = user_data["user"]
                telegram_id = user_data["telegram_id"]

                # Get yesterday's sales
                yesterday = date.today() - timedelta(days=1)
                sales_data = await self.user_service.get_sales_summary(
                    user=user,
                    start_date=yesterday,
                    end_date=yesterday,
                )

                # Get forecast
                forecast_data = await self.user_service.get_quick_forecast(
                    user=user,
                    days=7,
                )

                # Get alerts count
                anomalies = await self.user_service.get_recent_anomalies(
                    user=user,
                    days=7,
                    limit=10,
                )
                alerts_count = len([a for a in anomalies if a.severity in ("high", "critical")])

                # Format message
                message = format_morning_report(
                    yesterday_revenue=sales_data.total_revenue,
                    yesterday_receipts=sales_data.total_receipts,
                    forecast_today=forecast_data.avg_daily,
                    forecast_week=forecast_data.total,
                    alerts_count=alerts_count,
                )

                # Send
                success = await self.bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    reply_markup=get_daily_report_keyboard(),
                )

                if success:
                    sent_count += 1

            except Exception as e:
                logger.error(f"Error sending morning report to {user_data.get('telegram_id')}: {e}")

        logger.info(f"Morning report sent to {sent_count}/{len(users)} users")
        return sent_count

    async def send_evening_report(self) -> int:
        """
        Send evening report to all subscribed users.

        Returns number of successfully sent messages.
        """
        if not self.bot:
            logger.warning("Telegram bot not configured")
            return 0

        users = await self.user_service.get_users_for_notification("evening_report")
        sent_count = 0

        for user_data in users:
            try:
                user = user_data["user"]
                telegram_id = user_data["telegram_id"]

                # Get today's sales
                today = date.today()
                sales_data = await self.user_service.get_sales_summary(
                    user=user,
                    start_date=today,
                    end_date=today,
                )

                # Get yesterday for comparison
                yesterday = today - timedelta(days=1)
                yesterday_data = await self.user_service.get_sales_summary(
                    user=user,
                    start_date=yesterday,
                    end_date=yesterday,
                )

                vs_yesterday = None
                if yesterday_data.total_revenue > 0:
                    vs_yesterday = float(
                        (sales_data.total_revenue - yesterday_data.total_revenue)
                        / yesterday_data.total_revenue
                        * 100
                    )

                # Format message
                message = format_evening_report(
                    today_revenue=sales_data.total_revenue,
                    today_receipts=sales_data.total_receipts,
                    avg_check=sales_data.avg_receipt,
                    vs_yesterday=vs_yesterday,
                )

                # Send
                success = await self.bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    reply_markup=get_daily_report_keyboard(),
                )

                if success:
                    sent_count += 1

            except Exception as e:
                logger.error(f"Error sending evening report to {user_data.get('telegram_id')}: {e}")

        logger.info(f"Evening report sent to {sent_count}/{len(users)} users")
        return sent_count

    async def send_anomaly_alert(
        self,
        anomaly: AnomalyData,
        organization_id: str,
    ) -> int:
        """
        Send anomaly alert to subscribed users in organization.

        Returns number of successfully sent messages.
        """
        if not self.bot:
            logger.warning("Telegram bot not configured")
            return 0

        # Get users from this organization
        users = await self.user_service.get_users_for_notification("anomaly_alerts")
        org_users = [u for u in users if str(u["organization_id"]) == organization_id]

        sent_count = 0

        for user_data in org_users:
            try:
                telegram_id = user_data["telegram_id"]

                # Format message
                message = f"🚨 <b>Обнаружена аномалия!</b>\n\n{format_anomaly_alert(anomaly)}"

                # Send
                success = await self.bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                    reply_markup=get_anomaly_alert_keyboard(),
                )

                if success:
                    sent_count += 1

            except Exception as e:
                logger.error(f"Error sending anomaly alert to {user_data.get('telegram_id')}: {e}")

        logger.info(f"Anomaly alert sent to {sent_count}/{len(org_users)} users")
        return sent_count

    async def send_goal_achieved(
        self,
        goal_name: str,
        achieved_value: Decimal,
        target_value: Decimal,
        organization_id: str,
    ) -> int:
        """
        Send goal achievement notification.

        Returns number of successfully sent messages.
        """
        if not self.bot:
            logger.warning("Telegram bot not configured")
            return 0

        users = await self.user_service.get_users_for_notification("goal_alerts")
        org_users = [u for u in users if str(u["organization_id"]) == organization_id]

        sent_count = 0
        percent = float(achieved_value / target_value * 100) if target_value > 0 else 0

        message = f"""
🎯 <b>Цель достигнута!</b>

📊 {goal_name}
✅ Достигнуто: {achieved_value:,.0f}
🎯 Цель: {target_value:,.0f}
📈 Выполнение: {percent:.1f}%

Отличная работа! 🎉
""".replace(",", " ")

        for user_data in org_users:
            try:
                telegram_id = user_data["telegram_id"]
                success = await self.bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                )
                if success:
                    sent_count += 1
            except Exception as e:
                logger.error(f"Error sending goal alert to {user_data.get('telegram_id')}: {e}")

        logger.info(f"Goal achieved alert sent to {sent_count}/{len(org_users)} users")
        return sent_count

    async def send_sync_error(
        self,
        venue_name: str,
        error_message: str,
        organization_id: str,
    ) -> int:
        """
        Send sync error notification to admins.

        Returns number of successfully sent messages.
        """
        if not self.bot:
            return 0

        users = await self.user_service.get_users_for_notification("anomaly_alerts")
        # Filter to admins/owners only
        admin_users = [
            u
            for u in users
            if str(u["organization_id"]) == organization_id
            and u["user"].role in ("owner", "admin")
        ]

        sent_count = 0

        message = f"""
⚠️ <b>Ошибка синхронизации</b>

📍 Заведение: {venue_name}
❌ Ошибка: {error_message}

Проверьте настройки интеграции в веб-интерфейсе.
"""

        for user_data in admin_users:
            try:
                telegram_id = user_data["telegram_id"]
                success = await self.bot.send_message(
                    chat_id=telegram_id,
                    text=message,
                )
                if success:
                    sent_count += 1
            except Exception as e:
                logger.error(f"Error sending sync error to {user_data.get('telegram_id')}: {e}")

        return sent_count

    async def send_custom_message(
        self,
        telegram_id: int,
        message: str,
        reply_markup=None,
    ) -> bool:
        """
        Send custom message to specific user.

        Returns True if successful.
        """
        if not self.bot:
            return False

        return await self.bot.send_message(
            chat_id=telegram_id,
            text=message,
            reply_markup=reply_markup,
        )

    async def broadcast_message(
        self,
        message: str,
        organization_id: Optional[str] = None,
    ) -> int:
        """
        Broadcast message to all users (or organization users).

        Returns number of successfully sent messages.
        """
        if not self.bot:
            return 0

        users = await self.user_service.get_users_for_notification("morning_report")

        if organization_id:
            users = [u for u in users if str(u["organization_id"]) == organization_id]

        sent_count = 0

        for user_data in users:
            try:
                success = await self.bot.send_message(
                    chat_id=user_data["telegram_id"],
                    text=message,
                )
                if success:
                    sent_count += 1
            except Exception as e:
                logger.error(f"Error broadcasting to {user_data.get('telegram_id')}: {e}")

        return sent_count
