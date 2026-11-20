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
