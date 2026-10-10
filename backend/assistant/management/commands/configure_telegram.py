import httpx
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = "Register the Telegram webhook using configured secrets, without printing tokens."
    def add_arguments(self, parser):
        parser.add_argument("url")
    def handle(self, *args, **options):
        from urllib.parse import urlsplit
        uri = urlsplit(options["url"])
        if uri.scheme != "https" or uri.username or uri.password or uri.path != "/v1/telegram/webhook/":
            raise CommandError("Provide https://YOUR_DOMAIN/v1/telegram/webhook/")
        if not settings.TELEGRAM_BOT_TOKEN or not settings.TELEGRAM_WEBHOOK_SECRET or not settings.TELEGRAM_CHAT_ID:
            raise CommandError("Configure Telegram token, chat ID and webhook secret first")
        try:
            result = httpx.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/setWebhook", json={"url": options["url"], "secret_token": settings.TELEGRAM_WEBHOOK_SECRET, "allowed_updates": ["message"]}, timeout=20)
            result.raise_for_status()
            if not result.json().get("ok"):
                raise ValueError("Webhook rejected")
        except Exception:
            raise CommandError("Could not confirm webhook registration; check bot credentials and HTTPS endpoint") from None
        self.stdout.write(self.style.SUCCESS("Telegram webhook registered."))
