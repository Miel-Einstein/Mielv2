"""Langue de l'interface de l'organisateur (différente des langues de l'événement).

Le texte source est en français ; les traductions viennent de events/ui_catalog.py.
Côté navigateur, static/miel/js/ui-i18n.js traduit l'interface avec le même catalogue
(fichiers static/miel/i18n/ui-<langue>.js produits par « python manage.py build_ui_i18n »).
"""
from events.ui_catalog import UI

UI_LANGS = ("fr", "en", "it", "ln")
_INDEX = {"en": 0, "it": 1, "ln": 2}
COOKIE = "miel_ui"


def ui(text, lang):
    """Traduit un texte fixe de l'interface ; renvoie le français s'il manque une traduction."""
    i = _INDEX.get(lang)
    if i is None:
        return text
    row = UI.get(text)
    return row[i] if row and row[i] else text


def from_accept_language(header):
    for part in (header or "").split(","):
        code = part.split(";")[0].strip().lower()[:2]
        if code in UI_LANGS:
            return code
    return "fr"


def ui_lang_for(request):
    """Langue de l'interface : celle du compte, sinon celle choisie sur cet appareil, sinon celle du navigateur."""
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        try:
            if user.miel_settings.ui_lang in UI_LANGS:
                return user.miel_settings.ui_lang
        except Exception:
            pass
    c = request.COOKIES.get(COOKIE)
    if c in UI_LANGS:
        return c
    return from_accept_language(request.META.get("HTTP_ACCEPT_LANGUAGE"))


def user_ui_lang(user):
    try:
        return user.miel_settings.ui_lang if user.miel_settings.ui_lang in UI_LANGS else "fr"
    except Exception:
        return "fr"
