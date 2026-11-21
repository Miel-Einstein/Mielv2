from events.themes import THEMES, theme_of
from events.ui_i18n import ui_lang_for


def miel_theme(request):
    """Palette et langue d'interface de l'organisateur connecté (pages organisateur, connexion, inscription)."""
    user = getattr(request, "user", None)
    return {"app_theme": theme_of(user) if user and user.is_authenticated else "cacao", "app_themes": THEMES,
            "ui_lang": ui_lang_for(request),
            "ui_flags": [("fr", "🇫🇷", "Français"), ("en", "🇬🇧", "English"), ("it", "🇮🇹", "Italiano"), ("ln", "🇨🇬", "Lingála")]}
