"""API JSON.

- /api/e/<slug>/...  : réservée à l'organisateur connecté (propriétaire de l'événement)
- /api/p/<slug>/...  : publique (invités) ; l'identité passe par le jeton personnel
"""
import json
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from events import serializers as S
from events.models import (CARD_TEMPLATES, AlerterItem, BotSession, Category, Child, Companion, Contact, DeliveryOption, Event, Gift,
                           GalleryImage, GiftReservation, TelegramChannel, Guest, Moment, Reaction, Role, StoryStep, Table, Venue, Visitor, Wish, t)
from events.services import alerter, notify, seating
from events.services.defaults import CATEGORY_COLORS, reset_alerter
from events.services.realtime import broadcast


# ---------------------------------------------------------------- outils
def body(request):
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            return json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return {}
    return request.POST.dict()


def ok(data=None, status=200):
    return JsonResponse(data if data is not None else {"ok": True}, status=status, safe=False)


def err(msg, status=400):
    return JsonResponse({"error": msg}, status=status)


def owner_api(view):
    @wraps(view)
    @login_required
    def wrapper(request, slug, *args, **kwargs):
        event = get_object_or_404(Event, slug=slug)
        if event.owner_id != request.user.id and not request.user.is_superuser:
            raise Http404
        return view(request, event, *args, **kwargs)

    return wrapper


def public_api(view):
    @wraps(view)
    def wrapper(request, slug, *args, **kwargs):
        event = get_object_or_404(Event, slug=slug)
        return view(request, event, *args, **kwargs)

    return wrapper


def as_lang_dict(value, langs):
    if isinstance(value, dict):
        return {k: str(v).strip() for k, v in value.items() if k in langs or k == "fr"}
    return {langs[0] if langs else "fr": str(value or "").strip()}


def parse_time(v):
    if not v:
        return None
    try:
        return datetime.strptime(v[:5], "%H:%M").time()
    except ValueError:
        return None


def identity(event, token):
    """Invité (carte) ou visiteur (nom saisi sur le mur) correspondant au jeton."""
    if not token:
        return None
    g = event.guests.filter(token=token).first()
    if g:
        return {"token": g.token, "name": g.full_name, "first": g.first_name, "guest": g}
    v = event.visitors.filter(token=token).first()
    if v:
        return {"token": v.token, "name": v.name, "first": v.name.split(" ")[0], "guest": None}
    return None


# ---------------------------------------------------------------- préférences
@require_http_methods(["POST"])
def my_theme(request):
    from events.models import UserSettings
    from events.themes import KEYS
    if not request.user.is_authenticated:
        return err("Connexion requise", 401)
    theme = body(request).get("theme")
    if theme not in KEYS:
        return err("Palette inconnue")
    UserSettings.objects.update_or_create(user=request.user, defaults={"theme": theme})
    return ok({"theme": theme})


@require_http_methods(["POST"])
def my_ui_lang(request):
    from events.models import UserSettings
    from events.ui_i18n import COOKIE, UI_LANGS
    if not request.user.is_authenticated:
        return err("Connexion requise", 401)
    lang = body(request).get("lang")
    if lang not in UI_LANGS:
        return err("Langue inconnue")
    UserSettings.objects.update_or_create(user=request.user, defaults={"ui_lang": lang})
    resp = ok({"lang": lang})
    resp.set_cookie(COOKIE, lang, max_age=365 * 24 * 3600, samesite="Lax")
    return resp


# ---------------------------------------------------------------- aide de l'assistant
def _help_lang(request, d):
    from events.ui_i18n import UI_LANGS, ui_lang_for
    lang = d.get("lang") or ui_lang_for(request)
    return lang if lang in UI_LANGS else "fr"


@require_http_methods(["POST"])
@login_required
def help_ask(request):
    """Question libre : meilleure réponse (avec actions), autres pistes ; sinon la question est enregistrée pour l'admin."""
    from events.models import HelpEntry
    from events.services import help as H
    d = body(request)
    q, lang, ctx = (d.get("q") or "").strip()[:500], _help_lang(request, d), (d.get("context") or "")[:40]
    if not q:
        return err("Question vide")
    best, score, alts = H.search(q, lang, ctx)
    if best:
        HelpEntry.objects.filter(pk=best.pk).update(hits=best.hits + 1)
        return ok({"found": H.entry_payload(best, lang), "alts": [{"id": a.id, "question": H.localized(a.question, lang)} for a in alts]})
    event = Event.objects.filter(slug=d.get("event"), owner=request.user).first() if d.get("event") else None
    H.log_unanswered(q, lang, ctx, request.user, event)
    return ok({"found": None, "alts": [{"id": a.id, "question": H.localized(a.question, lang)} for a in alts]})


@require_http_methods(["GET"])
@login_required
def help_entry(request, pk):
    from events.models import HelpEntry
    from events.services import help as H
    e = get_object_or_404(HelpEntry, pk=pk, active=True)
    HelpEntry.objects.filter(pk=e.pk).update(hits=e.hits + 1)
    return ok(H.entry_payload(e, _help_lang(request, request.GET)))


