"""Crée un compte et un mariage de démonstration (données fictives).

python manage.py seed_demo  →  utilisateur « demo » / mot de passe « demo-miel-2026 »
"""
from datetime import date, time, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image, ImageDraw

from events.models import Child, Companion, Event, GalleryImage, Guest, Moment, Song, StoryStep, Venue, Wish


def _art(c1, c2, name="img.jpg", size=(900, 900)):
    """Image de démonstration : dégradé doux avec un cercle, sans photo réelle."""
    w, h = size
    im = Image.new("RGB", size, c1)
    d = ImageDraw.Draw(im)
    for y in range(h):
        k = y / h
        d.line([(0, y), (w, y)], fill=tuple(int(c1[i] * (1 - k) + c2[i] * k) for i in range(3)))
    d.ellipse([w * .3, h * .3, w * .7, h * .7], outline=(255, 245, 225), width=6)
    buf = BytesIO()
    im.save(buf, "JPEG", quality=82)
    return ContentFile(buf.getvalue(), name=name)
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
        ev.couple = {"p1": {"name": "Awa", "text": {"fr": "Rieuse, curieuse et toujours en avance. Elle a dit oui avant la fin de la question.", "en": "Cheerful, curious and always early. She said yes before the question was over."}},
                     "p2": {"name": "Daniel", "text": {"fr": "Calme, gourmand et un peu poète. Il a répété sa demande pendant trois mois.", "en": "Calm, a food lover and a bit of a poet. He rehearsed his proposal for three months."}}}
        ev.partner1_image.save("awa.jpg", _art((233, 168, 59), (110, 31, 42)), save=False)
        ev.partner2_image.save("daniel.jpg", _art((74, 24, 32), (201, 166, 107)), save=False)
        ev.save()
        for i, cols in enumerate([((231, 212, 173), (110, 31, 42)), ((201, 166, 107), (26, 18, 11)), ((243, 234, 217), (166, 124, 58)),
                                  ((110, 31, 42), (231, 212, 173)), ((74, 24, 32), (243, 234, 217)), ((166, 124, 58), (250, 246, 239))]):
            GalleryImage.objects.create(event=ev, order=i, image=_art(*cols, name=f"galerie-{i + 1}.jpg"))
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
