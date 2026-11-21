/* Miel — traduction de l'interface de l'organisateur.
 * Le texte source est en français. window.MIEL_UI (chargé avant ce fichier) contient les traductions
 * de la langue choisie. Chaque morceau de texte est traduit tel quel ; si la phrase entière n'est pas
 * connue, elle est coupée aux chiffres et aux signes « · : ? ! « » » et chaque morceau est traduit.
 * Les zones marquées translate="no" (noms, textes saisis par l'organisateur) ne sont pas touchées. */
(function () {
  const root = document.documentElement, lang = root.dataset.ui || 'fr', D = window.MIEL_UI;
  window.MielUI = { lang, locale: ({ fr: 'fr-FR', en: 'en-GB', it: 'it-IT', ln: 'fr-FR' })[lang] || 'fr-FR', t: s => s };
  if (lang === 'fr' || !D) { root.classList.remove('ui-pending'); return; }
  const SEP = /(\s*[·:]\s+|^[.,;]\s+|\s*[?!]+\s*|\s*[«»]\s*|\s+[+—–→]\s+|\d+(?:[.,:/h]\d+)*(?:\s?%)?)/;
  const SEP2 = /(\s+\(|\)(?=\s|$|[.,]))/; // parenthèses, seulement si la phrase n'est pas connue en entier
  const parts3 = s => s.match(/^(\s*)([\s\S]*?)(\s*)$/);
  function t(s) {
    if (!s || !/[A-Za-zÀ-ÿ]/.test(s)) return s;
    const m = parts3(s), core = m[2];
    let out = D[core];
    if (out == null) {
      const ps = core.split(SEP);
      if (ps.length < 2 && !SEP2.test(core)) { miss(core); return s; }
      let hit = false;
      const one = p => { const q = parts3(p); let v = D[q[2]];
        if (v == null && SEP2.test(q[2])) { const ps2 = q[2].split(SEP2); let h2 = false; v = ps2.map((x, j) => { if (j % 2) return x; const r = parts3(x); const w = D[r[2]]; if (w != null) { h2 = true; return r[1] + w + r[3]; } return x; }).join(''); if (!h2) v = null; }
        if (v != null) { hit = true; return q[1] + v + q[3]; } return p; };
      const tight = lang === 'en' || lang === 'it'; // pas d'espace avant « : ? ! » en anglais et en italien
      out = ps.map((p, i) => (i % 2 ? (tight ? p.replace(/^\s+([:?!])/, '$1') : p) : one(p))).join('');
      if (!hit) { miss(core); return s; }
      ps.forEach((p, i) => { if (!(i % 2)) { const q = parts3(p)[2]; if (q && /[A-Za-zÀ-ÿ]{2}/.test(q) && D[q] == null) miss(q); } });
    }
    return m[1] + out + m[3];
  }
  window.MielUI.t = t;
  // textes sans traduction (pour compléter le catalogue) : MielUI.missing
  const MISSING = window.MielUI.missing = new Set();
  function miss(x) { if (/[A-Za-zÀ-ÿ]{3}/.test(x)) MISSING.add(x); }
  const ORIG = new WeakMap(), ATTRS = ['placeholder', 'title', 'aria-label'];
  const skip = el => !el || el.closest('script,style,textarea,[translate="no"],.notranslate,[contenteditable="true"]');
  function textNode(n) {
    if (skip(n.parentElement)) return;
    const cur = n.nodeValue, o = ORIG.get(n);
    if (o && o.out === cur) return;            // déjà traduit par nous
    const out = t(cur);
    ORIG.set(n, { src: cur, out });
    if (out !== cur) n.nodeValue = out;
  }
  function attrs(el) {
    if (skip(el)) return;
    ATTRS.forEach(a => { const v = el.getAttribute(a); if (!v) return; const k = '__ui_' + a; if (el[k] === v) return; const out = t(v); el[k] = out; if (out !== v) el.setAttribute(a, out); });
    if (el.tagName === 'INPUT' && (el.type === 'button' || el.type === 'submit') && el.value) { const out = t(el.value); if (out !== el.value) el.value = out; }
  }
  function walk(node) {
    if (node.nodeType === 3) return textNode(node);
    if (node.nodeType !== 1 || skip(node)) return;
    attrs(node);
    const it = document.createTreeWalker(node, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let n; while ((n = it.nextNode())) n.nodeType === 3 ? textNode(n) : attrs(n);
  }
  function start() {
    walk(document.body);
    document.title = t(document.title);
    root.classList.remove('ui-pending');
    new MutationObserver(ms => ms.forEach(m => {
      if (m.type === 'characterData') textNode(m.target);
      else if (m.type === 'attributes') attrs(m.target);
      else m.addedNodes.forEach(walk);
    })).observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }
  if (document.body) start(); else document.addEventListener('DOMContentLoaded', start);
  setTimeout(() => root.classList.remove('ui-pending'), 1500);
})();