@require_http_methods(["GET"])
@login_required
def help_here(request):
    """Aide de l'écran en cours (proposée après 30 s sans action) : réponse liée à l'étape ou à la page."""
    from events.models import HelpEntry
    from events.services import help as H
    ctx = (request.GET.get("context") or "")[:40]
    e = (HelpEntry.objects.filter(active=True, context=ctx).order_by("id").first() if ctx else None) or HelpEntry.objects.filter(key="bot-section").first()
    if not e:
        return err("Aucune aide", 404)
    return ok(H.entry_payload(e, _help_lang(request, request.GET)))


@require_http_methods(["POST"])
@login_required
def help_feedback(request, pk):
    from django.db.models import F
    from events.models import HelpEntry
    useful = bool(body(request).get("useful"))
    HelpEntry.objects.filter(pk=pk).update(**({"helpful": F("helpful") + 1} if useful else {"not_helpful": F("not_helpful") + 1}))
    return ok({"thanks": True})


# ---------------------------------------------------------------- événement
EVENT_FIELDS = {"type", "title", "subtitle", "date", "time", "timezone", "languages", "services", "card_template",
                "site_template", "kids_invited", "kids_table", "age_with_parents", "age_kids_max", "baby_chair",
                "supervisor_name", "max_companions", "ask_languages", "conversation_languages", "budget", "currency",
                "guest_target", "song", "telegram_chat_id", "social_links", "couple", "site_bg", "plan_header", "card_message", "card_theme", "cover_focus"}


@require_http_methods(["GET", "PATCH", "POST"])
@owner_api
def event_detail(request, event):
    if request.method == "GET":
        return ok(S.event_data(event))
    data = body(request)
    type_changed = "type" in data and data["type"] != event.type
    for k, v in data.items():
        if k not in EVENT_FIELDS:
            continue
        if k == "date":
            event.date = datetime.strptime(v, "%Y-%m-%d").date() if v else None
        elif k == "time":
            event.start_time = parse_time(v) or event.start_time
        elif k == "site_template":
            if v not in ("A", "B", "C"):
                return err("Modèle de site inconnu")
            event.site_template = v
        elif k == "site_bg":
            if not isinstance(v, dict):
                return err("Format invalide")
            hexok = lambda c: isinstance(c, str) and len(c) == 7 and c[0] == "#" and all(x in "0123456789abcdefABCDEF" for x in c[1:])
            mode = v.get("mode") if v.get("mode") in ("default", "color", "gradient", "image") else "default"
            event.site_bg = {"mode": mode, "c1": v.get("c1") if hexok(v.get("c1")) else "#faf6ef", "c2": v.get("c2") if hexok(v.get("c2")) else "#e7d4ad",
                             "veil": max(0, min(85, int(v.get("veil") or 0))), "tone": "dark" if v.get("tone") == "dark" else "light",
                             "scope": "all" if v.get("scope") == "all" else "site"}
        elif k == "plan_header":
            if not isinstance(v, dict):
                return err("Format invalide")
            texts = {}
            for l, tx in (v.get("texts") or {}).items():
                if l in event.languages and isinstance(tx, dict):
                    texts[l] = {f: str(tx[f])[:120] for f in ("title", "tagline", "names", "place") if f in tx and tx[f] is not None}
            event.plan_header = {"monogram": str(v.get("monogram") or "")[:20], "stats": bool(v.get("stats", True)), "texts": texts}
        elif k == "couple":
            if not isinstance(v, dict):
                return err("Format invalide")
            event.couple = {p: {"name": str((v.get(p) or {}).get("name", ""))[:80],
                                "text": {l: str(t)[:1500] for l, t in ((v.get(p) or {}).get("text") or {}).items() if l in event.languages}}
                            for p in ("p1", "p2")}
        elif k == "song":
            event.song_id = int(v) if v else None
        elif k == "budget":
            try:
                event.budget = Decimal(str(v or 0))
            except InvalidOperation:
                return err("Budget invalide")
        elif k in ("title", "subtitle"):
            setattr(event, k, as_lang_dict(v, data.get("languages", event.languages)))
        elif k in ("card_message", "card_theme"):
            setattr(event, k, {l: str(x)[:160] for l, x in (as_lang_dict(v, event.languages) or {}).items() if x})
        elif k == "card_template":
            if v not in dict(CARD_TEMPLATES):
                return err("Modèle de carte inconnu")
            event.card_template = v
        elif k == "cover_focus":
            if not isinstance(v, dict):
                return err("Format invalide")
            num = lambda x, a, b, d: max(a, min(b, float(x))) if isinstance(x, (int, float)) else d
            focus = dict(event.cover_focus or {})
            for f in ("cover_image", "cover_image_2"):
                if isinstance(v.get(f), dict):
                    focus[f] = {"x": round(num(v[f].get("x"), 0, 100, 50), 2), "y": round(num(v[f].get("y"), 0, 100, 50), 2), "z": round(num(v[f].get("z"), 1, 3, 1), 3)}
            event.cover_focus = focus
        elif k == "languages":
            langs = [l for l in v if l in ("fr", "en", "it", "ln")]
            if not langs:
                return err("Choisissez au moins une langue")
            event.languages = langs
        elif k == "services":
            services = list(dict.fromkeys(["carte", *v]))
            if event.type != "mariage" and data.get("type", event.type) != "mariage":
                services = [s for s in services if s != "site"]
            event.services = services
        else:
            setattr(event, k, v)
    if event.type != "mariage":
        event.services = [s for s in event.services if s != "site"]
    event.age_kids_max = max(event.age_kids_max, event.age_with_parents)
    event.save()
    if type_changed:
        reset_alerter(event)
    if {"kids_invited", "kids_table", "age_with_parents", "age_kids_max", "baby_chair"} & set(data):
        seating.clean_seats(event)
    return ok(S.event_data(event))


