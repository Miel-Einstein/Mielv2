from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"
    verbose_name = "Miel — événements"

    def ready(self):
        from django.db.models.signals import post_migrate

        from events import signals  # noqa: F401
        post_migrate.connect(signals.load_help_if_empty, sender=self)
