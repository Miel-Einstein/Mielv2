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
