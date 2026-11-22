import json
from datetime import time, timedelta

from django.contrib.auth.models import User
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone

from events.models import AlertLog, Category, Child, Companion, Event, Guest, Moment, Table
from events.services import alerter, seating
from events.services.defaults import seed_event_defaults


def make_event(**kw):
    user = User.objects.create_user("org", "org@exemple.com", "pw-12345678")
    data = dict(owner=user, type="mariage", title={"fr": "Awa & Daniel"}, languages=["fr", "en"],
                services=["carte", "tables", "alerter", "mur", "moments", "site", "cadeaux"],
                date=timezone.localdate() + timedelta(days=30), start_time=time(15))
    data.update(kw)
    ev = Event.objects.create(**data)
    seed_event_defaults(ev)
    return user, ev


class SeatingTests(TestCase):
    def setUp(self):
        self.user, self.ev = make_event(kids_table=True, age_with_parents=4, age_kids_max=12)
        self.honor, self.fam = self.ev.categories.filter(is_honor=True).first(), self.ev.categories.filter(is_honor=False).first()

    def guest(self, first, cat, langs=("fr",), comps=0, kids=()):
        g = Guest.objects.create(event=self.ev, first_name=first, last_name="X", category=cat, languages=list(langs))
        for i in range(comps):
            Companion.objects.create(guest=g, first_name=f"C{i}")
        for age in kids:
            Child.objects.create(guest=g, first_name=f"K{age}", age=age)
        return g

    def test_honor_table_and_groups_together(self):
        p = self.guest("Papa", self.honor)
        g = self.guest("Marie", self.fam, comps=2)
        seating.assign(self.ev)
        honor_table = self.ev.tables.get(kind="honor")
        self.assertIn(seating.person_key(p.id, "p"), honor_table.seats)
        t, _ = seating.seat_of(self.ev, seating.person_key(g.id, "p"))
        self.assertIn(seating.person_key(g.id, "c", 1), t.seats)

    def test_kids_by_age(self):
        g = self.guest("Marie", self.fam, kids=(2, 7, 15))
        keys = {p.key: p for p in seating.persons(self.ev)}
        self.assertNotIn(seating.person_key(g.id, "k", 0), keys)  # bébé sans chaise
        self.assertEqual(keys[seating.person_key(g.id, "k", 1)].zone, "kids")
        self.assertEqual(keys[seating.person_key(g.id, "k", 2)].zone, "adult")
        seating.assign(self.ev)
        kt = self.ev.tables.get(kind="kids")
        self.assertEqual(kt.seats[0], seating.SUPERVISOR)
        self.assertIn(seating.person_key(g.id, "k", 1), kt.seats)

    def test_language_affinity(self):
        # Deux tables gardent une place libre : l'invité italophone va vers la table italophone.
        self.guest("B", self.fam, langs=("fr",), comps=2)
        a = self.guest("A", self.fam, langs=("it",), comps=2)
        c = self.guest("C", self.fam, langs=("it",))
        seating.assign(self.ev, {"tables": 3, "capacity": 4, "specials": []})
        ta, _ = seating.seat_of(self.ev, seating.person_key(a.id, "p"))
        tc, _ = seating.seat_of(self.ev, seating.person_key(c.id, "p"))
        self.assertEqual(ta.id, tc.id)

    def test_number_of_tables_and_special_capacities(self):
        for i in range(10):
            self.guest(f"G{i}", self.fam)
        unplaced = seating.assign(self.ev, {"tables": 2, "capacity": 3, "specials": [{"name": "Mariés", "capacity": 2, "kind": "std"}]})
        caps = [t.capacity for t in self.ev.tables.all()]
        self.assertEqual(caps, [2, 3, 3])  # le nombre de tables est respecté
        self.assertEqual(len(unplaced), 2)  # 10 personnes pour 8 places
        self.assertEqual(self.ev.table_config["tables"], 2)

    def test_kids_with_parents_without_kids_table(self):
        g = self.guest("Marie", self.fam, kids=(7,))
        seating.assign(self.ev, {"tables": 1, "capacity": 8, "specials": []})
        t, _ = seating.seat_of(self.ev, seating.person_key(g.id, "k", 0))
        self.assertIsNotNone(t)

    def test_deterministic(self):
        for i in range(12):
            self.guest(f"G{i}", self.fam, comps=i % 2)
        seating.assign(self.ev)
        first = [t.seats for t in self.ev.tables.all()]
        seating.assign(self.ev)
        self.assertEqual(first, [t.seats for t in self.ev.tables.all()])


