"""Valeurs de départ selon le type d'événement (modifiables ensuite)."""

ALERTER_BASE = {
    "mariage": [
        ("Fixer le budget", -365, None), ("Choisir la date", -365, None),
        ("Réserver la salle", -330, 4500), ("Réserver le traiteur", -300, 6000),
        ("Photographe / vidéaste", -240, 1800), ("DJ ou orchestre", -240, 1200),
        ("Décoration", -240, 900), ("Robe et costume", -180, 2200), ("Alliances", -180, 900),
        ("Démarches mairie / église / dot", -180, 150), ("Envoyer les invitations", -120, 150),
        ("Choisir la liste de cadeaux", -120, None), ("Essayages", -60, None), ("Gâteau", -60, 450),
        ("Transport des mariés et des invités", -60, 400), ("Hébergement des invités venant de loin", -60, None),
        ("Plan de table définitif", -30, None), ("Menu définitif", -30, None),
        ("Relancer les invités sans réponse", -30, None), ("Confirmer tous les prestataires", -7, None),
        ("Payer les soldes", -7, None), ("Préparer les enveloppes", -7, None),
        ("Récupérer les tenues et les alliances", -1, None),
    ],
    "anniversaire": [
        ("Fixer le budget", -60, None), ("Choisir le lieu", -60, 600), ("Envoyer les invitations", -30, None),
        ("Traiteur ou gâteau", -30, 250), ("Animation", -30, 300), ("Décoration", -14, 120),
        ("Relancer les réponses", -14, None), ("Courses", -3, 200), ("Confirmer le gâteau", -3, None),
    ],
    "bapteme": [
        ("Réserver la cérémonie religieuse", -90, None), ("Choisir parrain et marraine", -90, None),
        ("Lieu de la réception", -60, 700), ("Traiteur", -60, 900), ("Tenue de l'enfant", -30, 120),
        ("Envoyer les invitations", -30, None), ("Dragées et souvenirs", -30, 90),
        ("Confirmer le nombre de personnes", -7, None),
    ],
    "diner": [
        ("Choisir le restaurant", -30, None), ("Réserver", -30, None), ("Choisir le menu ou les options", -14, None),
        ("Demander les allergies", -14, None), ("Confirmer le nombre de personnes au restaurant", -7, None),
        ("Rappel aux invités (heure, adresse, dress code)", -2, None), ("Reconfirmer la réservation", -1, None),
    ],
    "entreprise": [
        ("Budget, lieu, date", -90, 3000), ("Intervenants", -60, 1500), ("Traiteur", -60, 2500),
        ("Matériel audiovisuel", -60, 800), ("Invitations", -30, None), ("Badges", -30, 200),
        ("Programme final", -7, None), ("Confirmations", -7, None),
    ],
}

DEFAULT_CATEGORIES = {
    "mariage": [("Parents & officiants", True), ("Famille de la mariée", False), ("Famille du marié", False), ("Amis", False), ("Collègues", False)],
    "anniversaire": [("Famille", False), ("Amis", False), ("Collègues", False)],
    "bapteme": [("Parrain, marraine & parents", True), ("Famille", False), ("Amis", False)],
    "diner": [("Famille", False), ("Amis", False)],
    "entreprise": [("Direction", True), ("Équipe", False), ("Partenaires", False), ("Clients", False)],
}

CATEGORY_COLORS = ["#e9a83b", "#d9897b", "#93a68c", "#7aa6d9", "#c78bd9", "#e2d27a", "#7cc59a", "#d97a9e"]

# Paliers de contrôle du nombre d'invités : (jours avant, % attendu)
GUEST_MILESTONES = [(-30, 50), (-14, 80), (-7, 100)]

# Seuils d'alerte budget (en %)
BUDGET_THRESHOLDS = [80, 100]


def seed_event_defaults(event):
    """Crée catégories et checklist Alerter de départ pour un événement."""
    from events.models import AlerterItem, Category

    if not event.categories.exists():
        for i, (name, honor) in enumerate(DEFAULT_CATEGORIES.get(event.type, DEFAULT_CATEGORIES["mariage"])):
            Category.objects.create(event=event, order=i, name={"fr": name}, is_honor=honor, color=CATEGORY_COLORS[i % len(CATEGORY_COLORS)])
    reset_alerter(event)


def reset_alerter(event):
    from events.models import AlerterItem

    event.alerter_items.filter(kind="task", done=False).delete()
    existing = set(event.alerter_items.values_list("title", flat=True))
    from events.ui_i18n import ui, user_ui_lang
    lang = user_ui_lang(event.owner)
    for title, offset, price in ALERTER_BASE.get(event.type, []):
        title = ui(title, lang)  # tâches de départ dans la langue de l'organisateur
        if title not in existing:
            AlerterItem.objects.create(event=event, title=title, due_offset_days=offset, price=price)
