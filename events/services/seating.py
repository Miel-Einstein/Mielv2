"""Répartition des invités sur les tables.

Règles (dans l'ordre) :
1. Les catégories marquées « table d'honneur » vont à la table d'honneur.
2. Les autres suivent l'ordre de priorité des catégories fixé par l'organisateur.
3. À l'intérieur d'une catégorie, on assoit ensemble les personnes qui ont
   au moins une langue de conversation en commun.
4. Un invité, ses accompagnants et ses enfants restent ensemble (groupe).
5. Enfants : selon les tranches d'âge de l'événement
   (avec les parents / table des enfants / place adulte). Les tout-petits
   ne prennent une chaise que si l'organisateur l'a choisi.
6. Une table des enfants réserve une place à la personne qui surveille.
Le résultat est déterministe (pas de hasard) pour qu'un nouveau calcul
donne toujours le même plan.
"""
from dataclasses import dataclass, field

SUPERVISOR = "SUPERVISOR"


def person_key(guest_id, kind, idx=0):
    if kind == "p":
        return f"g{guest_id}-p"
    return f"g{guest_id}-{kind}{idx}"


@dataclass
class Person:
    key: str
    gid: int
    name: str
    type: str  # principal | accomp | enfant
    cat_id: int | None
    langs: list = field(default_factory=list)
    age: int | None = None
    zone: str = "adult"  # adult | kids
    note: str = ""

    def as_dict(self):
        return {"key": self.key, "gid": self.gid, "name": self.name, "type": self.type, "cat": self.cat_id,
                "langs": self.langs, "age": self.age, "zone": self.zone, "note": self.note}


def persons(event):
    out = []
    guests = event.guests.filter(attending=True).prefetch_related("companions", "children").select_related("category")
    for g in guests:
        langs = g.table_languages()
        babies = [c for c in g.children.all() if c.age < event.age_with_parents]
        note = ""
        if babies and not event.baby_chair:
            note = "+ " + ", ".join(b.first_name for b in babies) + " (bébé)"
        out.append(Person(person_key(g.id, "p"), g.id, g.full_name, "principal", g.category_id, langs, note=note))
        for i, c in enumerate(g.companions.all()):
            out.append(Person(person_key(g.id, "c", i), g.id, f"{c.first_name} {g.last_name}".strip(), "accomp", g.category_id, langs))
        if not event.kids_invited:
            continue
        for i, k in enumerate(g.children.all()):
            if k.age < event.age_with_parents:
                if event.baby_chair:
                    out.append(Person(person_key(g.id, "k", i), g.id, k.first_name, "enfant", g.category_id, langs, k.age))
            elif event.kids_table and k.age <= event.age_kids_max:
                out.append(Person(person_key(g.id, "k", i), g.id, k.first_name, "enfant", g.category_id, langs, k.age, zone="kids"))
            else:
                out.append(Person(person_key(g.id, "k", i), g.id, k.first_name, "enfant", g.category_id, langs, k.age))
    return out


def compute_plan(event, persons_list, cap=8, kids_cap=10):
    """Calcule un plan sans toucher à la base. Renvoie une liste de dict tables."""
    order = list(event.categories.values_list("id", flat=True))
    honor = set(event.categories.filter(is_honor=True).values_list("id", flat=True))
    pindex = {p.key: p for p in persons_list}

    groups = {}
    for p in persons_list:
        if p.zone == "kids":
            continue
        groups.setdefault(p.gid, []).append(p)

    def sort_key(g):
        c = g[0].cat_id
        return (order.index(c) if c in order else len(order), (g[0].langs or [""])[0], -len(g), g[0].gid)

    group_list = sorted(groups.values(), key=sort_key)
    tables = []

    def new_table(name, capacity, kind):
        t = {"name": name, "capacity": capacity, "kind": kind, "seats": [None] * capacity}
        tables.append(t)
        return t

    def free(t):
        return t["seats"].count(None)

    def cats(t):
        return {pindex[k].cat_id for k in t["seats"] if k and k in pindex}

    def langs(t):
        return {l for k in t["seats"] if k and k in pindex for l in pindex[k].langs}

    def place(t, g):
        i = 0
        for p in g:
            while t["seats"][i] is not None:
                i += 1
            t["seats"][i] = p.key

    if honor:
        new_table("Table d'honneur", cap, "honor")

    for g in group_list:
        is_honor = g[0].cat_id in honor
        size = len(g)
        if size > cap:  # groupe plus grand qu'une table : on le découpe
            chunks = [g[i:i + cap] for i in range(0, size, cap)]
        else:
            chunks = [g]
        for chunk in chunks:
            kind = "honor" if is_honor else "std"
            cand = [t for t in tables if t["kind"] == kind and free(t) >= len(chunk)]
            best = (next((t for t in cand if chunk[0].cat_id in cats(t) and set(chunk[0].langs) & langs(t)), None)
                    or next((t for t in cand if chunk[0].cat_id in cats(t)), None)
                    or next((t for t in cand if not any(t["seats"])), None))
            if best is None and is_honor:
                best = next((t for t in tables if t["kind"] == "std" and free(t) >= len(chunk)), None)
            if best is None:
                best = new_table("", cap, "std")
            place(best, chunk)

    kids = [p for p in persons_list if p.zone == "kids"]
    if event.kids_table and kids:
        kt = None
        for k in sorted(kids, key=lambda p: (p.age or 0, p.gid)):
            if kt is None or free(kt) == 0:
                kt = new_table("Table des enfants", kids_cap, "kids")
                kt["seats"][0] = SUPERVISOR
            kt["seats"][kt["seats"].index(None)] = k.key
    return tables


def assign(event, cap=8, kids_cap=10):
    """Recalcule et enregistre le plan de table de l'événement."""
    from events.models import Table

    plan = compute_plan(event, persons(event), cap, kids_cap)
    event.tables.all().delete()
    Table.objects.bulk_create([
        Table(event=event, order=i, name=t["name"], capacity=t["capacity"], kind=t["kind"], seats=t["seats"])
        for i, t in enumerate(plan)
    ])
    return event.tables.all()


def clean_seats(event):
    """Retire des tables les personnes qui n'existent plus (RSVP modifié)."""
    valid = {p.key for p in persons(event)} | {SUPERVISOR}
    for t in event.tables.all():
        seats = [k if k in valid else None for k in t.seats]
        seats = (seats + [None] * t.capacity)[: t.capacity]
        if seats != t.seats:
            t.seats = seats
            t.save(update_fields=["seats"])


def seat_of(event, key):
    for t in event.tables.all():
        if key in t.seats:
            return t, t.seats.index(key)
    return None, None
