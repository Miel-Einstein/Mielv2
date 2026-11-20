"""Modèles de Miel v2.

Principes :
- Les textes que l'organisateur personnalise sont des JSONField
  {"fr": "...", "en": "...", ...} : une valeur par langue de l'événement.
- Le plan de table garde, pour chaque table, une liste de « clés de personne »
  (voir events.services.seating.person_key) : c'est simple à éditer depuis
  l'interface glisser-déposer et à recalculer quand un RSVP change.
"""
import secrets
import uuid
from datetime import datetime, time, timedelta

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


def new_token():
    return secrets.token_urlsafe(16)


def t(value, lang, fallback="fr"):
    """Renvoie la traduction d'un champ JSON multilingue."""
    if isinstance(value, str):
        return value
    if not value:
        return ""
    return value.get(lang) or value.get(fallback) or next(iter(value.values()), "")


class EventType(models.TextChoices):
    MARIAGE = "mariage", "Mariage"
    ANNIVERSAIRE = "anniversaire", "Anniversaire"
    BAPTEME = "bapteme", "Baptême"
    DINER = "diner", "Dîner au restaurant"
    ENTREPRISE = "entreprise", "Événement d'entreprise"


SERVICE_CHOICES = [
    ("carte", "Carte d'invitation & RSVP"),
    ("cadeaux", "Liste de cadeaux"),
    ("tables", "Plan de table"),
    ("alerter", "Alerter (rappels & budget)"),
    ("mur", "Mur des vœux & photos"),
    ("moments", "Moments forts"),
    ("site", "Site du mariage"),
]
CARD_TEMPLATES = [("botanique", "Botanique"), ("moderne", "Moderne"), ("rose", "Rose romantique")]
SITE_TEMPLATES = [("A", "Botanical Editorial"), ("B", "Modern Romance")]


class Song(models.Model):
    """Catalogue de musiques géré uniquement par le concepteur (admin)."""

    title = models.CharField(max_length=200)
    artist = models.CharField(max_length=200, default="Miel Production")
    audio_file = models.FileField(upload_to="songs/", blank=True, help_text="MP3 joué en musique d'ambiance")
    youtube_url = models.URLField(blank=True)
    spotify_url = models.URLField(blank=True)
    cover = models.ImageField(upload_to="songs/covers/", blank=True)
    active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "title"]

    def __str__(self):
        return self.title


class Event(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="events")
    slug = models.SlugField(max_length=80, unique=True)
    type = models.CharField(max_length=20, choices=EventType.choices, default=EventType.MARIAGE)
    title = models.JSONField(default=dict, blank=True)
    subtitle = models.JSONField(default=dict, blank=True)
    date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(default=time(15, 0))
    timezone = models.CharField(max_length=64, default="Europe/Rome")
    languages = models.JSONField(default=list, blank=True)
    services = models.JSONField(default=list, blank=True)
    card_template = models.CharField(max_length=20, choices=CARD_TEMPLATES, default="botanique")
    site_template = models.CharField(max_length=2, choices=SITE_TEMPLATES, default="A")
    cover_image = models.ImageField(upload_to="events/covers/", blank=True)
    cover_image_2 = models.ImageField(upload_to="events/covers/", blank=True)
    # Enfants
    kids_invited = models.BooleanField(default=True)
    kids_table = models.BooleanField(default=False)
    age_with_parents = models.PositiveSmallIntegerField(default=4, help_text="En dessous : avec les parents")
    age_kids_max = models.PositiveSmallIntegerField(default=12, help_text="Jusqu'à cet âge : table des enfants")
    baby_chair = models.BooleanField(default=False, help_text="Les tout-petits comptent pour une chaise")
    supervisor_name = models.CharField(max_length=120, blank=True)
    max_companions = models.PositiveSmallIntegerField(default=3)
    # RSVP
    ask_languages = models.BooleanField(default=True)
    conversation_languages = models.JSONField(default=list, blank=True, help_text="Langues proposées pour la conversation à table")
    # Alerter
    budget = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=8, default="€")
    guest_target = models.PositiveIntegerField(default=0)
    # Musique, partage
    song = models.ForeignKey(Song, null=True, blank=True, on_delete=models.SET_NULL)
    telegram_chat_id = models.CharField(max_length=64, blank=True, help_text="Groupe Telegram qui reçoit les photos du mur")
    social_links = models.JSONField(default=dict, blank=True)
    share_token = models.CharField(max_length=40, default=new_token, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title_in("fr") or self.slug

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(t(self.title, "fr")) or "evenement"
            self.slug = f"{base[:60]}-{uuid.uuid4().hex[:6]}"
        if not self.languages:
            self.languages = ["fr"]
        if not self.services:
            self.services = ["carte"]
        super().save(*args, **kwargs)

    # --- aides ---
    def title_in(self, lang):
        return t(self.title, lang)

    def subtitle_in(self, lang):
        return t(self.subtitle, lang)

    def has(self, service):
        return service in (self.services or [])

    @property
    def is_wedding(self):
        return self.type == EventType.MARIAGE

    @property
    def site_enabled(self):
        return self.is_wedding and self.has("site")

    def start_datetime(self):
        if not self.date:
            return None
        from zoneinfo import ZoneInfo

        return datetime.combine(self.date, self.start_time, tzinfo=ZoneInfo(self.timezone))

    def due_date(self, offset_days):
        if not self.date:
            return None
        return self.date + timedelta(days=offset_days)

    def public_url(self, name="rsvp", **kwargs):
        return settings.SITE_URL + reverse(name, kwargs={"slug": self.slug, **kwargs})


class Venue(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="venues")
    order = models.PositiveSmallIntegerField(default=0)
    name = models.JSONField(default=dict)
    kind = models.CharField(max_length=20, default="ceremonie", choices=[("ceremonie", "Cérémonie"), ("reception", "Réception"), ("autre", "Autre")])
    start = models.TimeField(null=True, blank=True)
    end = models.TimeField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lng = models.FloatField(null=True, blank=True)
    image = models.ImageField(upload_to="events/venues/", blank=True)
    parking = models.CharField(max_length=255, blank=True)
    entrance = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=255, blank=True)
    contact = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["order", "start"]


