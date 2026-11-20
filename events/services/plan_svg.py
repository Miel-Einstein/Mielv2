"""Plan de table en SVG (et PDF A4 à partir du même dessin).

Trois modèles :
- « jardin »  : ivoire, cartes à fronton arrondi, feuillages et or (repris du plan modèle Miel) ;
- « nuit »    : bleu nuit et or, style soirée ;
- « minimal » : blanc et noir, peu d'encre, idéal pour l'imprimante du traiteur.

render_svg(...) produit une grande affiche (une seule page, toutes les tables).
render_pdf(...) produit un PDF A4 de plusieurs pages, sans couper une table en deux.
"""
import base64
import math
from io import BytesIO
from xml.sax.saxutils import escape

from django.utils import formats, translation

from events.services.seating import SUPERVISOR, persons

W = 1578
MARGIN = 50
COLS = 3
COLW = 470
GAP = (W - 2 * MARGIN - COLS * COLW) // (COLS - 1)  # 34
PAGE_H = round(W * 297 / 210)  # format A4

LEAF = ('<path d="M0,0 C 14,-4 26,4 40,-8" stroke="{g}" stroke-width="1.4" fill="none" opacity="0.85"/>'
        + "".join('<g transform="translate({},{}) rotate({}) scale({})"><ellipse cx="0" cy="0" rx="7" ry="3.2" fill="{{l}}" opacity="0.8"/></g>'.format(*a)
                  for a in ((6, -2, 20, 1), (16, -6, -10, .85), (26, -3, 25, .75), (34, -8, -5, .6)))
        + '<g transform="translate(3,-3)">' + "".join(
            f'<ellipse cx="0" cy="-3.2" rx="2.6" ry="1.6" fill="{{p}}" stroke="{{g}}" stroke-width="0.4" transform="rotate({r})"/>' for r in (0, 72, 144, 216, 288))
        + '<circle cx="0" cy="0" r="1.6" fill="{g}"/></g>')

STYLES = {
    "jardin": {"label": "Jardin", "bg": ("#fdf9f0", "#f6efe4"), "head": "#7a3a20", "gold": "#b98a3e", "script": "#a9532f", "ink": "#3f2c1c",
               "card": "#fbf7ee", "kids": "#f3e6d6", "honor": "#5b7a4f", "row": "#ece1cd", "num_bg": "#fbf7ee", "ornament": "leaf",
               "leaf": ("#d8b978", "#8a9a6a", "#fbeede"), "arch": True,
               "f_title": "'Playfair Display', Georgia, serif", "f_body": "'Cormorant Garamond', Georgia, serif", "f_script": "'Great Vibes', 'Brush Script MT', cursive"},
    "nuit": {"label": "Nuit dorée", "bg": ("#121521", "#1d2135"), "head": "#ead7a8", "gold": "#c9a66b", "script": "#e6c27a", "ink": "#efe6d6",
             "card": "#1a1e2e", "kids": "#25213a", "honor": "#d8a7a0", "row": "#2c3148", "num_bg": "#121521", "ornament": "deco",
             "arch": True,
             "f_title": "'Playfair Display', Georgia, serif", "f_body": "'Cormorant Garamond', Georgia, serif", "f_script": "'Great Vibes', 'Brush Script MT', cursive"},
    "minimal": {"label": "Minimal", "bg": ("#ffffff", "#ffffff"), "head": "#111111", "gold": "#8a8a8a", "script": "#111111", "ink": "#222222",
                "card": "#ffffff", "kids": "#f4f4f4", "honor": "#111111", "row": "#e8e8e8", "num_bg": "#ffffff", "ornament": None,
                "arch": False,
                "f_title": "'Montserrat', 'Helvetica Neue', Arial, sans-serif", "f_body": "'Montserrat', 'Helvetica Neue', Arial, sans-serif",
                "f_script": "'Playfair Display', Georgia, serif"},
}