@require_http_methods(["POST"])
@owner_api
def event_upload(request, event):
    field = request.POST.get("field")
    f = request.FILES.get("file")
    if field not in ("cover_image", "cover_image_2", "partner1_image", "partner2_image", "site_bg_image") or not f:
        return err("Fichier manquant")
    setattr(event, field, f)
    if field in ("cover_image", "cover_image_2"):
        event.cover_focus = {k: v for k, v in (event.cover_focus or {}).items() if k != field}  # nouvelle photo : cadrage remis au centre
    event.save()
    return ok({"url": getattr(event, field).url})


@require_http_methods(["PUT", "POST"])
@owner_api
def categories(request, event):
    items = json.loads(request.body or b"[]")
    if not items:
        return err("Gardez au moins une catégorie")
    keep = []
    with transaction.atomic():
        for i, it in enumerate(items):
            c = event.categories.filter(id=it.get("id")).first() if it.get("id") else None
            c = c or Category(event=event)
            c.order, c.name, c.is_honor = i, as_lang_dict(it.get("name"), event.languages), bool(it.get("is_honor"))
            c.color = it.get("color") or CATEGORY_COLORS[i % len(CATEGORY_COLORS)]
            c.save()
            keep.append(c.id)
        event.categories.exclude(id__in=keep).delete()
    return ok([S.category_data(c) for c in event.categories.all()])


@require_http_methods(["PUT", "POST"])
@owner_api
def venues(request, event):
    items = json.loads(request.body or b"[]")
    keep = []
    with transaction.atomic():
        for i, it in enumerate(items):
            v = event.venues.filter(id=it.get("id")).first() if it.get("id") else None
            v = v or Venue(event=event)
            v.order, v.name = i, as_lang_dict(it.get("name"), event.languages)
            v.kind = it.get("kind") or "ceremonie"
            v.start, v.end = parse_time(it.get("start")), parse_time(it.get("end"))
            for f in ("address", "parking", "entrance", "landmark", "contact"):
                setattr(v, f, (it.get(f) or "")[:255])
            v.lat = float(it["lat"]) if it.get("lat") not in (None, "") else None
            v.lng = float(it["lng"]) if it.get("lng") not in (None, "") else None
            v.save()
            keep.append(v.id)
        event.venues.exclude(id__in=keep).delete()
    return ok([S.venue_data(v) for v in event.venues.all()])


@require_http_methods(["PUT", "POST"])
@owner_api
def story(request, event):
    items = json.loads(request.body or b"[]")
    keep = []
    with transaction.atomic():
        for i, it in enumerate(items):
            s = event.story.filter(id=it.get("id")).first() if it.get("id") else None
            s = s or StoryStep(event=event)
            s.order, s.title, s.text = i, as_lang_dict(it.get("title"), event.languages), as_lang_dict(it.get("text"), event.languages)
            s.save()
            keep.append(s.id)
        event.story.exclude(id__in=keep).delete()
    return ok([S.story_data(s) for s in event.story.all()])


@require_http_methods(["POST"])
@owner_api
def story_image(request, event, pk):
    s = get_object_or_404(StoryStep, pk=pk, event=event)
    if not request.FILES.get("file"):
        return err("Fichier manquant")
    s.image = request.FILES["file"]
    s.save()
    return ok(S.story_data(s))


@require_http_methods(["GET"])
@owner_api
def plan_header_defaults(request, event):
    """Textes d'en-tête affichés si l'organisateur ne les change pas (pour pré-remplir le formulaire)."""
    from events.services import plan_svg
    saved = event.plan_header
    event.plan_header = {}
    data = {l: plan_svg.header_texts(event, l) for l in event.languages}
    event.plan_header = saved
    return ok(data)


@require_http_methods(["POST"])
@owner_api
def tables_theme(request, event):
    from events.services.table_themes import apply_theme
    try:
        apply_theme(event, body(request).get("theme"))
    except KeyError:
        return err("Thème inconnu")
    return ok(tables_payload(event))


