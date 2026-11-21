/* Assistant organisateur : messages fixes, étape par étape.
   Chaque réponse est enregistrée tout de suite via l'API, et la progression
   (étape, historique, pause) est sauvegardée pour reprendre exactement ici. */
(function () {
  const { $, $$, esc, api, toast, openSheet, closeSheet, tr } = Miel;
  const EV = window.EVENT;
  const BASE = '/api/e/' + EV.slug + '/';
  const UI_LOCALE = (window.MielUI && window.MielUI.locale) || 'fr-FR';
  const LANGS = { fr: ['🇫🇷', 'Français'], en: ['🇬🇧', 'English'], it: ['🇮🇹', 'Italiano'], ln: ['🇨🇬', 'Lingala'] };
  const TYPES = [['mariage', '💍', 'Mariage'], ['anniversaire', '🎂', 'Anniversaire'], ['bapteme', '🕊️', 'Baptême'], ['diner', '🍽️', 'Dîner au restaurant'], ['entreprise', '🏢', "Événement d'entreprise"]];
  const SERVICES = [['carte', '💌', "Carte d'invitation & RSVP", 1], ['cadeaux', '🎁', 'Liste de cadeaux'], ['tables', '🪑', 'Plan de table'], ['alerter', '⏰', 'Alerter (rappels & budget)'], ['mur', '💬', 'Mur des vœux & photos'], ['moments', '✨', 'Moments forts'], ['site', '🌐', 'Site du mariage', 0, 1]];
  let S = { step: 'accueil', log: [], paused: false };
  let share = {};
  const has = s => EV.services.includes(s);
  const tile = (icon, label, attrs, on, disabled) => '<button type="button" class="opt' + (on ? ' on' : '') + '" ' + attrs + (disabled ? ' disabled' : '') + '><span class="em">' + icon + '</span><span>' + label + '</span></button>';
  let dirty = false;
  const L1 = () => EV.languages[0];

  // ---------- champs traduits : un champ par langue de l'événement
  function langInputs(id, obj, ph, tag = 'input') {
    return '<div class="grid" style="gap:6px">' + EV.languages.map(l =>
      '<div class="row" style="flex-wrap:nowrap"><span title="' + LANGS[l][1] + '" style="width:26px">' + LANGS[l][0] + '</span>' +
      (tag === 'textarea'
        ? '<textarea class="inp" rows="2" data-li="' + id + '" data-l="' + l + '" placeholder="' + esc(ph + ' (' + LANGS[l][1] + ')') + '">' + esc((obj || {})[l] || '') + '</textarea>'
        : '<input class="inp" data-li="' + id + '" data-l="' + l + '" value="' + esc((obj || {})[l] || '') + '" placeholder="' + esc(ph + ' (' + LANGS[l][1] + ')') + '">') +
      '</div>').join('') + '</div>';
  }
  function readLang(id, root = document) {
    const o = {};
    $$('[data-li="' + id + '"]', root).forEach(i => { if (i.value.trim()) o[i.dataset.l] = i.value.trim(); });
    return o;
  }
  const missingLangs = o => EV.languages.filter(l => !o[l]);

  async function patch(data) { Object.assign(EV, await api(BASE, { method: 'PATCH', json: data })); dirty = true; }

  // ---------- étapes
  const STEPS = [
    { id: 'accueil', label: 'Accueil', ask: () => "Bonjour 👋 Je suis <b>Miel</b>, ton assistant. Je vais t'aider à préparer ton événement, étape par étape.<br><br>Appuie sur <b>Pause</b> quand tu veux : je reprendrai exactement ici. Le bouton <b>Menu</b> te permet de revenir sur n'importe quelle partie.",
      ui: b => { b.innerHTML = '<div class="row center"><button class="btn gold" data-a="go">C\'est parti ✨</button></div>'; b.querySelector('[data-a=go]').onclick = () => answer("C'est parti !"); } },
    { id: 'langue', label: 'Langue de Miel', ask: () => "Je te parle en quelle langue ? <i>Tu pourras la changer à tout moment dans 🎨 Préférences.</i>",
      ui: b => { const cur = document.documentElement.dataset.ui || 'fr';
        b.innerHTML = '<div class="tiles-row" translate="no">' + [['fr', '🇫🇷', 'Français'], ['en', '🇬🇧', 'English'], ['it', '🇮🇹', 'Italiano'], ['ln', '🇨🇬', 'Lingála']].map(([k, f, n]) => tile(f, n, 'data-ul="' + k + '"', cur === k)).join('') + '</div>';
        $$('[data-ul]', b).forEach(x => x.onclick = async () => { const k = x.dataset.ul;
          if (k === cur) return answer(x.textContent.trim());
          try { await api('/api/me/ui-lang/', { method: 'POST', json: { lang: k } }); } catch (e) { return toast(e.message); }
          await answer(x.textContent.trim()); await save();   // l'étape suivante est enregistrée avant de recharger la page dans la nouvelle langue
          const u = new URL(location.href); u.searchParams.set('bot', '1'); location.href = u.toString(); }); } },
    { id: 'type', label: "Type d'événement", ask: () => "Quel type d'événement prépares-tu ?",
      ui: b => { b.innerHTML = '<div class="tiles-row">' + TYPES.map(([id, ic, l]) => tile(ic, l, 'data-id="' + id + '"', EV.type === id)).join('') + '</div>';
        $$('.opt', b).forEach(c => c.onclick = () => { const ty = TYPES.find(x => x[0] === c.dataset.id); answer(ty[1] + ' ' + ty[2], () => patch({ type: ty[0] })); }); } },
    { id: 'langues', label: 'Langues', ask: () => "Dans quelles langues tes invités vont-ils lire l'invitation ? Tu peux en choisir plusieurs. Pour chaque texte personnalisé, je te demanderai la traduction.",
      ui: b => { const sel = new Set(EV.languages);
        b.innerHTML = '<div class="tiles-row">' + Object.entries(LANGS).map(([k, l]) => tile(l[0], l[1], 'data-k="' + k + '"', sel.has(k))).join('') + '</div><div class="row center" style="margin-top:14px"><button class="btn gold" data-a="ok">Valider</button></div>';
        $$('.opt', b).forEach(c => c.onclick = () => { sel.has(c.dataset.k) ? sel.delete(c.dataset.k) : sel.add(c.dataset.k); c.classList.toggle('on'); });
        b.querySelector('[data-a=ok]').onclick = () => { if (!sel.size) return toast('Choisis au moins une langue'); const ls = Object.keys(LANGS).filter(k => sel.has(k)); answer(ls.map(k => LANGS[k][0] + ' ' + LANGS[k][1]).join(', '), () => patch({ languages: ls })); }; } },
    { id: 'titre', label: 'Titre (traduit)', ask: () => "Comment s'appelle ton événement ? Écris le <b>titre</b> puis la petite <b>phrase d'accroche</b> dans chaque langue.",
      ui: b => { b.innerHTML = '<div class="grid"><b>Titre</b>' + langInputs('title', EV.title, 'Titre') + '<b>Accroche</b>' + langInputs('subtitle', EV.subtitle, 'ex. Nous nous marions') + '<div><button class="btn gold" data-a="ok">Valider</button></div></div>';
        b.querySelector('[data-a=ok]').onclick = () => { const ti = readLang('title', b), su = readLang('subtitle', b); const miss = missingLangs(ti); if (miss.length) return toast('Il manque le titre en ' + miss.map(l => LANGS[l][1]).join(', ')); answer(EV.languages.map(l => LANGS[l][0] + ' ' + ti[l]).join(' · '), () => patch({ title: ti, subtitle: su })); }; } },
    { id: 'date', label: 'Date & lieux', ask: () => "Quand a lieu ton événement ? Ajoute ensuite les <b>lieux de la journée</b>, dans l'ordre : nom, heures, adresse et infos pratiques. Les coordonnées GPS servent à la carte « Y aller » (clic droit sur Google Maps → copier les coordonnées).",
      ui: b => {
        let vs = EV.venues.length ? JSON.parse(JSON.stringify(EV.venues)) : [{ name: {}, start: EV.time, end: '', address: '' }];
        const draw = () => {
          b.innerHTML = '<div class="grid"><div class="row"><label class="f" style="flex:1 1 150px">Date<input class="inp" type="date" id="bd-date" value="' + (EV.date || '') + '"></label><label class="f" style="flex:1 1 110px">Heure de début<input class="inp" type="time" id="bd-time" value="' + (EV.time || '') + '"></label></div>' +
            vs.map((v, i) => '<div class="card" style="padding:10px" data-v="' + i + '"><div class="row" style="justify-content:space-between"><b>Lieu ' + (i + 1) + '</b><button class="icon-btn" data-x="' + i + '" aria-label="Retirer">✕</button></div>' + langInputs('vn' + i, v.name, 'Nom du lieu') +
              '<div class="row" style="margin-top:6px"><input class="inp" style="flex:1 1 90px" type="time" data-f="start" value="' + (v.start || '') + '"><input class="inp" style="flex:1 1 90px" type="time" data-f="end" value="' + (v.end || '') + '"><input class="inp" style="flex:3 1 200px" data-f="address" value="' + esc(v.address || '') + '" placeholder="Adresse"></div>' +
              '<div class="row" style="margin-top:6px"><input class="inp" style="flex:1 1 110px" data-f="lat" value="' + (v.lat ?? '') + '" placeholder="Latitude"><input class="inp" style="flex:1 1 110px" data-f="lng" value="' + (v.lng ?? '') + '" placeholder="Longitude"></div>' +
              '<details style="margin-top:6px"><summary class="muted" style="cursor:pointer">Infos pratiques (parking, entrée, repère, contact)</summary><div class="grid" style="gap:6px;margin-top:6px"><input class="inp" data-f="parking" value="' + esc(v.parking || '') + '" placeholder="🅿️ Parking"><input class="inp" data-f="entrance" value="' + esc(v.entrance || '') + '" placeholder="🚪 Entrée"><input class="inp" data-f="landmark" value="' + esc(v.landmark || '') + '" placeholder="📍 Repère, ex. portail bleu"><input class="inp" data-f="contact" value="' + esc(v.contact || '') + '" placeholder="📞 Contact sur place"></div></details></div>').join('') +
            '<div class="row"><button class="btn sm" data-a="add">+ Ajouter un lieu</button><button class="btn gold" data-a="ok">Valider</button></div></div>';
          $$('[data-x]', b).forEach(x => x.onclick = () => { sync(); vs.splice(+x.dataset.x, 1); draw(); });
          b.querySelector('[data-a=add]').onclick = () => { sync(); vs.push({ name: {} }); draw(); };
          b.querySelector('[data-a=ok]').onclick = async () => {
            sync(); const date = $('#bd-date').value; if (!date) return toast('Indique la date');
            if (vs.some(v => !Object.keys(v.name).length)) return toast('Donne un nom à chaque lieu');
            answer(new Date(date + 'T12:00').toLocaleDateString(UI_LOCALE, { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' }) + ' · ' + vs.length + ' lieu(x)', async () => {
              await patch({ date, time: $('#bd-time').value }); EV.venues = await api(BASE + 'venues/', { method: 'PUT', json: vs });
            });
          };
        };
        const sync = () => $$('[data-v]', b).forEach(card => { const v = vs[+card.dataset.v]; v.name = readLang('vn' + card.dataset.v, card); $$('[data-f]', card).forEach(i => { v[i.dataset.f] = i.value; }); });
        draw();
      } },
    { id: 'photos', label: 'Photos', ask: () => "Ajoute une ou deux belles photos : elles servent à la carte, au carrousel du site et au plan de table. Ensuite, touche <b>✂️ Cadrer</b> pour choisir ce qui reste au centre et zoomer.",
      ui: b => { const draw = () => { b.innerHTML = '<div class="ph-row">' + ['cover_image', 'cover_image_2'].map((f, i) => '<div class="ph-slot">' + (EV[f] ? '<div class="ph-thumb"><img alt="" src="' + esc(EV[f]) + '" style="' + Miel.focusStyle(Object.assign({ x: 50, y: 50, z: 1 }, (EV.cover_focus || {})[f])) + '"></div>' : '<div class="ph-thumb empty">📷</div>') +
            '<label class="btn sm">' + (EV[f] ? 'Changer' : 'Photo ' + (i + 1)) + '<input type="file" accept="image/*" hidden data-f="' + f + '"></label>' + (EV[f] ? '<button type="button" class="btn sm gold" data-fr="' + f + '">✂️ Cadrer</button>' : '') + '</div>').join('') + '</div><div class="row center" style="margin-top:12px"><button class="btn gold" data-a="ok">Continuer</button></div>';
          $$('[data-f]', b).forEach(inp => inp.onchange = async () => { const fd = new FormData(); fd.append('field', inp.dataset.f); fd.append('file', inp.files[0]); try { const r = await api(BASE + 'upload/', { method: 'POST', form: fd }); EV[inp.dataset.f] = r.url; EV.cover_focus = Object.assign({}, EV.cover_focus); delete EV.cover_focus[inp.dataset.f]; dirty = true; toast('Photo enregistrée ✦'); draw(); } catch (e) { toast(e.message); } });
          $$('[data-fr]', b).forEach(x => x.onclick = () => { const f = x.dataset.fr; Miel.framer(EV[f], (EV.cover_focus || {})[f], async focus => { const r = await api(BASE, { method: 'PATCH', json: { cover_focus: { [f]: focus } } }); EV.cover_focus = r.cover_focus; dirty = true; toast('Cadrage enregistré ✦'); draw(); }); });
          b.querySelector('[data-a=ok]').onclick = () => answer(EV.cover_image ? 'Photo ajoutée' : 'Plus tard'); };
        draw(); } },
    { id: 'services', label: 'Services', ask: () => "Quels services veux-tu utiliser ? Tu pourras en ajouter plus tard.",
      ui: b => { const sel = new Set(EV.services); const wed = EV.type === 'mariage';
        b.innerHTML = '<div class="tiles-row">' + SERVICES.map(([id, ic, l, req, wo]) => tile(ic, l + (wo && !wed ? ' (mariages)' : ''), 'data-id="' + id + '"', sel.has(id), req || (wo && !wed))).join('') + '</div><div class="row center" style="margin-top:14px"><button class="btn gold" data-a="ok">Valider</button></div>';
        $$('.opt:not([disabled])', b).forEach(c => c.onclick = () => { sel.has(c.dataset.id) ? sel.delete(c.dataset.id) : sel.add(c.dataset.id); c.classList.toggle('on'); });
        b.querySelector('[data-a=ok]').onclick = () => { const arr = SERVICES.map(s => s[0]).filter(id => sel.has(id) || id === 'carte'); answer(arr.map(id => SERVICES.find(s => s[0] === id)[1]).join(' ') + ' ' + arr.length + ' services', () => patch({ services: arr })); }; } },
    { id: 'carte', label: "Carte d'invitation", ask: () => "Choisis le modèle de ta carte d'invitation. Appuie sur <b>Voir la carte</b> pour l'aperçu.",
      ui: b => { const PHOTO = ['luxe', 'scandinave'];
        const draw = () => { b.innerHTML = '<div class="tiles-row">' + [['botanique', '🌿', 'Botanique'], ['moderne', '🖤', 'Moderne'], ['rose', '🌸', 'Rose romantique'], ['luxe', '✨', 'Luxe doré'], ['scandinave', '🤍', 'Minimaliste scandinave']].map(([k, ic, l]) => tile(ic, l, 'data-k="' + k + '"', EV.card_template === k)).join('') + '</div>' +
            (PHOTO.includes(EV.card_template) ? '<div class="grid" style="gap:8px;margin-top:12px;text-align:left"><div class="hint">Ta photo de couverture remplit toute la carte.' + (EV.cover_image ? ' <button type="button" class="btn sm" data-a="fr">✂️ Cadrer la photo</button>' : ' Ajoute-la à l\'étape « Photos ».') + '</div>' +
              '<div><b style="font-size:13px">Message de la carte (facultatif)</b>' + langInputs('cm', EV.card_message || {}, 'ex. Avec joie, nous célébrons votre présence à nos côtés ! 🥂') + '</div>' +
              '<div><b style="font-size:13px">Thème ou dress code (facultatif)</b>' + langInputs('ct', EV.card_theme || {}, 'ex. Thème : blanc et doré') + '</div></div>' : '') +
            '<div class="row center" style="margin-top:14px"><button class="btn gold" data-a="ok">Garder ce modèle</button><button class="btn ghost sm" data-a="pv">👁 Voir la carte</button></div>';
          $$('.opt', b).forEach(c => c.onclick = async () => { await patch({ card_template: c.dataset.k }); draw(); });
          const fr = b.querySelector('[data-a=fr]'); if (fr) fr.onclick = () => Miel.framer(EV.cover_image, (EV.cover_focus || {}).cover_image, async focus => { const r = await api(BASE, { method: 'PATCH', json: { cover_focus: { cover_image: focus } } }); EV.cover_focus = r.cover_focus; dirty = true; toast('Cadrage enregistré ✦'); });
          const saveTexts = async () => { if (PHOTO.includes(EV.card_template)) await patch({ card_message: readLang('cm', b), card_theme: readLang('ct', b) }); };
          b.querySelector('[data-a=pv]').onclick = async () => { await saveTexts(); togglePreview(true); };
          b.querySelector('[data-a=ok]').onclick = async () => { await saveTexts(); answer('Modèle « ' + ({ botanique: 'Botanique', moderne: 'Moderne', rose: 'Rose romantique', luxe: 'Luxe doré', scandinave: 'Minimaliste scandinave' })[EV.card_template] + ' »'); }; };
        draw(); } },
    { id: 'categories', label: "Catégories d'invités", ask: () => "Voici les <b>catégories d'invités</b>. Chaque invité en choisira <b>une seule</b> dans le RSVP. L'ordre sert de priorité pour le plan de table, et 👑 réserve la catégorie à la table d'honneur (elle n'apparaît pas dans le RSVP).",
      ui: b => { let cats = JSON.parse(JSON.stringify(EV.categories));
        const draw = () => { b.innerHTML = '<div class="list-edit">' + cats.map((c, i) => '<div class="it" style="flex-wrap:wrap" data-c="' + i + '"><span style="width:10px;height:10px;border-radius:50%;background:' + c.color + ';flex-shrink:0"></span><div style="flex:1 1 220px">' + langInputs('cat' + i, c.name, 'Catégorie') + '</div><button class="icon-btn ' + (c.is_honor ? 'on' : '') + '" data-h="' + i + '" title="Table d\'honneur">👑</button><button class="icon-btn" data-u="' + i + '" title="Monter">▲</button><button class="icon-btn" data-x="' + i + '" title="Retirer">✕</button></div>').join('') + '</div><div class="row" style="margin-top:8px"><button class="btn sm" data-a="add">+ Ajouter une catégorie</button><button class="btn gold" data-a="ok">Valider</button></div>';
          const sync = () => $$('[data-c]', b).forEach(el => { cats[+el.dataset.c].name = readLang('cat' + el.dataset.c, el); });
          $$('[data-h]', b).forEach(x => x.onclick = () => { sync(); cats[+x.dataset.h].is_honor = !cats[+x.dataset.h].is_honor; draw(); });
          $$('[data-u]', b).forEach(x => x.onclick = () => { sync(); const i = +x.dataset.u; if (i > 0) [cats[i - 1], cats[i]] = [cats[i], cats[i - 1]]; draw(); });
          $$('[data-x]', b).forEach(x => x.onclick = () => { sync(); if (cats.length > 1) cats.splice(+x.dataset.x, 1); draw(); });
          b.querySelector('[data-a=add]').onclick = () => { sync(); cats.push({ name: {}, is_honor: false }); draw(); };
          b.querySelector('[data-a=ok]').onclick = () => { sync(); const bad = cats.find(c => missingLangs(c.name).length); if (bad) return toast('Chaque catégorie doit être traduite dans toutes les langues'); answer(cats.map(c => (c.is_honor ? '👑 ' : '') + tr(c.name, L1())).join(' › '), async () => { EV.categories = await api(BASE + 'categories/', { method: 'PUT', json: cats }); }); }; };
        draw(); } },
    { id: 'enfants', label: 'Enfants', ask: () => "Parlons des enfants 👶 Tout se règle ici, et le RSVP s'adaptera tout seul.",
      ui: b => { const k = { kids_invited: EV.kids_invited, kids_table: EV.kids_table, baby_chair: EV.baby_chair, age_with_parents: EV.age_with_parents, age_kids_max: EV.age_kids_max, supervisor_name: EV.supervisor_name };
        const draw = () => { b.innerHTML = '<div class="grid"><div class="chips"><button class="chip ' + (k.kids_invited ? 'on' : '') + '" data-t="kids_invited">Les enfants sont invités</button>' + (k.kids_invited ? '<button class="chip ' + (k.kids_table ? 'on' : '') + '" data-t="kids_table">Table des enfants</button><button class="chip ' + (k.baby_chair ? 'on' : '') + '" data-t="baby_chair">Les tout-petits comptent pour une chaise</button>' : '') + '</div>' +
            (k.kids_invited ? '<div class="row"><label class="f" style="flex:1 1 180px">Avec les parents jusqu\'à (âge)<input class="inp" type="number" min="1" max="17" id="k-wp" value="' + k.age_with_parents + '"></label>' + (k.kids_table ? '<label class="f" style="flex:1 1 180px">Table des enfants jusqu\'à (âge)<input class="inp" type="number" min="2" max="17" id="k-km" value="' + k.age_kids_max + '"></label>' : '') + '</div><div class="hint">Moins de <b>' + k.age_with_parents + ' ans</b> : avec les parents' + (k.kids_table ? ' · de ' + k.age_with_parents + ' à ' + k.age_kids_max + ' ans : table des enfants · plus de ' + k.age_kids_max + ' ans : place adulte' : '') + '.</div>' : '') +
            (k.kids_invited && k.kids_table ? '<div class="warn-box">⚠️ Une table des enfants demande <b>au moins une personne pour les surveiller</b>. Je lui réserve une place à leur table et j\'ajoute un rappel dans l\'Alerter tant qu\'elle n\'est pas désignée.<input class="inp" style="margin-top:8px" id="k-sup" value="' + esc(k.supervisor_name) + '" placeholder="Nom de la personne qui surveille"></div>' : '') +
            '<div><button class="btn gold" data-a="ok">Valider</button></div></div>';
          const rd = () => { if ($('#k-wp')) k.age_with_parents = +$('#k-wp').value || 4; if ($('#k-km')) k.age_kids_max = Math.max(k.age_with_parents, +$('#k-km').value || 12); if ($('#k-sup')) k.supervisor_name = $('#k-sup').value; };
          $$('[data-t]', b).forEach(c => c.onclick = () => { rd(); k[c.dataset.t] = !k[c.dataset.t]; draw(); });
          $$('input', b).forEach(i => i.onchange = () => { rd(); draw(); });
          b.querySelector('[data-a=ok]').onclick = () => { rd(); answer(k.kids_invited ? 'Enfants invités' + (k.kids_table ? ', table des enfants (surveillance : ' + (k.supervisor_name || 'à trouver') + ')' : '') : "Pas d'enfants", () => patch(k)); }; };
        draw(); } },
    { id: 'langtable', label: 'Langues à table', show: () => has('tables'), ask: () => "Veux-tu que le RSVP demande aux invités <b>dans quelles langues ils aiment converser</b> ? Je m'en sers pour asseoir ensemble des personnes qui se comprennent. S'ils ne choisissent rien, je garde leur langue de navigation.",
      ui: b => { b.innerHTML = '<div class="tiles-row">' + tile('💬', 'Oui, poser la question', 'data-v="1"', EV.ask_languages) + tile('🙅', 'Non, inutile', 'data-v="0"', !EV.ask_languages) + '</div>'; $$('.opt', b).forEach(c => c.onclick = () => answer(c.textContent.trim(), () => patch({ ask_languages: c.dataset.v === '1' }))); } },
    { id: 'site', label: 'Modèle du site', show: () => has('site') && EV.type === 'mariage', ask: () => "Choisis le style de ton <b>site de mariage</b>. Tu peux changer de modèle à tout moment : tes textes et tes photos restent les mêmes.",
      ui: b => { const T = [['A', 'Botanical Editorial', 'Crème, sauge, vert forêt et terracotta. Style magazine.', ['#fbf8f1', '#8a9a7b', '#2a3528', '#c87a55']], ['B', 'Modern Romance', 'Bleu nuit, vieux rose et or rosé. Style romantique.', ['#faf7f2', '#1a2a3a', '#d4a5a5', '#e8c4b8']], ['C', 'Luxe Romantique', 'Ivoire, champagne, bordeaux et or ancien. Galerie photos.', ['#faf6ef', '#e7d4ad', '#6e1f2a', '#c9a66b']]];
        b.innerHTML = '<div class="tiles-row">' + T.map(([k, n, d, c]) => '<button type="button" class="opt site-tile ' + (EV.site_template === k ? 'on' : '') + '" data-k="' + k + '"><span class="sw">' + c.map(x => '<i style="background:' + x + '"></i>').join('') + '</span><b>' + n + '</b><small>' + d + '</small></button>').join('') + '</div><div class="row center" style="margin-top:14px">' + T.map(([k, n]) => '<a class="btn ghost sm" target="_blank" rel="noopener" href="' + EV.urls.site + '?tpl=' + k + '">👁 Voir « ' + n + ' » ↗</a>').join('') + '</div><div class="row center" style="margin-top:10px"><button class="btn gold" data-a="ok">Garder ce modèle</button></div>';
        $$('.opt', b).forEach(c => c.onclick = async () => { await patch({ site_template: c.dataset.k }); $$('.opt', b).forEach(x => x.classList.toggle('on', x === c)); });
        b.querySelector('[data-a=ok]').onclick = () => answer('Site « ' + ({ A: 'Botanical Editorial', B: 'Modern Romance', C: 'Luxe Romantique' })[EV.site_template] + ' »'); } },
    { id: 'fond', label: 'Fond du site', show: () => has('site') && EV.type === 'mariage', ask: () => "Veux-tu changer le <b>fond</b> de ton site ? Garde celui du modèle, ou choisis une couleur, un dégradé ou une photo. Le voile rend le texte plus lisible.",
      ui: b => { const bg = Object.assign({ mode: 'default', c1: '#faf6ef', c2: '#e7d4ad', veil: 0, tone: 'light', scope: 'site' }, EV.site_bg || {});
        const PRESETS = [['#faf6ef', 'Ivoire'], ['#efe1c6', 'Champagne'], ['#f3dede', 'Rose poudré'], ['#dfe6d6', 'Sauge'], ['#e6e1f0', 'Lavande'], ['#1a2a3a', 'Bleu nuit'], ['#4a1820', 'Bordeaux']];
        const lum = h => { const n = parseInt(h.slice(1), 16), r = n >> 16 & 255, g = n >> 8 & 255, bl = n & 255; return (0.299 * r + 0.587 * g + 0.114 * bl) / 255; };
        const css = () => { const a = bg.veil / 100, v = bg.tone === 'dark' ? 'rgba(0,0,0,' + a + ')' : 'rgba(255,255,255,' + a + ')', veil = 'linear-gradient(' + v + ',' + v + ')';
          if (bg.mode === 'color') return veil + ',' + bg.c1; if (bg.mode === 'gradient') return veil + ',linear-gradient(160deg,' + bg.c1 + ',' + bg.c2 + ')';
          if (bg.mode === 'image' && EV.site_bg_image) return veil + ',url("' + EV.site_bg_image + '") center/cover,' + bg.c1; return ''; };
        const draw = () => {
          const lightTpl = EV.site_template !== 'B', dark = bg.mode !== 'default' && bg.mode !== 'image' && lum(bg.c1) < .45 && !(bg.tone === 'light' && bg.veil >= 50);
          b.innerHTML = '<div class="tiles-row">' + [['default', '🖼️', 'Celui du modèle'], ['color', '🎨', 'Couleur'], ['gradient', '🌅', 'Dégradé'], ['image', '📷', 'Photo']].map(([k, ic, l]) => tile(ic, l, 'data-m="' + k + '"', bg.mode === k)).join('') + '</div>' +
            (bg.mode === 'default' ? '' :
              (bg.mode !== 'image' ? '<div class="sw-row">' + PRESETS.map(([c, n]) => '<button type="button" class="sw' + (bg.c1 === c ? ' on' : '') + '" data-c="' + c + '" title="' + n + '" style="background:' + c + '"></button>').join('') + '</div>' +
                '<div class="row center" style="margin-top:8px"><label class="f">Couleur ' + (bg.mode === 'gradient' ? '1' : '') + '<input type="color" class="inp" id="bgC1" value="' + bg.c1 + '"></label>' + (bg.mode === 'gradient' ? '<label class="f">Couleur 2<input type="color" class="inp" id="bgC2" value="' + bg.c2 + '"></label>' : '') + '</div>'
              : '<div class="row center" style="margin-top:10px"><label class="btn">' + (EV.site_bg_image ? '✅ Changer la photo' : '📷 Choisir une photo') + '<input type="file" accept="image/*" hidden id="bgImg"></label></div>') +
              '<div class="bg-veil"><label>Voile pour la lisibilité : <b>' + bg.veil + ' %</b><input type="range" min="0" max="85" step="5" id="bgV" value="' + bg.veil + '"></label><span class="chips"><button type="button" class="chip' + (bg.tone === 'light' ? ' on' : '') + '" data-t="light">Clair</button><button type="button" class="chip' + (bg.tone === 'dark' ? ' on' : '') + '" data-t="dark">Sombre</button></span></div>' +
              '<div class="bg-prev" style="background:' + css() + '"><span>' + esc(tr(EV.title, L1)) + '</span></div>' +
              (lightTpl && dark ? '<div class="hint" style="color:#ffd27a">⚠️ Ce fond est foncé et le texte du modèle aussi : ajoute un voile clair (50 % ou plus) pour qu\'il reste lisible.</div>' : '') +
              '<label class="chk" style="margin-top:8px"><input type="checkbox" id="bgAll" ' + (bg.scope === 'all' ? 'checked' : '') + '> Aussi sur les pages RSVP, mur des vœux, liste de cadeaux et « Y aller »</label>') +
            '<div class="row center" style="margin-top:12px"><a class="btn ghost sm" target="_blank" rel="noopener" href="' + EV.urls.site + '">👁 Voir le site ↗</a><button type="button" class="btn gold" data-a="ok">Valider</button></div>';
          $$('[data-m]', b).forEach(x => x.onclick = () => { bg.mode = x.dataset.m; if (bg.mode === 'image' && !bg.veil) bg.veil = 45; draw(); });
          $$('[data-c]', b).forEach(x => x.onclick = () => { bg.c1 = x.dataset.c; draw(); });
          $$('[data-t]', b).forEach(x => x.onclick = () => { bg.tone = x.dataset.t; draw(); });
          const c1 = $('#bgC1', b), c2 = $('#bgC2', b), v = $('#bgV', b), all = $('#bgAll', b), img = $('#bgImg', b);
          if (c1) c1.onchange = () => { bg.c1 = c1.value; draw(); }; if (c2) c2.onchange = () => { bg.c2 = c2.value; draw(); };
          if (v) v.oninput = () => { bg.veil = +v.value; b.querySelector('.bg-veil b').textContent = bg.veil + ' %'; b.querySelector('.bg-prev').style.background = css(); }; if (v) v.onchange = draw;
          if (all) all.onchange = () => { bg.scope = all.checked ? 'all' : 'site'; };
          if (img) img.onchange = async () => { const fd = new FormData(); fd.append('field', 'site_bg_image'); fd.append('file', img.files[0]); try { const r = await api(BASE + 'upload/', { method: 'POST', form: fd }); EV.site_bg_image = r.url; dirty = true; toast('Photo enregistrée ✦'); draw(); } catch (e) { toast(e.message); } };
          b.querySelector('[data-a=ok]').onclick = () => { if (bg.mode === 'image' && !EV.site_bg_image) return toast('Choisis d\'abord une photo'); answer({ default: 'Fond du modèle', color: 'Fond couleur', gradient: 'Fond dégradé', image: 'Fond photo' }[bg.mode], () => patch({ site_bg: bg })); };
        };
        draw(); } },
    { id: 'couple', label: 'Les mariés & galerie', show: () => has('site') && EV.type === 'mariage', ask: () => "Présentons les mariés 💍 Écris vos prénoms et quelques mots sur chacun, dans chaque langue, puis ajoute vos photos." + (EV.site_template === 'C' ? '' : " <i>Ces sections s'affichent avec le modèle « Luxe Romantique ».</i>"),
      ui: b => { const c = JSON.parse(JSON.stringify(EV.couple || {})); ['p1', 'p2'].forEach(k => { c[k] = c[k] || { name: '', text: {} }; c[k].text = c[k].text || {}; });
        const up = async (field, file) => { const fd = new FormData(); fd.append('field', field); fd.append('file', file); const r = await api(BASE + 'upload/', { method: 'POST', form: fd }); EV[field] = r.url; };
        const sync = () => ['p1', 'p2'].forEach(k => { c[k].name = $('#cn-' + k, b).value.trim(); c[k].text = readLang('ct' + k, b); });
        const draw = () => { b.innerHTML = '<div class="grid">' + [['p1', 'partner1_image', 'Premier·e marié·e'], ['p2', 'partner2_image', 'Second·e marié·e']].map(([k, f, l]) => '<div class="card" style="padding:10px"><b>' + l + '</b><input class="inp" id="cn-' + k + '" style="margin:6px 0" value="' + esc(c[k].name) + '" placeholder="Prénom">' + langInputs('ct' + k, c[k].text, 'Quelques mots', 'textarea') + '<label class="btn sm" style="margin-top:6px">' + (EV[f] ? '✅' : '📷') + ' Photo<input type="file" hidden accept="image/*" data-pf="' + f + '"></label></div>').join('') +
            '<div class="card" style="padding:10px"><b>Galerie</b> <span class="muted">(' + (EV.gallery || []).length + ' / 40)</span><div class="gal-mini">' + (EV.gallery || []).map(g => '<span style="background-image:url(\'' + esc(g.url) + '\')"><button class="icon-btn" data-gx="' + g.id + '" aria-label="Retirer">✕</button></span>').join('') + '</div><label class="btn sm" style="margin-top:6px">📷 Ajouter des photos<input type="file" hidden accept="image/*" multiple data-gal></label></div>' +
            '<div class="row center"><button class="btn gold" data-a="ok">Valider</button></div></div>';
          $$('[data-pf]', b).forEach(i => i.onchange = async () => { sync(); try { await up(i.dataset.pf, i.files[0]); toast('Photo enregistrée ✦'); draw(); } catch (e) { toast(e.message); } });
          $('[data-gal]', b).onchange = async e => { sync(); const fd = new FormData(); [...e.target.files].forEach(f => fd.append('file', f)); try { EV.gallery = await api(BASE + 'gallery/', { method: 'POST', form: fd }); toast('Photos ajoutées ✦'); draw(); } catch (er) { toast(er.message); } };
          $$('[data-gx]', b).forEach(x => x.onclick = async () => { sync(); EV.gallery = await api(BASE + 'gallery/' + x.dataset.gx + '/', { method: 'DELETE' }); draw(); });
          b.querySelector('[data-a=ok]').onclick = () => { sync(); answer([c.p1.name, c.p2.name].filter(Boolean).join(' & ') || 'Plus tard', () => patch({ couple: c })); }; };
        draw(); } },
    { id: 'histoire', label: 'Notre histoire (site)', show: () => has('site') && EV.type === 'mariage', ask: () => "Pour ton site, racontons votre histoire. Ajoute, retire ou réordonne les étapes, avec tes propres titres, dans chaque langue.",
      ui: b => { let st = JSON.parse(JSON.stringify(EV.story));
        const draw = () => { b.innerHTML = '<div class="list-edit">' + st.map((s, i) => '<div class="card" style="padding:10px" data-s="' + i + '"><div class="row" style="justify-content:space-between"><b>Étape ' + (i + 1) + '</b><span><button class="icon-btn" data-u="' + i + '">▲</button> <button class="icon-btn" data-x="' + i + '">✕</button></span></div>' + langInputs('st' + i, s.title, 'Titre') + '<div style="height:6px"></div>' + langInputs('sx' + i, s.text, 'Texte', 'textarea') + (s.id ? '<label class="btn sm" style="margin-top:6px">' + (s.image ? '✅' : '📷') + ' Photo<input type="file" hidden accept="image/*" data-img="' + s.id + '"></label>' : '<div class="hint">Valide une première fois pour pouvoir ajouter la photo.</div>') + '</div>').join('') + '</div><div class="row" style="margin-top:8px"><button class="btn sm" data-a="add">+ Ajouter une étape</button><button class="btn sm" data-a="save">Enregistrer</button><button class="btn gold" data-a="ok">Valider</button></div>';
          const sync = () => $$('[data-s]', b).forEach(el => { const s = st[+el.dataset.s]; s.title = readLang('st' + el.dataset.s, el); s.text = readLang('sx' + el.dataset.s, el); });
          $$('[data-u]', b).forEach(x => x.onclick = () => { sync(); const i = +x.dataset.u; if (i > 0) [st[i - 1], st[i]] = [st[i], st[i - 1]]; draw(); });
          $$('[data-x]', b).forEach(x => x.onclick = () => { sync(); st.splice(+x.dataset.x, 1); draw(); });
          $$('[data-img]', b).forEach(inp => inp.onchange = async () => { const fd = new FormData(); fd.append('file', inp.files[0]); await api(BASE + 'story/' + inp.dataset.img + '/image/', { method: 'POST', form: fd }); toast('Photo enregistrée ✦'); });
          b.querySelector('[data-a=add]').onclick = () => { sync(); st.push({ title: {}, text: {} }); draw(); };
          const save = async () => { sync(); EV.story = await api(BASE + 'story/', { method: 'PUT', json: st }); st = JSON.parse(JSON.stringify(EV.story)); };
          b.querySelector('[data-a=save]').onclick = async () => { await save(); draw(); toast('Histoire enregistrée ✦'); };
          b.querySelector('[data-a=ok]').onclick = () => { sync(); answer(st.length + ' étapes dans votre histoire', save); }; };
        draw(); } },
    { id: 'musique', label: 'Musique', ask: () => "Choisis la musique de ton invitation dans le catalogue Miel 🎵 Elle jouera sur la page d'invitation et sur le mur des vœux.",
      ui: b => { b.innerHTML = '<div class="grid">' + (EV.songs.length ? EV.songs.map(s => '<div class="card" style="padding:12px;display:flex;gap:12px;align-items:center;flex-wrap:wrap"><div class="vinyl"></div><div style="flex:1;min-width:140px"><b>' + esc(s.title) + '</b><div class="muted" style="font-size:13px">' + esc(s.artist) + '</div>' + (s.audio ? '<audio controls preload="none" src="' + esc(s.audio) + '" style="width:100%;margin-top:6px"></audio>' : '') + '</div>' + (s.youtube ? '<a class="stream yt" href="' + esc(s.youtube) + '" target="_blank" rel="noopener">▶ YouTube</a>' : '') + (s.spotify ? '<a class="stream sp" href="' + esc(s.spotify) + '" target="_blank" rel="noopener">Spotify</a>' : '') + '<button class="btn gold sm" data-s="' + s.id + '">Choisir</button></div>').join('') : '<div class="muted">Le catalogue est vide pour le moment.</div>') + '<button class="btn ghost sm" data-s="">Pas de musique</button></div>';
        $$('[data-s]', b).forEach(x => x.onclick = () => answer(x.dataset.s ? '🎵 ' + EV.songs.find(s => String(s.id) === x.dataset.s).title : 'Pas de musique', () => patch({ song: x.dataset.s || null }))); } },
    { id: 'cadeaux', label: 'Liste de cadeaux', show: () => has('cadeaux'), ask: () => "Ta liste de cadeaux se gère dans l'onglet <b>🎁 Cadeaux</b> : ajoute les cadeaux, les options de livraison, et suis les réservations. Le lien apparaîtra sur le RSVP.",
      ui: b => { b.innerHTML = '<div class="row"><a class="btn" href="/app/e/' + EV.slug + '/cadeaux/" target="_blank" rel="noopener">Ouvrir la liste ↗</a><button class="btn gold" data-a="ok">Continuer</button></div>'; b.querySelector('[data-a=ok]').onclick = () => answer('OK pour les cadeaux'); } },
    { id: 'alerter', label: 'Alerter', show: () => has('alerter'), ask: () => "Voici ta checklist de départ. Désactive ce qui ne te concerne pas. Indique ton <b>budget</b> et le <b>nombre d'invités attendus</b> : je te préviens si le budget est dépassé ou si les réponses tardent.",
      ui: b => { b.innerHTML = '<div class="list-edit">' + EV.alerter.filter(a => a.kind === 'task').map(a => '<label class="it" style="cursor:pointer"><input type="checkbox" data-id="' + a.id + '" ' + (a.active ? 'checked' : '') + ' style="width:20px;height:20px;accent-color:#e9a83b"><span style="flex:1">' + esc(a.title) + '</span><span class="pill">J' + a.due + '</span></label>').join('') + '</div><div class="row" style="margin-top:10px"><label class="f" style="flex:1 1 140px">Budget prévu<input class="inp" type="number" id="al-b" value="' + (EV.budget || '') + '"></label><label class="f" style="flex:0 1 90px">Devise<input class="inp" id="al-c" value="' + esc(EV.currency) + '"></label><label class="f" style="flex:1 1 140px">Invités attendus<input class="inp" type="number" id="al-g" value="' + (EV.guest_target || '') + '"></label></div><div style="margin-top:10px"><button class="btn gold" data-a="ok">Valider</button></div>';
        b.querySelector('[data-a=ok]').onclick = () => answer('Budget ' + ($('#al-b').value || 0) + ' ' + $('#al-c').value + ' · ' + ($('#al-g').value || 0) + ' invités attendus', async () => {
          await Promise.all($$('input[data-id]', b).map(c => api(BASE + 'alerter/' + c.dataset.id + '/', { method: 'PATCH', json: { active: c.checked } })));
          await patch({ budget: $('#al-b').value || 0, currency: $('#al-c').value || '€', guest_target: +$('#al-g').value || 0 });
        }); } },
    { id: 'equipe', label: 'Équipe & rôles', show: () => has('alerter'), ask: () => "Veux-tu déléguer ? Crée un <b>rôle</b> (ce qu'il faut faire), puis ajoute la personne avec son <b>titre</b> (qui elle est). Elle recevra seulement des e-mails ou des messages WhatsApp, sans accès au site.",
      ui: b => { b.innerHTML = '<div class="grid"><div class="muted" style="font-size:13px">Rôles : ' + (EV.roles.map(r => '<b>' + esc(r.name) + '</b> (' + r.contacts.map(c => esc(c.name) + (c.title ? ', ' + esc(c.title) : '')).join(' ; ') + ')').join(' · ') || 'aucun pour le moment') + '</div>' +
          '<div class="row"><input class="inp" style="flex:1 1 180px" id="ro-n" placeholder="Rôle, ex. Accueil des invités"><input class="inp" style="flex:1 1 160px" id="ro-p" placeholder="Nom de la personne"></div><div class="row"><input class="inp" style="flex:1 1 160px" id="ro-t" placeholder="Titre, ex. Cousine de la mariée"><input class="inp" style="flex:1 1 160px" id="ro-e" placeholder="E-mail"><input class="inp" style="flex:1 1 140px" id="ro-w" placeholder="WhatsApp"></div>' +
          '<label class="row" style="font-size:13px"><input type="checkbox" id="ro-ok"> La personne accepte de recevoir des messages (obligatoire pour WhatsApp)</label><div class="row"><button class="btn sm" data-a="add">+ Ajouter ce rôle</button><button class="btn gold" data-a="ok">Continuer</button></div></div>';
        b.querySelector('[data-a=add]').onclick = async () => { try { EV.roles = await api(BASE + 'roles/', { method: 'POST', json: { name: $('#ro-n').value.trim(), contacts: [{ name: $('#ro-p').value.trim(), title: $('#ro-t').value.trim(), email: $('#ro-e').value.trim(), wa: $('#ro-w').value.trim(), consent: $('#ro-ok').checked }] } }); push('bot', '✅ Rôle <b>' + esc($('#ro-n').value) + '</b> créé.'); save(); render(); } catch (e) { toast(e.message); } };
        b.querySelector('[data-a=ok]').onclick = () => answer(EV.roles.length + " rôle(s) dans l'équipe"); } },
    { id: 'moments', label: 'Moments forts', show: () => has('moments'), ask: () => "Préparons tes <b>moments forts</b> ✨ Le jour J, tu les lances depuis le panneau, et ils s'affichent en même temps chez tous les invités. L'Alerter vérifie que chaque photo est bien chargée.",
      ui: b => { b.innerHTML = '<div class="list-edit">' + EV.moments.map(m => '<div class="it"><span style="flex:1">' + esc(tr(m.title, L1())) + '</span><span class="pill ' + (m.needs_photo ? 'bad' : 'ok') + '">' + (m.kind === 'reveal' ? (m.photo ? 'photo prête' : 'photo manquante') : 'message') + '</span></div>').join('') + '</div>' +
          '<div class="grid" style="margin-top:8px"><b>Nouveau moment</b>' + langInputs('mt', {}, 'Titre, ex. Le premier baiser') + '<div class="row"><select class="inp" style="flex:1 1 180px" id="mo-ty"><option value="reveal">Compte à rebours puis photo révélée</option><option value="message">Message surprise plein écran</option><option value="clock">Compte à rebours vers une heure (ex. minuit)</option></select><select class="inp" style="flex:1 1 120px" id="mo-du"><option>10</option><option>30</option><option>60</option></select><select class="inp" style="flex:1 1 140px" id="mo-ef"><option value="confetti">Confettis</option><option value="hearts">Cœurs</option><option value="fireworks">Feux d\'artifice</option></select></div><input class="inp" type="datetime-local" id="mo-at" title="Heure fixe (facultatif)"><div class="row"><label class="btn sm">📷 Photo (facultatif)<input type="file" accept="image/*" hidden id="mo-ph"></label><button class="btn sm" data-a="add">+ Ajouter</button><button class="btn gold" data-a="ok">Continuer</button></div></div>';
        b.querySelector('[data-a=add]').onclick = async () => { const ti = readLang('mt', b); if (!Object.keys(ti).length) return toast('Donne un titre au moment'); const fd = new FormData(); fd.append('title', JSON.stringify(ti)); fd.append('message', JSON.stringify(ti)); fd.append('kind', $('#mo-ty').value); fd.append('duration', $('#mo-du').value); fd.append('effect', $('#mo-ef').value); if ($('#mo-at').value) fd.append('scheduled_at', $('#mo-at').value); if ($('#mo-ph').files[0]) fd.append('photo', $('#mo-ph').files[0]); try { EV.moments = await api(BASE + 'moments/', { method: 'POST', form: fd }); render(); } catch (e) { toast(e.message); } };
        b.querySelector('[data-a=ok]').onclick = () => answer(EV.moments.length + ' moment(s) fort(s) prêts'); } },
    { id: 'telegram', label: 'Photos sur Telegram', show: () => has('mur'), ask: () => "Les photos et vidéos que tes invités envoient depuis le mur des vœux peuvent arriver <b>en direct dans ton groupe ou ton canal Telegram</b> ✈️ Relie-le en 3 gestes, c'est gratuit.",
      ui: b => { let T = null;
        const load = async () => { try { T = await api(BASE + 'telegram/'); } catch (e) { return toast(e.message); } draw(); };
        const draw = () => { if (!b.isConnected) return;
          const list = T.channels.filter(c => c.active);
          b.innerHTML = '<div class="grid" style="text-align:left;gap:10px">' +
            (list.length ? '<div class="tg-groups"><b>✈️ Groupes connectés (' + list.length + ')</b><div>' + list.map(c => '<span class="tg-badge" translate="no">' + (c.kind === 'channel' ? '📢 ' : '👥 ') + esc(c.title) + ' <button type="button" class="tg-x" data-del="' + c.id + '" aria-label="Retirer">✕</button></span>').join('') + '</div></div>' : '<div class="hint">Aucun groupe relié pour le moment.</div>') +
            (T.configured ? '' : '<div class="hint" style="color:#ffd27a">⚠️ Le bot Telegram de Miel n\'est pas encore configuré sur le serveur : la liaison marchera dès qu\'il le sera.</div>') +
            '<ol class="tg-steps"><li>' + (T.bot ? 'Ajoute <b translate="no">@' + esc(T.bot) + '</b> à ton groupe Telegram, ou comme administrateur de ton canal.' : 'Ajoute le bot Miel à ton groupe Telegram, ou comme administrateur de ton canal.') + '</li><li>Colle ce jeton dans le groupe ou le canal :</li></ol>' +
            '<div class="tg-token" translate="no">' + esc(T.token) + '</div>' +
            '<div class="row center"><button type="button" class="btn sm gold" data-a="copy">📋 Copier le jeton</button>' + (T.group_link ? '<a class="btn sm" href="' + esc(T.group_link) + '" target="_blank" rel="noopener">➕ Ajouter Miel à un groupe</a>' : '') + '</div>' +
            '<ol class="tg-steps" start="3"><li>Miel répond « ✅ Ce groupe est relié » et efface le jeton. Ton groupe apparaît ici tout de suite.</li></ol>' +
            '<div class="row center"><button type="button" class="btn sm ghost" data-a="new">↻ Nouveau jeton</button><button type="button" class="btn gold" data-a="ok">' + (list.length ? 'Valider' : 'Plus tard') + '</button></div></div>';
          b.querySelector('[data-a=copy]').onclick = async () => { try { await navigator.clipboard.writeText(T.token); toast('Jeton copié ✦'); } catch (e) { toast('Sélectionne le jeton et copie-le'); } };
          b.querySelector('[data-a=new]').onclick = async () => { if (!confirmNew) { confirmNew = true; toast('L\'ancien jeton ne marchera plus. Touche encore pour confirmer.'); setTimeout(() => confirmNew = false, 4000); return; } confirmNew = false; T = await api(BASE + 'telegram/', { method: 'POST', json: { regenerate: true } }); draw(); };
          $$('[data-del]', b).forEach(x => x.onclick = async () => { T = await api(BASE + 'telegram/' + x.dataset.del + '/', { method: 'DELETE' }); draw(); });
          b.querySelector('[data-a=ok]').onclick = () => { clearInterval(timer); answer(list.length ? list.length + ' groupe(s) Telegram relié(s)' : 'Plus tard'); }; };
        let confirmNew = false;
        const timer = setInterval(() => { if (!b.isConnected) return clearInterval(timer); api(BASE + 'telegram/').then(n => { if (JSON.stringify(n.channels) !== JSON.stringify(T && T.channels)) { T = n; draw(); } }).catch(() => {}); }, 4000);
        load(); } },
    { id: 'partage', label: 'Partage', ask: () => "Dernière étape : partager ton invitation 💌 Par quel moyen veux-tu l'envoyer ?",
      ui: b => { const url = EV.urls.share;
        if (!share.ch) { b.innerHTML = '<div class="tiles-row">' + tile('🟢', 'WhatsApp', 'data-c="wa"') + tile('✈️', 'Telegram', 'data-c="tg"') + tile('🔗', 'Copier le lien', 'data-c="cp"') + '</div>'; $$('.opt', b).forEach(c => c.onclick = () => { share.ch = c.dataset.c; push('me', esc(c.textContent.trim())); push('bot', 'Dans quelle langue veux-tu envoyer le message ?'); save(); render(); }); return; }
        if (!share.lang) { b.innerHTML = '<div class="tiles-row">' + EV.languages.map(k => tile(LANGS[k][0], LANGS[k][1], 'data-l="' + k + '"')).join('') + '</div>'; $$('.opt', b).forEach(c => c.onclick = () => { share.lang = c.dataset.l; push('me', esc(c.textContent.trim())); push('bot', HELP[share.ch]); save(); render(); }); return; }
        const msg = shareText(share.lang, url);
        const href = share.ch === 'wa' ? 'https://wa.me/?text=' + encodeURIComponent(msg) : share.ch === 'tg' ? 'https://t.me/share/url?url=' + encodeURIComponent(url) + '&text=' + encodeURIComponent(msg.replace(url, '')) : '';
        b.innerHTML = '<div class="grid"><textarea class="inp" rows="6" id="sh-msg">' + esc(msg) + '</textarea><div class="row">' + (href ? '<a class="btn gold" id="sh-go" href="' + href + '" target="_blank" rel="noopener">' + (share.ch === 'wa' ? 'Ouvrir WhatsApp' : 'Ouvrir Telegram') + '</a>' : '') + '<button class="btn" data-a="copy">Copier le message</button><button class="btn ghost sm" data-a="again">Autre moyen</button><button class="btn sm" data-a="ok">Terminer ✓</button></div></div>';
        $('#sh-msg').oninput = () => { const m = $('#sh-msg').value; if ($('#sh-go')) $('#sh-go').href = share.ch === 'wa' ? 'https://wa.me/?text=' + encodeURIComponent(m) : 'https://t.me/share/url?url=' + encodeURIComponent(url) + '&text=' + encodeURIComponent(m.replace(url, '')); };
        b.querySelector('[data-a=copy]').onclick = () => navigator.clipboard.writeText($('#sh-msg').value).then(() => toast('Message copié ✦'), () => { $('#sh-msg').select(); toast('Message sélectionné : copie-le'); });
        b.querySelector('[data-a=again]').onclick = () => { share = {}; render(); };
        b.querySelector('[data-a=ok]').onclick = () => { share = {}; answer('Invitation partagée 🎉'); }; } },
    { id: 'fin', label: 'Récapitulatif', ask: () => "Bravo, tout est prêt ! 🎉 Je reste là si tu veux modifier quelque chose : utilise le <b>Menu</b>.",
      ui: b => { b.innerHTML = '<div class="chips"><a class="chip" href="/app/e/' + EV.slug + '/">📊 Panneau de contrôle</a><a class="chip" href="' + EV.urls.site + '" target="_blank" rel="noopener">' + (has('site') && EV.type === 'mariage' ? '🌐 Voir le site' : '💌 Voir le RSVP') + '</a>' + (has('tables') ? '<a class="chip" href="/app/e/' + EV.slug + '/tables/">🪑 Plan de table</a>' : '') + (has('mur') ? '<a class="chip" href="' + EV.urls.wall + '" target="_blank" rel="noopener">💬 Mur des vœux</a>' : '') + '</div>'; } },
  ];
  const HELP = { wa: "Parfait. WhatsApp va s'ouvrir avec le message déjà écrit : choisis tes contacts ou un groupe, puis appuie sur <b>Envoyer</b>.", tg: 'Parfait. Telegram va s\'ouvrir : choisis une discussion ou un groupe, vérifie le message, puis envoie.', cp: 'Copie le message, puis colle-le où tu veux : SMS, e-mail, réseaux sociaux.' };
  function shareText(l, u) {
    const n = tr(EV.title, l), w = EV.type === 'mariage';
    if (l === 'en') return '✨🥂 ' + n + (w ? ' invite you to their wedding' : ' — you are invited') + ' ✨🥂\n\nWe would be delighted to have you with us. Could you please confirm your attendance?\n\n👉 ' + u + '\n\nLooking forward to seeing you ✨';
    if (l === 'it') return '✨🥂 ' + n + (w ? ' vi invitano al loro matrimonio' : ' — siete invitati') + ' ✨🥂\n\nSaremo felici di avervi con noi. Potete confermarci la vostra presenza?\n\n👉 ' + u + "\n\nNon vediamo l'ora di vedervi ✨";
    if (l === 'ln' && w) return '✨🥂 ' + n + ' babengi bino na libunga la bolongani ✨🥂\n\nNa esengo, toko kosangisa mokolo wana elongo na bino. Okoki koyebisa biso soki oyeli?\n\n👉 ' + u + '\n\nTozali kozela bino ✨';
    return '✨🥂 ' + n + (w ? ' vous invitent à leur mariage' : ' — vous êtes invités') + " ✨🥂\n\nNous serions ravis de vous compter parmi nous. Pourriez-vous nous confirmer votre présence ?\n\n👉 " + u + "\n\nDans l'attente de vous retrouver ✨";
  }

  // ---------- moteur (pop-up qui apparaît et disparaît)
  const idx = id => Math.max(0, STEPS.findIndex(s => s.id === id));
  const visible = i => !STEPS[i].show || STEPS[i].show();
  const push = (from, html) => S.log.push({ from, html });
  const save = () => api(BASE + 'bot/', { method: 'PUT', json: S }).catch(() => toast('Connexion perdue : la progression sera enregistrée au prochain essai'));
  function goStep(i, note) { S.step = STEPS[i].id; S.paused = false; if (note) push('bot', note); push('bot', STEPS[i].ask()); save(); render(true); }
  function nextStep() { let i = idx(S.step) + 1; while (i < STEPS.length && !visible(i)) i++; goStep(Math.min(i, STEPS.length - 1)); }
  async function answer(text, apply) {
    try { if (apply) { await apply(); dirty = true; } } catch (e) { toast(e.message); return; }
    push('me', esc(text)); nextStep();
  }
  function togglePause() { S.paused = !S.paused; push('bot', S.paused ? '⏸ Section en pause.' : '▶ On reprend !'); if (!S.paused) push('bot', STEPS[idx(S.step)].ask()); save(); render(true); }

  const pop = $('#botPop'), card = $('#botCard');
  let view = 'step'; // step | preview | history
  function open(stepId) { if (typeof stepId === 'string') { const i = STEPS.findIndex(x => x.id === stepId); if (i >= 0 && STEPS[i].id !== S.step) { S.step = STEPS[i].id; S.paused = false; push('bot', STEPS[i].ask()); save(); } } pop.hidden = false; requestAnimationFrame(() => pop.classList.add('show')); document.body.classList.add('bot-open'); render(); }
  function close() {
    pop.classList.remove('show'); document.body.classList.remove('bot-open'); voice.stop();
    if (view === 'help') view = 'step';
    setTimeout(() => { pop.hidden = true; }, 280);
    if (dirty) { dirty = false; window.dispatchEvent(new CustomEvent('miel:event-changed')); }
  }
  Miel.openBot = open;
  function togglePreview(force) { view = force === true || view !== 'preview' ? 'preview' : 'step'; render(true); }

  function render(animate) {
    if (pop.hidden) return;
    const draw = () => {
      const i = idx(S.step), st = STEPS[i];
      const visibleSteps = STEPS.filter((_, k) => visible(k));
      $('#botLabel').textContent = S.paused ? 'En pause' : 'Étape ' + (visibleSteps.indexOf(st) + 1) + ' / ' + visibleSteps.length + ' · ' + st.label;
      $('#botPause').textContent = S.paused ? '▶ Reprendre' : '⏸ Pause';
      $('#botPrev').classList.toggle('on', view === 'preview');
      $('#botHistBtn').classList.toggle('on', view === 'history');
      const body = $('#botBody');
      if (view === 'history') { body.innerHTML = '<div class="bot-hist">' + S.log.map(m => '<div class="msg ' + (m.from === 'me' ? 'me' : 'bot') + '">' + m.html + '</div>').join('') + '</div>'; const h = body.firstChild; h.scrollTop = h.scrollHeight; return; }
      if (view === 'preview') { body.innerHTML = '<div id="pvCol" class="show" translate="no"></div>'; preview(); return; }
      if (view === 'help') { $('#botLabel').textContent = 'Aide'; drawHelp(body); return; }
      const lastBot = [...S.log].reverse().find(m => m.from !== 'me');
      const lastMe = [...S.log].reverse().find(m => m.from === 'me');
      body.innerHTML = (lastMe && !S.paused ? '<div class="bot-echo">« ' + lastMe.html + ' »</div>' : '') + '<div class="bot-ask">' + (S.paused ? 'Tu as mis cette section en pause. Ne t\'inquiète pas, tu pourras revenir quand tu veux.' : (lastBot ? lastBot.html : st.ask())) + '</div><div class="bot-input" id="composer"></div>';
      const comp = $('#composer');
      if (S.paused) { comp.innerHTML = '<div class="row center"><button class="btn gold" id="bRes">▶ Reprendre</button></div>'; $('#bRes').onclick = togglePause; }
      else st.ui(comp);
      voice.auto(S.step + '|' + S.log.length, $('.bot-ask', body));
      if (offerFor === S.step) showOffer(body);
    };
    if (!animate) { draw(); return; }
    card.classList.add('swap');
    setTimeout(() => { draw(); card.classList.remove('swap'); card.scrollTop = 0; }, 160);
  }
  async function preview() {
    const pv = $('#pvCol'); if (!pv) return;
    const l = pv.dataset.lang || L1();
    pv.innerHTML = '<div class="row center" style="margin-bottom:12px">' + EV.languages.map(k => tile(LANGS[k][0], LANGS[k][1], 'data-pl="' + k + '"', l === k)).join('') + '</div><div id="pvCard" class="muted" style="text-align:center">…</div>';
    $$('[data-pl]', pv).forEach(b => b.onclick = () => { pv.dataset.lang = b.dataset.pl; preview(); });
    try {
      const r = await fetch('/app/e/' + EV.slug + '/carte-apercu/?lang=' + l + '&v=' + Date.now(), { credentials: 'same-origin' });
      const box = $('#pvCard', pv); if (!box) return;
      box.className = ''; box.innerHTML = await r.text(); Miel.renderQRs(box);
    } catch (e) { toast(e.message); }
  }


  // ---------- voix du navigateur (synthèse vocale intégrée, gratuite)
  const voice = (() => {
    const synth = window.speechSynthesis, lang = (window.MielUI && window.MielUI.lang) || 'fr';
    const CODES = { fr: 'fr', en: 'en', it: 'it' };
    let on = false, rate = 1, last = '', lastText = '';
    try { on = localStorage.getItem('miel_voice') === '1'; rate = +(localStorage.getItem('miel_voice_rate') || 1); } catch (e) {}
    const supported = !!(synth && window.SpeechSynthesisUtterance);
    const pickVoice = () => {
      const code = CODES[lang]; if (!code) return null;
      const vs = synth.getVoices().filter(v => v.lang && v.lang.toLowerCase().startsWith(code));
      const good = /natural|neural|premium|enhanced|google|siri|amélie|amelie|thomas|alice|federica|samantha|daniel/i;
      return vs.find(v => good.test(v.name) && v.localService === false) || vs.find(v => good.test(v.name)) || vs[0] || null;
    };
    const clean = el => (typeof el === 'string' ? (() => { const d = document.createElement('div'); d.innerHTML = el; return d; })() : el).innerText
      .replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}\u{200D}✦❤♥]/gu, '').replace(/\s+/g, ' ').trim();
    function speak(src) {
      if (!on || !supported || !src) return;
      if (!CODES[lang]) return;  // pas de voix en lingala pour l'instant
      const text = clean(src); if (!text) return;
      lastText = text; synth.cancel();
      const u = new SpeechSynthesisUtterance(text); const v = pickVoice();
      if (v) { u.voice = v; u.lang = v.lang; } else u.lang = ({ fr: 'fr-FR', en: 'en-GB', it: 'it-IT' })[lang];
      u.rate = rate; synth.speak(u);
    }
    function paint() {
      const b = $('#botVoice'); if (!b) return;
      b.hidden = !supported; b.textContent = on ? '🔊' : '🔇'; b.setAttribute('aria-pressed', on);
      b.title = on ? 'Couper la voix' : 'Lire à voix haute';
      $('#botReplay').hidden = !on; $('#botRate').hidden = !on; $('#botRate').textContent = (rate === 1 ? '1' : String(rate).replace('.', ',')) + '×';
    }
    if (supported && synth.onvoiceschanged !== undefined) synth.onvoiceschanged = () => {};
    return {
      paint, speak, stop: () => supported && synth.cancel(),
      auto(key, el) { if (key !== last) { last = key; speak(el); } },
      toggle() {
        on = !on; try { localStorage.setItem('miel_voice', on ? '1' : '0'); } catch (e) {}
        paint();
        if (on && !CODES[lang]) toast('La voix n\'existe pas encore en lingala : les messages restent écrits.');
        if (on) speak($('#botBody .bot-ask') || $('#botBody')); else synth.cancel();
      },
      replay() { if (lastText) { const t = lastText; lastText = ''; speak(t); } else speak($('#botBody .bot-ask') || $('#botBody')); },
      cycleRate() { rate = rate === 1 ? 1.25 : rate === 1.25 ? 0.85 : 1; try { localStorage.setItem('miel_voice_rate', rate); } catch (e) {} paint(); this.replay(); },
    };
  })();

  // ---------- aide : questions libres, réponses avec actions, proposition après 30 s sans action
  const HL = [];  // fil de l'aide (session)
  const helpOff = () => { try { return localStorage.getItem('miel_help_off') === '1'; } catch (e) { return false; } };
  const offered = new Set();
  let offerFor = null, lastAct = Date.now(), bubbleShown = false, lastErr = { m: '', t: 0 };
  const PAGES = { panel: '', tables: 'tables/', gifts: 'cadeaux/' };
  const context = () => (!pop.hidden && view !== 'help' ? 'bot:' + S.step : (document.body.dataset.page || ''));
  function pageUrl(p) {
    if (p in PAGES) return '/app/e/' + EV.slug + '/' + PAGES[p];
    return (EV.urls || {})[p] || '/app/e/' + EV.slug + '/';
  }
  function flash(sel) {
    const el = document.querySelector(sel);
    if (!el) return false;
    if (!pop.contains(el)) close();
    setTimeout(() => { el.scrollIntoView({ behavior: 'smooth', block: 'center' }); el.classList.remove('flash-hint'); void el.offsetWidth; el.classList.add('flash-hint'); setTimeout(() => el.classList.remove('flash-hint'), 3200); }, pop.contains(el) ? 0 : 320);
    return true;
  }
  function act(a) {
    if (a.step) { const i = STEPS.findIndex(x => x.id === a.step); if (i >= 0) { view = 'step'; if (!visible(i)) return toast('Cette étape apparaît quand le service correspondant est activé.'); goStep(i, '↩ « ' + esc(STEPS[i].label) + ' ».'); } return; }
    if (a.open === 'prefs') { close(); setTimeout(() => { const b = $('#themeBtn'); b && b.click(); }, 300); return; }
    if (a.flash) { if (!flash(a.flash)) { if (a.flash.startsWith('#tb')) location.href = pageUrl('tables') + '?flash=' + encodeURIComponent(a.flash); else toast('Ce bouton se trouve sur une autre page.'); } return; }
    if (a.go) { const u = pageUrl(a.go); if (['wall', 'screen', 'map', 'site'].includes(a.go)) window.open(u, '_blank', 'noopener'); else location.href = u; return; }
    if (a.url) location.href = a.url;
  }
  function drawHelp(body) {
    const lastQ = HL.length ? HL[HL.length - 1] : null;
    body.innerHTML = '<div class="help-thread">' + (HL.length ? '' : '<div class="msg bot">Je t\'écoute ✨ Pose ta question avec tes mots : « comment rouvrir l\'assistant », « photo », « plan de table », « prix »…</div>') +
      HL.map((h, k) => '<div class="msg me" translate="no">' + esc(h.q) + '</div>' + (h.typing ? '<div class="msg bot typing" aria-label="Miel écrit…"><i></i><i></i><i></i></div>' : h.res ? answerHTML(h, k) : '')).join('') +
      '</div><div class="row center" style="margin-top:12px"><button type="button" class="btn sm" data-a="back">↩ Revenir à l\'étape</button></div>';
    const th = $('.help-thread', body); th.scrollTop = th.scrollHeight;
    body.querySelector('[data-a=back]').onclick = () => { view = 'step'; render(true); };
    $$('[data-act]', body).forEach(b => b.onclick = () => { const h = HL[+b.dataset.h]; act(h.res.found.actions[+b.dataset.act]); });
    $$('[data-alt]', body).forEach(b => b.onclick = () => openEntry(+b.dataset.alt, b.textContent));
    $$('[data-fb]', body).forEach(b => b.onclick = async () => { const h = HL[+b.dataset.h]; if (h.fb) return; h.fb = b.dataset.fb; drawHelp(body);
      try { await api('/api/help/' + h.res.found.id + '/feedback/', { method: 'POST', json: { useful: h.fb === '1' } }); } catch (e) {} });
    if (lastQ && lastQ.res && !lastQ.spoken) { lastQ.spoken = true; const m = $$('.msg.bot', body).pop(); voice.speak(m); }
  }
  function answerHTML(h, k) {
    const r = h.res;
    if (r.found) {
      const f = r.found;
      return '<div class="msg bot"><span translate="no">' + esc(f.answer) + '</span>' +
        (f.actions.length ? '<div class="help-acts">' + f.actions.map((a, i) => '<button type="button" class="btn sm gold" translate="no" data-h="' + k + '" data-act="' + i + '">' + esc(a.label) + '</button>').join('') + '</div>' : '') +
        '<div class="help-fb">' + (h.fb ? (h.fb === '1' ? 'Merci ! 💛' : 'Merci, on va améliorer cette réponse.') : 'C\'était utile ? <button type="button" data-h="' + k + '" data-fb="1" aria-label="Oui">👍</button><button type="button" data-h="' + k + '" data-fb="0" aria-label="Non">👎</button>') + '</div></div>' +
        (r.alts.length ? '<div class="help-alts"><small>Tu voulais peut-être dire :</small>' + r.alts.map(a => '<button type="button" class="chip" translate="no" data-alt="' + a.id + '">' + esc(a.question) + '</button>').join('') + '</div>' : '');
    }
    return '<div class="msg bot">Je ne sais pas encore répondre à ça. J\'ai noté ta question : l\'équipe Miel va ajouter la réponse. 🐝</div>' +
      (r.alts.length ? '<div class="help-alts"><small>Ces réponses peuvent peut-être t\'aider :</small>' + r.alts.map(a => '<button type="button" class="chip" translate="no" data-alt="' + a.id + '">' + esc(a.question) + '</button>').join('') + '</div>' : '');
  }
  const wait = ms => new Promise(r => setTimeout(r, ms));
  async function askHelp(q, ctx) {
    q = (q || '').trim(); if (!q) return;
    if (pop.hidden) open();
    const c = ctx || context();
    view = 'help'; const h = { q, typing: true }; HL.push(h); render(true);
    const lang = (window.MielUI && window.MielUI.lang) || 'fr';
    const [res] = await Promise.all([api('/api/help/ask/', { method: 'POST', json: { q, lang, context: c, event: EV.slug } }).catch(e => ({ error: e.message })), wait(650 + Math.random() * 500)]);
    h.typing = false; h.res = res.error ? { found: null, alts: [] } : res; render();
  }
  async function openEntry(id, label, ctxHelp) {
    if (pop.hidden) open();
    view = 'help'; const h = { q: label, typing: true }; HL.push(h); render(true);
    const lang = (window.MielUI && window.MielUI.lang) || 'fr';
    const url = ctxHelp ? '/api/help/here/?lang=' + lang + '&context=' + encodeURIComponent(ctxHelp) : '/api/help/' + id + '/?lang=' + lang;
    const [res] = await Promise.all([api(url).catch(() => null), wait(500)]);
    h.typing = false; h.res = res ? { found: res, alts: [] } : { found: null, alts: [] }; render();
  }
  function showOffer(body) {
    if ($('.help-offer', body)) return;
    const d = document.createElement('div'); d.className = 'help-offer';
    d.innerHTML = '💡 Tu as besoin d\'un coup de main pour cette étape ?<div class="row center"><button type="button" class="btn sm gold" data-o="yes">Oui, explique-moi</button><button type="button" class="btn sm" data-o="no">Non merci</button><button type="button" class="btn sm ghost" data-o="never">Ne plus me le proposer</button></div>';
    body.prepend(d); voice.speak(d.firstChild.textContent);
    d.querySelector('[data-o=yes]').onclick = () => { offerFor = null; openEntry(null, 'Aide : ' + STEPS[idx(S.step)].label, 'bot:' + S.step); };
    d.querySelector('[data-o=no]').onclick = () => { offerFor = null; d.remove(); };
    d.querySelector('[data-o=never]').onclick = () => { offerFor = null; d.remove(); try { localStorage.setItem('miel_help_off', '1'); } catch (e) {} toast('D\'accord. Tu peux toujours poser une question en bas de l\'assistant.'); };
  }
  function offerNow() {
    if (helpOff() || offered.has(S.step) || S.paused) return;
    offered.add(S.step); offerFor = S.step; const b = $('#botBody'); if (b && view === 'step') showOffer(b);
  }
  function setupHelp() {
    ['pointerdown', 'keydown', 'input', 'wheel', 'touchstart'].forEach(t => document.addEventListener(t, () => { lastAct = Date.now(); }, { passive: true, capture: true }));
    setInterval(() => {
      if (document.visibilityState !== 'visible' || helpOff()) return;
      const idle = Date.now() - lastAct;
      const typing = document.activeElement && /INPUT|TEXTAREA/.test(document.activeElement.tagName) && document.activeElement.value && document.activeElement.id !== 'botAskQ';
      if (!pop.hidden && view === 'step' && idle > 30000 && !typing) offerNow();
      if (pop.hidden && idle > 30000 && !bubbleShown) { bubbleShown = true; $('#fabBubble').hidden = false; }
    }, 3000);
    // même message d'erreur deux fois de suite : proposer l'aide tout de suite
    const orig = Miel.toast;
    Miel.toast = function (m, u) { const now = Date.now(); if (!pop.hidden && view === 'step' && m === lastErr.m && now - lastErr.t < 60000) offerNow(); lastErr = { m, t: now }; return orig.apply(this, arguments); };
    $('#fabBubble').onclick = () => { $('#fabBubble').hidden = true; const c = document.body.dataset.page || ''; open(); if (c) openEntry(null, 'Aide sur cette page', c); else { view = 'help'; render(true); } };
    $('#botAskForm').onsubmit = e => { e.preventDefault(); const i = $('#botAskQ'); const q = i.value; i.value = ''; askHelp(q); };
    $('#botVoice').onclick = () => voice.toggle();
    $('#botReplay').onclick = () => voice.replay();
    $('#botRate').onclick = () => voice.cycleRate();
    voice.paint();
    const f = new URLSearchParams(location.search).get('flash'); if (f) setTimeout(() => flash(f), 900);
  }

  async function init() {
    S = await api(BASE + 'bot/');
    if (!S.log.length) { S.step = 'accueil'; push('bot', STEPS[0].ask()); save(); }
    $('#botFab').onclick = () => { $('#fabBubble').hidden = true; open(); };
    setupHelp();
    $('#botClose').onclick = close;
    pop.addEventListener('click', e => { if (e.target === pop) close(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !pop.hidden) close(); });
    $('#botPause').onclick = togglePause;
    $('#botPrev').onclick = () => togglePreview();
    $('#botHistBtn').onclick = () => { view = view === 'history' ? 'step' : 'history'; render(true); };
    $('#botMenu').onclick = () => {
      const cur = idx(S.step);
      const sh = openSheet('<h3>Étapes</h3><p class="muted" style="margin-top:0">Reviens sur n\'importe quelle partie.</p><div class="menu-list">' + STEPS.map((x, i) => visible(i) ? '<button data-i="' + i + '" class="' + (i === cur ? 'cur' : '') + '"><span>' + esc(x.label) + '</span><span class="pill">' + (i < cur ? 'fait' : i === cur ? 'en cours' : 'à venir') + '</span></button>' : '').join('') + '</div>');
      $$('[data-i]', sh).forEach(x => x.onclick = () => { closeSheet(); view = 'step'; goStep(+x.dataset.i, '↩ Retour à « ' + esc(STEPS[+x.dataset.i].label) + ' ».'); });
    };
    const qs = new URLSearchParams(location.search);
    if (qs.get('bot') === '1' || S.log.length <= 1) open();
  }
  init().catch(e => toast(e.message));
})();
