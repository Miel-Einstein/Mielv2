/* Miel v2 — outils communs : API, toasts, panneaux, temps réel, moments forts. */
(function () {
  const M = (window.Miel = window.Miel || {});
  const $ = (M.$ = (s, r = document) => r.querySelector(s));
  const $$ = (M.$$ = (s, r = document) => [...r.querySelectorAll(s)]);
  M.esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  M.tr = (obj, lang) => (typeof obj === 'string' ? obj : (obj && (obj[lang] || obj.fr || Object.values(obj)[0])) || '');
  M.i18n = window.MIEL_I18N || {};
  M.t = k => M.i18n[k] || k;

  function cookie(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '=([^;]*)');
    return m ? decodeURIComponent(m[2]) : '';
  }
  /* Appel API JSON (ou FormData). Lève une erreur avec le message du serveur. */
  M.api = async function (url, opts = {}) {
    const o = { method: opts.method || 'GET', headers: { 'X-CSRFToken': cookie('csrftoken') }, credentials: 'same-origin' };
    if (opts.form) o.body = opts.form;
    else if (opts.json !== undefined) { o.body = JSON.stringify(opts.json); o.headers['Content-Type'] = 'application/json'; }
    const r = await fetch(url, o);
    let data = null;
    try { data = await r.json(); } catch (e) { /* réponse vide */ }
    if (!r.ok) throw Object.assign(new Error((data && data.error) || 'Erreur ' + r.status), { status: r.status, data });
    return data;
  };

  // ---------- toasts, panneaux
  let tt;
  M.toast = function (msg, undo) {
    let el = $('#toast');
    if (!el) { el = document.createElement('div'); el.id = 'toast'; el.className = 'toast'; document.body.appendChild(el); }
    el.innerHTML = M.esc(msg) + (undo ? ' <button type="button" id="tUndo">' + M.esc(M.t('undo') === 'undo' ? 'Annuler' : M.t('undo')) + '</button>' : '');
    el.classList.add('show');
    clearTimeout(tt);
    if (undo) $('#tUndo').onclick = () => { undo(); el.classList.remove('show'); };
    tt = setTimeout(() => el.classList.remove('show'), undo ? 5000 : 2600);
  };
  function layer(id, inner) {
    let bg = document.getElementById(id);
    if (!bg) {
      bg = document.createElement('div'); bg.id = id; bg.className = id === 'sheetBg' ? 'sheet-bg' : 'glass-bg';
      bg.innerHTML = '<div class="' + inner + '"></div>'; document.body.appendChild(bg);
      bg.addEventListener('click', e => { if (e.target === bg) bg.classList.remove('open'); });
    }
    return bg;
  }
  M.openSheet = html => { const bg = layer('sheetBg', 'sheet'); bg.firstChild.innerHTML = html; bg.classList.add('open'); return bg.firstChild; };
  M.closeSheet = () => { const bg = document.getElementById('sheetBg'); bg && bg.classList.remove('open'); };
  M.openGlass = html => { const bg = layer('glassBg', 'glass'); bg.firstChild.innerHTML = html; bg.classList.add('open'); return bg.firstChild; };
  M.closeGlass = () => { const bg = document.getElementById('glassBg'); bg && bg.classList.remove('open'); };

  // ---------- Recadrage d'une photo : point de cadrage (x, y en %) + zoom (1 à 3)
  // Même calcul que le serveur (object-fit: cover + object-position + zoom autour du point).
  M.focusStyle = f => 'object-position:' + f.x + '% ' + f.y + '%;transform-origin:' + f.x + '% ' + f.y + '%;transform:scale(' + f.z + ')';
  M.framer = function (src, focus, onSave, labels) {
    const T = Object.assign({ title: 'Cadrer la photo', hint: 'Fais glisser la photo au doigt ou à la souris. Zoome avec le curseur (ou la molette, ou deux doigts).', zoom: 'Zoom', center: 'Recentrer', save: 'Enregistrer', cancel: 'Annuler', card: 'Carte', site: 'Site (écran large)', band: 'Bandeau', up: 'Monter', down: 'Descendre', left: 'Gauche', right: 'Droite' }, labels || {});
    const f = Object.assign({ x: 50, y: 50, z: 1 }, focus || {});
    const sh = M.openSheet('<h3>' + T.title + '</h3><p class="muted" style="margin-top:0;font-size:13px">' + T.hint + '</p>' +
      '<div class="fr-wrap"><div class="fr-main" id="frMain" style="aspect-ratio:3/4"><img alt="" draggable="false" src="' + M.esc(src) + '"><span class="fr-grid" aria-hidden="true"></span></div>' +
      '<div class="fr-side"><div><small>' + T.site + '</small><div class="fr-mini" style="aspect-ratio:16/9"><img alt="" src="' + M.esc(src) + '"></div></div><div><small>' + T.band + '</small><div class="fr-mini" style="aspect-ratio:40/17"><img alt="" src="' + M.esc(src) + '"></div></div>' +
      '<div class="fr-pad"><button type="button" class="icon-btn" data-mv="0,-1" aria-label="' + T.up + '">↑</button><button type="button" class="icon-btn" data-mv="-1,0" aria-label="' + T.left + '">←</button><button type="button" class="icon-btn" data-mv="center" aria-label="' + T.center + '">◎</button><button type="button" class="icon-btn" data-mv="1,0" aria-label="' + T.right + '">→</button><button type="button" class="icon-btn" data-mv="0,1" aria-label="' + T.down + '">↓</button></div></div></div>' +
      '<label class="fr-zoom">' + T.zoom + ' <input type="range" id="frZ" min="1" max="3" step="0.01" value="' + f.z + '"><b id="frZv"></b></label>' +
      '<div class="row" style="margin-top:12px"><button type="button" class="btn gold" id="frOk">' + T.save + '</button><button type="button" class="btn" id="frC">' + T.center + '</button><button type="button" class="btn ghost" id="frNo">' + T.cancel + '</button></div>');
    const main = M.$('#frMain', sh), imgs = M.$$('img', sh), z = M.$('#frZ', sh);
    const paint = () => { imgs.forEach(i => i.style.cssText = M.focusStyle(f)); z.value = f.z; M.$('#frZv', sh).textContent = '×' + (+f.z).toFixed(2); };
    // taille de la fenêtre visible, en fraction de l'image, pour le cadre principal
    const win = () => { const im = imgs[0], A = (im.naturalWidth || 4) / (im.naturalHeight || 3), r = main.clientWidth / main.clientHeight;
      return A > r ? [r / A / f.z, 1 / f.z] : [1 / f.z, A / r / f.z]; };
    const shift = (dxFrac, dyFrac) => { const [cw, ch] = win();
      // la fenêtre visible commence à left = x·(1 − cw) ; on la déplace puis on recalcule x
      if (cw < 0.999) { const left = Math.min(1 - cw, Math.max(0, f.x / 100 * (1 - cw) + dxFrac * cw)); f.x = +(left / (1 - cw) * 100).toFixed(2); }
      if (ch < 0.999) { const top = Math.min(1 - ch, Math.max(0, f.y / 100 * (1 - ch) + dyFrac * ch)); f.y = +(top / (1 - ch) * 100).toFixed(2); }
      paint(); };
    // glisser (souris ou doigt) et pincer pour zoomer
    const pts = new Map(); let last = null, pinch = null;
    main.addEventListener('pointerdown', e => { main.setPointerCapture(e.pointerId); pts.set(e.pointerId, [e.clientX, e.clientY]); last = [e.clientX, e.clientY];
      if (pts.size === 2) { const [a, b] = [...pts.values()]; pinch = { d: Math.hypot(a[0] - b[0], a[1] - b[1]), z: f.z }; } });
    main.addEventListener('pointermove', e => { if (!pts.has(e.pointerId)) return; pts.set(e.pointerId, [e.clientX, e.clientY]);
      if (pts.size === 2 && pinch) { const [a, b] = [...pts.values()]; f.z = Math.min(3, Math.max(1, pinch.z * Math.hypot(a[0] - b[0], a[1] - b[1]) / pinch.d)); paint(); return; }
      if (pts.size === 1 && last) { const dx = e.clientX - last[0], dy = e.clientY - last[1]; last = [e.clientX, e.clientY]; shift(-dx / main.clientWidth, -dy / main.clientHeight); } });
    const up = e => { pts.delete(e.pointerId); if (pts.size < 2) pinch = null; last = pts.size ? [...pts.values()][0] : null; };
    main.addEventListener('pointerup', up); main.addEventListener('pointercancel', up);
    main.addEventListener('wheel', e => { e.preventDefault(); f.z = Math.min(3, Math.max(1, f.z * (e.deltaY < 0 ? 1.06 : 1 / 1.06))); paint(); }, { passive: false });
    z.oninput = () => { f.z = +z.value; paint(); };
    M.$$('[data-mv]', sh).forEach(b => b.onclick = () => { if (b.dataset.mv === 'center') { f.x = 50; f.y = 50; return paint(); } const [dx, dy] = b.dataset.mv.split(',').map(Number); shift(dx * 0.04, dy * 0.04); });
    M.$('#frC', sh).onclick = () => { f.x = 50; f.y = 50; f.z = 1; paint(); };
    M.$('#frNo', sh).onclick = M.closeSheet;
    M.$('#frOk', sh).onclick = async () => { try { await onSave({ x: f.x, y: f.y, z: +(+f.z).toFixed(3) }); M.closeSheet(); } catch (e) { M.toast(e.message); } };
    imgs[0].onload = paint; paint();
  };

  // ---------- effets
  M.confetti = function (n = 70, kind = 'confetti') {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const cols = ['#e9a83b', '#f3cf8a', '#d9897b', '#ff6b9d', '#93a68c', '#fff'];
    for (let i = 0; i < n; i++) {
      const c = document.createElement('div');
      c.className = 'confetti';
      if (kind === 'hearts') { c.textContent = '♥'; c.style.background = 'none'; c.style.color = cols[i % cols.length]; c.style.fontSize = '18px'; }
      else c.style.background = cols[i % cols.length];
      c.style.left = Math.random() * 100 + 'vw';
      c.style.animationDuration = 2 + Math.random() * 2.5 + 's';
      c.style.animationDelay = Math.random() * 0.6 + 's';
      document.body.appendChild(c);
      setTimeout(() => c.remove(), 5200);
    }
  };
  M.floatEmoji = function (e) {
    const d = document.createElement('div');
    d.className = 'float-emo'; d.textContent = e; d.style.left = 10 + Math.random() * 80 + 'vw';
    document.body.appendChild(d); setTimeout(() => d.remove(), 3300);
  };
  M.renderQRs = function (root = document) {
    $$('[data-qr]', root).forEach(el => {
      if (el.dataset.done) return; el.dataset.done = 1; el.innerHTML = '';
      if (typeof QRCode === 'undefined') { el.innerHTML = '<small style="color:#333;font-size:9px;word-break:break-all">' + M.esc(el.dataset.qr) + '</small>'; return; }
      try { new QRCode(el, { text: el.dataset.qr, width: 256, height: 256, colorDark: '#1a1310', colorLight: '#ffffff', correctLevel: QRCode.CorrectLevel.M }); } catch (e) { el.textContent = 'QR'; }
    });
  };

  // ---------- comptes à rebours [data-countdown="ms"]
  M.serverOffset = 0; // serveur - client, pour aligner tous les écrans
  M.now = () => Date.now() + M.serverOffset;
  M.tickCountdowns = function () {
    $$('[data-countdown]').forEach(el => {
      let d = +el.dataset.countdown - M.now(); if (d < 0) d = 0;
      const p = n => String(n).padStart(2, '0');
      const set = (u, v) => { const x = el.querySelector('[data-u="' + u + '"]'); if (x) x.textContent = p(v); };
      set('d', Math.floor(d / 864e5)); set('h', Math.floor((d % 864e5) / 36e5)); set('m', Math.floor((d % 36e5) / 6e4)); set('s', Math.floor((d % 6e4) / 1e3));
    });
  };

  // ---------- temps réel : WebSocket, sinon interrogation toutes les 3 s
  const handlers = {};
  M.on = (kind, fn) => ((handlers[kind] = handlers[kind] || []).push(fn));
  function emit(kind, payload) { (handlers[kind] || []).forEach(fn => { try { fn(payload); } catch (e) { console.error(e); } }); }
  M.connect = function (slug) {
    let ws, polling = null, lastMomentKey = null;
    const poll = async () => {
      try {
        const d = await M.api('/api/p/' + slug + '/live/');
        M.serverOffset = d.server_now - Date.now();
        const key = d.moment ? d.moment.id + ':' + d.moment.ends_at : null;
        if (key && key !== lastMomentKey) { lastMomentKey = key; emit('moment', d.moment); }
        emit('poll', d);
      } catch (e) { /* hors ligne : on réessaie */ }
    };
    const startPolling = () => { if (!polling) { poll(); polling = setInterval(poll, 3000); } };
    const open = () => {
      try { ws = new WebSocket((location.protocol === 'https:' ? 'wss://' : 'ws://') + location.host + '/ws/e/' + slug + '/'); }
      catch (e) { startPolling(); return; }
      let opened = false;
      ws.onopen = () => { opened = true; if (polling) { clearInterval(polling); polling = null; } poll(); };
      ws.onmessage = e => {
        const m = JSON.parse(e.data);
        if (m.server_now) M.serverOffset = m.server_now - Date.now();
        if (m.kind === 'moment' && m.payload) lastMomentKey = m.payload.id + ':' + m.payload.ends_at;
        emit(m.kind, m.payload);
      };
      ws.onclose = () => { startPolling(); setTimeout(open, opened ? 3000 : 15000); };
    };
    open();
    poll();
  };

  // ---------- moment fort : popup plein écran synchronisée
  let live = null, dismissed = null, revealed = null;
  M.showMoment = function (m) { live = m; };
  M.momentLoop = function (slug, lang) {
    let box = document.getElementById('moment');
    if (!box) { box = document.createElement('div'); box.id = 'moment'; box.className = 'moment'; document.body.appendChild(box); }
    M.on('moment', m => { live = m; });
    M.on('float', p => M.floatEmoji(p.emoji));
    setInterval(() => {
      M.tickCountdowns();
      const L = live;
      const key = L && L.id + ':' + L.ends_at;
      if (!L || dismissed === key || M.now() > L.ends_at + 14000) { box.classList.remove('open'); return; }
      const rem = Math.ceil((L.ends_at - M.now()) / 1000);
      box.classList.add('open');
      const title = M.esc(M.tr(L.title, lang));
      if (rem > 0) {
        box.dataset.state = 'cd';
        box.innerHTML = '<button class="btn sm close" type="button" aria-label="Fermer">✕</button><div class="mt">' + title + '</div><div class="num">' + rem + '</div><div class="muted">' + M.esc(M.t('getReady')) + '</div>';
      } else if (revealed !== key) {
        revealed = key; box.dataset.state = 'rev';
        const media = L.kind === 'reveal' && L.photo ? '<img src="' + M.esc(L.photo) + '" alt="' + title + '">' : '<div class="msgbig">' + M.esc(M.tr(L.message, lang) || M.tr(L.title, lang)) + '</div>';
        box.innerHTML = '<button class="btn sm close" type="button" aria-label="Fermer">✕</button><div class="mt" style="margin-bottom:16px">' + title + '</div><div class="reveal">' + media + '</div><div class="reacts" style="justify-content:center;margin-top:16px">' +
          ['❤️', '😂', '🥂', '🙏', '🎉'].map(e => '<button type="button" data-me="' + e + '" style="background:rgba(255,255,255,.1);color:#fff;border-color:rgba(255,255,255,.3);font-size:20px">' + e + '</button>').join('') + '</div>';
        M.confetti(110, L.effect === 'hearts' ? 'hearts' : 'confetti');
        $$('[data-me]', box).forEach(b => b.onclick = () => { M.floatEmoji(b.dataset.me); M.api('/api/p/' + slug + '/moment-react/', { method: 'POST', json: { emoji: b.dataset.me } }).catch(() => {}); });
      }
      const c = box.querySelector('.close'); if (c) c.onclick = () => { dismissed = key; box.classList.remove('open'); };
    }, 250);
  };
})();
