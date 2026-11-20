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
