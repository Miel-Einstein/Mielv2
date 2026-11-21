from django.contrib.auth.signals import user_logged_in
from django.dispatch import receiver

from events.ui_i18n import COOKIE, UI_LANGS


@receiver(user_logged_in)
def keep_login_language(sender, request, user, **kwargs):
    """La langue choisie avec les drapeaux de la page de connexion devient celle du compte."""
    lang = request.COOKIES.get(COOKIE) if request else None
    if lang in UI_LANGS:
        from events.models import UserSettings
        UserSettings.objects.update_or_create(user=user, defaults={"ui_lang": lang})


def load_help_if_empty(sender, **kwargs):
    """Au premier « migrate », charge les réponses de départ de l'aide."""
    from django.db.utils import OperationalError, ProgrammingError
    try:
        from events.models import HelpEntry
        if not HelpEntry.objects.exists():
            from events.services.help import load_builtin
            load_builtin()
    except (OperationalError, ProgrammingError):
        pass
