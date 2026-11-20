"""Construit les fichiers de traduction (.po / .mo) sans outil gettext.

Les textes sources (en français) sont lus dans les templates ({% translate "…" %}),
et les traductions viennent de events/i18n_catalog.py. Un texte sans traduction
s'affiche en français. Lancer : python manage.py build_translations
"""
import re
from pathlib import Path

import polib
from django.conf import settings
from django.core.management.base import BaseCommand

from events.i18n_catalog import CATALOG

PATTERN = re.compile(r"""{%\s*(?:translate|trans)\s+(["'])(.+?)\1\s*%}""")


def extract():
    found = []
    for path in sorted(Path(settings.BASE_DIR, "templates").rglob("*.html")):
        for m in PATTERN.finditer(path.read_text(encoding="utf-8")):
            if m.group(2) not in found:
                found.append(m.group(2))
    return found


class Command(BaseCommand):
    help = "Génère locale/<langue>/LC_MESSAGES/django.po et django.mo"

    def add_arguments(self, parser):
        parser.add_argument("--missing", action="store_true", help="Affiche les textes sans traduction")

    def handle(self, *args, **opts):
        strings = extract()
        for lang in ("en", "it", "ln"):
            table = CATALOG.get(lang, {})
            po = polib.POFile()
            po.metadata = {"Content-Type": "text/plain; charset=utf-8", "Language": lang, "MIME-Version": "1.0",
                           "Content-Transfer-Encoding": "8bit", "Plural-Forms": "nplurals=2; plural=(n != 1);"}
            missing = []
            for s in strings:
                if table.get(s):
                    po.append(polib.POEntry(msgid=s, msgstr=table[s]))
                else:
                    missing.append(s)
            out = Path(settings.BASE_DIR, "locale", lang, "LC_MESSAGES")
            out.mkdir(parents=True, exist_ok=True)
            po.save(str(out / "django.po"))
            po.save_as_mofile(str(out / "django.mo"))
            self.stdout.write(f"{lang}: {len(strings) - len(missing)}/{len(strings)} textes traduits")
            if opts["missing"] and missing:
                for s in missing:
                    self.stdout.write(f"  - {s}")