class StoryStep(models.Model):
    """Étapes de l'histoire du couple : dynamiques (ajout, retrait, ordre)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="story")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.JSONField(default=dict)
    text = models.JSONField(default=dict, blank=True)
    image = models.ImageField(upload_to="events/story/", blank=True)

    class Meta:
        ordering = ["order", "id"]


class Category(models.Model):
    """Catégorie d'invités, choisie (une seule) par chaque invité au RSVP."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="categories")
    order = models.PositiveSmallIntegerField(default=0)
    name = models.JSONField(default=dict)
    is_honor = models.BooleanField(default=False, help_text="Placée automatiquement à la table d'honneur")
    color = models.CharField(max_length=9, default="#e9a83b")

    class Meta:
        ordering = ["order", "id"]


class Guest(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="guests")
    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40, blank=True)
    country = models.CharField(max_length=80, blank=True)
    attending = models.BooleanField(default=True)
    category = models.ForeignKey(Category, null=True, blank=True, on_delete=models.SET_NULL)
    languages = models.JSONField(default=list, blank=True, help_text="Langues de conversation (vide = langue de navigation)")
    nav_language = models.CharField(max_length=5, default="fr")
    message = models.TextField(blank=True)
    token = models.CharField(max_length=40, unique=True, default=new_token)
    arrived = models.BooleanField(default=False)
    arrived_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return self.full_name

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def table_languages(self):
        return self.languages or [self.nav_language]


class Companion(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="companions")
    first_name = models.CharField(max_length=80)

    class Meta:
        ordering = ["id"]


class Child(models.Model):
    guest = models.ForeignKey(Guest, on_delete=models.CASCADE, related_name="children")
    first_name = models.CharField(max_length=80)
    age = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["id"]


