"""Palettes de fond de Miel (choix de l'organisateur).

Elles changent seulement les fonds et les surfaces (et la couleur du texte quand le fond est clair).
Elles ne touchent pas : la connexion et l'inscription, le pop-up de l'assistant, les sites de mariage.
"""
THEMES = [
    # clé, nom, clair ?, aperçu (fond, carte)
    ("cacao", "Cacao", False, ("#1a1310", "#30241d")),
    ("nuit", "Nuit", False, ("#0f1522", "#1f2a40")),
    ("ardoise", "Ardoise", False, ("#15171b", "#272b31")),
    ("foret", "Forêt", False, ("#0f1713", "#1f2e25")),
    ("ocean", "Océan", False, ("#0b1a1f", "#19323a")),
    ("prune", "Prune", False, ("#1a1220", "#2e2138")),
    ("bordeaux", "Bordeaux", False, ("#1c0f12", "#331d22")),
    ("noir", "Noir", False, ("#0b0b0b", "#1e1e1e")),
    ("ivoire", "Ivoire", True, ("#f7f2ea", "#ffffff")),
    ("perle", "Perle", True, ("#f3f4f6", "#ffffff")),
    ("rose", "Rose poudré", True, ("#fbf1f1", "#fffafa")),
    ("sauge", "Sauge", True, ("#eef3ec", "#fbfdfa")),
]
KEYS = {k for k, *_ in THEMES}
DEFAULT = "cacao"


def theme_of(user):
    try:
        t = user.miel_settings.theme
    except Exception:
        return DEFAULT
    return t if t in KEYS else DEFAULT