def telegram_payload(event):
    from django.conf import settings
    from events.services.telegram_link import ensure_token
    token = ensure_token(event)
    bot = settings.TELEGRAM_BOT_USERNAME
    return {"token": token, "bot": bot, "configured": bool(settings.TELEGRAM_BOT_TOKEN),
            "group_link": f"https://t.me/{bot}?startgroup={token}" if bot else "",
            "channel_link": f"https://t.me/{bot}?startchannel&admin=post_messages+delete_messages" if bot else "",
            "channels": [{"id": c.id, "title": c.title, "kind": c.kind, "active": c.active} for c in event.telegram_channels.all()]}


@require_http_methods(["GET", "POST"])
@owner_api
def telegram(request, event):
    """GET : jeton et groupes reliés. POST {"regenerate": true} : nouveau jeton (l'ancien ne marche plus)."""
    if request.method == "POST" and body(request).get("regenerate"):
        from events.services.telegram_link import regenerate_token
        regenerate_token(event)
    return ok(telegram_payload(event))


@require_http_methods(["DELETE"])
@owner_api
def telegram_channel(request, event, pk):
    get_object_or_404(TelegramChannel, pk=pk, event=event).delete()
    return ok(telegram_payload(event))


@csrf_exempt
@require_http_methods(["POST"])
def telegram_webhook(request, secret):
    """Point d'entrée des mises à jour Telegram (setWebhook avec le même secret)."""
    from django.conf import settings
    from events.services.telegram_link import handle_update
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if not expected or secret != expected or request.headers.get("X-Telegram-Bot-Api-Secret-Token", expected) != expected:
        raise Http404
    try:
        handle_update(json.loads(request.body or b"{}"))
    except Exception:  # Telegram renverrait la même mise à jour en boucle : on répond toujours 200
        pass
    return JsonResponse({"ok": True})


@require_http_methods(["GET", "POST"])
@owner_api
def gallery(request, event):
    if request.method == "POST":
        files = request.FILES.getlist("file")
        if not files:
            return err("Fichier manquant")
        if event.gallery.count() + len(files) > 40:
            return err("La galerie est limitée à 40 photos")
        start = event.gallery.count()
        for i, f in enumerate(files):
            GalleryImage.objects.create(event=event, image=f, order=start + i)
    return ok([S.gallery_data(g) for g in event.gallery.all()])


@require_http_methods(["DELETE"])
@owner_api
def gallery_item(request, event, pk):
    get_object_or_404(GalleryImage, pk=pk, event=event).delete()
    return ok([S.gallery_data(g) for g in event.gallery.all()])


# ---------------------------------------------------------------- bot
@require_http_methods(["GET", "PUT", "POST"])
@owner_api
def bot_state(request, event):
    bot, _ = BotSession.objects.get_or_create(event=event)
    if request.method != "GET":
        data = body(request)
        bot.step = data.get("step", bot.step)[:40]
        bot.log = data.get("log", bot.log)[-200:]
        bot.paused = bool(data.get("paused", False))
        bot.save()
    return ok({"step": bot.step, "log": bot.log, "paused": bot.paused})


# ---------------------------------------------------------------- alerter, rôles, contacts
@require_http_methods(["GET", "POST"])
@owner_api
def alerter_list(request, event):
    if request.method == "POST":
        d = body(request)
        if not d.get("title"):
            return err("Titre manquant")
        AlerterItem.objects.create(event=event, title=d["title"][:200], due_offset_days=int(d.get("due", -14)),
                                   price=Decimal(str(d["price"])) if d.get("price") not in (None, "") else None,
                                   role_id=d.get("role") or None)
    return ok([S.alerter_data(i, event) for i in event.alerter_items.all()])


@require_http_methods(["PATCH", "POST", "DELETE"])
@owner_api
def alerter_item(request, event, pk):
    i = get_object_or_404(AlerterItem, pk=pk, event=event)
    if request.method == "DELETE":
        i.delete()
        return ok()
    d = body(request)
    for f in ("title", "done", "active"):
        if f in d:
            setattr(i, f, d[f])
    if "due" in d:
        i.due_offset_days = int(d["due"])
    if "price" in d:
        i.price = Decimal(str(d["price"])) if d["price"] not in (None, "") else None
    if "role" in d:
        i.role = event.roles.filter(id=d["role"]).first() if d["role"] else None
    i.save()
    return ok(S.alerter_data(i, event))


@require_http_methods(["POST"])
@owner_api
def alerter_reset(request, event):
    reset_alerter(event)
    return ok([S.alerter_data(i, event) for i in event.alerter_items.all()])


def _contact_from(event, d):
    emails = [e.strip() for e in (d.get("emails") or ([d["email"]] if d.get("email") else [])) if e and e.strip()]
    was = [w.strip() for w in (d.get("whatsapp") or ([d["wa"]] if d.get("wa") else [])) if w and w.strip()]
    if not d.get("name"):
        raise ValueError("Nom manquant")
    if not emails and not was and not d.get("telegram"):
        raise ValueError("Ajoutez un e-mail, un numéro WhatsApp ou un Telegram")
    return Contact.objects.create(event=event, name=d["name"][:120], title=(d.get("title") or "")[:120], emails=emails,
                                  whatsapp_numbers=was, telegram_chat_id=d.get("telegram") or "",
                                  language=d.get("language") or "fr", consent=bool(d.get("consent")))


