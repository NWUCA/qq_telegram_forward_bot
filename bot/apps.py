import logging

import telebot
from django.apps import AppConfig
from django.conf import settings

logger = logging.getLogger(__name__)


class BotConfig(AppConfig):
    name = 'bot'

    def ready(self):
        # 注册 Telegram bot 的 webhook
        bot = telebot.TeleBot(settings.TELEGRAM_API_TOKEN)
        bot.remove_webhook()
        res = bot.set_webhook(url=settings.TELEGRAM_WEBHOOK_URL)
        logger.info(f"Set webhook result {res}")
