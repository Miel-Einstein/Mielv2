"""Lance à la main les tâches de fond (sans Celery ni Redis).

Utile sur PythonAnywhere : à mettre dans une « Scheduled task ».
    python manage.py run_tasks            # alerter + vérification des photos des moments
    python manage.py run_tasks --alerter  # seulement l'Alerter
"""
from django.core.management.base import BaseCommand

from events.tasks import check_moment_media, run_daily_alerter


class Command(BaseCommand):
    help = "Exécute l'Alerter et la vérification des photos des moments forts (sans Celery)."

    def add_arguments(self, parser):
        parser.add_argument("--alerter", action="store_true", help="Seulement l'Alerter")
        parser.add_argument("--moments", action="store_true", help="Seulement la vérification des moments")

    def handle(self, *args, **opts):
        both = not opts["alerter"] and not opts["moments"]
        if both or opts["alerter"]:
            run_daily_alerter()
            self.stdout.write("Alerter : fait")
        if both or opts["moments"]:
            check_moment_media()
            self.stdout.write("Moments forts : fait")
