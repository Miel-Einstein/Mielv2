"""Configure le bot Telegram de Miel.

  python manage.py telegram_setup --url https://mon-domaine     → webhook (production, Railway)
  python manage.py telegram_setup --poll                         → relève en continu (développement, sans webhook)
  python manage.py telegram_setup --info                         → état du webhook
"""
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from events.services import telegram_link


class Command(BaseCommand):
    help = "Webhook ou relève des messages du bot Telegram (liaison des groupes par jeton)."

    def add_arguments(self, parser):
        parser.add_argument("--url", help="Adresse publique du site, ex. https://miel.up.railway.app")
        parser.add_argument("--poll", action="store_true")
        parser.add_argument("--info", action="store_true")

    def handle(self, url=None, poll=False, info=False, **kw):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN manquant")
        if info:
            self.stdout.write(str(telegram_link.api("getWebhookInfo")))
            return
        if url:
            if len(settings.TELEGRAM_WEBHOOK_SECRET) < 16:
                raise CommandError("TELEGRAM_WEBHOOK_SECRET doit faire au moins 16 caractères")
            hook = url.rstrip("/") + f"/telegram/webhook/{settings.TELEGRAM_WEBHOOK_SECRET}/"
            res = telegram_link.api("setWebhook", url=hook, secret_token=settings.TELEGRAM_WEBHOOK_SECRET,
                                    allowed_updates='["message","channel_post","edited_message","edited_channel_post","my_chat_member"]')
            self.stdout.write(f"Webhook : {res}")
            return
        if poll:
            telegram_link.api("deleteWebhook")
            self.stdout.write("Relève Telegram en cours (Ctrl+C pour arrêter)…")
            offset = None
            while True:
                offset = telegram_link.poll_once(offset, timeout=25)
                time.sleep(0.5)
        raise CommandError("Choisissez --url, --poll ou --info")
