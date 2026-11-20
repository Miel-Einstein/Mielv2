"""PDF générés côté serveur (polices DejaVu : accents, lingala ɔ ɛ, etc.).

- card_pdf : la carte d'invitation personnalisée, avec QR code vers le mur des vœux.
- plan_pdf : le plan de table (complet ou « noms seulement »).
"""
from io import BytesIO
from pathlib import Path

import qrcode
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, A6
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table as RLTable, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from events.models import focus_of, t
from events.services.images import focus_crop
from events.services.seating import SUPERVISOR, persons

FONT_DIR = Path(settings.BASE_DIR) / "static" / "miel" / "fonts"
_FONTS_READY = False

PALETTES = {
    "botanique": {"bg": "#fffdf8", "ph": "#e9d6b6", "ink": "#3a2a1d", "acc": "#9b7b5c", "box": "#fef6ea"},
    "moderne": {"bg": "#14110e", "ph": "#3a2c20", "ink": "#f0e7dc", "acc": "#ddb483", "box": "#1f1b17"},
    "rose": {"bg": "#fff5f7", "ph": "#f2c1cf", "ink": "#8e5464", "acc": "#b1475d", "box": "#fef0f3"},
}

LABELS = {
    "fr": {"dear": "Cher·e", "scan": "Scannez ou touchez le QR code : mur des vœux et vos photos", "plan": "Plan de table", "table": "Table", "seats": "places", "guest": "Invité·e", "type": "Type", "principal": "Invité principal", "accomp": "Accompagnant·e", "enfant": "Enfant", "supervisor": "Surveillance", "age": "ans"},
    "en": {"dear": "Dear", "scan": "Scan or tap the QR code: wish wall and your photos", "plan": "Seating plan", "table": "Table", "seats": "seats", "guest": "Guest", "type": "Type", "principal": "Main guest", "accomp": "Plus-one", "enfant": "Child", "supervisor": "Supervision", "age": "y/o"},
    "it": {"dear": "Caro/a", "scan": "Scansiona o tocca il QR code: muro degli auguri e le tue foto", "plan": "Piano dei tavoli", "table": "Tavolo", "seats": "posti", "guest": "Ospite", "type": "Tipo", "principal": "Ospite principale", "accomp": "Accompagnatore", "enfant": "Bambino", "supervisor": "Sorveglianza", "age": "anni"},
    "ln": {"dear": "Ndeko", "scan": "Scanner mpo na lisango ya mabondeli", "plan": "Mokano ya bamesa", "table": "Mesa", "seats": "bitiyu", "guest": "Moto", "type": "Ndenge", "principal": "Moto ya liboso", "accomp": "Moninga", "enfant": "Mwana", "supervisor": "Mokengeli", "age": "mbula"},
}


def lbl(lang):
    return LABELS.get(lang, LABELS["fr"])


