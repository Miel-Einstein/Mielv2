"""Recadrage des photos selon le point de cadrage choisi par l'organisateur.

Même calcul que le navigateur (object-fit: cover ; object-position: x% y% ; zoom autour du même point),
pour que la carte PDF et le plan de table montrent exactement le cadrage vu à l'écran.
"""
from PIL import Image, ImageOps


def focus_crop(fileobj, ratio, focus, max_side=1400):
    """Renvoie une image PIL recadrée au format « ratio » (largeur / hauteur)."""
    im = ImageOps.exif_transpose(Image.open(fileobj)).convert("RGB")
    w, h = im.size
    if w / h > ratio:
        cw, ch = h * ratio, h
    else:
        cw, ch = w, w / ratio
    z = focus.get("z", 1) or 1
    cw, ch = cw / z, ch / z
    x, y = focus.get("x", 50) / 100, focus.get("y", 50) / 100
    left, top = x * (w - cw), y * (h - ch)
    im = im.crop((round(left), round(top), round(left + cw), round(top + ch)))
    im.thumbnail((max_side, max_side))
    return im
