"""Logique de l'Alerter : rappels de tâches, budget, invités, médias des moments."""
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.utils import timezone

from events.models import AlertLog, t
from events.services import notify
from events.services.defaults import BUDGET_THRESHOLDS, GUEST_MILESTONES
from events.services.seating import persons

REMIND_DAYS = {7, 1, 0}  # rappels à J-7, J-1 et le jour même de l'échéance


def budget_status(event):
    used = sum((i.price or Decimal(0)) for i in event.alerter_items.filter(active=True))
    pct = int(used / event.budget * 100) if event.budget else 0
    return {"used": float(used), "budget": float(event.budget), "pct": pct, "over": float(max(Decimal(0), used - event.budget))}


def guest_status(event, today=None):
    today = today or timezone.localdate()
    confirmed = len(persons(event))
    target = event.guest_target or 0
    rows = []
    for offset, pct in GUEST_MILESTONES:
        need = round(target * pct / 100)
        day = event.due_date(offset)
        rows.append({"offset": offset, "pct": pct, "need": need, "day": day.isoformat() if day else None,
                     "reached": confirmed >= need, "passed": bool(day and today >= day)})
    return {"confirmed": confirmed, "target": target, "milestones": rows}


def warnings(event):
    """Alertes affichées en permanence dans le panneau (sans envoi)."""
    out = []
    for m in event.moments.all():
        if m.needs_photo and m.status == "ready":
            out.append(f"Photo du moment « {t(m.title, 'fr')} » pas encore chargée")
    if event.kids_invited and event.kids_table and not event.supervisor_name:
        out.append("Trouver quelqu'un pour surveiller la table des enfants")
    b = budget_status(event)
    if b["pct"] > 100:
        out.append(f"Budget dépassé de {b['over']:.0f} {event.currency}")
    return out


def _log_once(event, key, message):
    try:
        _, created = AlertLog.objects.get_or_create(event=event, key=key, defaults={"message": message})
        return created
    except IntegrityError:  # deux tâches Celery en même temps
        return False


def _recipients(event, item=None):
    if item and item.role and item.role.active:
        return list(item.role.contacts.all())
    return []


def _send(event, subject, text, item=None):
    contacts = _recipients(event, item)
    for c in contacts:
        notify.notify_contact(c, subject, text)
    notify.notify_owner(event, subject, text)


def task_message(event, item, contact_title=""):
    due = event.due_date(item.due_offset_days)
    role = f"\nRôle : {item.role.name}" if item.role else ""
    return (f"Bonjour 👋\n{role}\nTâche : {item.title} — avant le {due:%d/%m/%Y}\n"
            f"Événement : {event.title_in('fr')}\n"
            f"Pour toute question, contactez l'organisateur : {event.owner.email}")


def run_for_event(event, today=None):
    today = today or timezone.localdate()
    if not event.date or not event.has("alerter"):
        return 0
    sent = 0
    # 1) Tâches
    for item in event.alerter_items.filter(active=True, done=False, kind="task").select_related("role"):
        if item.role and not item.role.active:
            continue
        due = event.due_date(item.due_offset_days)
        left = (due - today).days
        if left in REMIND_DAYS and _log_once(event, f"task-{item.id}-{left}", item.title):
            _send(event, f"⏰ Rappel : {item.title}", task_message(event, item), item)
            sent += 1
    # 2) Budget
    b = budget_status(event)
    for th in BUDGET_THRESHOLDS:
        if b["pct"] >= th and _log_once(event, f"budget-{th}", f"Budget à {b['pct']}%"):
            _send(event, f"💰 Budget à {b['pct']}%", f"Vous avez utilisé {b['used']:.0f} {event.currency} sur {b['budget']:.0f} {event.currency}.")
            sent += 1
    # 3) Nombre d'invités aux paliers
    g = guest_status(event, today)
    for row in g["milestones"]:
        if row["passed"] and not row["reached"] and _log_once(event, f"guests-{row['offset']}", "palier invités"):
            _send(event, "👥 Réponses en retard",
                  f"À J{row['offset']}, {g['confirmed']} personnes confirmées sur {row['need']} attendues ({row['pct']}%). Pensez à relancer les invités sans réponse.")
            sent += 1
    # 4) Médias des moments forts (J-7, J-1, jour J)
    left_event = (event.date - today).days
    if left_event in REMIND_DAYS:
        for m in event.moments.filter(kind="reveal", status="ready"):
            if m.needs_photo and _log_once(event, f"moment-{m.id}-{left_event}", "photo manquante"):
                _send(event, "📷 Photo manquante", f"La photo du moment « {t(m.title, 'fr')} » n'est pas encore chargée.")
                sent += 1
    # 5) Surveillance de la table des enfants
    if event.kids_table and not event.supervisor_name and left_event in REMIND_DAYS and _log_once(event, f"supervisor-{left_event}", "surveillant"):
        _send(event, "👶 Table des enfants", "Personne n'est encore désigné pour surveiller la table des enfants.")
        sent += 1
    return sent


def check_scheduled_moments(event, now=None):
    """1 h et 10 min avant un moment à heure fixe : vérifie la photo."""
    now = now or timezone.now()
    sent = 0
    for m in event.moments.filter(status="ready", scheduled_at__isnull=False):
        delta = m.scheduled_at - now
        for label, win in (("1h", timedelta(hours=1)), ("10min", timedelta(minutes=10))):
            if timedelta(0) < delta <= win and m.needs_photo and _log_once(event, f"sched-{m.id}-{label}", "photo"):
                _send(event, "📷 Photo manquante", f"Le moment « {t(m.title, 'fr')} » commence dans moins de {label} et sa photo manque.")
                sent += 1
        if delta <= timedelta(0) and m.status == "ready":
            from events.views_api import launch_moment_obj

            launch_moment_obj(m, as_message=m.needs_photo)
    return sent
