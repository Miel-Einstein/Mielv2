from celery import shared_task

from events.models import Event
from events.services import alerter


@shared_task
def run_daily_alerter():
    total = 0
    for event in Event.objects.filter(date__isnull=False):
        total += alerter.run_for_event(event)
    return total


@shared_task
def check_moment_media():
    total = 0
    for event in Event.objects.filter(moments__scheduled_at__isnull=False).distinct():
        total += alerter.check_scheduled_moments(event)
    return total
