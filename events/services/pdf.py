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

from events.models import t
from events.services.seating import SUPERVISOR, persons

FONT_DIR = Path(settings.BASE_DIR) / "static" / "miel" / "fonts"
_FONTS_READY = False

PALETTES = {
    "botanique": {"bg": "#fffdf8", "ph": "#e9d6b6", "ink": "#3a2a1d", "acc": "#9b7b5c", "box": "#fef6ea"},
    "moderne": {"bg": "#14110e", "ph": "#3a2c20", "ink": "#f0e7dc", "acc": "#ddb483", "box": "#1f1b17"},
    "rose": {"bg": "#fff5f7", "ph": "#f2c1cf", "ink": "#8e5464", "acc": "#b1475d", "box": "#fef0f3"},
}

LABELS = {
    "fr": {"dear": "Cher·e", "scan": "Scannez pour le mur des vœux et vos photos", "plan": "Plan de table", "table": "Table", "seats": "places", "guest": "Invité·e", "type": "Type", "principal": "Invité principal", "accomp": "Accompagnant·e", "enfant": "Enfant", "supervisor": "Surveillance", "age": "ans"},
    "en": {"dear": "Dear", "scan": "Scan for the wish wall and your photos", "plan": "Seating plan", "table": "Table", "seats": "seats", "guest": "Guest", "type": "Type", "principal": "Main guest", "accomp": "Plus-one", "enfant": "Child", "supervisor": "Supervision", "age": "y/o"},
    "it": {"dear": "Caro/a", "scan": "Scansiona per il muro dei desideri e le foto", "plan": "Piano dei tavoli", "table": "Tavolo", "seats": "posti", "guest": "Ospite", "type": "Tipo", "principal": "Ospite principale", "accomp": "Accompagnatore", "enfant": "Bambino", "supervisor": "Sorveglianza", "age": "anni"},
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
    pal = PALETTES.get(event.card_template, PALETTES["botanique"])
    L = lbl(lang)
    buf = BytesIO()
    from reportlab.pdfgen import canvas

    W, H = A6
    c = canvas.Canvas(buf, pagesize=A6)
    c.setFillColor(colors.HexColor(pal["bg"]))
    c.rect(0, 0, W, H, stroke=0, fill=1)
    # bandeau photo
    ph_h = 4.2 * cm
    if event.cover_image:
        try:
            c.drawImage(ImageReader(event.cover_image.path), 0, H - ph_h, W, ph_h, preserveAspectRatio=True, anchor="c", mask="auto")
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
