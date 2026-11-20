"""Pages HTML (organisateur et invités)."""
from django import forms
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import translation
from django.views.decorators.http import require_POST

from events import serializers as S
from events.models import EventType, Event, Reaction
from events.services import pdf, seating
from events.services.defaults import seed_event_defaults

LANG_COOKIE = "miel_lang"


# ---------------------------------------------------------------- comptes
class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True, label="E-mail", help_text="Pour recevoir les rappels de l'Alerter")

    class Meta:
        model = User
        fields = ("username", "email")


def signup(request):
    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("home")
    return render(request, "registration/signup.html", {"form": form})


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
    return render(request, "events/bot.html", _organizer_ctx(owned(request, slug), "bot"))


@login_required
def panel(request, slug):
    return render(request, "events/panel.html", _organizer_ctx(owned(request, slug), "panel"))


@login_required
def tables_page(request, slug):
    return render(request, "events/tables.html", _organizer_ctx(owned(request, slug), "tables"))


@login_required
def gifts_manager(request, slug):
    return render(request, "events/gifts_manager.html", _organizer_ctx(owned(request, slug), "gifts"))


@login_required
def plan_pdf(request, slug):
    event = owned(request, slug)
    lang = request.GET.get("lang", "fr")
    buf = pdf.plan_pdf(event, lang, names_only=request.GET.get("names") == "1")
    return FileResponse(buf, as_attachment=True, filename=f"plan-de-table-{event.slug}.pdf")


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


def guest_render(request, template, event, ctx=None):
    lang = pick_lang(request, event)
    context = {"event": event, "lang": lang, "langs": event.languages,
               "song": S.song_data(event.song), "public": {"slug": event.slug, "lang": lang,
               "start_ms": S.event_data(event)["start_ms"], "title": event.title_in(lang)}}
    context.update(ctx or {})
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
    tpl = "events/site_A.html" if event.site_template == "A" else "events/site_B.html"
    return guest_render(request, tpl, event, {"venues": event.venues.all(), "story": event.story.all()})


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
