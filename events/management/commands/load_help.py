"""Charge ou met à jour les réponses de départ de l'aide (events/help_kb.py).

  python manage.py load_help            → ajoute seulement les réponses qui manquent
  python manage.py load_help --update   → met aussi à jour les réponses de Miel (celles créées dans l'admin ne sont pas touchées)
"""
from django.core.management.base import BaseCommand

from events.services.help import load_builtin


class Command(BaseCommand):
    help = "Réponses de départ de l'aide de l'assistant."

    def add_arguments(self, parser):
        parser.add_argument("--update", action="store_true")

    def handle(self, update=False, **kw):
        self.stdout.write(f"{load_builtin(update=update)} réponses de départ")
