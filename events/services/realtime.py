"""Diffusion temps réel vers les pages ouvertes d'un événement (WebSockets)."""
import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.utils import timezone

log = logging.getLogger(__name__)


def group_name(event):
    return f"event-{event.id}"


def broadcast(event, kind, payload=None):
    layer = get_channel_layer()
    if layer is None:
        return
    message = {"type": "event.message", "kind": kind, "payload": payload or {}, "server_now": timezone.now().timestamp() * 1000}
    try:
        async_to_sync(layer.group_send)(group_name(event), message)
    except Exception as exc:  # pragma: no cover - ne doit jamais casser une requête
        log.warning("Diffusion temps réel impossible : %s", exc)
