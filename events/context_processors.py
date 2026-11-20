from events.themes import THEMES, theme_of


def miel_theme(request):
    """Palette de l'organisateur connecté pour les pages de l'organisateur."""
    user = getattr(request, "user", None)
    return {"app_theme": theme_of(user) if user and user.is_authenticated else "cacao", "app_themes": THEMES}
