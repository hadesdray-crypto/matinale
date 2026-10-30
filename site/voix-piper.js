/* Matinale : voix téléchargeables (Piper), lues dans le téléphone, même sans Internet.
   - Le moteur (≈ 29 Mo) et chaque voix (28 à 77 Mo) se téléchargent seulement quand on le demande.
   - Ils sont gardés dans le téléphone (stockage « matinale-voix-piper ») ; « Effacer » les enlève.
   - Les voix viennent du projet Piper (rhasspy/piper-voices, sur Hugging Face) ; chaque voix a sa licence.
   Utilisé par index.html : window.VoixPiper. */
(function(){
  'use strict';
  const CACHE = 'matinale-voix-piper';
  const HF = 'https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/';
  const ECHANT = 'https://rhasspy.github.io/piper-samples/samples/';
  const VER = '1';
  const base = new URL('vendor/piper/', document.baseURI).href;
  const MOTEUR = ['piper-worker.js', 'ort.wasm.min.js', 'ort-wasm-simd.wasm', 'piper_phonemize.js', 'piper_phonemize.wasm', 'piper_phonemize.data'].map(f => base + f);
  const MOTEUR_MO = 29;
  let catalogue = null, worker = null, nMsg = 0, attente = new Map(), charge = '', au = null, jeton = 0, wurl = '';
  const cacheOK = () => typeof caches !== 'undefined';
  const ouvrir = () => caches.open(CACHE);
  const fichiers = v => ({ model: HF + v.onnx, config: HF + v.onnx + '.json' });

  /* La liste des voix : en ligne, sinon la copie gardée avec les voix (pour marcher sans Internet). */
  async function lireCatalogue(){
    if (catalogue) return catalogue;
    const u = new URL('voix-catalogue.json', document.baseURI).href;
    let j = null;
    try { const r = await fetch(u, { cache:'no-cache' }); if (r.ok){ j = await r.clone().json(); if (cacheOK()) ouvrir().then(c => c.put(u, r)).catch(() => {}); } } catch (e) {}
    if (!j && cacheOK()){ try { const r = await (await ouvrir()).match(u); if (r) j = await r.json(); } catch (e) {} }
    if (!j) throw new Error('Liste des voix indisponible');
    catalogue = j.voix || [];
    return catalogue;
  }
  async function present(url){ try { const c = await ouvrir(); return !!(await c.match(url)); } catch (e) { return false; } }
  async function moteurPresent(){ if (!cacheOK()) return false; for (const u of MOTEUR) if (!(await present(u))) return false; return true; }
  async function etat(){
    const out = { moteur:false, voix:[] }; if (!cacheOK()) return out;
    try {
      const c = await ouvrir(), keys = (await c.keys()).map(r => r.url);
      out.moteur = MOTEUR.every(u => keys.includes(u));
      const cat = await lireCatalogue().catch(() => []);
      cat.forEach(v => { const f = fichiers(v); if (keys.includes(f.model) && keys.includes(f.config)) out.voix.push(v.id); });
      out.voix = [...new Set(out.voix)];
    } catch (e) {}
    return out;
  }
  /* Téléchargement avec la progression (octets reçus / total). */
  async function telechargerUn(url, c, onp, attendu){
    const r = await fetch(url, { cache:'no-store' });
    if (!r.ok) throw new Error('Téléchargement refusé (' + r.status + ')');
    const total = Number(r.headers.get('Content-Length')) || attendu || 0;
    if (!r.body || !r.body.getReader){ const b = await r.blob(); await c.put(url, new Response(b)); onp && onp(b.size, total || b.size); return b.size; }
    const rd = r.body.getReader(), parts = []; let n = 0;
    for (;;){ const { done, value } = await rd.read(); if (done) break; parts.push(value); n += value.length; onp && onp(n, total); }
    const b = new Blob(parts, { type: r.headers.get('Content-Type') || 'application/octet-stream' });
    await c.put(url, new Response(b, { headers:{ 'Content-Type': b.type, 'Content-Length': String(b.size) } }));
    return b.size;
  }
  async function telechargerMoteur(onp){
    const c = await ouvrir(); let fait = 0; const tailles = [5e3, 143e3, 10.6e6, 121e3, 635e3, 18.1e6], tot = tailles.reduce((a, b) => a + b, 0);
    for (let i = 0; i < MOTEUR.length; i++){
      const u = MOTEUR[i];
      if (await present(u)){ fait += tailles[i]; onp && onp(fait, tot); continue; }
      const avant = fait;
      const r = await fetch(u + '?v=' + VER, { cache:'no-store' }); if (!r.ok) throw new Error('Moteur introuvable (' + r.status + ')');
      const b = await r.blob(); await c.put(u, new Response(b)); fait = avant + tailles[i]; onp && onp(fait, tot);
    }
  }
  async function persister(){ try { if (navigator.storage && navigator.storage.persist) await navigator.storage.persist(); } catch (e) {} }
  /* Télécharge une voix (et le moteur la première fois). onp(fraction 0..1, texte). */
  async function telecharger(id, onp){
    const cat = await lireCatalogue(), v = cat.find(x => x.id === id); if (!v) throw new Error('Voix inconnue');
    if (!cacheOK()) throw new Error('Ce navigateur ne peut pas garder de voix');
    await persister();
    const voixMo = v.mo || 60, totMo = (await moteurPresent() ? 0 : MOTEUR_MO) + voixMo;
    let fMo = 0;
    if (!(await moteurPresent())){
      await telechargerMoteur((n, t) => { fMo = MOTEUR_MO * n / t; onp && onp(fMo / totMo, 'Moteur de voix'); });
    }
    const c = await ouvrir(), f = fichiers(v), d0 = fMo;
    await telechargerUn(f.config, c);
    await telechargerUn(f.model, c, (n, t) => { onp && onp((d0 + (t ? voixMo * n / t : 0)) / totMo, v.nom); }, voixMo * 1e6);
    onp && onp(1, 'Terminé');
    return true;
  }
  async function effacer(id){
    const cat = await lireCatalogue(), v = cat.find(x => x.id === id); if (!v) return;
    const c = await ouvrir(), f = fichiers(v);
    /* plusieurs voix peuvent partager un fichier (même modèle, voix différentes) */
    const autres = (await etat()).voix.filter(x => x !== id).map(x => cat.find(y => y.id === x)).filter(y => y && y.onnx === v.onnx);
    if (!autres.length){ await c.delete(f.model); await c.delete(f.config); }
    if (charge && charge.split('#')[0] === v.onnx){ charge = ''; arreterWorker(); }
  }
  async function effacerMoteur(){ const c = await ouvrir(); for (const u of MOTEUR) await c.delete(u); arreterWorker(); }
  async function effacerTout(){ try { await caches.delete(CACHE); } catch (e) {} arreterWorker(); }
  async function place(){ try { const e = await navigator.storage.estimate(); return { utilise: e.usage || 0, libre: Math.max(0, (e.quota || 0) - (e.usage || 0)) }; } catch (e) { return null; } }

  /* ---------- Le moteur de synthèse (dans un « worker », pour ne pas figer l'écran) ---------- */
  function arreterWorker(){ if (worker){ try { worker.terminate(); } catch (e) {} } worker = null; charge = ''; attente.forEach(p => p.ko(new Error('arrêt'))); attente.clear(); }
  async function lancerWorker(){
    if (worker) return worker;
    const c = await ouvrir(); let r = await c.match(MOTEUR[0]);
    if (!r) r = await fetch(MOTEUR[0] + '?v=' + VER);
    if (!r || !r.ok) throw new Error('Moteur absent');
    if (wurl) URL.revokeObjectURL(wurl);
    wurl = URL.createObjectURL(new Blob([await r.text()], { type:'text/javascript' }));
    worker = new Worker(wurl);
    worker.onmessage = e => { const m = e.data || {}, p = attente.get(m.n); if (!p) return; attente.delete(m.n); if (m.type === 'erreur') p.ko(new Error(m.message)); else p.ok(m); };
    worker.onerror = () => { const w = worker; worker = null; charge = ''; attente.forEach(p => p.ko(new Error('Le moteur de voix s\'est arrêté'))); attente.clear(); try { w && w.terminate(); } catch (e) {} };
    return worker;
  }
  function envoyer(msg){
    return lancerWorker().then(w => new Promise((ok, ko) => { const n = ++nMsg; attente.set(n, { ok, ko }); w.postMessage(Object.assign({ n, base, cache:CACHE }, msg)); }));
  }
  async function preparer(id){
    const cat = await lireCatalogue(), v = cat.find(x => x.id === id); if (!v) throw new Error('Voix inconnue');
    const f = fichiers(v), cle = v.onnx;
    if (charge !== cle){ await envoyer({ type:'charger', id:cle, model:f.model, config:f.config }); charge = cle; }
    return v;
  }
  function wav(pcm, rate){
    const n = pcm.length, dv = new DataView(new ArrayBuffer(44 + n * 2));
    const s = (o, t) => { for (let i = 0; i < t.length; i++) dv.setUint8(o + i, t.charCodeAt(i)); };
    s(0, 'RIFF'); dv.setUint32(4, 36 + n * 2, true); s(8, 'WAVE'); s(12, 'fmt '); dv.setUint32(16, 16, true); dv.setUint16(20, 1, true); dv.setUint16(22, 1, true);
    dv.setUint32(24, rate, true); dv.setUint32(28, rate * 2, true); dv.setUint16(32, 2, true); dv.setUint16(34, 16, true); s(36, 'data'); dv.setUint32(40, n * 2, true);
    let o = 44; for (let i = 0; i < n; i++){ const x = Math.max(-1, Math.min(1, pcm[i])); dv.setInt16(o, x < 0 ? x * 0x8000 : x * 0x7FFF, true); o += 2; }
    return new Blob([dv.buffer], { type:'audio/wav' });
  }
  /* Fabrique l'audio d'un texte. lent : 1 = normal, 0.8 = plus rapide. */
  const memo = new Map();
  async function fabriquer(id, text, opt){
    opt = opt || {};
    const v = await preparer(id);
    const spk = opt.speaker != null ? opt.speaker : (v.speaker || 0);
    const cle = id + '|' + spk + '|' + (opt.lent || 1) + '|' + text;
    if (memo.has(cle)) return memo.get(cle);
    const p = envoyer({ type:'dire', id:v.onnx, text, lent:opt.lent || 1, speaker:spk }).then(m => ({ blob: wav(m.pcm, m.rate), dur: m.pcm.length / m.rate, ms: m.ms }));
    memo.set(cle, p); if (memo.size > 12) memo.delete(memo.keys().next().value);
    p.catch(() => memo.delete(cle));
    return p;
  }
  function audio(){ if (!au){ au = new Audio(); au.preload = 'auto'; } return au; }
  /* Lit un texte ; fin() à la fin, err(e) en cas de souci. Rend un numéro pour arrêter. */
  function dire(id, text, opt, fin, err){
    const tk = ++jeton, a = audio();
    fabriquer(id, text, opt).then(r => {
      if (tk !== jeton) return;
      const url = URL.createObjectURL(r.blob);
      a.onended = () => { URL.revokeObjectURL(url); if (tk === jeton) fin && fin(); };
      a.onerror = () => { URL.revokeObjectURL(url); if (tk === jeton) err && err(new Error('lecture')); };
      a.src = url; try { a.playbackRate = 1; } catch (e) {}
      const p = a.play(); if (p && p.catch) p.catch(e => { if (tk === jeton) err && err(e); });
      opt && opt.onstart && opt.onstart(r);
    }).catch(e => { if (tk === jeton) err && err(e); });
    return tk;
  }
  function stop(){ jeton++; if (au){ try { au.pause(); } catch (e) {} au.removeAttribute('src'); try { au.load(); } catch (e) {} } }
  /* Petit test : temps de fabrication / durée de l'audio (moins de 1 = assez rapide pour lire sans pause). */
  async function tester(id){
    const t = 'Bonjour, voici la météo du matin et les dernières découvertes de la science.';
    const r = await fabriquer(id, t + ' ', {});
    return { ratio: r.ms / 1000 / Math.max(0.1, r.dur), ms: r.ms, dur: r.dur };
  }
  function exemple(v){ return v && v.ech ? ECHANT + v.ech : ''; }
  window.VoixPiper = { arreter: arreterWorker, lireCatalogue, etat, telecharger, effacer, effacerMoteur, effacerTout, place, preparer, fabriquer, dire, stop, tester, exemple, moteurPresent, MOTEUR_MO, audio };
})();