class Visitor(models.Model):
    """Personne arrivée sur le mur sans sa carte : nom saisi une seule fois."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="visitors")
    name = models.CharField(max_length=120)
    token = models.CharField(max_length=40, unique=True, default=new_token)
    created_at = models.DateTimeField(auto_now_add=True)


class Wish(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="wishes")
    author_name = models.CharField(max_length=120)
    author_token = models.CharField(max_length=40, db_index=True)
    text = models.TextField(max_length=600)
    hidden = models.BooleanField(default=False, help_text="Masqué par l'organisateur")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Reaction(models.Model):
    EMOJIS = ["❤️", "😂", "🥂", "🙏", "🎉"]
    wish = models.ForeignKey(Wish, on_delete=models.CASCADE, related_name="reactions")
    token = models.CharField(max_length=40)
    emoji = models.CharField(max_length=8)

    class Meta:
        unique_together = [("wish", "token", "emoji")]


class Moment(models.Model):
    TYPES = [("reveal", "Compte à rebours + photo"), ("message", "Message surprise"), ("clock", "Compte à rebours vers une heure")]
    STATUS = [("ready", "Prêt"), ("launched", "Lancé")]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="moments")
    order = models.PositiveSmallIntegerField(default=0)
    title = models.JSONField(default=dict)
    kind = models.CharField(max_length=10, choices=TYPES, default="reveal")
    message = models.JSONField(default=dict, blank=True)
    duration = models.PositiveSmallIntegerField(default=10, help_text="Secondes de compte à rebours")
    scheduled_at = models.DateTimeField(null=True, blank=True, help_text="Pour un lancement à heure fixe (ex. minuit)")
    photo = models.ImageField(upload_to="events/moments/", blank=True)
    effect = models.CharField(max_length=20, default="confetti", choices=[("confetti", "Confettis"), ("hearts", "Cœurs"), ("fireworks", "Feux d'artifice")])
    song = models.ForeignKey(Song, null=True, blank=True, on_delete=models.SET_NULL)
    status = models.CharField(max_length=10, choices=STATUS, default="ready")
    ends_at = models.DateTimeField(null=True, blank=True)
    launched_as_message = models.BooleanField(default=False)

    class Meta:
        ordering = ["order", "id"]

    @property
    def needs_photo(self):
        return self.kind == "reveal" and not self.photo


class Role(models.Model):
    """Rôle dynamique : un ensemble de tâches confiées à des contacts."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="roles")
    name = models.CharField(max_length=120)
    active = models.BooleanField(default=True)
    contacts = models.ManyToManyField("Contact", blank=True, related_name="roles")

    class Meta:
        ordering = ["id"]


class Contact(models.Model):
    """Personne déléguée : reçoit seulement des e-mails / messages, sans accès au site."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="contacts")
    name = models.CharField(max_length=120)
    title = models.CharField(max_length=120, blank=True, help_text="Ex. Témoin du marié")
    emails = models.JSONField(default=list, blank=True)
    whatsapp_numbers = models.JSONField(default=list, blank=True)
    telegram_chat_id = models.CharField(max_length=64, blank=True)
    language = models.CharField(max_length=5, default="fr")
    consent = models.BooleanField(default=False, help_text="Accord pour recevoir des messages (obligatoire pour WhatsApp)")


class AlerterItem(models.Model):
    KINDS = [("task", "Tâche"), ("auto", "Contrôle automatique")]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="alerter_items")
    title = models.CharField(max_length=200)
    due_offset_days = models.IntegerField(default=-30, help_text="Jours par rapport à l'événement (négatif = avant)")
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    done = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    role = models.ForeignKey(Role, null=True, blank=True, on_delete=models.SET_NULL, related_name="tasks")
    kind = models.CharField(max_length=10, choices=KINDS, default="task")
    last_sent_on = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["due_offset_days", "id"]


class AlertLog(models.Model):
    """Trace des alertes envoyées (évite les doublons, affichée au panneau)."""

    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="alert_logs")
    key = models.CharField(max_length=120)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("event", "key")]
        ordering = ["-created_at"]


class Table(models.Model):
    KINDS = [("std", "Standard"), ("honor", "Table d'honneur"), ("kids", "Table des enfants")]
    SHAPES = [("round", "Ronde"), ("rect", "Rectangulaire")]
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="tables")
    order = models.PositiveSmallIntegerField(default=0)
    name = models.CharField(max_length=120, blank=True)
    capacity = models.PositiveSmallIntegerField(default=8)
    kind = models.CharField(max_length=6, choices=KINDS, default="std")
    shape = models.CharField(max_length=6, choices=SHAPES, default="round")
    seats = models.JSONField(default=list, help_text="Liste de clés de personne (ou null), longueur = capacité")

    class Meta:
        ordering = ["order", "id"]

    def label(self):
        return self.name or f"Table {self.order + 1}"


class BotSession(models.Model):
    """Progression du bot organisateur : reprise exacte après une pause."""

    event = models.OneToOneField(Event, on_delete=models.CASCADE, related_name="bot")
    step = models.CharField(max_length=40, default="accueil")
    log = models.JSONField(default=list, blank=True)
    paused = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)


# --------------------------------------------------------------------------
# Liste de cadeaux (reprise du gestionnaire existant)
# --------------------------------------------------------------------------
class DeliveryOption(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="delivery_options")
    name = models.CharField(max_length=120)


class Gift(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="gifts")
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    link = models.URLField(blank=True)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["id"]

    @property
    def quantity_reserved(self):
        return sum(r.quantity for r in self.reservations.all())


class GiftReservation(models.Model):
    gift = models.ForeignKey(Gift, on_delete=models.CASCADE, related_name="reservations")
    full_name = models.CharField(max_length=160)
    token = models.CharField(max_length=40, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    delivery_option = models.ForeignKey(DeliveryOption, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(default=timezone.now)
