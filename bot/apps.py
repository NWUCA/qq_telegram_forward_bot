from django.apps import AppConfig
import telebot
from django.conf import settings


class BotConfig(AppConfig):
    name = 'bot'

    def ready(self):
        telebot.apihelper.RETRY_ON_ERROR = True

        # 注册 Telegram bot 的 webhook
        bot = telebot.TeleBot(settings.TELEGRAM_API_TOKEN)
        bot.remove_webhook()
        bot.set_webhook(url=settings.TELEGRAM_WEBHOOK_URL)
