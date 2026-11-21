"""Aide de l'assistant : retrouve la meilleure réponse à une question écrite librement.

Pas d'intelligence artificielle : des mots-clés, des synonymes, une tolérance aux fautes de frappe
et le contexte (l'étape ou la page où se trouve l'utilisateur). Si rien ne correspond assez,
la question est enregistrée pour que l'équipe Miel ajoute la réponse dans l'admin.
"""
import difflib
import re
import unicodedata

STOP = set("""
le la les l un une des de du d a au aux et ou en dans sur pour par avec sans ce cet cette ces ca cela c est
je j tu te t il elle on nous vous ils elles me m mon ma mes ton ta tes son sa ses notre nos votre vos leur leurs
qui que quoi qu comment mettre mets pourquoi quand ou est-ce peux peut puis-je faire fait faut dois doit veux voudrais
y a ai as avoir etre suis es sont ne n pas plus tres bien aussi encore deja moi toi merci bonjour salut svp stp
the a an of to in on for with and or is are be can could how what why when where do does i my me you your it this that please
il lo la gli le un una di da in con per e o come cosa perche quando dove posso puoi mio mia tuo tua questo questa grazie
na ya mpo ndenge nini ezali nakoki ngai yo
""".split())

SYN = {  # mot (sans accent) -> forme commune
    "foto": "photo", "photos": "photo", "image": "photo", "images": "photo", "picture": "photo", "immagine": "photo", "elili": "photo", "bilili": "photo",
    "popup": "assistant", "pop": "assistant", "bot": "assistant", "fenetre": "assistant", "assistente": "assistant", "mosungi": "assistant",
    "reouvrir": "rouvrir", "reactiver": "rouvrir", "riaprire": "rouvrir", "reopen": "rouvrir",
    "mdp": "password", "motdepasse": "password", "pass": "password",
    "tavolo": "table", "tavoli": "table", "tables": "table", "mesa": "table", "bamesa": "table",
    "regalo": "cadeau", "regali": "cadeau", "gift": "cadeau", "gifts": "cadeau", "makabo": "cadeau", "likabo": "cadeau", "cadeaux": "cadeau",
    "prezzo": "prix", "price": "prix", "tarif": "prix", "cout": "prix", "cost": "prix", "ntalo": "prix", "combien": "prix",
    "lingua": "langue", "language": "langue", "monoko": "langue", "langues": "langue",
    "invitati": "invite", "invites": "invite", "guests": "invite", "guest": "invite", "babyangami": "invite",
    "couleur": "colour", "color": "colour", "colore": "colour", "langi": "colour",
}


def norm(text):
    t = unicodedata.normalize("NFD", (text or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = re.sub(r"[’'`]", " ", t)
    t = re.sub(r"[^a-z0-9+]+", " ", t)
    return " ".join(t.split())


def tokens(text):
    out = []
    for w in norm(text).split():
        if w in STOP or len(w) < 2:
            continue
        w = SYN.get(w, w)
        out.append(w)
    return out


def _stem(w):
    return w[:5] if len(w) > 5 else w


def _match(word, vocab):
    """Poids de la correspondance d'un mot de la question avec un ensemble de mots (exact, racine, faute de frappe)."""
    if word in vocab:
        return 1.0
    st = _stem(word)
    if len(word) >= 4 and any(_stem(v) == st for v in vocab if len(v) >= 4):
        return 0.8
    if len(word) >= 5 and difflib.get_close_matches(word, [v for v in vocab if len(v) >= 4], n=1, cutoff=0.82):
        return 0.6
    return 0.0


def _index(entry):
    kw = set(tokens(entry.keywords))
    qs = set()
    for q in (entry.question or {}).values():
        qs |= set(tokens(q))
    an = set()
    for a in (entry.answer or {}).values():
        an |= set(tokens(a))
    return kw, qs, an


THIS_SECTION = {"section", "etape", "step", "sezione", "passo", "ici", "here", "qui", "remplir", "fill", "compilare", "cette", "this", "questa", "eteni", "bloque", "stuck", "bloccato"}


def search(question, lang="fr", context="", entries=None):
    """Renvoie (meilleure entrée ou None, score, [autres entrées proches])."""
    from events.models import HelpEntry

    words = tokens(question)
    if not words:
        return None, 0.0, []
    entries = list(entries if entries is not None else HelpEntry.objects.filter(active=True))
    about_here = bool(set(norm(question).split()) & THIS_SECTION)
    scored = []
    for e in entries:
        kw, qs, an = _index(e)
        s = 0.0
        hit = 0
        for w in words:
            m = max(3 * _match(w, kw), 2 * _match(w, qs), 0.5 * _match(w, an))
            if m:
                hit += 1
            s += m
        s = s / max(1.0, len(words) ** 0.5)
        if context and e.context:
            if e.context == context:
                s += 1.5 if not about_here else 4.0
            elif context.startswith("bot:") and e.context.startswith("bot:"):
                s -= 0.3
        coverage = hit / len(words)
        scored.append((s * (0.6 + 0.4 * coverage), coverage, e))
    scored.sort(key=lambda x: -x[0])
    if about_here and context:  # « comment remplir cette section ? » : l'aide de l'écran en cours passe en premier
        here = [x for x in scored if x[2].context == context]
        if here:
            scored.remove(here[0])
            scored.insert(0, (max(here[0][0], 3.0), max(here[0][1], 0.5), here[0][2]))
    best_s, best_cov, best = scored[0] if scored else (0, 0, None)
    if best is None or best_s < 2.2 or best_cov < 0.25:
        return None, best_s, [e for s, c, e in scored[:3] if s >= 1.2]
    alts = [e for s, c, e in scored[1:4] if s >= max(1.8, best_s * 0.6)]
    return best, best_s, alts


def localized(d, lang):
    d = d or {}
    return d.get(lang) or d.get("fr") or next(iter(d.values()), "")


def entry_payload(e, lang):
    return {"id": e.id, "question": localized(e.question, lang), "answer": localized(e.answer, lang),
            "actions": [{**{k: v for k, v in a.items() if k != "label"}, "label": localized(a.get("label"), lang)} for a in (e.actions or [])]}


def log_unanswered(text, lang, context, user=None, event=None):
    from events.models import UnansweredQuestion

    n = norm(text)[:500]
    if not n:
        return
    q = UnansweredQuestion.objects.filter(normalized=n, resolved__isnull=True).first()
    if q:
        q.count += 1
        q.save(update_fields=["count", "last_at"])
    else:
        UnansweredQuestion.objects.create(text=text[:500], normalized=n, lang=lang, context=context[:40],
                                          user=user if (user and user.is_authenticated) else None, event=event)


def load_builtin(update=False):
    """Charge les réponses de départ (events/help_kb.py). Avec update=True, met à jour celles de Miel sans toucher à celles de l'admin."""
    from events.help_kb import ENTRIES
    from events.models import HelpEntry

    n = 0
    for d in ENTRIES:
        fields = {"category": d["cat"], "context": d["ctx"], "keywords": d["kw"], "question": d["q"], "answer": d["a"], "actions": d.get("actions", [])}
        obj, created = HelpEntry.objects.get_or_create(key=d["key"], defaults=fields)
        if not created and update:
            for k, v in fields.items():
                setattr(obj, k, v)
            obj.save()
        n += 1
    return n