@require_http_methods(["GET", "POST"])
@owner_api
def roles(request, event):
    if request.method == "POST":
        d = body(request)
        if not d.get("name"):
            return err("Nom du rôle manquant")
        try:
            with transaction.atomic():
                r = Role.objects.create(event=event, name=d["name"][:120])
                for c in d.get("contacts", []):
                    r.contacts.add(_contact_from(event, c))
                for tid in d.get("tasks", []):
                    event.alerter_items.filter(id=tid).update(role=r)
        except ValueError as e:
            return err(str(e))
    return ok([S.role_data(r) for r in event.roles.prefetch_related("contacts")])


@require_http_methods(["PATCH", "POST", "DELETE"])
@owner_api
def role_detail(request, event, pk):
    r = get_object_or_404(Role, pk=pk, event=event)
    if request.method == "DELETE":
        mode = request.GET.get("tasks", "owner")
        if mode == "delete":
            r.tasks.all().delete()
        elif mode.isdigit():
            r.tasks.update(role=event.roles.filter(id=int(mode)).first())
        else:
            r.tasks.update(role=None)
        r.delete()
        return ok()
    d = body(request)
    if "name" in d:
        r.name = d["name"][:120]
    if "active" in d:
        r.active = bool(d["active"])
    r.save()
    if d.get("add_contact"):
        try:
            r.contacts.add(_contact_from(event, d["add_contact"]))
        except ValueError as e:
            return err(str(e))
    if d.get("remove_contact"):
        r.contacts.remove(d["remove_contact"])
    return ok(S.role_data(r))


# ---------------------------------------------------------------- moments forts
def launch_moment_obj(m, as_message=False):
    m.status = "launched"
    m.launched_as_message = as_message
    m.ends_at = timezone.now() + timedelta(seconds=m.duration)
    m.save()
    data = S.live_moment(m.event)
    broadcast(m.event, "moment", data)
    return data


@require_http_methods(["GET", "POST"])
@owner_api
def moments(request, event):
    if request.method == "POST":
        d = request.POST
        title = json.loads(d.get("title") or "{}") if d.get("title", "").startswith("{") else {"fr": d.get("title", "")}
        if not any(title.values()):
            return err("Titre manquant")
        m = Moment.objects.create(event=event, order=event.moments.count(), title=title, kind=d.get("kind", "reveal"),
                                  message=json.loads(d["message"]) if d.get("message", "").startswith("{") else {"fr": d.get("message") or title.get("fr", "")},
                                  duration=int(d.get("duration") or 10), effect=d.get("effect") or "confetti",
                                  scheduled_at=datetime.fromisoformat(d["scheduled_at"]) if d.get("scheduled_at") else None)
        if request.FILES.get("photo"):
            m.photo = request.FILES["photo"]
            m.save()
    return ok([S.moment_data(m) for m in event.moments.all()])


@require_http_methods(["POST", "DELETE"])
@owner_api
def moment_detail(request, event, pk):
    m = get_object_or_404(Moment, pk=pk, event=event)
    if request.method == "DELETE":
        m.delete()
        return ok()
    if request.FILES.get("photo"):
        m.photo = request.FILES["photo"]
    for f in ("duration",):
        if request.POST.get(f):
            setattr(m, f, int(request.POST[f]))
    if request.POST.get("reset"):
        m.status, m.ends_at = "ready", None
    m.save()
    return ok(S.moment_data(m))


@require_http_methods(["POST"])
@owner_api
def moment_launch(request, event, pk):
    m = get_object_or_404(Moment, pk=pk, event=event)
    as_message = bool(body(request).get("as_message"))
    if m.needs_photo and not as_message:
        return err("La photo de ce moment n'est pas chargée", 409)
    return ok(launch_moment_obj(m, as_message))


# ---------------------------------------------------------------- plan de table
def tables_payload(event):
    seating.clean_seats(event)
    ps = seating.persons(event)
    placed = {k for tb in event.tables.all() for k in tb.seats if k}
    return {
        "tables": [{"id": tb.id, "name": tb.name, "capacity": tb.capacity, "kind": tb.kind, "shape": tb.shape, "seats": tb.seats, "quote": tb.quote, "quote_ref": tb.quote_ref} for tb in event.tables.all()],
        "persons": {p.key: p.as_dict() for p in ps},
        "unplaced": [p.key for p in ps if p.key not in placed],
        "categories": [S.category_data(c) for c in event.categories.all()],
        "supervisor": event.supervisor_name,
        "config": event.table_config or seating.default_config(event, ps),
    }


