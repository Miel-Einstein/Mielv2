"""Pages HTML (organisateur et invités)."""
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import translation
from django.views.decorators.http import require_POST

from events import serializers as S
from events.models import EventType, Event, Reaction, TermsAcceptance
from events.services import pdf, seating
from events.services import plan_svg as plan_render
from events.services.defaults import seed_event_defaults
from events.themes import theme_of

LANG_COOKIE = "miel_lang"


# ---------------------------------------------------------------- comptes
def signup(request):
    """Inscription : les conditions d'utilisation doivent être acceptées (pop-up)."""
    errors, data = [], {}
    if request.method == "POST":
        data = {"username": request.POST.get("username", "").strip(), "email": request.POST.get("email", "").strip()}
        password, confirmation = request.POST.get("password", ""), request.POST.get("confirmation", "")
        if not all([data["username"], data["email"], password, confirmation]):
            errors.append("Merci de remplir tous les champs")
        if password != confirmation:
            errors.append("Attention : les deux mots de passe doivent être identiques")
        try:
            validate_email(data["email"])
        except ValidationError:
            errors.append("Merci d'entrer une adresse e-mail valide")
        if data["username"] and User.objects.filter(username__iexact=data["username"]).exists():
            errors.append("Ce nom d'utilisateur existe déjà")
        if data["email"] and User.objects.filter(email__iexact=data["email"]).exists():
            errors.append("Un compte existe déjà avec cet e-mail")
        if request.POST.get("terms_accepted") != "1":
            errors.append("Vous devez accepter les conditions d'utilisation pour vous inscrire sur Miel.")
        if not errors:
            try:
                validate_password(password, User(username=data["username"], email=data["email"]))
            except ValidationError as e:
                errors += list(e.messages)
        if not errors:
            user = User.objects.create_user(data["username"], data["email"], password)
            TermsAcceptance.objects.create(user=user)
            login(request, user)
            return redirect("home")
    return render(request, "registration/signup.html", {"errors": errors, "data": data})


