"""Telegram bot setup and configuration."""

from functools import lru_cache
from typing import Optional

from telegram import Bot, Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.core.config import settings
from app.telegram.handlers import commands, callbacks


class TelegramBot:
    """Telegram bot wrapper for MOZG Analytics."""

    def __init__(self, token: str):
        self.token = token
        self._bot: Optional[Bot] = None
        self._application: Optional[Application] = None

    @property
    def bot(self) -> Bot:
        """Get bot instance."""
        if self._bot is None:
            self._bot = Bot(token=self.token)
        return self._bot

    @property
    def application(self) -> Application:
        """Get application instance with handlers."""
        if self._application is None:
            self._application = self._build_application()
        return self._application

    def _build_application(self) -> Application:
        """Build application with all handlers."""
        app = ApplicationBuilder().token(self.token).build()

        # Command handlers
        app.add_handler(CommandHandler("start", commands.start_handler))
        app.add_handler(CommandHandler("help", commands.help_handler))
        app.add_handler(CommandHandler("sales", commands.sales_handler))
        app.add_handler(CommandHandler("today", commands.today_handler))
        app.add_handler(CommandHandler("week", commands.week_handler))
        app.add_handler(CommandHandler("month", commands.month_handler))
        app.add_handler(CommandHandler("forecast", commands.forecast_handler))
        app.add_handler(CommandHandler("alerts", commands.alerts_handler))
        app.add_handler(CommandHandler("venues", commands.venues_handler))
        app.add_handler(CommandHandler("report", commands.report_handler))
        app.add_handler(CommandHandler("settings", commands.settings_handler))
        app.add_handler(CommandHandler("link", commands.link_handler))

        # Callback query handlers (inline keyboard buttons)
        app.add_handler(CallbackQueryHandler(callbacks.venue_callback, pattern=r"^venue:"))
        app.add_handler(CallbackQueryHandler(callbacks.period_callback, pattern=r"^period:"))
        app.add_handler(CallbackQueryHandler(callbacks.report_callback, pattern=r"^report:"))
        app.add_handler(CallbackQueryHandler(callbacks.settings_callback, pattern=r"^settings:"))
        app.add_handler(CallbackQueryHandler(callbacks.notification_callback, pattern=r"^notify:"))
        app.add_handler(CallbackQueryHandler(callbacks.back_callback, pattern=r"^back:"))

        # Error handler
        app.add_error_handler(self._error_handler)

        return app

    async def _error_handler(
        self, update: object, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle errors in bot."""
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Telegram bot error: {context.error}", exc_info=context.error)

        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Произошла ошибка. Попробуйте позже или обратитесь в поддержку."
            )

    async def send_message(
        self,
        chat_id: int,
        text: str,
        parse_mode: str = "HTML",
        reply_markup=None,
        disable_notification: bool = False,
    ) -> bool:
        """Send message to user."""
        try:
            await self.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                disable_notification=disable_notification,
            )
            return True
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send message to {chat_id}: {e}")
            return False

    async def send_document(
        self,
        chat_id: int,
        document: bytes,
        filename: str,
        caption: str = None,
    ) -> bool:
        """Send document to user."""
        try:
            from io import BytesIO

            file = BytesIO(document)
            file.name = filename

            await self.bot.send_document(
                chat_id=chat_id,
                document=file,
                caption=caption,
                parse_mode="HTML",
            )
            return True
        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send document to {chat_id}: {e}")
            return False


_bot_instance: Optional[TelegramBot] = None


def get_bot() -> Optional[TelegramBot]:
    """Get global bot instance."""
    global _bot_instance

    if _bot_instance is None and settings.TELEGRAM_BOT_TOKEN:
        _bot_instance = TelegramBot(settings.TELEGRAM_BOT_TOKEN)

    return _bot_instance


async def setup_webhook(webhook_url: str) -> bool:
    """Set up Telegram webhook."""
    bot = get_bot()
    if not bot:
        return False

    try:
        await bot.bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"],
        )
        return True
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Failed to setup webhook: {e}")
        return False


async def delete_webhook() -> bool:
    """Delete Telegram webhook."""
    bot = get_bot()
    if not bot:
        return False

    try:
        await bot.bot.delete_webhook()
        return True
    except Exception:
        return False