class ApiTests(TestCase):
    def setUp(self):
        self.user, self.ev = make_event()
        self.client.login(username="org", password="pw-12345678")

    def j(self, method, url, data=None):
        return getattr(self.client, method)(url, data=json.dumps(data or {}), content_type="application/json")

    def test_event_patch_and_translations(self):
        r = self.j("patch", f"/api/e/{self.ev.slug}/", {"title": {"fr": "Fête", "en": "Party"}, "services": ["tables"]})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["title"]["en"], "Party")
        self.assertIn("carte", r.json()["services"])

    def test_site_only_for_weddings(self):
        r = self.j("patch", f"/api/e/{self.ev.slug}/", {"type": "anniversaire"})
        self.assertNotIn("site", r.json()["services"])

    def test_other_user_forbidden(self):
        User.objects.create_user("intrus", password="pw-12345678")
        self.client.logout()
        self.client.login(username="intrus", password="pw-12345678")
        self.assertEqual(self.client.get(f"/api/e/{self.ev.slug}/").status_code, 404)

    def test_rsvp_wall_reactions_flow(self):
        cat = self.ev.categories.filter(is_honor=False).first()
        r = self.j("post", f"/api/p/{self.ev.slug}/rsvp/", {"first_name": "Marie", "last_name": "D", "attending": True, "category": cat.id,
                                                             "companions": ["Jean"], "children": [{"name": "Léa", "age": 6}], "languages": ["fr", "ln"], "lang": "en"})
        self.assertEqual(r.status_code, 201)
        token = r.json()["token"]
        g = Guest.objects.get(token=token)
        self.assertEqual(g.companions.count(), 1)
        self.assertEqual(g.languages, ["fr", "ln"])
        self.assertEqual(self.client.get(r.json()["card_url"].split("8000")[-1]).status_code, 200)
        pdf = self.client.get(r.json()["pdf_url"].split("8000")[-1])
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(b"".join(pdf.streaming_content).startswith(b"%PDF"))
        w = self.j("post", f"/api/p/{self.ev.slug}/wishes/", {"token": token, "text": "Bravo !"}).json()
        r1 = self.j("post", f"/api/p/{self.ev.slug}/wishes/{w['id']}/react/", {"token": token, "emoji": "❤️"}).json()
        self.assertEqual(r1["reactions"]["❤️"], 1)
        r2 = self.j("post", f"/api/p/{self.ev.slug}/wishes/{w['id']}/react/", {"token": token, "emoji": "❤️"}).json()
        self.assertEqual(r2["reactions"]["❤️"], 0)  # une seule réaction par personne : second clic = retrait
        self.assertEqual(self.j("post", f"/api/p/{self.ev.slug}/wishes/", {"token": "inconnu", "text": "x"}).status_code, 403)
        self.j("post", f"/api/p/{self.ev.slug}/arrived/", {"token": token})
        self.assertTrue(Guest.objects.get(token=token).arrived)

    def test_honor_category_not_selectable_in_rsvp(self):
        honor = self.ev.categories.filter(is_honor=True).first()
        r = self.j("post", f"/api/p/{self.ev.slug}/rsvp/", {"first_name": "X", "category": honor.id})
        self.assertIsNone(Guest.objects.get(token=r.json()["token"]).category)

    def test_moment_needs_photo(self):
        m = Moment.objects.create(event=self.ev, title={"fr": "Baiser"}, kind="reveal")
        self.assertEqual(self.j("post", f"/api/e/{self.ev.slug}/moments/{m.id}/launch/").status_code, 409)
        r = self.j("post", f"/api/e/{self.ev.slug}/moments/{m.id}/launch/", {"as_message": True})
        self.assertEqual(r.status_code, 200)
        live = self.client.get(f"/api/p/{self.ev.slug}/live/").json()
        self.assertEqual(live["moment"]["kind"], "message")

    def test_tables_put_rejects_duplicates_and_unknown(self):
        cat = self.ev.categories.filter(is_honor=False).first()
        g = Guest.objects.create(event=self.ev, first_name="A", category=cat)
        k = seating.person_key(g.id, "p")
        r = self.j("put", f"/api/e/{self.ev.slug}/tables/", [{"capacity": 4, "seats": [k, k, "gX-p", None]}])
        self.assertEqual(r.json()["tables"][0]["seats"], [k, None, None, None])

    def test_role_delete_reassigns_tasks(self):
        r = self.j("post", f"/api/e/{self.ev.slug}/roles/", {"name": "Traiteur", "contacts": [{"name": "Paul", "email": "p@x.com"}]}).json()[0]
        item = self.ev.alerter_items.first()
        self.j("patch", f"/api/e/{self.ev.slug}/alerter/{item.id}/", {"role": r["id"]})
        self.client.delete(f"/api/e/{self.ev.slug}/roles/{r['id']}/?tasks=owner")
        item.refresh_from_db()
        self.assertIsNone(item.role)

    def test_contact_requires_channel(self):
        r = self.j("post", f"/api/e/{self.ev.slug}/roles/", {"name": "X", "contacts": [{"name": "Sans moyen"}]})
        self.assertEqual(r.status_code, 400)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class AlerterTests(TestCase):
    def test_reminders_budget_and_once_only(self):
        user, ev = make_event(budget=1000, guest_target=10)
        item = ev.alerter_items.first()
        item.due_offset_days = -7
        item.price = 900
        item.save()
        today = ev.date - timedelta(days=14)  # échéance J-7 → rappel « 7 jours avant »
        n = alerter.run_for_event(ev, today)
        self.assertGreaterEqual(n, 2)  # tâche + budget 80 %
        self.assertTrue(mail.outbox)
        self.assertEqual(alerter.run_for_event(ev, today), 0)  # pas de doublon
        self.assertTrue(AlertLog.objects.filter(event=ev, key="budget-80").exists())

    def test_warning_for_missing_photo_and_supervisor(self):
        user, ev = make_event(kids_table=True, supervisor_name="")
        Moment.objects.create(event=ev, title={"fr": "Baiser"}, kind="reveal")
        w = alerter.warnings(ev)
        self.assertTrue(any("Baiser" in x for x in w))
        self.assertTrue(any("surveiller" in x for x in w))