LABELS = {
    "fr": {"plan": "PLAN DE TABLE", "thanks": "— Merci de célébrer ce jour avec nous —", "table": "TABLE", "tables": "tables", "guests": "invités",
           "kids": "table(s) des enfants", "honor": "Table d'honneur", "kids_name": "Enfants", "made": "Fait par Miel", "sup": "Personne qui surveille", "page": "page"},
    "en": {"plan": "SEATING PLAN", "thanks": "— Thank you for celebrating this day with us —", "table": "TABLE", "tables": "tables", "guests": "guests",
           "kids": "children's table(s)", "honor": "Top table", "kids_name": "Children", "made": "Made with Miel", "sup": "Supervising adult", "page": "page"},
    "it": {"plan": "DISPOSIZIONE DEI TAVOLI", "thanks": "— Grazie di festeggiare con noi questo giorno —", "table": "TAVOLO", "tables": "tavoli", "guests": "invitati",
           "kids": "tavolo/i dei bambini", "honor": "Tavolo d'onore", "kids_name": "Bambini", "made": "Realizzato con Miel", "sup": "Adulto di sorveglianza", "page": "pagina"},
}


def _e(s):
    return escape(str(s or ""), {'"': "&quot;"})


def _cut(s, n):
    s = str(s or "")
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _wrap(text, width=46):
    words, lines, cur = str(text or "").split(), [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > width:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines[:3]


def _photo_data(event, max_side=640):
    """Photo de couverture réduite et intégrée au fichier (le SVG reste autonome)."""
    if not event.cover_image:
        return None
    try:
        from events.models import focus_of
        from events.services.images import focus_crop
        with event.cover_image.open("rb") as f:
            im = focus_crop(f, 220 / 297, focus_of(event, "cover_image"), max_side)  # même cadrage qu'à l'écran
            buf = BytesIO()
            im.save(buf, "JPEG", quality=82)
        return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()
    except Exception:
        return None


def _monogram(event, lang):
    couple = event.couple or {}
    names = [(couple.get(k) or {}).get("name", "") for k in ("p1", "p2")]
    if not all(names):
        title = event.title_in(lang)
        for sep in ("&", " et ", " and ", " e "):
            if sep in title:
                names = [p.strip() for p in title.split(sep, 1)]
                break
        else:
            names = [title]
    return " | ".join(n[0].upper() for n in names if n)


def _date_line(event, lang):
    parts = []
    if event.date:
        with translation.override(lang if lang in ("fr", "en", "it") else "fr"):
            parts.append(formats.date_format(event.date, "l j F Y").upper())
    venues = list(event.venues.all())
    if venues and venues[-1].address:
        segs = [x.strip() for x in venues[-1].address.split(",") if x.strip()]
        parts.append(", ".join(segs[-2:] if len(segs) >= 3 else segs[-1:]).upper())
    return " · ".join(parts)


def plan_data(event, lang):
    """Tables à dessiner : seulement celles qui ont au moins une personne."""
    L = LABELS.get(lang, LABELS["fr"])
    pmap = {p.key: p for p in persons(event)}
    out = []
    for i, t in enumerate(event.tables.all()):
        names = []
        for k in t.seats:
            if not k:
                continue
            if k == SUPERVISOR:
                names.append(event.supervisor_name or L["sup"])
            elif k in pmap:
                names.append(pmap[k].name)
        if not names:
            continue
        default = L["honor"] if t.kind == "honor" else L["kids_name"] if t.kind == "kids" else ""
        out.append({"n": i + 1, "name": t.name or default, "kind": t.kind, "quote": t.quote, "ref": t.quote_ref, "names": names})
    return out


def _card(t, S, L, quotes=True):
    """Dessine une table ; renvoie (markup, hauteur)."""
    w = COLW
    ink, gold = S["ink"], S["gold"]
    stroke = S["honor"] if t["kind"] == "honor" else gold
    fill = S["kids"] if t["kind"] == "kids" else S["card"]
    fb, fs, ft = S["f_body"], S["f_script"], S["f_title"]
    out = []
    y_name = 80 if t["name"] else 62
    y_label = y_name + 16 if t["name"] else 70
    y = y_label
    q_lines = _wrap(t["quote"]) if (quotes and t["quote"]) else []
    body = []
    if t["name"]:
        script_size = 30 if S["f_script"].startswith("'Great") else 24
        body.append(f'<text x="{w / 2}" y="{y_name}" text-anchor="middle" font-family="{fs}" font-size="{script_size}" fill="{S["script"]}">{_e(_cut(t["name"], 34))}</text>')
    label = f'{L["table"]} {t["n"]}'
    body.append(f'<text x="{w / 2}" y="{y_label}" text-anchor="middle" font-family="{fb}" font-size="10.5" letter-spacing="1.2" fill="{ink}" opacity="0.6">{_e(label)}</text>')
    if q_lines:
        y = y_label + 31
        for i, ln in enumerate(q_lines):
            txt = ("“" if i == 0 else "") + ln + ("”" if i == len(q_lines) - 1 else "")
            body.append(f'<text x="{w / 2}" y="{y}" text-anchor="middle" font-family="{fb}" font-style="italic" font-size="13.5" fill="{ink}">{_e(txt)}</text>')
            y += 17
        if t["ref"]:
            y += 1
            body.append(f'<text x="{w / 2}" y="{y}" text-anchor="middle" font-family="{fb}" font-size="10.5" letter-spacing="1.5" fill="{gold}">{_e(t["ref"].upper())}</text>')
            y += 4
    sep = y + 17
    body.append(f'<line x1="18" y1="{sep}" x2="{w - 18}" y2="{sep}" stroke="{stroke}" stroke-width="0.7" opacity="0.5"/>')
    ny = sep + 20
    for i, name in enumerate(t["names"]):
        if i:
            body.append(f'<line x1="10" y1="{ny - 15}" x2="{w - 10}" y2="{ny - 15}" stroke="{S["row"]}" stroke-width="0.6"/>')
        body.append(f'<text x="16" y="{ny}" font-family="{fb}" font-size="13.5" fill="{gold}">{i + 1}.</text>')
        body.append(f'<text x="40" y="{ny}" font-family="{fb}" font-size="13.5" fill="{ink}">{_e(_cut(name, 58))}</text>')
        ny += 21
    h = max(ny + 10, 180)
    if S["arch"]:
        d = f"M 0,34 Q {w / 2},0 {w},34 L {w},{h - 16} Q {w},{h} {w - 16},{h} L 16,{h} Q 0,{h} 0,{h - 16} Z"
    else:
        d = f"M 0,24 L {w},24 L {w},{h} L 0,{h} Z"
    out.append(f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{2 if t["kind"] == "honor" and not S["arch"] else 1.4}"/>')
    if S["arch"]:
        out.append(f'<path d="{d}" fill="none" stroke="{stroke}" stroke-width="0.5" opacity="0.55" transform="translate(4,4) scale({(w - 8) / w:.4f},{(h - 8) / h:.4f})"/>')
    if S["ornament"] == "leaf":
        g, lf, p = S["leaf"]
        leaf = LEAF.format(g=g, l=lf, p=p)
        out.append(f'<g transform="translate(14,34)">{leaf}</g><g transform="translate({w - 14},34) scale(-1,1)">{leaf}</g>')
    elif S["ornament"] == "deco":
        for x, sx in ((18, 1), (w - 18, -1)):
            out.append(f'<g transform="translate({x},40) scale({sx},1)" stroke="{gold}" fill="none" stroke-width="0.9" opacity="0.8">'
                       '<path d="M0,0 L28,0 M0,0 L0,22 M6,6 L22,6 M6,6 L6,18"/><circle cx="0" cy="0" r="2.2" fill="' + gold + '"/></g>')
    cy = 26 if S["arch"] else 24
    out.append(f'<circle cx="{w / 2}" cy="{cy}" r="24" fill="{S["num_bg"]}" stroke="{stroke}" stroke-width="1.6"/>')
    out.append(f'<text x="{w / 2}" y="{cy + 7}" text-anchor="middle" font-family="{ft}" font-size="19" font-weight="700" fill="{S["head"] if t["kind"] != "honor" else stroke}">{t["n"]}</text>')
    return "".join(out + body), h


def header_texts(event, lang):
    """Textes de l'en-tête : ceux saisis par l'organisateur, sinon les textes automatiques."""
    L = LABELS.get(lang, LABELS["fr"])
    h = event.plan_header or {}
    custom = (h.get("texts") or {}).get(lang) or {}
    return {
        "monogram": h.get("monogram") or _monogram(event, lang),
        "title": custom.get("title") or L["plan"],
        "tagline": custom.get("tagline") if custom.get("tagline") is not None and "tagline" in custom else L["thanks"],
        "names": custom.get("names") or event.title_in(lang),
        "place": custom.get("place") if "place" in custom else _date_line(event, lang),
        "stats": h.get("stats", True),
    }


def _header(event, S, L, lang, tables, photo, compact=False, count_people=None):
    """En-tête : monogramme, titre, photo, prénoms, date, chiffres. Renvoie (markup, y de fin)."""
    c = W / 2
    ft, fb, fs = S["f_title"], S["f_body"], S["f_script"]
    H = header_texts(event, lang)
    out = [f'<text x="{c}" y="66" text-anchor="middle" font-family="{ft}" font-size="26" font-weight="700" letter-spacing="8" fill="{S["head"]}">{_e(H["monogram"])}</text>' if H["monogram"] else "",
           f'<text x="{c}" y="112" text-anchor="middle" font-family="{ft}" font-size="42" font-weight="700" letter-spacing="6" fill="{S["head"]}">{_e(H["title"].upper())}</text>',
           f'<text x="{c}" y="140" text-anchor="middle" font-family="{fb}" font-style="italic" font-size="17" fill="{S["gold"]}">{_e(H["tagline"])}</text>' if H["tagline"] else ""]
    y = 158
    data = _photo_data(event) if photo and not compact else None
    if data:
        out.append(f'<clipPath id="photoClip"><rect x="0" y="0" width="220" height="297" rx="14" ry="14"/></clipPath>'
                   f'<g transform="translate({c - 110},{y})"><rect x="-6" y="-6" width="232" height="309" rx="20" fill="none" stroke="{S["gold"]}" stroke-width="2"/>'
                   f'<image href="{data}" xlink:href="{data}" x="0" y="0" width="220" height="297" preserveAspectRatio="xMidYMid slice" clip-path="url(#photoClip)"/></g>')
        y += 297 + 62
    else:
        y += 70
    script_size = 56 if fs.startswith("'Great") else 44
    out.append(f'<text x="{c}" y="{y}" text-anchor="middle" font-family="{fs}" font-size="{script_size}" fill="{S["script"]}">{_e(H["names"])}</text>')
    dl = H["place"]
    if dl:
        out.append(f'<text x="{c}" y="{y + 34}" text-anchor="middle" font-family="{fb}" letter-spacing="3" font-size="15" fill="{S["ink"]}">{_e(dl)}</text>')
    n_people = sum(len(t["names"]) for t in tables)
    n_kids = sum(1 for t in tables if t["kind"] == "kids")
    stats = f'{len(tables)} {L["tables"]} · {n_people} {L["guests"]}' + (f' · {n_kids} {L["kids"]}' if n_kids else "")
    if H["stats"]:
        out.append(f'<text x="{c}" y="{y + 62}" text-anchor="middle" font-family="{fb}" font-size="14" fill="{S["ink"]}">{_e(stats)}</text>')
    line_y = y + 110
    out.append(f'<line x1="{MARGIN}" y1="{line_y}" x2="{W - MARGIN}" y2="{line_y}" stroke="{S["gold"]}" stroke-width="1" opacity="0.5"/>')
    return "".join(out), line_y + 30


def _doc(S, height, inner, fonts=True):
    imp = ("<style>@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,400;0,500;0,600;1,500"
           "&amp;family=Playfair+Display:ital,wght@0,600;0,700;1,500&amp;family=Great+Vibes&amp;family=Montserrat:wght@400;600&amp;display=swap');</style>") if fonts else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" width="{W}" height="{height}" viewBox="0 0 {W} {height}">'
            f'<defs>{imp}<linearGradient id="bgGrad" x1="0" y1="0" x2="1" y2="1"><stop offset="0%" stop-color="{S["bg"][0]}"/>'
            f'<stop offset="100%" stop-color="{S["bg"][1]}"/></linearGradient></defs>'
            f'<rect x="0" y="0" width="{W}" height="{height}" fill="url(#bgGrad)"/>{inner}</svg>')


def _rows(cards):
    """Regroupe les cartes par rangées de 3 ; renvoie [(cartes, hauteur de la rangée)]."""
    rows = []
    for i in range(0, len(cards), COLS):
        r = cards[i:i + COLS]
        rows.append((r, max(h for _, h in r)))
    return rows


def _place_row(row, y):
    return "".join(f'<g transform="translate({MARGIN + j * (COLW + GAP)},{y})">{m}</g>' for j, (m, _) in enumerate(row))


LAYOUTS = ("cards", "alpha", "table")


def _list_blocks(event, S, L, lang, layout, quotes, sort):
    return _alpha_blocks(event, S, L, lang, sort) if layout == "alpha" else _table_blocks(event, S, L, lang, quotes)


def render_svg(event, style="jardin", lang="fr", photo=True, quotes=True, layout="cards", sort="prenom"):
    """Affiche complète (une seule page)."""
    S = STYLES.get(style, STYLES["jardin"])
    L = LABELS.get(lang, LABELS["fr"])
    tables = plan_data(event, lang)
    head, y = _header(event, S, L, lang, tables, photo)
    parts = [head]
    if layout in ("alpha", "table"):
        m, y = _flow(_list_blocks(event, S, L, lang, layout, quotes, sort), y)[0]
        parts.append(m)
        y += 30
    for row, h in (_rows([_card(t, S, L, quotes) for t in tables]) if layout == "cards" else []):
        parts.append(_place_row(row, y))
        y += h + 40
    y += 10
    parts.append(f'<text x="{W / 2}" y="{y}" text-anchor="middle" font-family="{S["f_body"]}" font-style="italic" font-size="13" fill="{S["gold"]}">{_e(L["made"])}</text>')
    return _doc(S, y + 30, "".join(parts))


def small_title(event, S, lang):
    H = header_texts(event, lang)
    return (f'<text x="{W / 2}" y="60" text-anchor="middle" font-family="{S["f_title"]}" font-size="20" font-weight="700" letter-spacing="5" fill="{S["head"]}">'
            f'{_e(H["title"].upper())} · {_e(H["names"])}</text>')


def render_pages(event, style="jardin", lang="fr", photo=True, quotes=True, fonts=True, layout="cards", sort="prenom"):
    """Pages A4 (même largeur que l'affiche) ; une table n'est jamais coupée."""
    S = STYLES.get(style, STYLES["jardin"])
    L = LABELS.get(lang, LABELS["fr"])
    tables = plan_data(event, lang)
    head, y = _header(event, S, L, lang, tables, photo)
    rows = _rows([_card(t, S, L, quotes) for t in tables]) if layout == "cards" else []
    pages, cur = [], [head]
    bottom = PAGE_H - 70
    if layout in ("alpha", "table"):
        flowed = _flow(_list_blocks(event, S, L, lang, layout, quotes, sort), y, bottom)
        pages = [[head, flowed[0][0]]] + [[small_title(event, S, lang), m] for m, _ in flowed[1:]]
        cur = None
    H = header_texts(event, lang)
    small = (f'<text x="{W / 2}" y="60" text-anchor="middle" font-family="{S["f_title"]}" font-size="20" font-weight="700" letter-spacing="5" fill="{S["head"]}">'
             f'{_e(H["title"].upper())} · {_e(H["names"])}</text>')
    for row, h in rows:
        if y + h > bottom and len(cur) > 1:
            pages.append(cur)
            cur, y = [small], 110
        cur.append(_place_row(row, y))
        y += h + 40
    if cur is not None:
        pages.append(cur)
    n = len(pages)
    return [_doc(S, PAGE_H, "".join(p) + f'<text x="{W / 2}" y="{PAGE_H - 30}" text-anchor="middle" font-family="{S["f_body"]}" font-style="italic" font-size="14" '
                 f'fill="{S["gold"]}">{_e(L["made"])} · {L["page"]} {i + 1}/{n}</text>', fonts) for i, p in enumerate(pages)]


# ---------------------------------------------------------------- mises en page « liste »
import unicodedata


def _fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", s or "") if unicodedata.category(c) != "Mn").casefold()


def _list_entries(event, lang, sort="prenom"):
    """Une ligne par personne : (nom affiché, clé de tri, n° de table, nom de table)."""
    L = LABELS.get(lang, LABELS["fr"])
    out = []
    for t in plan_data(event, lang):
        for name in t["names"]:
            parts = name.split()
            key = _fold(parts[-1] + " " + " ".join(parts[:-1])) if (sort == "nom" and len(parts) > 1) else _fold(name)
            shown = (parts[-1].upper() + " " + " ".join(parts[:-1])) if (sort == "nom" and len(parts) > 1) else name
            out.append((shown, key, t["n"], t["name"]))
    out.sort(key=lambda e: (e[1], e[2]))
    return out


def _alpha_blocks(event, S, L, lang, sort):
    """Liste A–Z « Trouvez votre table » : une lettre en écriture, puis nom ……… Table n · Nom."""
    fb, fs, ft = S["f_body"], S["f_script"], S["f_title"]
    blocks, cur = [], None
    for shown, key, n, tname in _list_entries(event, lang, sort):
        letter = (key[:1] or "#").upper()
        head = ""
        h = 26
        if letter != cur:
            cur = letter
            head = (f'<text x="0" y="36" font-family="{fs}" font-size="{38 if fs.startswith(chr(39) + "Great") else 30}" fill="{S["script"]}">{_e(letter)}</text>'
                    f'<line x1="44" y1="27" x2="{COLW}" y2="27" stroke="{S["gold"]}" stroke-width="0.7" opacity="0.5"/>')
            h += 46
        y = h - 8
        right = f'{L["table"].capitalize()} {n}' + (f" · {tname}" if tname else "")
        row = (f'<text x="0" y="{y}" font-family="{fb}" font-size="15" fill="{S["ink"]}">{_e(_cut(shown, 34))}</text>'
               f'<text x="{COLW}" y="{y}" text-anchor="end" font-family="{fb}" font-style="italic" font-size="14" fill="{S["gold"]}">{_e(_cut(right, 32))}</text>'
               f'<line x1="{min(330, 9 * len(_cut(shown, 34)) + 12)}" y1="{y - 4}" x2="{COLW - 8.2 * len(_cut(right, 32)) - 10}" y2="{y - 4}" stroke="{S["gold"]}" stroke-width="1" stroke-dasharray="1 5" opacity="0.7"/>')
        blocks.append((head + row, h))
    return blocks


def _table_blocks(event, S, L, lang, quotes):
    """Liste par table, sans cartes : numéro + nom de la table, puis les invités en lignes fines."""
    fb, fs, ft = S["f_body"], S["f_script"], S["f_title"]
    blocks = []
    for t in plan_data(event, lang):
        color = S["honor"] if t["kind"] == "honor" else S["gold"]
        m = [f'<circle cx="16" cy="22" r="16" fill="none" stroke="{color}" stroke-width="1.3"/>'
             f'<text x="16" y="27" text-anchor="middle" font-family="{ft}" font-size="14" font-weight="700" fill="{S["head"]}">{t["n"]}</text>'
             f'<text x="44" y="32" font-family="{fs}" font-size="{30 if fs.startswith(chr(39) + "Great") else 24}" fill="{S["script"]}">{_e(_cut(t["name"] or (L["table"].capitalize() + " " + str(t["n"])), 30))}</text>']
        y = 50
        if quotes and t["quote"]:
            m.append(f'<text x="44" y="{y + 2}" font-family="{fb}" font-style="italic" font-size="12.5" fill="{S["ink"]}" opacity="0.8">{_e(_cut("“" + t["quote"] + "”" + (" — " + t["ref"] if t["ref"] else ""), 70))}</text>')
            y += 18
        m.append(f'<line x1="44" y1="{y}" x2="{COLW}" y2="{y}" stroke="{color}" stroke-width="0.7" opacity="0.5"/>')
        y += 20
        for name in t["names"]:
            m.append(f'<text x="44" y="{y}" font-family="{fb}" font-size="14.5" fill="{S["ink"]}">{_e(_cut(name, 52))}</text>')
            y += 21
        blocks.append(("".join(m), y + 16))
    return blocks


def _flow(blocks, top, bottom=None):
    """Range les blocs en 3 colonnes, de haut en bas. Sans « bottom » : colonnes équilibrées (affiche).
    Avec « bottom » : remplit page par page. Renvoie [(markup, hauteur utilisée)] par page."""
    if not blocks:
        return [("", top)]
    if bottom is None:
        total = sum(h for _, h in blocks)
        target = max(total / COLS, max(h for _, h in blocks))
        cols, cur, ch = [], [], 0
        for b in blocks:
            if cur and ch + b[1] > target + 20 and len(cols) < COLS - 1:
                cols.append(cur)
                cur, ch = [], 0
            cur.append(b)
            ch += b[1]
        cols.append(cur)
        out, maxy = [], top
        for j, col in enumerate(cols):
            y = top
            for m, h in col:
                out.append(f'<g transform="translate({MARGIN + j * (COLW + GAP)},{y})">{m}</g>')
                y += h
            maxy = max(maxy, y)
        return [("".join(out), maxy)]
    pages, out, j, y, start = [], [], 0, top, top
    for m, h in blocks:
        if y + h > bottom and y > start:
            j += 1
            y = start
            if j >= COLS:
                pages.append(("".join(out), bottom))
                out, j, start = [], 0, 110
                y = start
        out.append(f'<g transform="translate({MARGIN + j * (COLW + GAP)},{y})">{m}</g>')
        y += h
    pages.append(("".join(out), bottom))
    return pages


_SVG_FONTS = False


def _register_svg_fonts():
    """Polices DejaVu (déjà fournies avec Miel) utilisées pour le PDF, à la place des polices web."""
    global _SVG_FONTS
    if _SVG_FONTS:
        return
    from svglib.fonts import register_font
    from events.services.pdf import FONT_DIR
    serif, serif_i = str(FONT_DIR / "DejaVuSerif.ttf"), str(FONT_DIR / "DejaVuSerif-Italic.ttf")
    sans, sans_b = str(FONT_DIR / "DejaVuSans.ttf"), str(FONT_DIR / "DejaVuSans-Bold.ttf")
    bold = FONT_DIR / "DejaVuSerif-Bold.ttf"
    bold = str(bold) if bold.exists() else serif
    for fam, normal, italic, b in (("Playfair Display", serif, serif_i, bold), ("Cormorant Garamond", serif, serif_i, bold),
                                   ("Great Vibes", serif_i, serif_i, serif_i), ("Montserrat", sans, sans, sans_b)):
        register_font(fam, normal, weight="normal", style="normal", rlgFontName=f"{fam}-n")
        register_font(fam, italic, weight="normal", style="italic", rlgFontName=f"{fam}-i")
        register_font(fam, b, weight="bold", style="normal", rlgFontName=f"{fam}-b")
    _SVG_FONTS = True


def render_pdf(event, style="jardin", lang="fr", photo=True, quotes=True, layout="cards", sort="prenom"):
    from reportlab.graphics import renderPDF
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from svglib.svglib import svg2rlg

    _register_svg_fonts()
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    c.setTitle(f"Plan de table — {event.title_in(lang)}")
    for page in render_pages(event, style, lang, photo, quotes, fonts=False, layout=layout, sort=sort):
        drawing = svg2rlg(BytesIO(page.encode("utf-8")))
        scale = min(A4[0] / drawing.width, A4[1] / drawing.height)  # svglib peut compter en points plutôt qu'en pixels
        drawing.scale(scale, scale)
        drawing.width, drawing.height = A4
        renderPDF.draw(drawing, c, 0, 0)
        c.showPage()
    c.save()
    buf.seek(0)
    return buf