@require_http_methods(["GET", "PUT"])
@owner_api
def tables(request, event):
    if request.method == "PUT":
        items = json.loads(request.body or b"[]")
        valid = {p.key for p in seating.persons(event)} | {seating.SUPERVISOR}
        seen = set()
        keep = []
        with transaction.atomic():
            for i, it in enumerate(items):
                cap = max(1, min(30, int(it.get("capacity") or 8)))
                seats = []
                for k in (it.get("seats") or [])[:cap]:
                    ok_key = k in valid and (k == seating.SUPERVISOR or k not in seen)
                    seats.append(k if ok_key else None)
                    if ok_key and k != seating.SUPERVISOR:
                        seen.add(k)
                seats += [None] * (cap - len(seats))
                tb = event.tables.filter(id=it.get("id")).first() if it.get("id") else None
                tb = tb or Table(event=event)
                tb.order, tb.name, tb.capacity, tb.seats = i, (it.get("name") or "")[:120], cap, seats
                tb.quote, tb.quote_ref = (it.get("quote") or "")[:200], (it.get("quote_ref") or "")[:60]
                tb.kind = it.get("kind") if it.get("kind") in ("std", "honor", "kids") else "std"
                tb.shape = it.get("shape") if it.get("shape") in ("round", "rect") else "round"
                tb.save()
                keep.append(tb.id)
            event.tables.exclude(id__in=keep).delete()
    return ok(tables_payload(event))


@require_http_methods(["POST"])
@owner_api
def tables_auto(request, event):
    d = body(request)
    config = d.get("config") or None
    unplaced = seating.assign(event, config)
    data = tables_payload(event)
    data["last_unplaced"] = len(unplaced)
    return ok(data)


# ---------------------------------------------------------------- invités & tableau de bord
@require_http_methods(["GET"])
@owner_api
def guests(request, event):
    qs = event.guests.prefetch_related("companions", "children")
    return ok([S.guest_data(g) for g in qs])


@require_http_methods(["PATCH", "POST", "DELETE"])
@owner_api
def guest_detail(request, event, pk):
    g = get_object_or_404(Guest, pk=pk, event=event)
    if request.method == "DELETE":
        g.delete()
        seating.clean_seats(event)
        return ok()
    d = body(request)
    if "arrived" in d:
        _mark_arrived(g, bool(d["arrived"]))
    if "category" in d:
        g.category = event.categories.filter(id=d["category"]).first()
        g.save()
    return ok(S.guest_data(g))


def arrivals_payload(event):
    att = event.guests.filter(attending=True)
    by_cat = []
    for c in event.categories.all():
        n = att.filter(category=c).count()
        if n:
            by_cat.append({"id": c.id, "name": c.name, "color": c.color, "total": n, "arrived": att.filter(category=c, arrived=True).count()})
    return {"arrived": att.filter(arrived=True).count(), "total": att.count(), "by_category": by_cat,
            "recent": [{"name": g.full_name, "at": g.arrived_at.isoformat() if g.arrived_at else None}
                       for g in att.filter(arrived=True).order_by("-arrived_at")[:8]]}


def _mark_arrived(g, value=True):
    g.arrived = value
    g.arrived_at = timezone.now() if value else None
    g.save(update_fields=["arrived", "arrived_at"])
    broadcast(g.event, "arrival", arrivals_payload(g.event))


@require_http_methods(["GET"])
@owner_api
def dashboard(request, event):
    ps = seating.persons(event)
    return ok({
        "responses": event.guests.count(),
        "confirmed_people": len(ps),
        "children": sum(1 for p in ps if p.type == "enfant"),
        "budget": alerter.budget_status(event),
        "guests": alerter.guest_status(event),
        "warnings": alerter.warnings(event),
        "arrivals": arrivals_payload(event),
        "alerts_sent": [{"message": a.message, "at": a.created_at.isoformat()} for a in event.alert_logs.all()[:10]],
        "wishes": [{"id": w.id, "author": w.author_name, "text": w.text, "hidden": w.hidden} for w in event.wishes.all()[:30]],
        "guest_list": [S.guest_data(g) for g in event.guests.prefetch_related("companions", "children").order_by("-created_at")[:300]],
    })


@require_http_methods(["POST"])
@owner_api
def wish_hide(request, event, pk):
    w = get_object_or_404(Wish, pk=pk, event=event)
    w.hidden = not w.hidden
    w.save()
    broadcast(event, "wishes_changed", {})
    return ok({"hidden": w.hidden})


# ---------------------------------------------------------------- cadeaux (organisateur)
def gift_data(g):
    return {"id": g.id, "name": g.name, "description": g.description, "price": float(g.price) if g.price is not None else None,
            "link": g.link, "quantity": g.quantity, "quantity_reserved": g.quantity_reserved}


