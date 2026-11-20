"""Envoi des messages de l'Alerter : e-mail, Telegram, WhatsApp (préparé)."""
import logging

import requests
from django.conf import settings
from django.core.mail import send_mail

log = logging.getLogger(__name__)


def send_email(to, subject, body):
    to = [a for a in (to or []) if a]
    if not to:
        return False
    try:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, to, fail_silently=False)
        return True
    except Exception as exc:  # pragma: no cover - dépend du serveur SMTP
        log.warning("E-mail non envoyé à %s : %s", to, exc)
        return False


def send_telegram(chat_id, text):
    if not (settings.TELEGRAM_BOT_TOKEN and chat_id):
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            data={"chat_id": chat_id, "text": text}, timeout=10,
        )
        return r.ok
    except requests.RequestException as exc:  # pragma: no cover
        log.warning("Telegram non envoyé : %s", exc)
        return False


def send_telegram_media(chat_id, file_obj, caption="", is_video=False):
    """Envoie une photo ou une vidéo du mur des vœux au groupe Telegram."""
    if not (settings.TELEGRAM_BOT_TOKEN and chat_id):
        return False
    method, field = ("sendVideo", "video") if is_video else ("sendPhoto", "photo")
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
            data={"chat_id": chat_id, "caption": caption[:1000]},
            files={field: (file_obj.name, file_obj.read())}, timeout=60,
        )
        return r.ok
    except requests.RequestException as exc:  # pragma: no cover
        log.warning("Média Telegram non envoyé : %s", exc)
        return False


def send_whatsapp(number, text):
    """WhatsApp Business API : actif seulement si WHATSAPP_TOKEN est configuré."""
    if not (settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_ID and number):
        log.info("WhatsApp non configuré : message pour %s mis de côté", number)
        return False
    try:  # pragma: no cover - nécessite un compte Meta validé
        r = requests.post(
            f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_ID}/messages",
            headers={"Authorization": f"Bearer {settings.WHATSAPP_TOKEN}"},
            json={"messaging_product": "whatsapp", "to": number.replace(" ", ""), "type": "text", "text": {"body": text}},
            timeout=10,
        )
        return r.ok
    except requests.RequestException as exc:
        log.warning("WhatsApp non envoyé : %s", exc)
        return False


def notify_contact(contact, subject, text):
    sent = False
    sent |= send_email(contact.emails, subject, text)
    if contact.consent:
        for n in contact.whatsapp_numbers:
            sent |= send_whatsapp(n, text)
    sent |= send_telegram(contact.telegram_chat_id, text)
    return sent


def notify_owner(event, subject, text):
    return send_email([event.owner.email], subject, text)
