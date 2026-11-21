from django.contrib import admin

from events import models as m


@admin.register(m.Song)
class SongAdmin(admin.ModelAdmin):
    """Catalogue musical : seul le concepteur ajoute ou modifie les morceaux."""

    list_display = ("title", "artist", "active", "order", "youtube_url", "spotify_url")
    list_editable = ("active", "order")


class VenueInline(admin.TabularInline):
    model = m.Venue
    extra = 0


class CategoryInline(admin.TabularInline):
    model = m.Category
    extra = 0


@admin.register(m.Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("__str__", "type", "date", "owner", "slug")
    list_filter = ("type",)
    search_fields = ("slug", "owner__username")
    inlines = [VenueInline, CategoryInline]


@admin.register(m.Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = ("full_name", "event", "attending", "category", "arrived")
    list_filter = ("attending", "arrived")
    search_fields = ("first_name", "last_name", "email")


for model in (m.Moment, m.Wish, m.AlerterItem, m.Role, m.Contact, m.Table, m.Gift, m.GiftReservation, m.AlertLog):
    admin.site.register(model)


# ---------------------------------------------------------------- aide de l'assistant
from django.urls import reverse  # noqa: E402
from django.utils.html import format_html  # noqa: E402
from urllib.parse import urlencode  # noqa: E402

from events.models import HelpEntry, UnansweredQuestion  # noqa: E402


@admin.register(HelpEntry)
class HelpEntryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "category", "context", "hits", "useful", "active")
    list_filter = ("active", "category")
    search_fields = ("keywords", "question", "answer", "key")
    readonly_fields = ("hits", "helpful", "not_helpful", "updated_at")
    fieldsets = (
        (None, {"fields": ("question", "answer", "keywords", "actions", "active")}),
        ("Classement", {"fields": ("category", "context", "key")}),
        ("Statistiques", {"fields": ("hits", "helpful", "not_helpful", "updated_at")}),
    )

    @admin.display(description="👍 / 👎")
    def useful(self, obj):
        return f"{obj.helpful} / {obj.not_helpful}"

    def get_changeform_initial_data(self, request):
        """Pré-remplit la fiche depuis une question sans réponse (?from_question=<id>)."""
        initial = super().get_changeform_initial_data(request)
        qid = request.GET.get("from_question")
        if qid:
            q = UnansweredQuestion.objects.filter(pk=qid).first()
            if q:
                from events.services.help import tokens
                initial.update({"question": {q.lang: q.text}, "answer": {q.lang: ""}, "keywords": " ".join(sorted(set(tokens(q.text)))),
                                "context": q.context if q.context in ("panel", "tables", "gifts") or q.context.startswith("bot:") else ""})
        return initial

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        qid = request.GET.get("from_question")
        if qid and not change:
            UnansweredQuestion.objects.filter(pk=qid).update(resolved=obj)


@admin.register(UnansweredQuestion)
class UnansweredQuestionAdmin(admin.ModelAdmin):
    list_display = ("text", "count", "lang", "context", "last_at", "answer_link")
    list_filter = ("resolved", "lang")
    search_fields = ("text",)
    readonly_fields = ("normalized", "first_at", "last_at", "user", "event")
    actions = ["mark_done"]

    @admin.display(description="Réponse")
    def answer_link(self, obj):
        if obj.resolved_id:
            return format_html('<a href="{}">✅ {}</a>', reverse("admin:events_helpentry_change", args=[obj.resolved_id]), obj.resolved)
        return format_html('<a class="button" href="{}?{}">✍️ Créer la réponse</a>', reverse("admin:events_helpentry_add"), urlencode({"from_question": obj.pk}))

    @admin.action(description="Marquer comme traitées (sans créer de réponse)")
    def mark_done(self, request, queryset):
        from events.models import HelpEntry
        done, _ = HelpEntry.objects.get_or_create(key="traitee-sans-reponse", defaults={"question": {"fr": "(question traitée sans réponse)"}, "answer": {"fr": ""}, "active": False})
        queryset.update(resolved=done)