@require_http_methods(["GET", "POST"])
@owner_api
def gifts(request, event):
    if request.method == "POST":
        d = body(request)
        if not d.get("name"):
            return err("Nom manquant")
        g = Gift.objects.create(event=event, name=d["name"][:200], description=d.get("description") or "",
                                price=Decimal(str(d["price"])) if d.get("price") not in (None, "") else None,
                                link=d.get("link") or "", quantity=max(1, int(d.get("quantity") or 1)))
        return ok(gift_data(g), 201)
    return ok([gift_data(g) for g in event.gifts.prefetch_related("reservations")])


@require_http_methods(["GET", "PUT", "DELETE"])
@owner_api
def gift_detail(request, event, pk):
    g = get_object_or_404(Gift, pk=pk, event=event)
    if request.method == "DELETE":
        g.delete()
        return ok()
    if request.method == "PUT":
        d = body(request)
        g.name = d.get("name", g.name)[:200]
        g.description = d.get("description") or ""
        g.price = Decimal(str(d["price"])) if d.get("price") not in (None, "") else None
        g.link = d.get("link") or ""
        g.quantity = max(1, int(d.get("quantity") or 1))
        g.save()
    return ok(gift_data(g))


@require_http_methods(["GET", "POST"])
@owner_api
def delivery_options(request, event):
    if request.method == "POST":
        name = body(request).get("name", "").strip()
        if not name:
            return err("Nom manquant")
        DeliveryOption.objects.create(event=event, name=name[:120])
    return ok([{"id": o.id, "name": o.name} for o in event.delivery_options.all()])


@require_http_methods(["PUT", "DELETE"])
@owner_api
def delivery_option_detail(request, event, pk):
    o = get_object_or_404(DeliveryOption, pk=pk, event=event)
    if request.method == "DELETE":
        o.delete()
        return ok()
    o.name = body(request).get("name", o.name)[:120]
    o.save()
    return ok({"id": o.id, "name": o.name})


@require_http_methods(["GET"])
@owner_api
def gift_reservations(request, event):
    rs = GiftReservation.objects.filter(gift__event=event).select_related("gift", "delivery_option")
    return ok([{"full_name": r.full_name, "cadeau_reserve": r.gift.name, "quantite_reservee": r.quantity,
                "delivery_option_name": r.delivery_option.name if r.delivery_option else ""} for r in rs])


# =================================================================== PUBLIC
@require_http_methods(["POST"])
@public_api
def rsvp_submit(request, event):
    d = body(request)
    first, last = (d.get("first_name") or "").strip(), (d.get("last_name") or "").strip()
    if not first:
        return err("Le prénom est obligatoire")
    lang = d.get("lang") if d.get("lang") in event.languages else event.languages[0]
    attending = bool(d.get("attending", True))
    cat = event.categories.filter(id=d.get("category"), is_honor=False).first() if d.get("category") else None
    with transaction.atomic():
        g = Guest.objects.create(event=event, first_name=first[:80], last_name=last[:80], email=(d.get("email") or "")[:254],
                                 phone=(d.get("phone") or "")[:40], country=(d.get("country") or "")[:80], attending=attending,
                                 category=cat, nav_language=lang, message=(d.get("message") or "")[:2000],
                                 languages=[str(l)[:30] for l in (d.get("languages") or [])][:8])
        if attending:
            for name in (d.get("companions") or [])[: event.max_companions]:
                Companion.objects.create(guest=g, first_name=(name or "Accompagnant·e")[:80])
            if event.kids_invited:
                for k in (d.get("children") or [])[:10]:
                    if (k.get("name") or "").strip():
                        Child.objects.create(guest=g, first_name=k["name"].strip()[:80], age=max(0, min(17, int(k.get("age") or 0))))
        if (d.get("wish") or "").strip() and event.has("mur"):
            w = Wish.objects.create(event=event, author_name=g.full_name, author_token=g.token, text=d["wish"].strip()[:600])
            broadcast(event, "wish", S.wish_data(w))
    return ok({"token": g.token, "card_url": event.public_url("card", token=g.token) + f"?lang={lang}",
               "pdf_url": event.public_url("card_pdf", token=g.token) + f"?lang={lang}"}, 201)


@require_http_methods(["GET"])
@public_api
def live(request, event):
    att = event.guests.filter(attending=True)
    return ok({"server_now": timezone.now().timestamp() * 1000, "moment": S.live_moment(event),
               "arrived": att.filter(arrived=True).count(), "total": att.count(),
               "wishes": event.wishes.filter(hidden=False).count()})


@require_http_methods(["GET"])
@public_api
def me(request, event):
    who = identity(event, request.GET.get("g"))
    if not who:
        return ok({"known": False})
    table = None
    if who["guest"]:
        tb, idx = seating.seat_of(event, seating.person_key(who["guest"].id, "p"))
        if tb:
            table = {"label": tb.label() if tb.name else f"Table {tb.order + 1}", "seat": idx + 1}
    return ok({"known": True, "name": who["name"], "first": who["first"], "table": table,
               "arrived": bool(who["guest"] and who["guest"].arrived)})


@require_http_methods(["POST"])
@public_api
def visitor(request, event):
    name = (body(request).get("name") or "").strip()
    if len(name) < 2:
        return err("Indiquez votre prénom et votre nom")
    v = Visitor.objects.create(event=event, name=name[:120])
    return ok({"token": v.token, "name": v.name})


