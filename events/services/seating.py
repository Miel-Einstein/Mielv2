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


def default_config(event, persons_list=None, cap=8):
    """Configuration proposée par défaut : tables particulières + assez de tables standard."""
    ps = persons_list if persons_list is not None else persons(event)
    specials = []
    if event.categories.filter(is_honor=True).exists():
        specials.append({"name": "Table d'honneur", "capacity": cap, "kind": "honor"})
    if event.kids_table and any(p.zone == "kids" for p in ps):
        specials.append({"name": "Table des enfants", "capacity": 10, "kind": "kids"})
    special_seats = sum(t["capacity"] for t in specials)
    n = max(1, -(-max(0, len(ps) - special_seats) // cap))  # arrondi au supérieur
    return {"tables": n, "capacity": cap, "specials": specials}


def normalize_config(config):
    cap = max(1, min(30, int(config.get("capacity") or 8)))
    n = max(0, min(200, int(config.get("tables") or 0)))
    specials = []
    for t in (config.get("specials") or [])[:50]:
        kind = t.get("kind") if t.get("kind") in ("std", "honor", "kids") else "std"
        specials.append({"name": (t.get("name") or "")[:120], "capacity": max(1, min(30, int(t.get("capacity") or cap))), "kind": kind})
    return {"tables": n, "capacity": cap, "specials": specials}


def compute_plan(event, persons_list, config):
    """Calcule un plan sans toucher à la base.

    config = {"tables": nombre de tables standard, "capacity": places par table standard,
              "specials": [{"name", "capacity", "kind": honor|kids|std}, ...]}
    Le nombre de tables est respecté : s'il manque des places, les personnes restantes
    sont laissées « non placées » (renvoyées dans unplaced).
    """
    config = normalize_config(config)
    order = list(event.categories.values_list("id", flat=True))
    honor = set(event.categories.filter(is_honor=True).values_list("id", flat=True))
    pindex = {p.key: p for p in persons_list}
    tables = [{"name": t["name"], "capacity": t["capacity"], "kind": t["kind"], "seats": [None] * t["capacity"]} for t in config["specials"]]
    tables += [{"name": "", "capacity": config["capacity"], "kind": "std", "seats": [None] * config["capacity"]} for _ in range(config["tables"])]
    kids_tables = [t for t in tables if t["kind"] == "kids"]
    for kt in kids_tables:
        kt["seats"][0] = SUPERVISOR  # place réservée à la personne qui surveille

    # Sans table des enfants, les enfants restent avec leurs parents.
    groups = {}
    kids = []
    for p in persons_list:
        if p.zone == "kids" and kids_tables:
            kids.append(p)
        else:
            groups.setdefault(p.gid, []).append(p)

    def sort_key(g):
        c = g[0].cat_id
        return (order.index(c) if c in order else len(order), (g[0].langs or [""])[0], -len(g), g[0].gid)

    def free(t):
        return t["seats"].count(None)

    def cats(t):
        return {pindex[k].cat_id for k in t["seats"] if k and k in pindex}

    def langs(t):
        return {l for k in t["seats"] if k and k in pindex for l in pindex[k].langs}

    def place(t, people):
        for p in people:
            t["seats"][t["seats"].index(None)] = p.key

    unplaced = []
    for g in sorted(groups.values(), key=sort_key):
        is_honor = g[0].cat_id in honor
        pool = [t for t in tables if t["kind"] == "honor"] if is_honor else []
        pool += [t for t in tables if t["kind"] == "std"]
        cand = [t for t in pool if free(t) >= len(g)]
        best = None
        if is_honor:
            best = next((t for t in cand if t["kind"] == "honor"), None)
        best = best or (next((t for t in cand if g[0].cat_id in cats(t) and set(g[0].langs) & langs(t)), None)
                        or next((t for t in cand if g[0].cat_id in cats(t)), None)
                        or next((t for t in cand if not any(t["seats"])), None)
                        or next((t for t in cand), None))
        if best:
            place(best, g)
            continue
        # Le groupe ne tient sur aucune table : on le répartit sur les places libres restantes.
        rest = list(g)
        for t in sorted(pool, key=free, reverse=True):
            while rest and free(t):
                place(t, [rest.pop(0)])
        unplaced += rest

    for k in sorted(kids, key=lambda p: (p.age or 0, p.gid)):
        kt = next((t for t in kids_tables if free(t)), None)
        if kt:
            place(kt, [k])
        else:
            st = next((t for t in tables if t["kind"] == "std" and free(t)), None)
            if st:
                place(st, [k])
            else:
                unplaced.append(k)
    return tables, [p.key for p in unplaced]


def assign(event, config=None):
    """Recalcule et enregistre le plan de table de l'événement."""
    from events.models import Table

    ps = persons(event)
    config = normalize_config(config or event.table_config or default_config(event, ps))
    plan, unplaced = compute_plan(event, ps, config)
    event.table_config = config
    event.save(update_fields=["table_config"])
    event.tables.all().delete()
    Table.objects.bulk_create([
        Table(event=event, order=i, name=t["name"], capacity=t["capacity"], kind=t["kind"], seats=t["seats"])
        for i, t in enumerate(plan)
    ])
    return unplaced


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