class PageTests(TestCase):
    def test_pages_render(self):
        user, ev = make_event()
        self.client.login(username="org", password="pw-12345678")
        self.assertRedirects(self.client.get(f"/app/e/{ev.slug}/bot/"), f"/app/e/{ev.slug}/?bot=1")
        for url in ["/", f"/app/e/{ev.slug}/", f"/app/e/{ev.slug}/tables/", f"/app/e/{ev.slug}/cadeaux/", f"/e/{ev.slug}/?tpl=B"]:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.client.logout()
        for url in [f"/e/{ev.slug}/", f"/e/{ev.slug}/rsvp/", f"/e/{ev.slug}/rsvp/?lang=en", f"/e/{ev.slug}/mur/", f"/e/{ev.slug}/ecran/",
                    f"/e/{ev.slug}/y-aller/", f"/e/{ev.slug}/cadeaux/", f"/i/{ev.share_token}/"]:
            r = self.client.get(url, follow=True)
            self.assertEqual(r.status_code, 200, url)
        ev.site_template = "B"
        ev.save()
        self.assertEqual(self.client.get(f"/e/{ev.slug}/").status_code, 200)
        self.assertEqual(self.client.get(f"/app/e/{ev.slug}/plan.pdf").status_code, 302)  # connexion requise


