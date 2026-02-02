"""Telegram webhook endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Update

from app.api.deps import get_current_user, get_db
from app.core.config import settings
from app.db.models import Organization, User
from app.telegram.bot import get_bot, setup_webhook, delete_webhook
from app.telegram.services import TelegramUserService

router = APIRouter(prefix="/telegram", tags=["Telegram"])


class WebhookSetupRequest(BaseModel):
    """Webhook setup request."""

    webhook_url: str


class LinkCodeRequest(BaseModel):
    """Link code verification request."""

    code: str


class LinkCodeResponse(BaseModel):
    """Link code verification response."""

    success: bool
    telegram_id: Optional[int] = None
    telegram_username: Optional[str] = None
    first_name: Optional[str] = None
    message: str


# ==================== Webhook Endpoints ====================


@router.post("/webhook")
async def telegram_webhook(request: Request):
    """
    Handle Telegram webhook updates.

    This endpoint receives updates from Telegram and processes them.
    """
    bot = get_bot()
    if not bot:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Telegram bot not configured",
        )

    try:
        data = await request.json()
        update = Update.de_json(data, bot.bot)

        # Process update through handlers
        await bot.application.process_update(update)

        return {"ok": True}

    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}


@router.post("/webhook/setup")
async def setup_telegram_webhook(
    data: WebhookSetupRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Set up Telegram webhook URL.

    Requires admin access.
    """
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    success = await setup_webhook(data.webhook_url)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to setup webhook",
        )

    return {"success": True, "webhook_url": data.webhook_url}


@router.delete("/webhook")
async def remove_telegram_webhook(
    current_user: User = Depends(get_current_user),
):
    """
    Remove Telegram webhook.

    Requires admin access.
    """
    if current_user.role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    success = await delete_webhook()

    return {"success": success}


# ==================== Account Linking ====================


@router.post("/link", response_model=LinkCodeResponse)
async def verify_link_code(
    data: LinkCodeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Verify Telegram link code and associate account.

    Users get a code from the Telegram bot (/link command)
    and enter it here to link their accounts.
    """
    service = TelegramUserService()
    link_data = await service.verify_link_code(data.code.upper())

    if not link_data:
        return LinkCodeResponse(
            success=False,
            message="Неверный или истекший код. Получите новый код командой /link в боте.",
        )

    # Check if telegram_id is already linked to another user
    result = await db.execute(
        select(User).where(User.telegram_id == link_data["telegram_id"])
    )
    existing_user = result.scalar_one_or_none()

    if existing_user and existing_user.id != current_user.id:
        return LinkCodeResponse(
            success=False,
            message="Этот Telegram аккаунт уже привязан к другому пользователю.",
        )

    # Link the account
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(
            telegram_id=link_data["telegram_id"],
            telegram_username=link_data["telegram_username"],
        )
    )
    await db.commit()

    # Send confirmation to Telegram
    bot = get_bot()
    if bot:
        await bot.send_message(
            chat_id=link_data["telegram_id"],
            text=(
                f"✅ <b>Аккаунт успешно привязан!</b>\n\n"
                f"Пользователь: {current_user.email or current_user.first_name}\n"
                f"Организация: {current_user.organization.name if hasattr(current_user, 'organization') else 'N/A'}\n\n"
                f"Теперь вы можете получать уведомления и просматривать аналитику."
            ),
        )

    return LinkCodeResponse(
        success=True,
        telegram_id=link_data["telegram_id"],
        telegram_username=link_data["telegram_username"],
        first_name=link_data["first_name"],
        message="Telegram аккаунт успешно привязан.",
    )


@router.delete("/link")
async def unlink_telegram(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Unlink Telegram account from user.
    """
    if not current_user.telegram_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Telegram аккаунт не привязан",
        )

    telegram_id = current_user.telegram_id

    # Unlink
    await db.execute(
        update(User)
        .where(User.id == current_user.id)
        .values(telegram_id=None, telegram_username=None)
    )
    await db.commit()

    # Notify via Telegram
    bot = get_bot()
    if bot:
        await bot.send_message(
            chat_id=telegram_id,
            text=(
                "ℹ️ <b>Аккаунт отвязан</b>\n\n"
                "Ваш Telegram аккаунт отвязан от MOZG Analytics.\n"
                "Для повторной привязки используйте /link."
            ),
        )

    return {"success": True, "message": "Telegram аккаунт отвязан"}


# ==================== Notification Settings ====================


class NotificationSettingsRequest(BaseModel):
    """Notification settings update request."""

    morning_report: Optional[bool] = None
    evening_report: Optional[bool] = None
    anomaly_alerts: Optional[bool] = None
    goal_alerts: Optional[bool] = None


class NotificationSettingsResponse(BaseModel):
    """Notification settings response."""

    morning_report: bool
    evening_report: bool
    anomaly_alerts: bool
    goal_alerts: bool


@router.get("/notifications/settings", response_model=NotificationSettingsResponse)
async def get_notification_settings(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current notification settings.
    """
    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    settings_data = {}
    if org.settings and "telegram_notifications" in org.settings:
        settings_data = org.settings["telegram_notifications"]

    return NotificationSettingsResponse(
        morning_report=settings_data.get("morning_report", True),
        evening_report=settings_data.get("evening_report", True),
        anomaly_alerts=settings_data.get("anomaly_alerts", True),
        goal_alerts=settings_data.get("goal_alerts", True),
    )


@router.patch("/notifications/settings", response_model=NotificationSettingsResponse)
async def update_notification_settings(
    data: NotificationSettingsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Update notification settings.
    """
    if current_user.role not in ("owner", "admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )

    result = await db.execute(
        select(Organization).where(Organization.id == current_user.organization_id)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    # Update settings
    if org.settings is None:
        org.settings = {}

    if "telegram_notifications" not in org.settings:
        org.settings["telegram_notifications"] = {
            "morning_report": True,
            "evening_report": True,
            "anomaly_alerts": True,
            "goal_alerts": True,
        }

    # Apply updates
    update_data = data.model_dump(exclude_none=True)
    for key, value in update_data.items():
        org.settings["telegram_notifications"][key] = value

    # Force update
    org.settings = dict(org.settings)
    await db.commit()

    return NotificationSettingsResponse(
        morning_report=org.settings["telegram_notifications"]["morning_report"],
        evening_report=org.settings["telegram_notifications"]["evening_report"],
        anomaly_alerts=org.settings["telegram_notifications"]["anomaly_alerts"],
        goal_alerts=org.settings["telegram_notifications"]["goal_alerts"],
    )


# ==================== Bot Info ====================


@router.get("/bot/info")
async def get_bot_info(
    current_user: User = Depends(get_current_user),
):
    """
    Get Telegram bot information.
    """
    bot = get_bot()
    if not bot:
        return {
            "configured": False,
            "message": "Telegram bot not configured",
        }

    try:
        bot_info = await bot.bot.get_me()
        return {
            "configured": True,
            "username": bot_info.username,
            "name": bot_info.first_name,
            "can_join_groups": bot_info.can_join_groups,
            "supports_inline_queries": bot_info.supports_inline_queries,
        }
    except Exception as e:
        return {
            "configured": True,
            "error": str(e),
        }