def _fonts():
    global _FONTS_READY
    if _FONTS_READY:
        return
    pdfmetrics.registerFont(TTFont("Sans", str(FONT_DIR / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont("Sans-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFont(TTFont("Serif", str(FONT_DIR / "DejaVuSerif.ttf")))
    pdfmetrics.registerFont(TTFont("Serif-Italic", str(FONT_DIR / "DejaVuSerif-Italic.ttf")))
    _FONTS_READY = True


def qr_image(data):
    img = qrcode.make(data, box_size=8, border=1)
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def card_pdf(event, guest, lang):
    """Carte A6 personnalisée."""
    _fonts()
    if event.card_template in ("luxe", "scandinave"):
        return _photo_card_pdf(event, guest, lang)
    pal = PALETTES.get(event.card_template, PALETTES["botanique"])
    L = lbl(lang)
    buf = BytesIO()
    from reportlab.pdfgen import canvas

    W, H = A6
    c = canvas.Canvas(buf, pagesize=A6)
    c.setFillColor(colors.HexColor(pal["bg"]))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    # bandeau photo, recadré comme à l'écran (point de cadrage + zoom)
    ph_h = 4.2 * cm
    if event.cover_image:
        try:
            with event.cover_image.open("rb") as f:
                im = focus_crop(f, W / ph_h, focus_of(event, "cover_image"))
            c.drawImage(ImageReader(im), 0, H - ph_h, W, ph_h)
        except Exception:
            c.setFillColor(colors.HexColor(pal["ph"]))
            c.rect(0, H - ph_h, W, ph_h, stroke=0, fill=1)
    else:
        c.setFillColor(colors.HexColor(pal["ph"]))
        c.rect(0, H - ph_h, W, ph_h, stroke=0, fill=1)
        title = event.title_in(lang)
        mono = " & ".join(w[0] for w in title.replace("&", " ").split()[:2]) if title else ""
        c.setFillColor(colors.HexColor(pal["acc"]))
        c.setFont("Serif-Italic", 34)
        c.drawCentredString(W / 2, H - ph_h / 2 - 10, mono)
    y = H - ph_h - 1.0 * cm
    c.setFillColor(colors.HexColor(pal["acc"]))
    c.setFont("Serif", 18)
    c.drawCentredString(W / 2, y, event.title_in(lang)[:40])
    y -= 0.55 * cm
    c.setFillColor(colors.HexColor(pal["ink"]))
    c.setFont("Sans", 7.5)
    c.drawCentredString(W / 2, y, event.subtitle_in(lang)[:70])
    y -= 0.6 * cm
    c.setFont("Sans-Bold", 8.5)
    c.drawCentredString(W / 2, y, f"{L['dear']} {guest.full_name}".upper()[:48])
    y -= 0.55 * cm
    if event.date:
        c.setFont("Sans", 8)
        from django.utils import formats, translation

        with translation.override(lang if lang != "ln" else "fr"):
            c.drawCentredString(W / 2, y, formats.date_format(event.date, "l j F Y"))
        y -= 0.45 * cm
    # lieux
    venues = list(event.venues.all())
    box_h = 0.42 * cm * max(1, len(venues)) + 0.3 * cm
    c.setFillColor(colors.HexColor(pal["box"]))
    c.roundRect(0.6 * cm, y - box_h, W - 1.2 * cm, box_h, 6, stroke=0, fill=1)
    c.setFillColor(colors.HexColor(pal["ink"]))
    yy = y - 0.45 * cm
    for v in venues:
        c.setFont("Sans-Bold", 7.5)
        hour = v.start.strftime("%H:%M") if v.start else ""
        c.drawString(0.9 * cm, yy, hour)
        c.setFont("Sans", 7.5)
        c.drawString(2.0 * cm, yy, (t(v.name, lang) + (" — " + v.address if v.address else ""))[:60])
        yy -= 0.42 * cm
    y = y - box_h - 0.35 * cm
    # QR code vers le mur des vœux (avec le jeton personnel de l'invité)
    wall = event.public_url("wall") + f"?g={guest.token}"
    q = 2.3 * cm
    c.drawImage(qr_image(wall), 0.8 * cm, max(0.5 * cm, y - q), q, q)
    # le QR code est aussi un lien : sur téléphone, on le touche au lieu de le scanner
    c.linkURL(wall, (0.8 * cm, max(0.5 * cm, y - q), 0.8 * cm + q, max(0.5 * cm, y - q) + q), relative=0, thickness=0)
    c.setFont("Sans", 7)
    c.setFillColor(colors.HexColor(pal["ink"]))
    tx = c.beginText(0.8 * cm + q + 0.3 * cm, max(0.5 * cm, y - q) + q - 0.4 * cm)
    tx.setFont("Sans", 7)
    for line in _wrap(L["scan"], 38):
        tx.textLine(line)
    if event.song:
        tx.setFont("Sans-Bold", 7)
        tx.textLine("♪ " + event.song.title[:36])
    c.drawText(tx)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf


def _wrap(text, n):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def plan_pdf(event, lang="fr", names_only=False):
    _fonts()
    L = lbl(lang)
    pmap = {p.key: p for p in persons(event)}
    cats = {c.id: c for c in event.categories.all()}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=1.8 * cm, bottomMargin=1.8 * cm, leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    W = A4[0] - 3.6 * cm
    rose, gold, ink = colors.HexColor("#a6431f"), colors.HexColor("#c9a96e"), colors.HexColor("#2a1d16")
    st_title = ParagraphStyle("t", fontName="Serif-Italic", fontSize=30, leading=36, alignment=TA_CENTER, textColor=rose)
    st_sub = ParagraphStyle("s", fontName="Sans", fontSize=10, alignment=TA_CENTER, textColor=gold)
    st_cell = ParagraphStyle("c", fontName="Sans", fontSize=9, leading=11, textColor=ink, alignment=TA_LEFT)
    st_head = ParagraphStyle("h", fontName="Sans-Bold", fontSize=12, textColor=colors.white)
    story = [Paragraph(L["plan"], st_title), Paragraph(event.title_in(lang), st_sub), Spacer(1, 0.8 * cm)]
    for i, tb in enumerate(event.tables.all()):
        occupied = [k for k in tb.seats if k]
        if not occupied:
            continue
        head = RLTable([[Paragraph(f"{tb.label() if tb.name else L['table'] + ' ' + str(i + 1)}", st_head),
                         Paragraph(f"{len(occupied)} / {tb.capacity} {L['seats']}", ParagraphStyle('r', parent=st_head, fontSize=9, alignment=2))]],
                       colWidths=[W * 0.6, W * 0.4])
        head.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), rose), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        rows = [] if names_only else [[Paragraph("<b>N°</b>", st_cell), Paragraph(f"<b>{L['guest']}</b>", st_cell), Paragraph(f"<b>{L['type']}</b>", st_cell)]]
        for si, k in enumerate(tb.seats):
            if not k:
                continue
            if k == SUPERVISOR:
                name, typ = event.supervisor_name or "—", L["supervisor"]
            else:
                p = pmap.get(k)
                if not p:
                    continue
                name = p.name + (f"  <font size=7 color='#8a7f5f'>{p.note}</font>" if p.note else "")
                typ = L[p.type] + (f" · {p.age} {L['age']}" if p.type == "enfant" and p.age is not None else "")
            rows.append([Paragraph(name, st_cell)] if names_only else [Paragraph(str(si + 1), st_cell), Paragraph(name, st_cell), Paragraph(typ, st_cell)])
        body = RLTable(rows, colWidths=[W] if names_only else [1.2 * cm, W - 5.2 * cm, 4 * cm], repeatRows=0 if names_only else 1)
        body.setStyle(TableStyle([("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#fdf0f2")]),
                                  ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#f0c9cf")),
                                  ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
        story += [KeepTogether([head, body]), Spacer(1, 0.6 * cm)]
    doc.build(story)
    buf.seek(0)
    return buf


def _photo_card_pdf(event, guest, lang):
    """Cartes « Luxe doré » et « Minimaliste scandinave » : la photo remplit la carte, texte clair sur verre sombre."""
    from django.utils import formats, timezone, translation
    from django.utils.translation import gettext as _
    from reportlab.pdfgen import canvas

    W, H = A6
    luxe = event.card_template == "luxe"
    gold, cream = colors.HexColor("#f3cd97" if luxe else "#e8d5b8"), colors.HexColor("#fff5ea")
    buf = BytesIO()
    c = canvas.Canvas(buf, pagesize=A6)
    # fond : photo recadrée, sinon dégradé chaud
    drawn = False
    if event.cover_image:
        try:
            with event.cover_image.open("rb") as f:
                im = focus_crop(f, W / H, focus_of(event, "cover_image"))
            c.drawImage(ImageReader(im), 0, 0, W, H)
            drawn = True
        except Exception:
            pass
    if not drawn:
        c.setFillColor(colors.HexColor("#2a1e14" if luxe else "#2b2b2b"))
        c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillColor(colors.black)
    c.setFillAlpha(0.55)
    c.rect(0, 0, W, H, stroke=0, fill=1)
    c.setFillAlpha(1)

    def glass(x, y, w, h, r=10, alpha=0.5, stroke=None):
        c.setFillColor(colors.black)
        c.setFillAlpha(alpha)
        if stroke:
            c.setStrokeColor(stroke)
            c.setStrokeAlpha(0.6)
        c.roundRect(x, y, w, h, r, stroke=1 if stroke else 0, fill=1)
        c.setFillAlpha(1)
        c.setStrokeAlpha(1)

    def centered(text, y, font, size, color=cream):
        c.setFillColor(color)
        c.setFont(font, size)
        c.drawCentredString(W / 2, y, text)

    with translation.override(lang):
        title, subtitle = event.title_in(lang), event.subtitle_in(lang)
        message = t(event.card_message, lang) if event.card_message else ""
        theme = t(event.card_theme, lang) if event.card_theme else ""
        venues = list(event.venues.all())
        date_txt = formats.date_format(event.date, "j F Y") if event.date else ""
        y = H - 1.0 * cm
        if luxe:
            centered((subtitle or _("✧ AVEC TOUT NOTRE AMOUR ✧")).upper()[:44], y, "Sans-Bold", 6.5, gold)
            y -= 0.95 * cm
            centered(title[:30], y, "Serif", 22)
            y -= 0.7 * cm
            centered(f"{_('Cher·e')} {guest.full_name}"[:48], y, "Serif-Italic", 11)
            y -= 0.55 * cm
            for line in _wrap(message or _("Avec joie, nous célébrons votre présence à nos côtés ! 🥂").replace(" 🥂", ""), 60)[:2]:
                centered(line, y, "Serif-Italic", 8)
                y -= 0.38 * cm
            days = (event.date - timezone.localdate()).days if event.date else -1
            if days >= 0:
                txt = (_("C'est aujourd'hui !") if days == 0 else f"J-{days}") + " · " + _("Le grand jour approche !")
                glass(W / 2 - 3.2 * cm, y - 0.22 * cm, 6.4 * cm, 0.55 * cm, 8, 0.35, gold)
                centered(txt[:50], y - 0.02 * cm, "Sans-Bold", 6.5, gold)
                y -= 0.65 * cm
        else:
            tag = subtitle or (_("CARTE D'INVITATION AU MARIAGE") if event.type == "mariage" else _("CARTE D'INVITATION"))
            glass(0.9 * cm, y - 0.25 * cm, W - 1.8 * cm, 0.7 * cm, 10, 0.4)
            centered(tag.upper()[:46], y, "Sans-Bold", 6.5, gold)
            y -= 1.2 * cm
            glass(0.9 * cm, y - 0.35 * cm, W - 1.8 * cm, 1.15 * cm, 12, 0.4)
            centered(title[:30], y, "Serif", 20)
            y -= 0.95 * cm
            centered(f"{_('Cher·e')} {guest.full_name}"[:48], y, "Serif-Italic", 10.5, colors.HexColor("#f0dbc0"))
            y -= 0.55 * cm
            for line in _wrap(message or _("Un grand merci pour votre réponse positive"), 52)[:2]:
                centered(line, y, "Serif-Italic", 8.5, colors.HexColor("#f5e6d3"))
                y -= 0.38 * cm
        # lieux
        if venues:
            rows = []
            for v in venues:
                hours = (v.start.strftime("%H:%M") if v.start else "") + (" – " + v.end.strftime("%H:%M") if v.end else "")
                rows.append((t(v.name, lang)[:40], (v.address or "")[:52], f"{date_txt} · {hours}".strip(" ·")))
            box_h = sum((0.95 if r[1] else 0.7) * cm for r in rows) + 0.3 * cm
            y -= 0.15 * cm
            glass(0.7 * cm, y - box_h, W - 1.4 * cm, box_h, 10, 0.5)
            yy = y - 0.45 * cm
            for name, addr, when in rows:
                c.setFillColor(gold)
                c.setFont("Sans-Bold", 7)
                c.drawString(1.0 * cm, yy, name.upper() if luxe else name)
                c.setFillColor(cream)
                c.setFont("Sans", 6.5)
                if addr:
                    c.drawString(1.0 * cm, yy - 0.3 * cm, addr)
                c.setFillColor(gold)
                c.drawString(1.0 * cm, yy - (0.58 if addr else 0.32) * cm, when)
                yy -= (0.95 if addr else 0.7) * cm
            y -= box_h + 0.3 * cm
        n = len(venues)
        info = (f"{n} " + _("lieux de fête")) if (luxe and n > 1) else _("Lieu unique · Magie garantie ✨").replace(" ✨", "") if luxe else (
            _("Événement en %(n)s lieux différents") % {"n": n} if n > 1 else _("Lieu unique · Célébration"))
        centered(info[:60], y, "Sans", 6.5, colors.HexColor("#f0dbc0"))
        y -= 0.45 * cm
        if theme:
            centered(theme[:60], y, "Serif-Italic", 7.5, gold)
        # QR code en bas, cliquable
        wall = event.public_url("wall") + f"?g={guest.token}"
        q = 2.0 * cm
        qx, qy = 0.9 * cm, 0.6 * cm
        glass(0.6 * cm, 0.35 * cm, W - 1.2 * cm, q + 0.5 * cm, 10, 0.5)
        c.setFillColor(colors.white)
        c.roundRect(qx - 0.1 * cm, qy - 0.1 * cm, q + 0.2 * cm, q + 0.2 * cm, 6, stroke=0, fill=1)
        c.drawImage(qr_image(wall), qx, qy, q, q)
        c.linkURL(wall, (qx, qy, qx + q, qy + q), relative=0, thickness=0)
        tx = c.beginText(qx + q + 0.35 * cm, qy + q - 0.45 * cm)
        tx.setFont("Sans", 6.5)
        tx.setFillColor(cream)
        for line in _wrap(_("Scannez ou touchez le QR code : mur des vœux et vos photos"), 34):
            tx.textLine(line)
        if event.song:
            tx.setFont("Sans-Bold", 6.5)
            tx.textLine("♪ " + event.song.title[:32])
        c.drawText(tx)
    c.showPage()
    c.save()
    buf.seek(0)
    return buf
