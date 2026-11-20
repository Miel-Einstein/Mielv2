import json

from django import template
from django.utils.safestring import mark_safe

from events.models import t

register = template.Library()


@register.filter
def tr(value, lang):
    """{{ event.title|tr:lang }} : texte dans la langue demandée."""
    return t(value, lang)


@register.filter
def to_json(value):
    return mark_safe(json.dumps(value, ensure_ascii=False).replace("</", "<\\/"))


@register.simple_tag
def cover_img(event, field="cover_image", cls="fimg", alt=""):
    """Photo de couverture cadrée : <img> qui remplit son cadre selon le point de cadrage et le zoom."""
    from django.utils.html import escape
    from events.models import focus_of
    img = getattr(event, field, None)
    if not img:
        return ""
    f = focus_of(event, field)
    style = f"object-position:{f['x']:.1f}% {f['y']:.1f}%;transform-origin:{f['x']:.1f}% {f['y']:.1f}%;transform:scale({f['z']:.3f})"
    return mark_safe(f'<img class="{escape(cls)}" src="{escape(img.url)}" alt="{escape(alt)}" style="{style}" loading="eager" decoding="async">')


@register.filter
def days_until(d):
    """Nombre de jours avant une date (None si la date est passée)."""
    from django.utils import timezone
    if not d:
        return None
    n = (d - timezone.localdate()).days
    return n if n >= 0 else None
