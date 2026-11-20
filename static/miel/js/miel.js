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
