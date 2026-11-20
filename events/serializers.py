"""Conversion des modèles en dictionnaires JSON (sans dépendance externe)."""
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from events.models import Reaction, Song, t
from events.services.seating import person_key


def _url(f):
    return f.url if f else ""


def song_data(s):
    if not s:
        return None
    return {"id": s.id, "title": s.title, "artist": s.artist, "audio": _url(s.audio_file), "youtube": s.youtube_url,
            "spotify": s.spotify_url, "cover": _url(s.cover)}


def category_data(c):
    return {"id": c.id, "name": c.name, "is_honor": c.is_honor, "color": c.color, "order": c.order}


def venue_data(v):
    return {"id": v.id, "order": v.order, "name": v.name, "kind": v.kind,
            "start": v.start.strftime("%H:%M") if v.start else "", "end": v.end.strftime("%H:%M") if v.end else "",
            "address": v.address, "lat": v.lat, "lng": v.lng, "image": _url(v.image), "parking": v.parking,
            "entrance": v.entrance, "landmark": v.landmark, "contact": v.contact}


def gallery_data(g):
    return {"id": g.id, "url": _url(g.image)}


def story_data(s):
    return {"id": s.id, "order": s.order, "title": s.title, "text": s.text, "image": _url(s.image)}


def moment_data(m):
    return {"id": m.id, "order": m.order, "title": m.title, "kind": m.kind, "message": m.message, "duration": m.duration,
            "scheduled_at": m.scheduled_at.isoformat() if m.scheduled_at else None, "photo": _url(m.photo),
            "effect": m.effect, "status": m.status, "needs_photo": m.needs_photo,
            "ends_at": m.ends_at.timestamp() * 1000 if m.ends_at else None, "as_message": m.launched_as_message}


def contact_data(c):
    return {"id": c.id, "name": c.name, "title": c.title, "emails": c.emails, "whatsapp": c.whatsapp_numbers,
            "telegram": c.telegram_chat_id, "language": c.language, "consent": c.consent}


def role_data(r):
    return {"id": r.id, "name": r.name, "active": r.active, "contacts": [contact_data(c) for c in r.contacts.all()],
            "tasks": r.tasks.count()}


def alerter_data(i, event):
    due = event.due_date(i.due_offset_days)
    return {"id": i.id, "title": i.title, "due": i.due_offset_days, "due_date": due.isoformat() if due else None,
            "price": float(i.price) if i.price is not None else None, "done": i.done, "active": i.active,
            "role": i.role_id, "kind": i.kind}


def event_data(e):
    return {
        "slug": e.slug, "type": e.type, "title": e.title, "subtitle": e.subtitle,
        "date": e.date.isoformat() if e.date else "", "time": e.start_time.strftime("%H:%M") if e.start_time else "",
        "timezone": e.timezone, "languages": e.languages, "services": e.services, "card_template": e.card_template,
        "site_template": e.site_template, "cover_image": _url(e.cover_image), "cover_image_2": _url(e.cover_image_2),
        "kids_invited": e.kids_invited, "kids_table": e.kids_table, "age_with_parents": e.age_with_parents,
        "age_kids_max": e.age_kids_max, "baby_chair": e.baby_chair, "supervisor_name": e.supervisor_name,
        "max_companions": e.max_companions, "ask_languages": e.ask_languages,
        "conversation_languages": e.conversation_languages, "budget": float(e.budget), "currency": e.currency,
        "guest_target": e.guest_target, "song": e.song_id, "telegram_chat_id": e.telegram_chat_id,
        "social_links": e.social_links, "table_config": e.table_config,
        "start_ms": e.start_datetime().timestamp() * 1000 if e.start_datetime() else None,
        "urls": {"rsvp": e.public_url("rsvp"), "site": e.public_url("event_home"), "wall": e.public_url("wall"),
                 "screen": e.public_url("screen"), "map": e.public_url("map"),
                 "share": settings.SITE_URL + reverse("share_link", kwargs={"token": e.share_token})},
        "categories": [category_data(c) for c in e.categories.all()],
        "venues": [venue_data(v) for v in e.venues.all()],
        "story": [story_data(s) for s in e.story.all()],
        "site_bg": e.site_bg or {"mode": "default"}, "site_bg_image": _url(e.site_bg_image),
        "couple": e.couple or {}, "partner1_image": _url(e.partner1_image), "partner2_image": _url(e.partner2_image),
        "gallery": [gallery_data(g) for g in e.gallery.all()],
        "moments": [moment_data(m) for m in e.moments.all()],
        "roles": [role_data(r) for r in e.roles.prefetch_related("contacts")],
        "alerter": [alerter_data(i, e) for i in e.alerter_items.all()],
        "songs": [song_data(s) for s in Song.objects.filter(active=True)],
    }


def guest_data(g):
    return {"id": g.id, "first_name": g.first_name, "last_name": g.last_name, "email": g.email, "attending": g.attending,
            "category": g.category_id, "languages": g.table_languages(), "nav_language": g.nav_language,
            "companions": [c.first_name for c in g.companions.all()],
            "children": [{"name": c.first_name, "age": c.age} for c in g.children.all()],
            "arrived": g.arrived, "arrived_at": g.arrived_at.isoformat() if g.arrived_at else None,
            "key": person_key(g.id, "p")}


def wish_data(w, token=None):
    counts = {e: 0 for e in Reaction.EMOJIS}
    mine = []
    for r in w.reactions.all():
        counts[r.emoji] = counts.get(r.emoji, 0) + 1
        if token and r.token == token:
            mine.append(r.emoji)
    return {"id": w.id, "author": w.author_name, "text": w.text, "created": w.created_at.isoformat(),
            "reactions": counts, "mine": mine, "own": bool(token and w.author_token == token)}


def live_moment(event):
    """Le moment en cours (compte à rebours ou révélation encore affichée)."""
    now = timezone.now()
    m = event.moments.filter(status="launched", ends_at__isnull=False).order_by("-ends_at").first()
    if not m or (now - m.ends_at).total_seconds() > 14:
        return None
    d = moment_data(m)
    if m.launched_as_message:
        d["kind"] = "message"
        d["photo"] = ""
    return d


def title_for(value, lang):
    return t(value, lang)