@require_http_methods(["GET", "POST"])
@public_api
def wishes(request, event):
    token = request.GET.get("g") or body(request).get("token")
    if request.method == "POST":
        who = identity(event, token)
        if not who:
            return err("Dites-nous d'abord qui vous êtes", 403)
        text = (body(request).get("text") or "").strip()
        if not text:
            return err("Le message est vide")
        w = Wish.objects.create(event=event, author_name=who["name"], author_token=who["token"], text=text[:600])
        broadcast(event, "wish", S.wish_data(w))
        return ok(S.wish_data(w, token), 201)
    qs = event.wishes.filter(hidden=False).prefetch_related("reactions")[:200]
    return ok([S.wish_data(w, token) for w in qs])


@require_http_methods(["DELETE", "POST"])
@public_api
def wish_delete(request, event, pk):
    w = get_object_or_404(Wish, pk=pk, event=event)
    token = request.GET.get("g") or body(request).get("token")
    if not token or w.author_token != token:
        return err("Vous ne pouvez supprimer que vos propres vœux", 403)
    w.delete()
    broadcast(event, "wish_deleted", {"id": pk})
    return ok()


@require_http_methods(["POST"])
@public_api
def wish_react(request, event, pk):
    w = get_object_or_404(Wish, pk=pk, event=event, hidden=False)
    d = body(request)
    who = identity(event, d.get("token"))
    if not who:
        return err("Dites-nous d'abord qui vous êtes", 403)
    emoji = d.get("emoji")
    if emoji not in Reaction.EMOJIS:
        return HttpResponseBadRequest()
    r = Reaction.objects.filter(wish=w, token=who["token"], emoji=emoji).first()
    if r:
        r.delete()
        added = False
    else:
        Reaction.objects.create(wish=w, token=who["token"], emoji=emoji)
        added = True
    data = S.wish_data(w)
    broadcast(event, "reaction", {"id": w.id, "reactions": data["reactions"], "emoji": emoji if added else None})
    return ok(S.wish_data(w, who["token"]))


@require_http_methods(["POST"])
@public_api
def moment_react(request, event):
    """Réaction emoji pendant la révélation d'un moment fort (sans enregistrement)."""
    emoji = body(request).get("emoji")
    if emoji in Reaction.EMOJIS:
        broadcast(event, "float", {"emoji": emoji})
    return ok()


@require_http_methods(["POST"])
@public_api
def arrived(request, event):
    who = identity(event, body(request).get("token"))
    if not who or not who["guest"]:
        return err("Invité inconnu", 404)
    if not who["guest"].arrived:
        _mark_arrived(who["guest"], True)
    return ok({"arrived": True})


@require_http_methods(["POST"])
@public_api
def media_upload(request, event):
    who = identity(event, request.POST.get("token"))
    f = request.FILES.get("file")
    if not who:
        return err("Dites-nous d'abord qui vous êtes", 403)
    if not f:
        return err("Aucun fichier")
    if f.size > 15 * 1024 * 1024:
        return err("Fichier trop lourd (15 Mo maximum)")
    is_video = (f.content_type or "").startswith("video/")
    caption = f"📸 {who['name']}" + (f" — {request.POST.get('caption')}" if request.POST.get("caption") else "")
    channels = list(event.telegram_channels.filter(active=True))
    if not channels:
        return err("Aucun groupe Telegram n'est encore relié à cet événement", 503)
    content = f.read()
    sent = sum(1 for ch in channels if notify.send_telegram_media(ch.chat_id, None, caption, is_video, name=f.name, content=content))
    if not sent:
        return err("L'envoi vers Telegram a échoué, réessayez dans un instant", 503)
    return ok({"sent": sent, "total": len(channels)})


@require_http_methods(["GET"])
@public_api
def public_gifts(request, event):
    return ok({"gifts": [gift_data(g) for g in event.gifts.prefetch_related("reservations")],
               "delivery_options": [{"id": o.id, "name": o.name} for o in event.delivery_options.all()]})


@require_http_methods(["POST"])
@public_api
def gift_reserve(request, event, pk):
    g = get_object_or_404(Gift, pk=pk, event=event)
    d = body(request)
    qty = max(1, int(d.get("quantity") or 1))
    who = identity(event, d.get("token"))
    name = (who["name"] if who else (d.get("full_name") or "")).strip()
    if not name:
        return err("Indiquez votre nom")
    with transaction.atomic():
        g = Gift.objects.select_for_update().get(pk=g.pk)
        if g.quantity_reserved + qty > g.quantity:
            return err("Ce cadeau n'est plus disponible en cette quantité", 409)
        GiftReservation.objects.create(gift=g, full_name=name[:160], token=who["token"] if who else "", quantity=qty,
                                       delivery_option=event.delivery_options.filter(id=d.get("delivery_option")).first())
    return ok(gift_data(g))
