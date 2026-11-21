"""Liaison des groupes et canaux Telegram par jeton.

1. Miel génère un jeton de 64 caractères pour chaque événement.
2. L'organisateur ajoute le bot Miel dans son groupe (ou comme administrateur de son canal) et y colle le jeton,
   ou utilise le lien « Ajouter à un groupe » (t.me/<bot>?startgroup=<jeton>).
3. Le bot reçoit le message (webhook ou relève), reconnaît le jeton, enregistre le groupe et répond dans le groupe.
   Il essaie aussi d'effacer le message qui contient le jeton.
Ensuite, chaque photo ou vidéo envoyée depuis le mur des vœux part en direct vers tous les groupes reliés.

Dans les groupes, le bot ne lit un message ordinaire que si son « mode privé » est désactivé
(BotFather → /setprivacy → Disable) ou s'il est administrateur. Le lien « startgroup » marche dans tous les cas.
"""
import logging
import re
import secrets

import requests
from django.conf import settings

log = logging.getLogger(__name__)
TOKEN_RE = re.compile(r"\b[a-f0-9]{64}\b")

LINKED = {
    "fr": "✅ Ce {where} est relié à « {title} » sur Miel. Les photos et vidéos du mur des vœux arriveront ici en direct. 📸",
    "en": "✅ This {where} is now linked to “{title}” on Miel. Photos and videos from the wishes wall will arrive here live. 📸",
    "it": "✅ Questo {where} è collegato a «{title}» su Miel. Le foto e i video del muro degli auguri arriveranno qui in diretta. 📸",
    "ln": "✅ {where} oyo ekangami na « {title} » na Miel. Bililí mpe ba vidéo ya mur ya bilaka ekoya awa mbala moko. 📸",
}
WHERE = {"fr": ("groupe", "canal"), "en": ("group", "channel"), "it": ("gruppo", "canale"), "ln": ("lisanga", "canal")}


def ensure_token(event):
    if not event.telegram_token:
        event.telegram_token = secrets.token_hex(32)
        event.save(update_fields=["telegram_token"])
    return event.telegram_token


def regenerate_token(event):
    event.telegram_token = secrets.token_hex(32)
    event.save(update_fields=["telegram_token"])
    return event.telegram_token


def api(method, **data):
    if not settings.TELEGRAM_BOT_TOKEN:
        return None
    try:
        r = requests.post(f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}", data=data, timeout=10)
        return r.json() if r.ok else None
    except requests.RequestException as exc:  # pragma: no cover
        log.warning("Telegram %s : %s", method, exc)
        return None


def handle_update(update):
    """Traite une mise à jour Telegram ; renvoie le TelegramChannel relié, ou None."""
    from events.models import Event, TelegramChannel
    from events.services.realtime import broadcast
    from events.ui_i18n import user_ui_lang

    # Le bot a été retiré d'un groupe : on désactive ce groupe.
    member = update.get("my_chat_member")
    if member:
        status = (member.get("new_chat_member") or {}).get("status")
        if status in ("left", "kicked"):
            for ch in TelegramChannel.objects.filter(chat_id=str(member["chat"]["id"]), active=True):
                ch.active = False
                ch.save(update_fields=["active"])
                broadcast(ch.event, "telegram", {})
        return None

    msg = update.get("message") or update.get("channel_post") or update.get("edited_message") or update.get("edited_channel_post")
    if not msg:
        return None
    chat = msg.get("chat") or {}
    # Un groupe devenu « supergroupe » change d'identifiant.
    if msg.get("migrate_to_chat_id"):
        TelegramChannel.objects.filter(chat_id=str(chat.get("id"))).update(chat_id=str(msg["migrate_to_chat_id"]))
        return None
    text = msg.get("text") or msg.get("caption") or ""
    m = TOKEN_RE.search(text)
    if not m or chat.get("type") == "private":
        return None
    event = Event.objects.filter(telegram_token=m.group(0)).first()
    if not event:
        return None
    ch, _ = TelegramChannel.objects.update_or_create(
        event=event, chat_id=str(chat["id"]),
        defaults={"title": chat.get("title") or chat.get("username") or "Telegram", "kind": chat.get("type", ""), "active": True})
    lang = user_ui_lang(event.owner)
    where = WHERE.get(lang, WHERE["fr"])[1 if chat.get("type") == "channel" else 0]
    api("sendMessage", chat_id=chat["id"], text=LINKED.get(lang, LINKED["fr"]).format(where=where, title=event.title_in(lang if lang in event.languages else event.languages[0])))
    api("deleteMessage", chat_id=chat["id"], message_id=msg.get("message_id"))  # le jeton ne reste pas visible (si le bot en a le droit)
    broadcast(event, "telegram", {"title": ch.title})
    return ch


def poll_once(offset=None, timeout=0):
    """Relève les mises à jour (si aucun webhook n'est configuré). Renvoie le prochain offset."""
    data = {"timeout": timeout, "allowed_updates": '["message","channel_post","edited_message","edited_channel_post","my_chat_member"]'}
    if offset:
        data["offset"] = offset
    res = api("getUpdates", **data) or {}
    for upd in res.get("result", []):
        try:
            handle_update(upd)
        except Exception as exc:  # pragma: no cover
            log.exception("Mise à jour Telegram ignorée : %s", exc)
        offset = upd["update_id"] + 1
    return offset
