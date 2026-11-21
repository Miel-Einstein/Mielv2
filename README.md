# Miel v2

Plateforme de gestion d'événements (mariages, anniversaires, baptêmes, dîners, événements d'entreprise),
pilotée par un assistant à messages fixes.

**Fonctionnalités**
- **Assistant (bot) organisateur** qui remplace la barre latérale « Wedding Control ». Il gère la pause, la reprise exacte et un menu pour revenir sur une étape.
- **Textes personnalisés traduits** par l'organisateur, une saisie par langue (FR, EN, IT, LN).
- **Cartes d'invitation** en 3 modèles. La carte en PDF est personnalisée avec le nom de l'invité et un QR code vers le mur des vœux, qui contient le jeton personnel de l'invité.
- **RSVP dynamique** : catégories d'invités, accompagnants, enfants avec tranches d'âge, langues de conversation.
- **Plan de table** :
  - répartition automatique, qui place la table d'honneur et la table des enfants (avec une place pour la personne qui surveille) et regroupe les invités par langue ;
  - éditeur responsive : toucher-toucher, appui long + glisser, « Déplacer vers… », annulation, deux tables côte à côte ;
  - export PDF.
- **Mur des vœux** : réactions emoji (une par personne), photos et vidéos envoyées vers Telegram.
- **Écran géant** (TV ou projecteur).
- **Moments forts** synchronisés en temps réel : compte à rebours, puis photo révélée ou message surprise.
- **Y aller** : position en direct sur le téléphone de l'invité (jamais envoyée), ligne droite jusqu'au lieu, liens Google Maps, Waze et Plans, détection d'arrivée avec le numéro de table.
- **Arrivées** : compteur en direct dans la barre de l'organisateur, sans alerte à chaque arrivée.
- **Alerter** :
  - checklist de départ selon le type d'événement ;
  - budget avec alertes à 80 % et à 100 % ;
  - paliers de réponses des invités (J-30, J-14, J-7) ;
  - photos manquantes des moments forts ;
  - rôles et contacts dynamiques (e-mail, Telegram, WhatsApp préparé).
- **Liste de cadeaux** : gestion côté organisateur et réservation côté invités.
- **Musique** : catalogue géré dans l'admin, avec boutons « Streamer sur YouTube / Spotify ».
- **Sites de mariage** : deux modèles, « Botanical Editorial » et « Modern Romance ».

Le paiement et les abonnements ne sont pas encore intégrés.

## Démarrer en local

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py build_translations
python manage.py build_ui_i18n
python manage.py seed_demo          # compte « demo » / « demo-miel-2026 »
python manage.py createsuperuser    # pour l'admin (catalogue musical)
uvicorn config.asgi:application --reload
```

Ouvrir http://localhost:8000. En local, sans `REDIS_URL` :
- le temps réel passe par une couche en mémoire (un seul processus) ;
- les tâches Celery s'exécutent immédiatement ;
- les e-mails s'affichent dans la console.

Tests : `python manage.py test events`

## Déployer sur Railway

1. **Créer le projet** à partir de ce dépôt GitHub.
2. **Ajouter les services** :
   - **PostgreSQL** et **Redis**, qui fournissent `DATABASE_URL` et `REDIS_URL` ;
   - un **volume** monté sur `/data`, avec `MEDIA_ROOT=/data/media`, pour garder les photos et les MP3.
3. **Service web** : la commande de démarrage est dans `railway.json`. Elle applique les migrations, compile les traductions et lance uvicorn, qui gère HTTP et WebSockets.
4. **Service worker** pour l'Alerter : dupliquer le service avec la commande de démarrage
   `celery -A config worker -B --loglevel=info --concurrency=2`
5. **Variables d'environnement** : voir `.env.example`. Au minimum :
   - `SECRET_KEY`, `DEBUG=False`, `SITE_URL`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS` ;
   - la configuration SMTP pour les e-mails ;
   - `TELEGRAM_BOT_TOKEN`.
6. **Après le premier déploiement** : `python manage.py createsuperuser`, puis ajouter les morceaux du catalogue dans `/admin/` (Song).

## Organisation du code

| Dossier / fichier | Rôle |
|---|---|
| `events/models.py` | Événement, lieux, histoire, catégories, invités, vœux, moments, Alerter, rôles, tables, cadeaux |
| `events/services/seating.py` | Algorithme de répartition des tables (testé) |
| `events/services/alerter.py` | Rappels, budget, paliers d'invités, contrôle des photos |
| `events/services/pdf.py` | Carte d'invitation et plan de table en PDF (polices DejaVu : accents et lingala) |
| `events/views_api.py` | API JSON : `/api/e/…` pour l'organisateur, `/api/p/…` pour les invités |
| `events/consumers.py` | WebSocket d'un événement (moments, vœux, réactions, arrivées) |
| `static/miel/js/` | Assistant, panneau, plan de table, outils communs (temps réel, moments) |
| `templates/events/` | Pages organisateur et invités, 2 sites, 3 cartes |
| `events/i18n_catalog.py` | Traductions de l'interface invités |

## Traductions

L'interface invités est traduite avec l'i18n de Django : Google Translate n'est plus utilisé.
- Les textes sources sont en français, dans les templates (`{% translate "…" %}`).
- Les traductions sont dans `events/i18n_catalog.py`. `python manage.py build_translations` génère les fichiers `.po` et `.mo`, sans avoir besoin de l'outil gettext.
- **Lingala** : seuls les textes déjà présents dans les anciens modèles sont traduits. `python manage.py build_translations --missing` liste ce qui manque à compléter. Tout texte non traduit s'affiche en français.

## Reste à faire

- **Paiement et abonnements** : prochaine étape.
- **WhatsApp Business API** : le code est prêt (`events/services/notify.py`). Il faut un compte Meta validé, puis remplir `WHATSAPP_TOKEN` et `WHATSAPP_PHONE_ID`.
- **Éditeur photo avancé du mur** (filtres, stickers, recadrage) et **galerie photos du site** de l'ancienne version : à reprendre.
