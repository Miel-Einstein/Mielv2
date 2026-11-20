/* Plan de table responsive : toucher-toucher, appui long + glisser, « Déplacer vers… »,
   annulation, vue liste, deux tables côte à côte, tiroir des tables sur téléphone. */
(function () {
  const { $, $$, esc, api, toast, openSheet, closeSheet, tr } = Miel;
  const EV = window.EVENT, BASE = '/api/e/' + EV.slug + '/', L1 = EV.languages[0];
  let P = null; // {tables, persons, unplaced, categories, supervisor}
  const TB = { a: 0, b: 1, sel: null, list: false, two: false, drawer: false, undo: [] };
  const main = $('#main');

  const catOf = id => P.categories.find(c => c.id === id);
  const label = (t, i) => t.name || 'Table ' + (i + 1);
  const snap = () => { TB.undo.push(JSON.stringify(P.tables)); if (TB.undo.length > 30) TB.undo.shift(); };
  async function persist() {
    try { P = await api(BASE + 'tables/', { method: 'PUT', json: P.tables }); }
    catch (e) { toast(e.message); P = await api(BASE + 'tables/'); }
    render();
  }
  async function undo() { const s = TB.undo.pop(); if (!s) return; P.tables = JSON.parse(s); TB.sel = null; await persist(); toast('Modification annulée'); }

  function doSwap(src, dst) {
    const B = P.tables[dst.t];
    if (src.u) {
      if (B.seats[dst.s] === 'SUPERVISOR') return toast('Place réservée à la personne qui surveille');
      snap(); const prev = B.seats[dst.s]; B.seats[dst.s] = src.u; TB.sel = null; persist();
      toast(prev ? 'Échangé : l\'invité précédent passe dans « non placés »' : 'Invité placé ✦', undo); return;
    }
    if (src.t === dst.t && src.s === dst.s) { TB.sel = null; render(); return; }
    const A = P.tables[src.t];
    if (A.seats[src.s] === 'SUPERVISOR' || B.seats[dst.s] === 'SUPERVISOR') return toast('Place réservée à la personne qui surveille');
    snap(); [A.seats[src.s], B.seats[dst.s]] = [B.seats[dst.s], A.seats[src.s]]; TB.sel = null; persist(); toast('Échange effectué ✦', undo);
  }

  function seatHTML(t, ti, si, mode) {
    const k = t.seats[si], sel = TB.sel && !TB.sel.u && TB.sel.t === ti && TB.sel.s === si;
    const ang = (si / t.capacity) * Math.PI * 2 - Math.PI / 2;
    let pos = '';
    if (mode === 'round') pos = 'style="left:' + (50 + 40 * Math.cos(ang)) + '%;top:' + (50 + 40 * Math.sin(ang)) + '%"';
    if (mode === 'rect') { const half = Math.ceil(t.capacity / 2), top = si < half, col = top ? si : si - half; pos = 'style="left:' + (10 + (80 * (col + 0.5)) / half) + '%;top:' + (top ? 18 : 82) + '%"'; }
    const target = TB.sel && !sel ? ' target' : '';
    if (!k) return '<button type="button" class="seat empty' + target + '" ' + pos + ' data-t="' + ti + '" data-s="' + si + '" aria-label="Siège ' + (si + 1) + ' libre"><span class="sn">' + (si + 1) + '</span>+</button>';
    if (k === 'SUPERVISOR') return '<button type="button" class="seat" ' + pos + ' data-t="' + ti + '" data-s="' + si + '" style="background:#f3cf8a"><span class="sn">' + (si + 1) + '</span><span class="nm">' + esc(P.supervisor || 'Surveillant·e') + '</span><span class="ty">surveille</span></button>';
    const p = P.persons[k];
    if (!p) return '<button type="button" class="seat empty' + target + '" ' + pos + ' data-t="' + ti + '" data-s="' + si + '"><span class="sn">' + (si + 1) + '</span>+</button>';
    const parts = p.name.split(' '), short = parts[0] + (parts[1] ? ' ' + parts[1][0] + '.' : '');
    const c = catOf(p.cat);
    const ty = p.type === 'enfant' ? p.age + ' ans' : p.type === 'accomp' ? 'Accomp.' : c && c.is_honor ? '👑' : '';
    return '<button type="button" class="seat' + (sel ? ' sel' : '') + target + '" ' + pos + ' data-t="' + ti + '" data-s="' + si + '" data-k="' + esc(k) + '" title="' + esc(p.name + (p.note ? ' ' + p.note : '')) + '"><span class="sn">' + (si + 1) + '</span><span class="dot" style="background:' + (c ? c.color : '#999') + '"></span><span class="nm">' + esc(mode === 'list' ? p.name : short) + '</span><span class="ty">' + ty + (p.note && mode === 'list' ? ' · ' + esc(p.note) : '') + '</span></button>';
  }

  function tableCard(ti) {
    const t = P.tables[ti]; if (!t) return '';
    const occ = t.seats.filter(Boolean).length;
    let body;
    if (TB.list) body = '<div class="seat-list">' + t.seats.map((_, si) => seatHTML(t, ti, si, 'list')).join('') + '</div>';
    else if (t.shape === 'rect') body = '<div class="round" style="aspect-ratio:1.6"><div class="cloth" style="inset:32% 6%;border-radius:18px"><div><b>' + (ti + 1) + '</b><small>' + occ + ' / ' + t.capacity + '</small></div></div>' + t.seats.map((_, si) => seatHTML(t, ti, si, 'rect')).join('') + '</div>';
    else body = '<div class="round"><div class="cloth"><div><b>' + (ti + 1) + '</b><small>' + occ + ' / ' + t.capacity + '</small></div></div>' + t.seats.map((_, si) => seatHTML(t, ti, si, 'round')).join('') + '</div>';
    return '<div class="tbl-card" data-tc="' + ti + '"><div class="tbl-head"><button type="button" class="icon-btn" data-nav="' + ti + '" data-d="-1" aria-label="Table précédente">‹</button><h3>' + (t.kind === 'kids' ? '👶 ' : t.kind === 'honor' ? '👑 ' : '') + esc(label(t, ti)) + '</h3><span class="pill ' + (occ === t.capacity ? 'ok' : '') + '">' + occ + '/' + t.capacity + '</span><button type="button" class="icon-btn" data-edit="' + ti + '" aria-label="Modifier la table">✎</button><button type="button" class="icon-btn" data-nav="' + ti + '" data-d="1" aria-label="Table suivante">›</button></div>' + body + '</div>';
  }

  function render() {
    const wide = innerWidth >= 900, n = P.tables.length;
    if (!n) {
      main.innerHTML = '<div class="wrap"><div class="card"><h2>Plan de table</h2><p class="muted">Aucune table pour le moment. Choisis le nombre de tables, les places par table et tes tables particulières : la répartition tient compte des catégories, des langues, des enfants et de la table d\'honneur.</p><button type="button" class="btn gold" id="tbAuto">↻ Répartition automatique</button></div></div>';
      $('#tbAuto').onclick = auto; return;
    }
    if (TB.a >= n) TB.a = 0; if (TB.b >= n || TB.b === TB.a) TB.b = (TB.a + 1) % n;
    const selName = TB.sel ? (TB.sel.u ? (P.persons[TB.sel.u] || {}).name : (P.persons[P.tables[TB.sel.t].seats[TB.sel.s]] || {}).name) : '';
    main.innerHTML = '<div class="wrap">' +
      '<div class="tb-toolbar">' + (!wide ? '<button type="button" class="btn sm" id="tbDrawer">☰ Tables</button>' : '') + '<button type="button" class="btn gold sm" id="tbAuto">↻ Répartir automatiquement</button><button type="button" class="btn sm" id="tbUndo" ' + (TB.undo.length ? '' : 'disabled') + '>↩ Annuler</button><button type="button" class="btn sm" id="tbView">' + (TB.list ? '⭕ Vue table' : '☰ Vue liste') + '</button>' + (innerWidth >= 700 ? '<button type="button" class="btn sm ' + (TB.two ? 'gold' : '') + '" id="tbTwo">⧉ Deux tables côte à côte</button>' : '') + '<button type="button" class="btn sm ' + (P.unplaced.length ? 'danger' : '') + '" id="tbUn">Non placés : ' + P.unplaced.length + '</button><button type="button" class="btn sm" id="tbAdd">+ Table</button><a class="btn sm ghost" href="/app/e/' + EV.slug + '/plan.pdf?lang=' + L1 + '">⤓ PDF</a><a class="btn sm ghost" href="/app/e/' + EV.slug + '/plan.pdf?lang=' + L1 + '&names=1">⤓ PDF noms</a></div>' +
      '<div class="tb-layout"><aside class="tb-side ' + (TB.drawer ? 'open' : '') + '" id="tbSide"><div class="card"><div class="row" style="justify-content:space-between;margin-bottom:8px"><b>' + n + ' tables</b>' + (!wide ? '<button type="button" class="icon-btn" id="tbClose" aria-label="Fermer">✕</button>' : '') + '</div><input class="inp" id="tbSearch" placeholder="Rechercher un invité…" style="margin-bottom:8px"><div id="tbHits"></div><div class="tlist">' +
      P.tables.map((t, i) => { const o = t.seats.filter(Boolean).length; return '<div class="titem ' + (i === TB.a ? 'on' : '') + '"><button type="button" class="titem" style="padding:0;border:none" data-ta="' + i + '"><span class="num">' + (i + 1) + '</span><span class="meta">' + (t.kind === 'kids' ? '👶 ' : t.kind === 'honor' ? '👑 ' : '') + esc(label(t, i)) + '</span><span class="pill ' + (o === t.capacity ? 'ok' : '') + '">' + o + '/' + t.capacity + '</span></button><span class="mv"><button type="button" class="icon-btn" style="width:28px;height:22px;border:none" data-mv="' + i + '" data-d="-1" aria-label="Monter">▲</button><button type="button" class="icon-btn" style="width:28px;height:22px;border:none" data-mv="' + i + '" data-d="1" aria-label="Descendre">▼</button></span></div>'; }).join('') +
      '</div></div></aside><div><div class="tables-area ' + (TB.two ? 'two' : '') + '">' + tableCard(TB.a) + (TB.two ? tableCard(TB.b) : '') + '</div>' +
      '<div class="legend">' + P.categories.map(c => '<span><i style="background:' + c.color + '"></i>' + esc(tr(c.name, L1)) + '</span>').join('') + '</div>' +
      '<div class="hint">Touchez un invité puis un autre siège pour les échanger · appui long puis glisser · ‹ › ou glisser du doigt pour changer de table.</div>' +
      (TB.sel ? '<div class="selbar"><span class="lbl"><b>' + esc(selName || '') + '</b> sélectionné·e : touchez un siège pour échanger.</span><button type="button" class="btn sm" id="selMove">Déplacer vers…</button>' + (!TB.sel.u ? '<button type="button" class="btn sm danger" id="selOut">Retirer</button>' : '') + '<button type="button" class="btn sm ghost" id="selCancel">Annuler</button></div>' : '') +
      '</div></div></div>';
    bind();
  }

  // Répartition automatique : nombre de tables, places par table et tables particulières
  function auto() {
    const cfg = JSON.parse(JSON.stringify(P.config || { tables: 1, capacity: 8, specials: [] }));
    const people = Object.keys(P.persons).length;
    const KINDS = { std: 'Standard', honor: "Table d'honneur", kids: 'Table des enfants' };
    const sh = openSheet('<h3>Répartition automatique</h3><p class="muted" style="margin-top:0">' + people + ' personnes confirmées à placer.</p><div class="grid" id="cfgBox"></div>');
    const box = $('#cfgBox', sh);
    const sync = () => {
      cfg.tables = Math.max(0, +$('#cfgN', box).value || 0); cfg.capacity = Math.max(1, +$('#cfgC', box).value || 1);
      $$('[data-sp]', box).forEach(r => { const t = cfg.specials[+r.dataset.sp]; t.name = $('[data-f=name]', r).value; t.capacity = Math.max(1, +$('[data-f=capacity]', r).value || 1); t.kind = $('[data-f=kind]', r).value; });
    };
    const draw = () => {
      const special = cfg.specials.reduce((a, t) => a + (+t.capacity || 0) - (t.kind === 'kids' ? 1 : 0), 0);
      const total = cfg.tables * cfg.capacity + special;
      box.innerHTML = '<div class="row"><label class="f" style="flex:1 1 140px">Nombre de tables<input class="inp" type="number" min="0" max="200" id="cfgN" value="' + cfg.tables + '"></label><label class="f" style="flex:1 1 140px">Places par table<input class="inp" type="number" min="1" max="30" id="cfgC" value="' + cfg.capacity + '"></label></div>' +
        '<b>Tables particulières</b><p class="hint" style="margin:0">Elles s\'ajoutent aux tables ci-dessus, avec leur propre nombre de places (table d\'honneur, table des mariés, table des enfants…).</p>' +
        cfg.specials.map((t, i) => '<div class="row" data-sp="' + i + '" style="background:var(--surface-2);border:1px solid var(--line);border-radius:12px;padding:8px"><input class="inp" style="flex:2 1 150px" data-f="name" value="' + esc(t.name) + '" placeholder="Nom de la table"><input class="inp" style="flex:0 1 90px" type="number" min="1" max="30" data-f="capacity" value="' + t.capacity + '" aria-label="Places"><select class="inp" style="flex:1 1 150px" data-f="kind">' + Object.entries(KINDS).map(([k, l]) => '<option value="' + k + '" ' + (t.kind === k ? 'selected' : '') + '>' + l + '</option>').join('') + '</select><button type="button" class="icon-btn" data-rm="' + i + '" aria-label="Retirer">✕</button></div>').join('') +
        '<button type="button" class="btn sm" id="cfgAdd">+ Ajouter une table particulière</button>' +
        '<div class="' + (total < people ? 'warn-box' : 'card') + '" style="padding:10px 12px">' + (cfg.tables + cfg.specials.length) + ' tables · <b>' + total + ' places</b> pour ' + people + ' personnes' + (total < people ? ' : il manque ' + (people - total) + ' place(s), ces personnes resteront « non placées ».' : (total - people ? ' · ' + (total - people) + ' place(s) libre(s)' : '')) + (cfg.specials.some(t => t.kind === 'kids') ? '<br><span class="muted" style="font-size:12.5px">Une place de chaque table des enfants est réservée à la personne qui surveille.</span>' : '') + '</div>' +
        '<div class="row"><button type="button" class="btn gold" id="cfgGo">↻ Lancer la répartition</button><button type="button" class="btn ghost" id="cfgFit">Ajuster le nombre de tables</button></div>' +
        (P.tables.length ? '<p class="hint" style="margin:0">Le plan actuel sera remplacé. Tu pourras annuler juste après.</p>' : '');
      $$('input,select', box).forEach(i => i.onchange = () => { sync(); draw(); });
      $$('[data-rm]', box).forEach(b => b.onclick = () => { sync(); cfg.specials.splice(+b.dataset.rm, 1); draw(); });
      $('#cfgAdd', box).onclick = () => { sync(); cfg.specials.push({ name: '', capacity: cfg.capacity, kind: 'std' }); draw(); };
      $('#cfgFit', box).onclick = () => { sync(); const sp = cfg.specials.reduce((a, t) => a + (+t.capacity || 0) - (t.kind === 'kids' ? 1 : 0), 0); cfg.tables = Math.max(0, Math.ceil((people - sp) / cfg.capacity)); draw(); };
      $('#cfgGo', box).onclick = async () => {
        sync(); closeSheet();
        if (P.tables.length) snap();
        try { P = await api(BASE + 'tables/auto/', { method: 'POST', json: { config: cfg } }); }
        catch (e) { toast(e.message); return; }
        TB.sel = null; TB.a = 0; render();
        toast(P.last_unplaced ? 'Répartition faite : ' + P.last_unplaced + ' personne(s) sans place, ajoute des tables ou des places' : 'Répartition automatique terminée ✦', TB.undo.length ? undo : null);
      };
    };
    draw();
  }

  function bind() {
    const on = (id, fn) => { const el = $('#' + id); if (el) el.onclick = fn; };
    on('tbAuto', auto); on('tbUndo', undo);
    on('tbView', () => { TB.list = !TB.list; render(); });
    on('tbTwo', () => { TB.two = !TB.two; render(); });
    on('tbDrawer', () => { TB.drawer = true; render(); });
    on('tbClose', () => { TB.drawer = false; render(); });
    on('tbUn', () => openUnplaced());
    on('tbAdd', () => { snap(); P.tables.push({ name: '', capacity: 8, kind: 'std', shape: 'round', seats: Array(8).fill(null) }); TB.a = P.tables.length - 1; persist(); });
    $('#tbSide').onclick = e => { if (e.target.id === 'tbSide') { TB.drawer = false; render(); } };
    $$('[data-ta]').forEach(b => b.onclick = () => { TB.a = +b.dataset.ta; TB.drawer = false; render(); });
    $$('[data-mv]').forEach(b => b.onclick = () => { const i = +b.dataset.mv, j = i + +b.dataset.d; if (j < 0 || j >= P.tables.length) return; snap(); [P.tables[i], P.tables[j]] = [P.tables[j], P.tables[i]]; if (TB.a === i) TB.a = j; persist(); });
    $$('[data-nav]').forEach(b => b.onclick = () => nav(+b.dataset.nav, +b.dataset.d));
    $$('[data-edit]').forEach(b => b.onclick = () => editTable(+b.dataset.edit));
    $('#tbSearch').oninput = e => {
      const q = e.target.value.trim().toLowerCase(), out = $('#tbHits'); if (q.length < 2) { out.innerHTML = ''; return; }
      const hits = []; P.tables.forEach((t, ti) => t.seats.forEach((k, si) => { const p = P.persons[k]; if (p && p.name.toLowerCase().includes(q)) hits.push({ ti, si, n: p.name }); }));
      out.innerHTML = hits.slice(0, 8).map(h => '<button type="button" class="btn sm ghost" style="width:100%;justify-content:space-between;margin-bottom:4px" data-hit="' + h.ti + '" data-hs="' + h.si + '">' + esc(h.n) + ' <span class="pill">T' + (h.ti + 1) + '</span></button>').join('') || '<div class="muted" style="font-size:13px">Aucun résultat</div>';
      $$('[data-hit]', out).forEach(x => x.onclick = () => { TB.a = +x.dataset.hit; TB.sel = { t: +x.dataset.hit, s: +x.dataset.hs }; TB.drawer = false; render(); });
    };
    if (TB.sel) {
      on('selCancel', () => { TB.sel = null; render(); });
      on('selMove', openMoveSheet);
      on('selOut', () => { snap(); P.tables[TB.sel.t].seats[TB.sel.s] = null; TB.sel = null; persist(); toast('Invité retiré : il est dans « non placés »', undo); });
    }
    bindSeats();
  }
  const nav = (ti, d) => { const n = P.tables.length, nt = (ti + d + n) % n; if (TB.two && ti === TB.b) TB.b = nt; else TB.a = nt; render(); };

  function bindSeats() {
    $$('.seat').forEach(el => {
      el.addEventListener('contextmenu', e => e.preventDefault());
      el.addEventListener('click', () => {
        if (el._dragged) { el._dragged = false; return; }
        const ref = { t: +el.dataset.t, s: +el.dataset.s };
        if (TB.sel) { doSwap(TB.sel, ref); return; }
        if (!el.dataset.k) { if (P.tables[ref.t].seats[ref.s] === 'SUPERVISOR') return; openUnplaced(ref); return; }
        TB.sel = ref; try { navigator.vibrate && navigator.vibrate(12); } catch (e) { } render();
      });
      el.addEventListener('pointerdown', e => {
        if (!el.dataset.k) return;
        const sx = e.clientX, sy = e.clientY; let ghost = null;
        const timer = setTimeout(() => {
          try { navigator.vibrate && navigator.vibrate(18); } catch (_) { }
          ghost = el.cloneNode(true); ghost.classList.add('drag-ghost'); Object.assign(ghost.style, { left: sx + 'px', top: sy + 'px', width: el.offsetWidth + 'px', position: 'fixed' });
          document.body.appendChild(ghost); el.style.opacity = 0.35; try { el.setPointerCapture(e.pointerId); } catch (_) { }
        }, 350);
        const mv = ev => {
          if (!ghost) { if (Math.hypot(ev.clientX - sx, ev.clientY - sy) > 10) clearTimeout(timer); return; }
          ev.preventDefault(); ghost.style.left = ev.clientX + 'px'; ghost.style.top = ev.clientY + 'px';
          $$('.seat.target').forEach(s => s.classList.remove('target'));
          const u = document.elementFromPoint(ev.clientX, ev.clientY); const s = u && u.closest('.seat'); if (s && s !== el) s.classList.add('target');
        };
        const up = ev => {
          clearTimeout(timer); el.removeEventListener('pointermove', mv); el.removeEventListener('pointerup', up); el.removeEventListener('pointercancel', up);
          if (ghost) { ghost.remove(); el.style.opacity = ''; el._dragged = true; const u = document.elementFromPoint(ev.clientX, ev.clientY); const s = u && u.closest('.seat'); if (s && s !== el) doSwap({ t: +el.dataset.t, s: +el.dataset.s }, { t: +s.dataset.t, s: +s.dataset.s }); else render(); }
        };
        el.addEventListener('pointermove', mv); el.addEventListener('pointerup', up); el.addEventListener('pointercancel', up);
      });
    });
    $$('.tbl-card').forEach(card => {
      let sx = null, sy = null, onSeat = false;
      card.addEventListener('pointerdown', e => { sx = e.clientX; sy = e.clientY; onSeat = !!e.target.closest('.seat'); });
      card.addEventListener('pointerup', e => { if (sx === null) return; const dx = e.clientX - sx, dy = e.clientY - sy; if (!onSeat && Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) nav(+card.dataset.tc, dx < 0 ? 1 : -1); sx = null; });
    });
  }

  function openMoveSheet() {
    const sh = openSheet('<h3>Déplacer vers…</h3><input class="inp" id="mvQ" placeholder="Rechercher une table" style="margin-bottom:10px"><div class="menu-list" id="mvList"></div>');
    const draw = q => {
      $('#mvList', sh).innerHTML = P.tables.map((t, i) => ({ t, i, free: t.seats.filter(s => !s).length })).filter(x => !q || label(x.t, x.i).toLowerCase().includes(q) || String(x.i + 1) === q)
        .map(x => '<button type="button" data-mt="' + x.i + '"><span>' + (x.t.kind === 'kids' ? '👶 ' : x.t.kind === 'honor' ? '👑 ' : '') + esc(label(x.t, x.i)) + '</span><span class="pill ' + (x.free ? 'ok' : '') + '">' + (x.free ? x.free + ' place(s) libre(s)' : 'complète') + '</span></button>').join('');
      $$('[data-mt]', sh).forEach(b => b.onclick = () => { const ti = +b.dataset.mt, s = P.tables[ti].seats.indexOf(null); closeSheet(); if (s < 0) { TB.a = ti; render(); toast('Table complète : touchez un invité de cette table pour échanger'); return; } TB.a = ti; doSwap(TB.sel, { t: ti, s }); });
    };
    draw(''); $('#mvQ', sh).oninput = e => draw(e.target.value.trim().toLowerCase());
  }
  function openUnplaced(target) {
    const un = P.unplaced.map(k => P.persons[k]).filter(Boolean);
    const sh = openSheet('<h3>Invités non placés (' + un.length + ')</h3>' + (un.length ? '<p class="muted" style="margin-top:0">' + (target ? 'Touchez un invité pour l\'asseoir au siège ' + (target.s + 1) + '.' : 'Touchez un invité, puis un siège libre.') + '</p><div class="unplaced">' + un.map(p => '<button type="button" class="chip" data-up="' + esc(p.key) + '"><span style="width:9px;height:9px;border-radius:50%;background:' + ((catOf(p.cat) || {}).color || '#999') + '"></span>' + esc(p.name) + (p.type === 'enfant' ? ' · ' + p.age + ' ans' : '') + '</button>').join('') + '</div>' : '<p class="muted">Tout le monde a une place 🎉</p>'));
    $$('[data-up]', sh).forEach(b => b.onclick = () => { closeSheet(); if (target) doSwap({ u: b.dataset.up }, target); else { TB.sel = { u: b.dataset.up }; render(); } });
  }
  function editTable(ti) {
    const t = P.tables[ti];
    const sh = openSheet('<h3>' + esc(label(t, ti)) + '</h3><div class="grid"><label class="f">Nom (facultatif)<input class="inp" id="etN" value="' + esc(t.name) + '" placeholder="ex. Table d\'honneur, Famille Mbala"></label><div class="row"><label class="f" style="flex:1">Places<input class="inp" type="number" min="1" max="30" id="etC" value="' + t.capacity + '"></label><label class="f" style="flex:1">Forme<select class="inp" id="etS"><option value="round" ' + (t.shape === 'round' ? 'selected' : '') + '>Ronde</option><option value="rect" ' + (t.shape === 'rect' ? 'selected' : '') + '>Rectangulaire</option></select></label><label class="f" style="flex:1">Type<select class="inp" id="etK"><option value="std">Standard</option><option value="honor" ' + (t.kind === 'honor' ? 'selected' : '') + '>Table d\'honneur</option><option value="kids" ' + (t.kind === 'kids' ? 'selected' : '') + '>Table des enfants</option></select></label></div><div class="row"><button type="button" class="btn gold" id="etOk">Enregistrer</button><button type="button" class="btn danger" id="etDel">Supprimer la table</button></div><p class="hint">Si tu réduis les places ou supprimes la table, les invités concernés passent dans « non placés ».</p></div>');
    $('#etOk', sh).onclick = () => { snap(); const cap = Math.max(1, Math.min(30, +$('#etC', sh).value || t.capacity)); t.name = $('#etN', sh).value.trim(); t.shape = $('#etS', sh).value; t.kind = $('#etK', sh).value; t.seats = (t.seats.concat(Array(30).fill(null))).slice(0, cap); t.capacity = cap; closeSheet(); persist(); };
    $('#etDel', sh).onclick = () => { snap(); P.tables.splice(ti, 1); closeSheet(); persist(); toast('Table supprimée', undo); };
  }
  window.addEventListener('miel:event-changed', () => api(BASE + 'tables/').then(d => { P = d; render(); }));
  addEventListener('resize', () => { clearTimeout(window._rz); window._rz = setTimeout(() => P && render(), 200); });
  api(BASE + 'tables/').then(d => { P = d; render(); }).catch(e => toast(e.message));
})();
