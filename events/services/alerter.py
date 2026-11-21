"""Logique de l'Alerter : rappels de tâches, budget, invités, médias des moments."""
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError
from django.utils import timezone

from events.models import AlertLog, t
from events.services import notify
from events.services.defaults import BUDGET_THRESHOLDS, GUEST_MILESTONES
from events.services.seating import persons
from events.ui_i18n import user_ui_lang

REMIND_DAYS = {7, 1, 0}  # rappels à J-7, J-1 et le jour même de l'échéance

# Messages envoyés, dans la langue de chaque destinataire (organisateur : langue de son compte ; délégué : sa langue).
# Le lingala est une première version, à faire relire.
MSG = {
    "task_subject": {"fr": "⏰ Rappel : {title}", "en": "⏰ Reminder: {title}", "it": "⏰ Promemoria: {title}", "ln": "⏰ Bokundoli : {title}"},
    "task_body": {
        "fr": "Bonjour 👋\n{role}\nTâche : {title} — avant le {due}\nÉvénement : {event}\nPour toute question, contactez l'organisateur : {email}",
        "en": "Hello 👋\n{role}\nTask: {title} — before {due}\nEvent: {event}\nAny questions? Contact the organiser: {email}",
        "it": "Ciao 👋\n{role}\nCompito: {title} — entro il {due}\nEvento: {event}\nPer qualsiasi domanda, contatta l'organizzatore: {email}",
        "ln": "Mbote 👋\n{role}\nMosala : {title} — liboso ya {due}\nFɛti : {event}\nSoki ozali na motuna, benga mobongisi : {email}"},
    "role": {"fr": "Rôle : {name}", "en": "Role: {name}", "it": "Ruolo: {name}", "ln": "Mosala na yo : {name}"},
    "budget_subject": {"fr": "💰 Budget à {pct}%", "en": "💰 Budget at {pct}%", "it": "💰 Budget al {pct}%", "ln": "💰 Mbongo esalelami {pct}%"},
    "budget_body": {"fr": "Vous avez utilisé {used} {cur} sur {budget} {cur}.", "en": "You have used {used} {cur} out of {budget} {cur}.",
                    "it": "Hai usato {used} {cur} su {budget} {cur}.", "ln": "Bosaleli {used} {cur} na kati ya {budget} {cur}."},
    "guests_subject": {"fr": "👥 Réponses en retard", "en": "👥 Late replies", "it": "👥 Risposte in ritardo", "ln": "👥 Biyano ezali kozanga"},
    "guests_body": {
        "fr": "À J{off}, {conf} personnes confirmées sur {need} attendues ({pct}%). Pensez à relancer les invités sans réponse.",
        "en": "At D{off}, {conf} people confirmed out of {need} expected ({pct}%). Remember to remind the guests who haven't replied.",
        "it": "A G{off}, {conf} persone confermate su {need} attese ({pct}%). Ricordati di sollecitare gli invitati che non hanno risposto.",
        "ln": "Na J{off}, bato {conf} bandimi na kati ya {need} oyo tozelaki ({pct}%). Bokundola babyangami oyo bazongisi naino te."},
    "photo_subject": {"fr": "📷 Photo manquante", "en": "📷 Missing photo", "it": "📷 Foto mancante", "ln": "📷 Elili ezangi"},
    "photo_body": {"fr": "La photo du moment « {m} » n'est pas encore chargée.", "en": "The photo for the moment “{m}” hasn't been uploaded yet.",
                   "it": "La foto del momento «{m}» non è ancora stata caricata.", "ln": "Elili ya ntango « {m} » etíami naino te."},
    "sched_body": {"fr": "Le moment « {m} » commence dans moins de {left} et sa photo manque.", "en": "The moment “{m}” starts in less than {left} and its photo is missing.",
                   "it": "Il momento «{m}» inizia tra meno di {left} e manca la foto.", "ln": "Ntango « {m} » ekobanda na {left} mpe elili na yango ezali te."},
    "kids_subject": {"fr": "👶 Table des enfants", "en": "👶 Children's table", "it": "👶 Tavolo dei bambini", "ln": "👶 Mesa ya bana"},
    "kids_body": {"fr": "Personne n'est encore désigné pour surveiller la table des enfants.", "en": "Nobody has been chosen yet to look after the children's table.",
                  "it": "Nessuno è ancora stato scelto per sorvegliare il tavolo dei bambini.", "ln": "Moto moko te aponami naino mpo na kokengela mesa ya bana."},
}


def msg(key, lang, **kw):
    table = MSG[key]
    return table.get(lang, table["fr"]).format(**kw)


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


def _send(event, build, item=None):
    """build(lang) -> (sujet, texte) : chaque destinataire reçoit le message dans sa langue."""
    for c in _recipients(event, item):
        notify.notify_contact(c, *build(c.language or "fr"))
    notify.notify_owner(event, *build(user_ui_lang(event.owner)))


def _ev_title(event, lang):
    return event.title_in(lang if lang in (event.languages or []) else (event.languages or ["fr"])[0])


def task_message(event, item, lang="fr"):
    due = event.due_date(item.due_offset_days)
    role = msg("role", lang, name=item.role.name) if item.role else ""
    return msg("task_body", lang, role=role, title=item.title, due=f"{due:%d/%m/%Y}", event=_ev_title(event, lang), email=event.owner.email)


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
            _send(event, lambda l, item=item: (msg("task_subject", l, title=item.title), task_message(event, item, l)), item)
            sent += 1
    # 2) Budget
    b = budget_status(event)
    for th in BUDGET_THRESHOLDS:
        if b["pct"] >= th and _log_once(event, f"budget-{th}", f"Budget à {b['pct']}%"):
            _send(event, lambda l: (msg("budget_subject", l, pct=b["pct"]), msg("budget_body", l, used=f"{b['used']:.0f}", budget=f"{b['budget']:.0f}", cur=event.currency)))
            sent += 1
    # 3) Nombre d'invités aux paliers
    g = guest_status(event, today)
    for row in g["milestones"]:
        if row["passed"] and not row["reached"] and _log_once(event, f"guests-{row['offset']}", "palier invités"):
            _send(event, lambda l, row=row: (msg("guests_subject", l), msg("guests_body", l, off=row["offset"], conf=g["confirmed"], need=row["need"], pct=row["pct"])))
            sent += 1
    # 4) Médias des moments forts (J-7, J-1, jour J)
    left_event = (event.date - today).days
    if left_event in REMIND_DAYS:
        for m in event.moments.filter(kind="reveal", status="ready"):
            if m.needs_photo and _log_once(event, f"moment-{m.id}-{left_event}", "photo manquante"):
                _send(event, lambda l, m=m: (msg("photo_subject", l), msg("photo_body", l, m=t(m.title, l))))
                sent += 1
    # 5) Surveillance de la table des enfants
    if event.kids_table and not event.supervisor_name and left_event in REMIND_DAYS and _log_once(event, f"supervisor-{left_event}", "surveillant"):
        _send(event, lambda l: (msg("kids_subject", l), msg("kids_body", l)))
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
                _send(event, lambda l, m=m, label=label: (msg("photo_subject", l), msg("sched_body", l, m=t(m.title, l), left=label)))
                sent += 1
        if delta <= timedelta(0) and m.status == "ready":
            from events.views_api import launch_moment_obj

            launch_moment_obj(m, as_message=m.needs_photo)
    return sent