# ---------------------------------------------------------------- organisateur
def owned(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if event.owner_id != request.user.id and not request.user.is_superuser:
        raise Http404
    return event


@login_required
def home(request):
    return render(request, "events/home.html", {"events": request.user.events.all(), "types": EventType.choices})


@login_required
@require_POST
def event_create(request):
    etype = request.POST.get("type") if request.POST.get("type") in EventType.values else EventType.MARIAGE
    title = (request.POST.get("title") or "").strip() or "Mon événement"
    services = ["carte", "cadeaux", "tables", "alerter", "mur", "moments"] + (["site"] if etype == "mariage" else [])
    event = Event.objects.create(owner=request.user, type=etype, title={"fr": title}, subtitle={"fr": ""},
                                 languages=["fr"], services=services, kids_table=etype in ("mariage", "bapteme"))
    seed_event_defaults(event)
    return redirect("bot", slug=event.slug)


def _organizer_ctx(event, page):
    return {"event": event, "event_json": S.event_data(event), "page": page}


@login_required
def bot(request, slug):
    """L'assistant est un pop-up disponible sur toutes les pages : on ouvre le panneau avec le pop-up."""
    owned(request, slug)
    return redirect(reverse("panel", kwargs={"slug": slug}) + "?bot=1")


@login_required
def panel(request, slug):
    return render(request, "events/panel.html", _organizer_ctx(owned(request, slug), "panel"))


@login_required
def tables_page(request, slug):
    return render(request, "events/tables.html", _organizer_ctx(owned(request, slug), "tables"))


@login_required
def gifts_manager(request, slug):
    return render(request, "events/gifts_manager.html", _organizer_ctx(owned(request, slug), "gifts"))


def _plan_opts(request, event):
    lang = request.GET.get("lang") if request.GET.get("lang") in (event.languages or ["fr"]) else (event.languages or ["fr"])[0]
    style = request.GET.get("style") if request.GET.get("style") in plan_render.STYLES else "jardin"
    layout = request.GET.get("layout") if request.GET.get("layout") in plan_render.LAYOUTS else "cards"
    return {"style": style, "lang": lang, "photo": request.GET.get("photo", "1") == "1", "quotes": request.GET.get("quotes", "1") == "1",
            "layout": layout, "sort": "nom" if request.GET.get("sort") == "nom" else "prenom"}


@login_required
def plan_pdf(request, slug):
    """Plan de table en PDF A4 (plusieurs pages, une table n'est jamais coupée)."""
    event = owned(request, slug)
    o = _plan_opts(request, event)
    buf = plan_render.render_pdf(event, **o)
    return FileResponse(buf, as_attachment=request.GET.get("inline") != "1", filename=f"plan-de-table-{event.slug}-{o['layout']}-{o['style']}.pdf")


@login_required
def plan_svg(request, slug):
    """Plan de table en SVG : une grande affiche, nette à toutes les tailles (impression, écran, imprimeur)."""
    event = owned(request, slug)
    o = _plan_opts(request, event)
    resp = HttpResponse(plan_render.render_svg(event, **o), content_type="image/svg+xml; charset=utf-8")
    if request.GET.get("inline") != "1":
        resp["Content-Disposition"] = f'attachment; filename="plan-de-table-{event.slug}-{o["layout"]}-{o["style"]}.svg"'
    return resp


# ---------------------------------------------------------------- invités
def pick_lang(request, event):
    langs = event.languages or ["fr"]
    lang = request.GET.get("lang") or request.COOKIES.get(LANG_COOKIE) or translation.get_language_from_request(request)
    lang = (lang or "")[:2]
    if lang not in langs:
        lang = langs[0]
    translation.activate(lang)
    request.LANGUAGE_CODE = lang
    return lang


BG_PAGES_SITE = {"events/site_A.html", "events/site_B.html", "events/site_C.html"}
BG_PAGES_ALL = BG_PAGES_SITE | {"events/rsvp.html", "events/wall.html", "events/gift_list.html", "events/map.html"}


def site_bg_css(event, template):
    """CSS du fond choisi par l'organisateur (couleur, dégradé ou photo, avec un voile pour la lisibilité)."""
    bg = event.site_bg or {}
    mode = bg.get("mode", "default")
    pages = BG_PAGES_ALL if bg.get("scope") == "all" else BG_PAGES_SITE
    if mode == "default" or template not in pages:
        return ""
    c1, c2 = bg.get("c1", "#faf6ef"), bg.get("c2", "#e7d4ad")
    a = max(0, min(85, int(bg.get("veil", 0)))) / 100
    v = f"rgba(255,255,255,{a})" if bg.get("tone") != "dark" else f"rgba(0,0,0,{a})"
    veil = f"linear-gradient({v},{v})"
    if mode == "color":
        layers = f"{veil},{c1}"
    elif mode == "gradient":
        layers = f"{veil},linear-gradient(160deg,{c1},{c2})"
    elif mode == "image" and event.site_bg_image:
        url = event.site_bg_image.url.replace('"', "%22").replace("\\", "")
        layers = f'{veil},url("{url}") center/cover no-repeat,{c1}'
    else:
        return ""
    return (f"html{{background:{c1}}}body.guest-body{{background:transparent!important}}"
            f"body.guest-body::after{{content:'';position:fixed;inset:0;z-index:-1;pointer-events:none;background:{layers}}}")


def guest_render(request, template, event, ctx=None):
    lang = pick_lang(request, event)
    context = {"event": event, "lang": lang, "langs": event.languages,
               "song": S.song_data(event.song), "public": {"slug": event.slug, "lang": lang,
               "start_ms": S.event_data(event)["start_ms"], "title": event.title_in(lang)}}
    context.update(ctx or {})
    context["site_bg_css"] = site_bg_css(event, template)
    context["page_theme"] = theme_of(event.owner)
    resp = render(request, template, context)
    resp.set_cookie(LANG_COOKIE, lang, max_age=60 * 60 * 24 * 365, samesite="Lax")
    return resp


def share_link(request, token):
    event = get_object_or_404(Event, share_token=token)
    return redirect("event_home", slug=event.slug)


def event_home(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if not event.site_enabled:
        return redirect("rsvp", slug=slug)
    choice = request.GET.get("tpl") if request.GET.get("tpl") in ("A", "B", "C") else event.site_template  # ?tpl= : aperçu
    tpl = {"A": "events/site_A.html", "B": "events/site_B.html", "C": "events/site_C.html"}.get(choice, "events/site_A.html")
    return guest_render(request, tpl, event, {"venues": event.venues.all(), "story": event.story.all(), "gallery": event.gallery.all()})


def rsvp(request, slug):
    event = get_object_or_404(Event, slug=slug)
    cats = event.categories.filter(is_honor=False)
    return guest_render(request, "events/rsvp.html", event, {
        "categories": cats, "venues": event.venues.all(),
        "rsvp_conf": {"kids_invited": event.kids_invited, "kids_table": event.kids_table, "age_with_parents": event.age_with_parents,
                      "age_kids_max": event.age_kids_max, "baby_chair": event.baby_chair, "ask_languages": event.ask_languages,
                      "conversation_languages": event.conversation_languages or event.languages, "max_companions": event.max_companions}})


def card(request, slug, token):
    event = get_object_or_404(Event, slug=slug)
    guest = get_object_or_404(event.guests, token=token)
    title = event.title_in(event.languages[0])
    monogram = " & ".join(w[0] for w in title.replace("&", " ").split()[:2]) if title else ""
    return guest_render(request, "events/card.html", event, {
        "guest": guest, "venues": event.venues.all(), "monogram": monogram,
        "wall_url": event.public_url("wall") + f"?g={guest.token}"})


def card_pdf(request, slug, token):
    event = get_object_or_404(Event, slug=slug)
    guest = get_object_or_404(event.guests, token=token)
    lang = pick_lang(request, event)
    return FileResponse(pdf.card_pdf(event, guest, lang), as_attachment=True, filename=f"invitation-{guest.first_name.lower()}.pdf")


def wall(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if not event.has("mur"):
        raise Http404
    done = [m for m in event.moments.filter(status="launched")]
    return guest_render(request, "events/wall.html", event, {"emojis": Reaction.EMOJIS, "done_moments": done})


def screen(request, slug):
    event = get_object_or_404(Event, slug=slug)
    return guest_render(request, "events/screen.html", event, {"next_moment": event.moments.filter(status="ready").first()})


def map_page(request, slug):
    event = get_object_or_404(Event, slug=slug)
    return guest_render(request, "events/map.html", event, {"venues_json": [S.venue_data(v) for v in event.venues.all()]})


def gift_list(request, slug):
    event = get_object_or_404(Event, slug=slug)
    if not event.has("cadeaux"):
        raise Http404
    return guest_render(request, "events/gift_list.html", event)
