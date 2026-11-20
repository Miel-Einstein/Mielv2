"""Thèmes de noms pour les tables (appliqués aux tables standard, dans l'ordre).

Chaque entrée : (nom, citation, référence). La citation est facultative.
Les versets du thème « Vertus & versets » reprennent ceux du plan modèle fourni par Miel.
"""

VERTUS_VERSETS = [
    ("Amour", "L'amour ne périt jamais.", "1 Corinthiens 13:8"),
    ("Foi", "Nous marchons par la foi et non par la vue.", "2 Corinthiens 5:7"),
    ("Complicité", "Deux valent mieux qu'un.", "Ecclésiaste 4:9"),
    ("Grâce", "Ma grâce te suffit.", "2 Corinthiens 12:9"),
    ("Paix", "Que la paix de Christ règne dans vos cœurs.", "Colossiens 3:15"),
    ("Joie", "La joie de l'Éternel est votre force.", "Néhémie 8:10"),
    ("Fidélité", "Grand est ton amour, grande est ta fidélité.", "Lamentations 3:23"),
    ("Patience", "L'amour est patient.", "1 Corinthiens 13:4"),
    ("Bonté", "Goûtez et voyez combien l'Éternel est bon.", "Psaume 34:8"),
    ("Bienveillance", "Soyez bons les uns envers les autres.", "Éphésiens 4:32"),
    ("Douceur", "Que votre douceur soit connue de tous.", "Philippiens 4:5"),
    ("Bonheur", "Heureux ceux qui se confient en l'Éternel.", "Jérémie 17:7"),
    ("Pardon", "Pardonnez-vous réciproquement.", "Colossiens 3:13"),
    ("Harmonie", "Vivez en paix les uns avec les autres.", "Romains 12:16-18"),
    ("Humilité", "Revêtez-vous d'humilité.", "1 Pierre 5:5"),
    ("Sagesse", "L'Éternel donne la sagesse.", "Proverbes 2:6"),
    ("Sainteté", "Soyez saints, car je suis saint.", "1 Pierre 1:16"),
    ("Pureté", "Heureux ceux qui ont le cœur pur.", "Matthieu 5:8"),
    ("Obéissance", "Si vous m'aimez, gardez mes commandements.", "Jean 14:15"),
    ("Confiance", "Confie-toi en l'Éternel de tout ton cœur.", "Proverbes 3:5"),
    ("Bénédiction", "Je te bénirai et tu seras une source de bénédiction.", "Genèse 12:2"),
    ("Alliance", "Ce que Dieu a uni, que l'homme ne le sépare pas.", "Matthieu 19:6"),
    ("Destin", "Je connais les projets que j'ai formés sur vous.", "Jérémie 29:11"),
    ("Victoire", "Grâce soit rendue à Dieu, qui nous donne la victoire.", "1 Corinthiens 15:57"),
    ("Histoire", "L'Éternel a fait pour nous de grandes choses.", "Psaume 126:3"),
]

THEMES = {
    "vertus_versets": {"label": "Vertus & versets", "items": VERTUS_VERSETS},
    "vertus": {"label": "Vertus", "items": [(n, "", "") for n, _, _ in VERTUS_VERSETS]},
    "villes": {"label": "Villes", "items": [(n, "", "") for n in (
        "Rome", "Venise", "Florence", "Milan", "Turin", "Naples", "Paris", "Lisbonne", "Vienne", "Prague", "Séville", "Kinshasa",
        "Brazzaville", "Yaoundé", "Douala", "Dakar", "Abidjan", "Marrakech", "Le Cap", "Zanzibar", "Kyoto", "Bali", "Santorin",
        "New York", "Rio", "Montréal", "Londres", "Bruxelles", "Genève", "Amsterdam")]},
    "fleurs": {"label": "Fleurs", "items": [(n, "", "") for n in (
        "Rose", "Pivoine", "Orchidée", "Lys", "Magnolia", "Jasmin", "Hibiscus", "Lavande", "Camélia", "Tulipe", "Gardénia", "Iris",
        "Lotus", "Mimosa", "Dahlia", "Freesia", "Hortensia", "Frangipanier", "Bougainvillier", "Coquelicot", "Marguerite", "Violette",
        "Anémone", "Glycine", "Renoncule", "Gypsophile", "Myosotis", "Capucine", "Amaryllis", "Tournesol")]},
    "pierres": {"label": "Pierres précieuses", "items": [(n, "", "") for n in (
        "Diamant", "Saphir", "Émeraude", "Rubis", "Perle", "Améthyste", "Topaze", "Opale", "Jade", "Turquoise", "Grenat", "Ambre",
        "Onyx", "Quartz rose", "Aigue-marine", "Citrine", "Malachite", "Lapis-lazuli", "Tourmaline", "Péridot", "Corail", "Nacre",
        "Agate", "Cristal", "Obsidienne")]},
    "numeros": {"label": "Numéros seulement", "items": []},
}


def apply_theme(event, key):
    """Nomme les tables standard selon le thème ; les tables d'honneur et des enfants gardent leur nom."""
    theme = THEMES.get(key)
    if theme is None:
        raise KeyError(key)
    items = theme["items"]
    i = 0
    for t in event.tables.all():
        if t.kind != "std":
            continue
        name, quote, ref = items[i] if i < len(items) else ("", "", "")
        t.name, t.quote, t.quote_ref = name, quote, ref
        t.save(update_fields=["name", "quote", "quote_ref"])
        i += 1