class AuthTests(TestCase):
    def test_signup_requires_terms(self):
        data = {"username": "awa", "email": "awa@exemple.com", "password": "Miel-secret-2026", "confirmation": "Miel-secret-2026"}
        r = self.client.post("/inscription/", data)
        self.assertContains(r, "accepter les conditions")
        self.assertFalse(User.objects.filter(username="awa").exists())
        r = self.client.post("/inscription/", {**data, "terms_accepted": "1"})
        self.assertRedirects(r, "/")
        self.assertTrue(User.objects.get(username="awa").terms)

    def test_signup_password_mismatch_and_login_page(self):
        r = self.client.post("/inscription/", {"username": "x", "email": "x@exemple.com", "password": "a", "confirmation": "b", "terms_accepted": "1"})
        self.assertContains(r, "identiques")
        self.assertEqual(self.client.get("/connexion/").status_code, 200)


class SiteCTests(TestCase):
    def test_template_c_renders_couple_and_gallery(self):
        u = User.objects.create_user("c", "c@x.co", "pw-12345678")
        ev = Event.objects.create(owner=u, type="mariage", title={"fr": "Awa & Daniel"}, languages=["fr", "en"], services=["carte", "site"], site_template="C",
                                  couple={"p1": {"name": "Awa", "text": {"fr": "Rieuse", "en": "Cheerful"}}, "p2": {"name": "Daniel", "text": {}}})
        r = self.client.get(f"/e/{ev.slug}/?lang=en")
        self.assertContains(r, "c-hero")
        self.assertContains(r, "Cheerful")
        self.assertContains(r, "The couple")
        self.client.force_login(u)
        r = self.client.patch(f"/api/e/{ev.slug}/", data='{"site_template": "Z"}', content_type="application/json")
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(f"/api/e/{ev.slug}/", data='{"couple": {"p1": {"name": "A", "text": {"fr": "x", "de": "y"}}}}', content_type="application/json")
        self.assertEqual(r.status_code, 200)
        ev.refresh_from_db()
        self.assertEqual(ev.couple["p1"]["text"], {"fr": "x"})


