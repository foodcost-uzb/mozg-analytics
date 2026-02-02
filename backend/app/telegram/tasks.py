"""Celery tasks for Telegram notifications."""

import asyncio
import logging
from datetime import date, timedelta
from decimal import Decimal

from celery import shared_task

from app.core.celery_app import celery_app
from app.telegram.formatters import AnomalyData
from app.telegram.notifications import NotificationService

logger = logging.getLogger(__name__)


def run_async(coro):
    """Run async function in sync context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(name="telegram.send_morning_reports")
def send_morning_reports():
    """
    Send morning reports to all subscribed users.

    Scheduled to run at 9:00 AM Moscow time.
    """
    logger.info("Starting morning reports task")

    service = NotificationService()
    sent_count = run_async(service.send_morning_report())

    logger.info(f"Morning reports sent: {sent_count}")
    return {"sent": sent_count}


@celery_app.task(name="telegram.send_evening_reports")
def send_evening_reports():
    """
    Send evening reports to all subscribed users.

    Scheduled to run at 10:00 PM Moscow time.
    """
    logger.info("Starting evening reports task")

    service = NotificationService()
    sent_count = run_async(service.send_evening_report())

    logger.info(f"Evening reports sent: {sent_count}")
    return {"sent": sent_count}


@celery_app.task(name="telegram.send_anomaly_alert")
def send_anomaly_alert_task(
    anomaly_type: str,
    severity: str,
    anomaly_date: str,
    actual_value: float,
    expected_value: float,
    deviation_percent: float,
    metric_name: str,
    description: str,
    organization_id: str,
    possible_causes: list = None,
    product_name: str = None,
):
    """
    Send anomaly alert to organization users.

    Called from anomaly detection service when anomaly is found.
    """
    logger.info(f"Sending anomaly alert: {anomaly_type} for org {organization_id}")

    anomaly = AnomalyData(
        anomaly_type=anomaly_type,
        severity=severity,
        date=date.fromisoformat(anomaly_date),
        actual_value=Decimal(str(actual_value)),
        expected_value=Decimal(str(expected_value)),
        deviation_percent=deviation_percent,
        metric_name=metric_name,
        description=description,
        possible_causes=possible_causes or [],
        product_name=product_name,
    )

    service = NotificationService()
    sent_count = run_async(
        service.send_anomaly_alert(anomaly=anomaly, organization_id=organization_id)
    )

    logger.info(f"Anomaly alert sent: {sent_count}")
    return {"sent": sent_count}


@celery_app.task(name="telegram.send_goal_achieved")
def send_goal_achieved_task(
    goal_name: str,
    achieved_value: float,
    target_value: float,
    organization_id: str,
):
    """
    Send goal achievement notification.

    Called when a goal is reached.
    """
    logger.info(f"Sending goal achieved: {goal_name} for org {organization_id}")

    service = NotificationService()
    sent_count = run_async(
        service.send_goal_achieved(
            goal_name=goal_name,
            achieved_value=Decimal(str(achieved_value)),
            target_value=Decimal(str(target_value)),
            organization_id=organization_id,
        )
    )

    logger.info(f"Goal achieved sent: {sent_count}")
    return {"sent": sent_count}


@celery_app.task(name="telegram.send_sync_error")
def send_sync_error_task(
    venue_name: str,
    error_message: str,
    organization_id: str,
):
    """
    Send sync error notification to admins.

    Called when venue sync fails.
    """
    logger.info(f"Sending sync error for venue {venue_name}")

    service = NotificationService()
    sent_count = run_async(
        service.send_sync_error(
            venue_name=venue_name,
            error_message=error_message,
            organization_id=organization_id,
        )
    )

    return {"sent": sent_count}


@celery_app.task(name="telegram.broadcast_message")
def broadcast_message_task(
    message: str,
    organization_id: str = None,
):
    """
    Broadcast custom message to users.

    For admin announcements.
    """
    logger.info(f"Broadcasting message to org {organization_id or 'all'}")

    service = NotificationService()
    sent_count = run_async(
        service.broadcast_message(message=message, organization_id=organization_id)
    )

    return {"sent": sent_count}


@celery_app.task(name="telegram.check_and_send_anomalies")
def check_and_send_anomalies():
    """
    Check for anomalies and send alerts.

    Runs periodically to detect new anomalies.
    """
    logger.info("Checking for anomalies")

    # This would integrate with AnomalyDetectionService
    # For now, just a placeholder
    from app.telegram.services import TelegramUserService

    async def check_anomalies():
        service = TelegramUserService()
        notification_service = NotificationService()

        users = await service.get_users_for_notification("anomaly_alerts")

        # Group by organization
        org_ids = set(str(u["organization_id"]) for u in users)

        total_sent = 0
        for org_id in org_ids:
            # Get first user from org to fetch data
            org_user = next(u for u in users if str(u["organization_id"]) == org_id)

            # Check for anomalies
            anomalies = await service.get_recent_anomalies(
                user=org_user["user"],
                days=1,  # Only today
                limit=5,
            )

            # Send alerts for high/critical anomalies
            for anomaly in anomalies:
                if anomaly.severity in ("high", "critical"):
                    sent = await notification_service.send_anomaly_alert(
                        anomaly=anomaly,
                        organization_id=org_id,
                    )
                    total_sent += sent

        return total_sent

    sent_count = run_async(check_anomalies())
    logger.info(f"Anomaly alerts sent: {sent_count}")
    return {"sent": sent_count}
