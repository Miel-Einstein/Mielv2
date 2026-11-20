/* Panneau de contrôle de l'organisateur : tout voir, lancer les moments forts. */
(function () {
  const { $, $$, esc, api, toast, openSheet, closeSheet, tr } = Miel;
  let EV = window.EVENT;
  const BASE = '/api/e/' + EV.slug + '/';
  const L1 = EV.languages[0];
  let D = null;
  const money = v => Number(v || 0).toLocaleString('fr-FR', { maximumFractionDigits: 0 }) + ' ' + EV.currency;

  async function load() {
    [D, EV] = await Promise.all([api(BASE + 'dashboard/'), api(BASE)]);
    render();
  }
  Miel.emitPanel = a => { if (D) { D.arrivals = a; render(); } };
  Miel.on('wish', () => load());
  window.addEventListener('miel:event-changed', () => load());

  function render() {
    const b = D.budget, pct = b.pct, g = D.guests, a = D.arrivals;
    const roleName = id => (EV.roles.find(r => r.id === id) || {}).name || '';
    $('#main').innerHTML = '<div class="wrap">' +
      '<div class="row" style="justify-content:space-between;margin-bottom:14px"><h1 style="font-size:36px;font-style:italic;color:var(--honey-soft)">' + esc(tr(EV.title, L1)) + '</h1><span class="muted">' + (EV.date ? new Date(EV.date + 'T12:00').toLocaleDateString('fr-FR', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) + ' · ' + EV.time : 'Date à définir') + '</span></div>' +
      '<div class="tiles">' +
      '<div class="tile"><span>Réponses RSVP</span><b>' + D.responses + '</b></div>' +
      '<div class="tile"><span>Personnes confirmées</span><b>' + D.confirmed_people + '</b></div>' +
      '<div class="tile"><span>Invitations arrivées</span><b>' + a.arrived + '<small style="font-size:18px;color:var(--muted)"> / ' + a.total + '</small></b></div>' +
      '<div class="tile"><span>Enfants</span><b>' + D.children + '</b></div>' +
      (EV.services.includes('alerter') ? '<div class="tile"><span>Budget utilisé</span><b style="color:' + (pct > 100 ? 'var(--bad)' : pct >= 80 ? 'var(--warn)' : 'var(--honey)') + '">' + pct + '%</b></div>' : '') +
      '</div>' +
      (D.warnings.length ? '<div class="card" style="margin-top:14px;border-color:rgba(226,114,91,.5)">' + D.warnings.map(w => '<div style="color:var(--bad);font-weight:700">⚠️ ' + esc(w) + '</div>').join('') + '</div>' : '') +
      '<div class="panel-grid">' +
      // partage
      '<div class="card"><h2 style="font-size:26px">🔗 Liens à partager</h2><div class="grid" style="gap:8px;margin-top:10px">' +
      [['Invitation (RSVP / site)', EV.urls.share], ['Mur des vœux', EV.urls.wall], ['Écran géant (TV)', EV.urls.screen], ['Y aller', EV.urls.map]].map(([l, u]) => '<div class="row"><span style="flex:1;min-width:140px;font-size:13px"><b>' + l + '</b><br><span class="muted" style="word-break:break-all">' + esc(u) + '</span></span><button class="btn sm" data-copy="' + esc(u) + '">Copier</button><a class="btn sm ghost" href="' + esc(u) + '" target="_blank" rel="noopener">Ouvrir</a></div>').join('') +
      '</div><a class="btn ghost sm" style="margin-top:10px" href="/app/e/' + EV.slug + '/bot/">🤖 Partager avec l\'assistant (WhatsApp, Telegram)</a></div>' +
      // modèle du site
      (EV.services.includes('site') && EV.type === 'mariage' ? '<div class="card"><h2 style="font-size:26px">🌐 Site du mariage</h2><p class="muted" style="font-size:13px;margin:6px 0 10px">Choisis le style : tes textes et tes photos restent les mêmes.</p><div class="grid" style="gap:8px">' +
        [['A', 'Botanical Editorial', 'Crème, sauge, vert forêt, terracotta'], ['B', 'Modern Romance', 'Bleu nuit, vieux rose, or rosé']].map(([k, n, d]) => '<div class="row" style="border:1px solid ' + (EV.site_template === k ? 'var(--honey)' : 'var(--line)') + ';border-radius:12px;padding:8px 10px"><span style="flex:1;min-width:150px"><b>' + n + '</b>' + (EV.site_template === k ? ' <span class="pill ok">en ligne</span>' : '') + '<br><span class="muted" style="font-size:12.5px">' + d + '</span></span><a class="btn sm ghost" target="_blank" rel="noopener" href="' + esc(EV.urls.site) + '?tpl=' + k + '">Aperçu ↗</a>' + (EV.site_template === k ? '' : '<button class="btn sm gold" data-tpl="' + k + '">Choisir</button>') + '</div>').join('') + '</div></div>' : '') +
      // moments
      (EV.services.includes('moments') ? '<div class="card"><div class="row" style="justify-content:space-between"><h2 style="font-size:26px">✨ Moments forts</h2><span class="pill">temps réel</span></div><p class="muted" style="font-size:13px;margin:6px 0">Ils s\'affichent en même temps sur le téléphone des invités qui sont sur le mur, et sur l\'écran géant.</p>' +
        (EV.moments.map(m => '<div class="mo-row"><div class="th" style="' + (m.photo ? "background-image:url('" + esc(m.photo) + "')" : '') + '">' + (m.photo ? '' : m.kind === 'reveal' ? '📷' : '💬') + '</div><div class="tt"><b>' + esc(tr(m.title, L1)) + '</b><div class="muted" style="font-size:12px">' + ({ reveal: 'Compte à rebours + photo', message: 'Message surprise', clock: 'Compte à rebours vers une heure' }[m.kind]) + ' · ' + m.duration + ' s' + (m.status === 'launched' ? ' · <span class="pill ok">lancé</span>' : '') + '</div></div>' +
          (m.kind === 'reveal' ? '<label class="btn sm">' + (m.photo ? 'Changer' : 'Ajouter') + ' la photo<input type="file" accept="image/*" hidden data-ph="' + m.id + '"></label>' : '') +
          (m.status === 'launched' ? '<button class="btn sm ghost" data-reset="' + m.id + '">Remettre prêt</button>' : '') +
          '<button class="btn gold sm" data-launch="' + m.id + '">Lancer maintenant</button></div>').join('') || '<p class="muted">Aucun moment. Crée-les avec l\'assistant.</p>') + '</div>' : '') +
      // alerter
      (EV.services.includes('alerter') ? '<div class="card"><div class="row" style="justify-content:space-between"><h2 style="font-size:26px">⏰ Alerter</h2><span class="pill ' + (pct > 100 ? 'bad' : pct >= 80 ? 'warn' : 'ok') + '">' + money(b.used) + ' / ' + money(b.budget) + '</span></div>' +
        '<div class="bar ' + (pct > 100 ? 'bad' : pct >= 80 ? 'warn' : '') + '" style="margin:10px 0"><i style="width:' + Math.min(pct, 100) + '%"></i></div>' +
        (pct > 100 ? '<div class="warn-box" style="border-color:var(--bad)">Budget dépassé de <b>' + money(b.over) + '</b>.</div>' : pct >= 80 ? '<div class="warn-box">Tu as utilisé ' + pct + '% du budget. Une alerte part à 80 % et à 100 %.</div>' : '') +
        EV.alerter.filter(i => i.active).map(i => '<div class="al-row ' + (i.done ? 'done' : '') + '"><input type="checkbox" data-done="' + i.id + '" ' + (i.done ? 'checked' : '') + ' style="width:20px;height:20px;accent-color:#e9a83b" aria-label="Fait"><span class="t">' + esc(i.title) + '<br><small class="muted">' + (i.due_date ? new Date(i.due_date + 'T12:00').toLocaleDateString('fr-FR') : '') + ' · J' + i.due + (i.role ? ' · ' + esc(roleName(i.role)) : '') + '</small></span><input class="inp" type="number" placeholder="' + esc(EV.currency) + '" data-price="' + i.id + '" value="' + (i.price ?? '') + '" aria-label="Prix"></div>').join('') +
        '<div class="row" style="margin-top:10px"><input class="inp" style="flex:2 1 180px" id="al-new" placeholder="Ajouter un rappel"><input class="inp" style="flex:1 1 80px" type="number" id="al-due" value="-14" title="Jours avant l\'événement"><select class="inp" style="flex:1 1 140px" id="al-role"><option value="">Organisateur</option>' + EV.roles.map(r => '<option value="' + r.id + '">' + esc(r.name) + '</option>').join('') + '</select><button class="btn sm" id="alAdd">+ Ajouter</button></div>' +
        (D.alerts_sent.length ? '<details style="margin-top:10px"><summary class="muted" style="cursor:pointer">Alertes envoyées</summary>' + D.alerts_sent.map(x => '<div class="muted" style="font-size:12.5px">' + new Date(x.at).toLocaleString('fr-FR') + ' · ' + esc(x.message) + '</div>').join('') + '</details>' : '') + '</div>' : '') +
      // invités
      '<div class="card"><h2 style="font-size:26px">👥 Suivi des invités</h2><p class="muted" style="font-size:13px;margin:6px 0 12px">' + g.confirmed + ' personnes confirmées sur ' + (g.target || '?') + ' attendues.</p>' +
      (g.target ? '<div class="mini-bars">' + g.milestones.map(r => '<div><div class="lb"><span>J' + r.offset + ' : ' + r.pct + '% attendus (' + r.need + ')</span><span class="pill ' + (r.reached ? 'ok' : r.passed ? 'bad' : 'warn') + '">' + (r.reached ? 'atteint' : r.passed ? 'alerte envoyée' : 'à venir') + '</span></div><div class="bar ' + (r.reached ? '' : 'warn') + '"><i style="width:' + Math.min(100, Math.round(g.confirmed / Math.max(1, r.need) * 100)) + '%"></i></div></div>').join('') + '</div>' : '<p class="muted">Indique le nombre d\'invités attendus dans l\'assistant (étape Alerter).</p>') +
      '<details style="margin-top:12px"><summary style="cursor:pointer;font-weight:700">Liste des réponses (' + D.guest_list.length + ')</summary><div class="grid" style="gap:6px;margin-top:8px">' + D.guest_list.map(x => '<div class="row" style="font-size:13px;border-bottom:1px solid rgba(233,168,59,.1);padding:6px 0"><span style="flex:1;min-width:150px"><b>' + esc(x.first_name + ' ' + x.last_name) + '</b> ' + (x.attending ? '' : '<span class="pill bad">absent·e</span>') + '<br><span class="muted">' + esc(tr((EV.categories.find(c => c.id === x.category) || {}).name, L1) || '—') + (x.companions.length ? ' · +' + x.companions.length : '') + (x.children.length ? ' · ' + x.children.length + ' enfant(s)' : '') + ' · ' + esc(x.languages.join(', ')) + '</span></span>' + (x.attending ? '<button class="btn sm ' + (x.arrived ? 'gold' : 'ghost') + '" data-arr="' + x.id + '">' + (x.arrived ? '✅ Arrivé·e' : 'Marquer arrivé·e') + '</button>' : '') + '</div>').join('') + '</div></details></div>' +
      // arrivées
      '<div class="card"><h2 style="font-size:26px">🟢 Arrivées</h2><p class="muted" style="font-size:13px;margin:6px 0 10px">Mises à jour en direct, sans alerte à chaque arrivée.</p><div class="mini-bars">' +
      a.by_category.map(c => '<div><div class="lb"><span><i style="display:inline-block;width:9px;height:9px;border-radius:50%;background:' + c.color + '"></i> ' + esc(tr(c.name, L1)) + '</span><span>' + c.arrived + ' / ' + c.total + '</span></div><div class="bar"><i style="width:' + Math.round(c.arrived / c.total * 100) + '%"></i></div></div>').join('') + '</div>' +
      (a.recent.length ? '<div style="margin-top:10px;font-size:13px" class="muted">Derniers arrivés : ' + a.recent.map(r => esc(r.name)).join(', ') + '</div>' : '') + '</div>' +
      // équipe
      (EV.services.includes('alerter') ? '<div class="card"><h2 style="font-size:26px">🧑‍🤝‍🧑 Équipe & rôles</h2><p class="muted" style="font-size:13px;margin:6px 0 10px">Les délégués reçoivent seulement des e-mails ou des messages, sans accès au site.</p><div class="grid" style="gap:10px">' +
        (EV.roles.map(r => '<div class="role ' + (r.active ? '' : 'off') + '"><div class="row" style="justify-content:space-between"><b>' + esc(r.name) + '</b><div class="row"><button class="btn sm ghost" data-rt="' + r.id + '">' + (r.active ? 'Désactiver' : 'Réactiver') + '</button><button class="btn sm danger" data-rd="' + r.id + '">Supprimer</button></div></div>' + r.contacts.map(c => '<div class="ct">' + esc(c.name) + (c.title ? ' · <i>' + esc(c.title) + '</i>' : '') + ' · ' + [c.emails.length && '✉️ ' + esc(c.emails.join(', ')), c.whatsapp.length && '🟢 ' + esc(c.whatsapp.join(', '))].filter(Boolean).join(' · ') + '</div>').join('') + '<div class="ct">' + r.tasks + ' tâche(s)</div></div>').join('') || '<p class="muted">Aucun rôle. Crée-les avec l\'assistant.</p>') + '</div></div>' : '') +
      // vœux
      (EV.services.includes('mur') ? '<div class="card"><h2 style="font-size:26px">💬 Vœux récents</h2><p class="muted" style="font-size:13px;margin:6px 0 10px">Masque un vœu s\'il ne doit pas apparaître sur le mur.</p>' + (D.wishes.map(w => '<div class="row" style="border-bottom:1px solid rgba(233,168,59,.1);padding:6px 0;font-size:13px;' + (w.hidden ? 'opacity:.5' : '') + '"><span style="flex:1;min-width:160px"><b>' + esc(w.author) + '</b> · ' + esc(w.text) + '</span><button class="btn sm ghost" data-hide="' + w.id + '">' + (w.hidden ? 'Afficher' : 'Masquer') + '</button></div>').join('') || '<p class="muted">Pas encore de vœux.</p>') + '</div>' : '') +
      '</div></div>';
    bind();
  }

  function bind() {
    $$('[data-copy]').forEach(b => b.onclick = () => navigator.clipboard.writeText(b.dataset.copy).then(() => toast('Lien copié ✦')));
    $$('[data-launch]').forEach(b => b.onclick = () => launch(+b.dataset.launch));
    $$('[data-tpl]').forEach(b => b.onclick = async () => { await api(BASE, { method: 'PATCH', json: { site_template: b.dataset.tpl } }); toast('Modèle du site changé ✦'); load(); });
    $$('[data-reset]').forEach(b => b.onclick = async () => { const fd = new FormData(); fd.append('reset', '1'); await api(BASE + 'moments/' + b.dataset.reset + '/', { method: 'POST', form: fd }); load(); });
    $$('[data-ph]').forEach(i => i.onchange = async () => { const fd = new FormData(); fd.append('photo', i.files[0]); await api(BASE + 'moments/' + i.dataset.ph + '/', { method: 'POST', form: fd }); toast('Photo chargée ✦'); load(); });
    $$('[data-done]').forEach(c => c.onchange = async () => { await api(BASE + 'alerter/' + c.dataset.done + '/', { method: 'PATCH', json: { done: c.checked } }); load(); });
    $$('[data-price]').forEach(c => c.onchange = async () => { await api(BASE + 'alerter/' + c.dataset.price + '/', { method: 'PATCH', json: { price: c.value } }); load(); });
    const add = $('#alAdd'); if (add) add.onclick = async () => { const v = $('#al-new').value.trim(); if (!v) return; await api(BASE + 'alerter/', { method: 'POST', json: { title: v, due: +$('#al-due').value || -14, role: $('#al-role').value || null } }); load(); };
    $$('[data-rt]').forEach(b => b.onclick = async () => { const r = EV.roles.find(x => x.id === +b.dataset.rt); await api(BASE + 'roles/' + r.id + '/', { method: 'PATCH', json: { active: !r.active } }); toast(r.active ? 'Rôle en pause : plus aucun rappel ne part' : 'Rôle réactivé'); load(); });
    $$('[data-rd]').forEach(b => b.onclick = () => {
      const r = EV.roles.find(x => x.id === +b.dataset.rd);
      const sh = openSheet('<h3>Supprimer « ' + esc(r.name) + ' »</h3><p class="muted">Ce rôle a ' + r.tasks + ' tâche(s). Que veux-tu en faire ?</p><div class="grid"><button class="btn" data-k="owner">Les rendre à l\'organisateur</button>' + EV.roles.filter(x => x.id !== r.id).map(x => '<button class="btn" data-k="' + x.id + '">Les donner à « ' + esc(x.name) + ' »</button>').join('') + '<button class="btn danger" data-k="delete">Supprimer aussi les tâches</button><button class="btn ghost" data-k="no">Annuler</button></div>');
      $$('[data-k]', sh).forEach(x => x.onclick = async () => { closeSheet(); if (x.dataset.k === 'no') return; await api(BASE + 'roles/' + r.id + '/?tasks=' + x.dataset.k, { method: 'DELETE' }); toast('Rôle supprimé'); load(); });
    });
    $$('[data-arr]').forEach(b => b.onclick = async () => { const x = D.guest_list.find(g => g.id === +b.dataset.arr); await api(BASE + 'guests/' + x.id + '/', { method: 'PATCH', json: { arrived: !x.arrived } }); load(); });
    $$('[data-hide]').forEach(b => b.onclick = async () => { await api(BASE + 'wishes/' + b.dataset.hide + '/hide/', { method: 'POST' }); load(); });
  }

  async function launch(id, asMessage) {
    const m = EV.moments.find(x => x.id === id);
    if (m.needs_photo && !asMessage) {
      const sh = openSheet('<h3>Il manque la photo</h3><p class="muted">« ' + esc(tr(m.title, L1)) + ' » n\'a pas encore de photo. Que veux-tu faire ?</p><div class="grid"><label class="btn gold">📷 Ajouter la photo maintenant<input type="file" accept="image/*" hidden id="lmPh"></label><button class="btn" id="lmMsg">Lancer en simple message</button><button class="btn ghost" id="lmNo">Annuler</button></div>');
      $('#lmPh', sh).onchange = async e => { const fd = new FormData(); fd.append('photo', e.target.files[0]); await api(BASE + 'moments/' + id + '/', { method: 'POST', form: fd }); closeSheet(); EV = await api(BASE); launch(id); };
      $('#lmMsg', sh).onclick = () => { closeSheet(); launch(id, true); };
      $('#lmNo', sh).onclick = closeSheet;
      return;
    }
    try { await api(BASE + 'moments/' + id + '/launch/', { method: 'POST', json: { as_message: !!asMessage } }); toast('Moment lancé chez tous les invités ✨'); load(); } catch (e) { toast(e.message); }
  }
  load().catch(e => toast(e.message));
})();