class PlanAndBackgroundTests(TestCase):
    def setUp(self):
        from events.services.defaults import seed_event_defaults
        self.u = User.objects.create_user("p", "p@x.co", "pw-12345678")
        self.ev = Event.objects.create(owner=self.u, type="mariage", title={"fr": "Ruth & Christian"}, languages=["fr"], services=["carte", "tables", "site"])
        seed_event_defaults(self.ev)
        cat = self.ev.categories.filter(is_honor=False).first()
        for i in range(20):
            Guest.objects.create(event=self.ev, first_name=f"Invité{i}", last_name="Test", attending=True, category=cat)
        self.client.force_login(self.u)

    def test_plan_downloads_and_themes(self):
        from events.services import seating
        seating.assign(self.ev, {"tables": 3, "capacity": 8, "specials": []})
        r = self.client.post(f"/api/e/{self.ev.slug}/tables/theme/", data='{"theme": "vertus_versets"}', content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual([t["name"] for t in r.json()["tables"]], ["Amour", "Foi", "Complicité"])
        # les noms et versets restent après une nouvelle répartition
        seating.assign(self.ev, {"tables": 3, "capacity": 8, "specials": []})
        self.assertEqual(self.ev.tables.first().quote_ref, "1 Corinthiens 13:8")
        for style in ("jardin", "nuit", "minimal"):
            r = self.client.get(f"/app/e/{self.ev.slug}/plan.svg?style={style}")
            self.assertEqual(r["Content-Type"], "image/svg+xml; charset=utf-8")
            body = r.content.decode()
            self.assertIn("PLAN DE TABLE", body)
            self.assertIn("Invité0 Test", body)
            self.assertIn("1 CORINTHIENS 13:8", body)
        r = self.client.get(f"/app/e/{self.ev.slug}/plan.pdf?style=nuit")
        self.assertEqual(b"".join(r.streaming_content)[:4], b"%PDF")

    def test_site_background(self):
        self.ev.site_template = "C"
        self.ev.save()
        r = self.client.patch(f"/api/e/{self.ev.slug}/", data='{"site_bg": {"mode": "gradient", "c1": "#123456", "c2": "javascript:x", "veil": 200, "scope": "site"}}', content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.ev.refresh_from_db()
        self.assertEqual(self.ev.site_bg["c2"], "#e7d4ad")
        self.assertEqual(self.ev.site_bg["veil"], 85)
        self.assertContains(self.client.get(f"/e/{self.ev.slug}/"), "linear-gradient(160deg,#123456,#e7d4ad)")
        self.assertNotContains(self.client.get(f"/e/{self.ev.slug}/rsvp/"), "160deg,#123456")  # seulement le site
        self.assertNotContains(self.client.get("/connexion/"), "#123456")


class PlanListTests(PlanAndBackgroundTests):
    def test_list_layouts_and_custom_header(self):
        from events.services import seating
        seating.assign(self.ev, {"tables": 3, "capacity": 8, "specials": []})
        hdr = {"monogram": "R | C", "stats": False, "texts": {"fr": {"title": "Trouvez votre table", "tagline": "", "place": "Yaoundé"}, "de": {"title": "x"}}}
        r = self.client.patch(f"/api/e/{self.ev.slug}/", data=json.dumps({"plan_header": hdr}), content_type="application/json")
        self.assertEqual(r.status_code, 200)
        self.assertNotIn("de", r.json()["plan_header"]["texts"])
        body = self.client.get(f"/app/e/{self.ev.slug}/plan.svg?layout=alpha&sort=nom").content.decode()
        self.assertIn("TROUVEZ VOTRE TABLE", body)
        self.assertIn("TEST Invité0", body)
        self.assertNotIn("Merci de célébrer", body)
        self.assertNotIn("invités", body)  # nombre d'invités masqué
        body = self.client.get(f"/app/e/{self.ev.slug}/plan.svg?layout=table").content.decode()
        self.assertIn("Invité0 Test", body)
        r = self.client.get(f"/app/e/{self.ev.slug}/plan.pdf?layout=alpha")
        self.assertEqual(b"".join(r.streaming_content)[:4], b"%PDF")
        self.assertEqual(self.client.get(f"/api/e/{self.ev.slug}/plan-header/").json()["fr"]["title"], "PLAN DE TABLE")


class ThemeTests(TestCase):
    def test_palette_applies_to_app_and_guest_pages_not_login(self):
        u = User.objects.create_user("t", "t@x.co", "pw-12345678")
        ev = Event.objects.create(owner=u, type="anniversaire", title={"fr": "Fête"}, languages=["fr"], services=["carte"])
        self.client.force_login(u)
        self.assertEqual(self.client.post("/api/me/theme/", data='{"theme": "rouge-vif"}', content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post("/api/me/theme/", data='{"theme": "ivoire"}', content_type="application/json").status_code, 200)
        self.assertContains(self.client.get(f"/app/e/{ev.slug}/"), 'data-theme="ivoire"')
        self.client.logout()
        self.assertContains(self.client.get(f"/e/{ev.slug}/rsvp/"), 'data-theme="ivoire"')  # invités : palette de l'organisateur
        self.assertNotContains(self.client.get("/connexion/"), "data-theme")


class CardTemplatesTests(TestCase):
    def setUp(self):
        from io import BytesIO
        from django.core.files.base import ContentFile
        from PIL import Image
        self.u = User.objects.create_user("k", "k@x.co", "pw-12345678")
        self.ev = Event.objects.create(owner=self.u, type="mariage", title={"fr": "Awa & Daniel", "en": "Awa & Daniel"}, languages=["fr", "en"], services=["carte", "mur"],
                                       date=timezone.localdate() + timedelta(days=10), card_message={"fr": "Merci d'être là"})
        b = BytesIO(); Image.new("RGB", (1200, 600), (120, 40, 40)).save(b, "JPEG")
        self.ev.cover_image.save("c.jpg", ContentFile(b.getvalue()))
        self.g = Guest.objects.create(event=self.ev, first_name="Marie", last_name="Dupont", attending=True)

    def test_photo_cards_render_with_clickable_qr_and_pdf(self):
        for tpl in ("luxe", "scandinave", "botanique"):
            self.ev.card_template = tpl
            self.ev.save()
            r = self.client.get(f"/e/{self.ev.slug}/carte/{self.g.token}/?lang=fr")
            self.assertContains(r, f'<a class="qr" href="')
            self.assertContains(r, f"?g={self.g.token}")
            self.assertContains(r, 'class="fimg"')
            pdf = b"".join(self.client.get(f"/e/{self.ev.slug}/carte/{self.g.token}/pdf/").streaming_content)
            self.assertTrue(pdf.startswith(b"%PDF"))
            self.assertIn(b"/URI", pdf)  # le QR code du PDF est un lien
        self.ev.card_template = "luxe"
        self.ev.save()
        self.assertContains(self.client.get(f"/e/{self.ev.slug}/carte/{self.g.token}/?lang=fr"), "J-10")

    def test_focus_api_and_crop(self):
        from events.services.images import focus_crop
        self.client.force_login(self.u)
        r = self.client.patch(f"/api/e/{self.ev.slug}/", data=json.dumps({"cover_focus": {"cover_image": {"x": 150, "y": 20, "z": 9}}, "card_template": "luxe"}), content_type="application/json")
        self.assertEqual(r.json()["cover_focus"]["cover_image"], {"x": 100.0, "y": 20.0, "z": 3.0})
        self.assertEqual(self.client.patch(f"/api/e/{self.ev.slug}/", data='{"card_template": "zzz"}', content_type="application/json").status_code, 400)
        with self.ev.cover_image.open("rb") as f:
            im = focus_crop(f, 3 / 4, {"x": 100, "y": 50, "z": 2})
        self.assertAlmostEqual(im.size[0] / im.size[1], 0.75, places=2)
        self.assertEqual(self.client.get(f"/app/e/{self.ev.slug}/carte-apercu/?lang=en").status_code, 200)


class InterfaceLanguageTests(TestCase):
    def test_signup_login_api_and_alert_language(self):
        from django.core import mail
        from events.models import UserSettings, Contact, Role, AlerterItem
        from events.services import alerter
        self.client.cookies["miel_ui"] = "it"
        r = self.client.get("/connexion/")
        self.assertContains(r, "dataset.ui='it'")
        self.assertContains(r, "ui-it.js")
        data = {"username": "giulia", "email": "g@x.co", "password": "Miel-secret-2026", "confirmation": "Miel-secret-2026", "terms_accepted": "1"}
        self.client.post("/inscription/", data)
        u = User.objects.get(username="giulia")
        self.assertEqual(u.miel_settings.ui_lang, "it")
        self.assertEqual(self.client.post("/api/me/ui-lang/", data='{"lang": "xx"}', content_type="application/json").status_code, 400)
        r = self.client.post("/api/me/ui-lang/", data='{"lang": "en"}', content_type="application/json")
        self.assertEqual(r.cookies["miel_ui"].value, "en")
        u.refresh_from_db()
        self.assertEqual(u.miel_settings.ui_lang, "en")
        # navigateur en lingala, sans cookie : page de connexion en lingala
        c2 = self.client_class()
        self.assertContains(c2.get("/connexion/", HTTP_ACCEPT_LANGUAGE="ln-CG,fr;q=0.8"), "dataset.ui='ln'")
        # tâches de départ et rappels dans la langue de chacun
        ev = Event.objects.create(owner=u, type="mariage", title={"fr": "Fête"}, languages=["fr"], services=["alerter"], date=timezone.localdate())
        from events.services.defaults import seed_event_defaults
        seed_event_defaults(ev)
        self.assertTrue(ev.alerter_items.filter(title="Set the budget").exists())
        role = Role.objects.create(event=ev, name="Fleurs")
        tante = Contact.objects.create(event=ev, name="Tante Rose", emails=["rose@x.co"], language="it", consent=True)
        role.contacts.add(tante)
        AlerterItem.objects.create(event=ev, title="Fleuriste", due_offset_days=0, role=role)
        mail.outbox.clear()
        alerter.run_for_event(ev)
        subjects = {m.to[0]: m.subject for m in mail.outbox}
        self.assertEqual(subjects["rose@x.co"], "⏰ Promemoria: Fleuriste")
        self.assertEqual(subjects["g@x.co"], "⏰ Reminder: Fleuriste")


class TelegramLinkTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user("tg", "tg@x.co", "pw-12345678")
        self.ev = Event.objects.create(owner=self.u, type="mariage", title={"fr": "Awa & Daniel"}, languages=["fr"], services=["mur"])
        self.client.force_login(self.u)

    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_BOT_USERNAME="MielBot", TELEGRAM_WEBHOOK_SECRET="s" * 20)
    def test_token_links_group_and_channel_then_photos_go_to_all(self):
        from unittest import mock
        from events.models import TelegramChannel
        data = self.client.get(f"/api/e/{self.ev.slug}/telegram/").json()
        tok = data["token"]
        self.assertRegex(tok, r"^[a-f0-9]{64}$")
        self.assertEqual(data["group_link"], f"https://t.me/MielBot?startgroup={tok}")
        hook = "/telegram/webhook/" + "s" * 20 + "/"
        self.assertEqual(self.client.post("/telegram/webhook/mauvais-secret/", data="{}", content_type="application/json").status_code, 404)
        upd = {"update_id": 1, "message": {"message_id": 5, "chat": {"id": -100123, "type": "supergroup", "title": "Famille Mbala"}, "text": "token: " + tok}}
        self.assertEqual(self.client.post(hook, data=json.dumps(upd), content_type="application/json").status_code, 200)
        upd2 = {"update_id": 2, "channel_post": {"message_id": 9, "chat": {"id": -100999, "type": "channel", "title": "Photos du mariage"}, "text": f"/start@MielBot {tok}"}}
        self.client.post(hook, data=json.dumps(upd2), content_type="application/json")
        self.assertEqual(sorted(self.ev.telegram_channels.values_list("title", flat=True)), ["Famille Mbala", "Photos du mariage"])
        # un mauvais jeton ou une conversation privée ne relient rien
        self.client.post(hook, data=json.dumps({"update_id": 3, "message": {"message_id": 1, "chat": {"id": 7, "type": "private"}, "text": tok}}), content_type="application/json")
        self.assertEqual(self.ev.telegram_channels.count(), 2)
        # le mur affiche les groupes et la photo part vers les deux
        self.assertContains(self.client.get(f"/e/{self.ev.slug}/mur/"), "Famille Mbala")
        g = Guest.objects.create(event=self.ev, first_name="Paul", last_name="M", attending=True)
        from django.core.files.uploadedfile import SimpleUploadedFile
        with mock.patch("events.services.notify.send_telegram_media", return_value=True) as send:
            r = self.client.post(f"/api/p/{self.ev.slug}/media/", {"token": g.token, "file": SimpleUploadedFile("a.jpg", b"img", content_type="image/jpeg")})
        self.assertEqual(r.json()["sent"], 2)
        self.assertEqual({c.args[0] for c in send.call_args_list}, {"-100123", "-100999"})
        # le bot retiré du groupe : groupe désactivé ; nouveau jeton : l'ancien ne marche plus
        self.client.post(hook, data=json.dumps({"update_id": 4, "my_chat_member": {"chat": {"id": -100123}, "new_chat_member": {"status": "kicked"}}}), content_type="application/json")
        self.assertFalse(TelegramChannel.objects.get(chat_id="-100123").active)
        new = self.client.post(f"/api/e/{self.ev.slug}/telegram/", data='{"regenerate": true}', content_type="application/json").json()["token"]
        self.assertNotEqual(new, tok)


class HelpAndPasswordTests(TestCase):
    def setUp(self):
        from events.services.help import load_builtin
        load_builtin()
        self.u = User.objects.create_user("h", "h@x.co", "pw-12345678")
        self.client.force_login(self.u)

    def ask(self, q, **kw):
        return self.client.post("/api/help/ask/", data=json.dumps({"q": q, **kw}), content_type="application/json").json()

    def test_answers_context_actions_feedback_and_unknown(self):
        from events.models import HelpEntry, UnansweredQuestion
        r = self.ask("le pop-up du bot a disparu", lang="fr")
        self.assertEqual(r["found"]["question"], "Comment rouvrir l'assistant Miel ?")
        self.assertEqual(r["found"]["actions"][0]["flash"], "#botFab")
        r = self.ask("how much does it cost", lang="en")
        self.assertIn("€25", r["found"]["answer"])
        r = self.ask("comment remplir cette section ?", lang="fr", context="bot:enfants")
        self.assertIn("table des enfants", r["found"]["answer"])
        eid = r["found"]["id"]
        self.client.post(f"/api/help/{eid}/feedback/", data='{"useful": true}', content_type="application/json")
        self.assertEqual(HelpEntry.objects.get(pk=eid).helpful, 1)
        # question hors sujet : enregistrée (et comptée si elle revient)
        for _ in range(2):
            r = self.ask("Quelle est la recette du poulet moambe ?", lang="fr", context="panel")
        self.assertIsNone(r["found"])
        q = UnansweredQuestion.objects.get()
        self.assertEqual((q.count, q.context, q.user), (2, "panel", self.u))
        # l'admin crée la réponse : elle sert tout de suite
        HelpEntry.objects.create(question={"fr": "Recette du moambe ?"}, answer={"fr": "Miel ne fait pas encore la cuisine 😄"}, keywords="recette poulet moambe cuisine")
        self.assertIn("cuisine", self.ask("recette du poulet moambe", lang="fr")["found"]["answer"])
        self.assertIn("Chaque étape", self.client.get("/api/help/here/?context=bot:inconnue&lang=fr").json()["answer"])

    def test_admin_prefills_from_unanswered(self):
        from events.models import UnansweredQuestion
        self.u.is_staff = self.u.is_superuser = True
        self.u.save()
        q = UnansweredQuestion.objects.create(text="Comment imprimer les badges ?", normalized="comment imprimer les badges", context="panel")
        self.assertContains(self.client.get("/admin/events/unansweredquestion/"), "Créer la réponse")
        self.assertContains(self.client.get(f"/admin/events/helpentry/add/?from_question={q.pk}"), "imprimer")

    def test_password_reset_mail_in_interface_language(self):
        from django.core import mail
        self.client.logout()
        self.client.cookies["miel_ui"] = "it"
        self.assertContains(self.client.get("/connexion/"), "/mot-de-passe-oublie/")
        r = self.client.post("/mot-de-passe-oublie/", {"email": "h@x.co"})
        self.assertRedirects(r, "/mot-de-passe-oublie/envoye/")
        self.assertEqual(mail.outbox[0].subject, "Miel · Reimposta la password")
        link = [l for l in mail.outbox[0].body.split() if "/mot-de-passe/" in l][0]
        r = self.client.get(link.replace("http://testserver", ""), follow=True)
        self.assertContains(r, "new_password1")
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": "Nuovo-miele-2027", "new_password2": "Nuovo-miele-2027"})
        self.assertRedirects(r, "/mot-de-passe/termine/")
        self.assertTrue(self.client.login(username="h", password="Nuovo-miele-2027"))


class CreateAndHelpVoiceTests(TestCase):
    def test_double_submit_creates_one_event(self):
        u = User.objects.create_user("dbl", "d@x.co", "pw-12345678")
        self.client.force_login(u)
        r1 = self.client.post("/app/nouveau/")
        r2 = self.client.post("/app/nouveau/")
        self.assertEqual(u.events.count(), 1)
        self.assertEqual(r1["Location"], r2["Location"])

    def test_identity_and_terms_questions(self):
        from events.services.help import load_builtin, search
        load_builtin(update=True)
        for q, key in [("qu'est-ce que Miel ?", "about"), ("qui es-tu", "about"), ("Who are you?", "about"),
                       ("comment ça marche", "about-how"), ("que disent les conditions d'utilisation", "terms"),
                       ("qui est responsable si bug", "terms-bugs")]:
            best, _, _ = search(q, "fr", "")
            self.assertEqual(best and best.key, key, q)
        self.assertIsNone(search("quelle est la capitale du Japon", "fr", "")[0])
