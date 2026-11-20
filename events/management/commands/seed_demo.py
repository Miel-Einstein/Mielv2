"""Crée un compte et un mariage de démonstration (données fictives).

python manage.py seed_demo  →  utilisateur « demo » / mot de passe « demo-miel-2026 »
"""
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from events.models import Child, Companion, Event, Guest, Moment, Song, StoryStep, Venue, Wish
from events.services import seating
from events.services.defaults import seed_event_defaults


class Command(BaseCommand):
    help = "Crée un événement de démonstration complet"

    def handle(self, *args, **opts):
        user, created = User.objects.get_or_create(username="demo", defaults={"email": "demo@exemple.com"})
        if created:
            user.set_password("demo-miel-2026")
            user.save()
        song, _ = Song.objects.get_or_create(title="Morceau Miel n°1", defaults={
            "artist": "Miel Production", "youtube_url": "https://youtu.be/GqYPTMhw2m4"})
        langs = ["fr", "en", "it", "ln"]
        ev = Event.objects.create(
            owner=user, type="mariage", title={l: "Awa & Daniel" for l in langs},
            subtitle={"fr": "Nous nous marions", "en": "We're getting married", "it": "Ci sposiamo", "ln": "Tokobala"},
            date=timezone.localdate() + timedelta(days=60), start_time=time(15, 0), languages=langs,
            services=["carte", "cadeaux", "tables", "alerter", "mur", "moments", "site"], kids_table=True,
            supervisor_name="Tata Clarisse", budget=18000, guest_target=60, song=song)
        seed_event_defaults(ev)
        for i, (n, s, e, lat, lng, extra) in enumerate([
            ("Mairie", time(15), time(15, 45), 41.8935, 12.4829, {"parking": "Parking public à 200 m"}),
            ("Église Saint-Paul", time(16, 30), time(17, 45), 41.8986, 12.4768, {"entrance": "Portail latéral"}),
            ("Villa delle Rose — réception", time(19), time(23, 59), 41.9102, 12.4963, {"landmark": "Portail bleu après la station-service"}),
        ]):
            Venue.objects.create(event=ev, order=i, name={l: n for l in langs}, start=s, end=e, lat=lat, lng=lng, **extra)
        for i, (ti, tx) in enumerate([("Première rencontre", "Un mariage d'amis, une danse imprévue."), ("La demande", "Au coucher du soleil, sur le Pincio.")]):
            StoryStep.objects.create(event=ev, order=i, title={"fr": ti}, text={"fr": tx})
        cats = list(ev.categories.all())
        names = [("Papa", "Mbala", 0), ("Maman", "Mbala", 0), ("Grace", "Nkosi", 1), ("Paolo", "Bianchi", 2), ("Fatou", "Diop", 1),
                 ("Luca", "Romano", 3), ("Esther", "Mensah", 3), ("Didier", "Kabongo", 2), ("Chiara", "Ricci", 4), ("Samuel", "Dubois", 4)]
        for i, (f, l, c) in enumerate(names):
            g = Guest.objects.create(event=ev, first_name=f, last_name=l, category=cats[min(c, len(cats) - 1)],
                                     languages=[["fr", "ln"], ["it", "fr"], ["fr"], ["en", "fr"]][i % 4], nav_language="fr")
            if i % 3 == 0:
                Companion.objects.create(guest=g, first_name="Partenaire")
            if i % 4 == 1:
                Child.objects.create(guest=g, first_name="Noah", age=7)
                Child.objects.create(guest=g, first_name="Léa", age=2)
        Moment.objects.create(event=ev, order=0, title={"fr": "Entrée des mariés"}, kind="message", message={"fr": "Accueillons les mariés 👏✨"})
        Moment.objects.create(event=ev, order=1, title={"fr": "Le premier baiser 💋"}, kind="reveal")
        g = ev.guests.first()
        Wish.objects.create(event=ev, author_name=g.full_name, author_token=g.token, text="Que votre amour grandisse chaque jour !")
        seating.assign(ev)
        self.stdout.write(self.style.SUCCESS(f"Démo créée : /app/e/{ev.slug}/  (demo / demo-miel-2026)"))
