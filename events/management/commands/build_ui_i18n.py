"""Produit static/miel/i18n/ui-<langue>.js à partir de events/ui_catalog.py."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from events.ui_catalog import UI


class Command(BaseCommand):
    help = "Construit les dictionnaires de l'interface organisateur (anglais, italien, lingala)."

    def handle(self, *args, **opts):
        out = Path(settings.BASE_DIR) / "static" / "miel" / "i18n"
        out.mkdir(parents=True, exist_ok=True)
        for i, lang in enumerate(("en", "it", "ln")):
            d = {k: v[i] for k, v in UI.items() if v[i] and v[i] != k}
            (out / f"ui-{lang}.js").write_text("window.MIEL_UI=" + json.dumps(d, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
            self.stdout.write(f"ui-{lang}.js : {len(d)} textes")
