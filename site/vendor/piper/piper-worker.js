/* Matinale : voix téléchargeables. La synthèse Piper tourne ici, dans le téléphone, sans Internet
   (une fois la voix et le moteur gardés). Ce fichier est lancé par voix-piper.js.
   Moteur : onnxruntime-web (MIT) et piper_phonemize (MIT) avec espeak-ng (GPL-3.0, sources :
   https://github.com/espeak-ng/espeak-ng, https://github.com/rhasspy/piper-phonemize). */
let BASE = '', CACHE = 'matinale-voix-piper', phon = null, phonOut = null, sess = null, cfg = null, cur = '', pret = null;
async function fichier(url){
  try { const c = await caches.open(CACHE), r = await c.match(url); if (r) return r; } catch (e) {}
  const r = await fetch(url); if (!r.ok) throw new Error('Fichier introuvable (' + r.status + ')'); return r;
}
async function moteur(){
  if (pret) return pret;
  pret = (async () => {
    const [ortJs, phJs, ortWasm, phWasm, phData] = await Promise.all([
      fichier(BASE + 'ort.wasm.min.js').then(r => r.blob()), fichier(BASE + 'piper_phonemize.js').then(r => r.blob()),
      fichier(BASE + 'ort-wasm-simd.wasm').then(r => r.blob()), fichier(BASE + 'piper_phonemize.wasm').then(r => r.arrayBuffer()),
      fichier(BASE + 'piper_phonemize.data').then(r => r.arrayBuffer())]);
    importScripts(URL.createObjectURL(ortJs), URL.createObjectURL(phJs));
    const w = URL.createObjectURL(new Blob([ortWasm], { type:'application/wasm' }));
    ort.env.wasm.numThreads = 1; ort.env.wasm.proxy = false;
    ort.env.wasm.wasmPaths = { 'ort-wasm-simd.wasm': w, 'ort-wasm.wasm': w, 'ort-wasm-simd-threaded.wasm': w, 'ort-wasm-threaded.wasm': w };
    phon = { wasm: phWasm, data: phData, mod: null };
  })();
  try { await pret; } catch (e) { pret = null; throw e; }
}
async function phonModule(){
  if (phon.mod) return phon.mod;
  phon.mod = await createPiperPhonemize({
    wasmBinary: phon.wasm,
    getPreloadedPackage: () => phon.data.slice(0),
    print: l => { if (phonOut) phonOut.push(l); },
    printErr: () => {},
    locateFile: f => BASE + f
  });
  return phon.mod;
}
async function phonemes(text){
  for (let essai = 0; essai < 2; essai++){
    const m = await phonModule(); phonOut = [];
    try {
      m.callMain(['-l', (cfg.espeak && cfg.espeak.voice) || 'fr', '--input', JSON.stringify([{ text }]), '--espeak_data', '/espeak-ng-data']);
      const out = phonOut; phonOut = null;
      const ids = []; out.forEach(l => { try { const j = JSON.parse(l); if (j && j.phoneme_ids) ids.push(...j.phoneme_ids); } catch (e) {} });
      if (ids.length) return ids;
    } catch (e) { phonOut = null; }
    phon.mod = null;   /* le module ne repart pas : on en recrée un */
  }
  throw new Error('Texte illisible pour cette voix');
}
async function charger(m){
  await moteur();
  if (cur === m.id && sess) return;
  sess = null; cur = '';
  cfg = await (await fichier(m.config)).json();
  const buf = await (await fichier(m.model)).arrayBuffer();
  sess = await ort.InferenceSession.create(buf, { executionProviders:['wasm'], graphOptimizationLevel:'all' });
  cur = m.id;
}
async function dire(m){
  if (!sess || cur !== m.id) await charger(m);
  const t0 = performance.now();
  const ids = await phonemes(m.text);
  const big = a => BigInt64Array.from(a.map(x => BigInt(x)));
  const inf = cfg.inference || {};
  const feeds = {
    input: new ort.Tensor('int64', big(ids), [1, ids.length]),
    input_lengths: new ort.Tensor('int64', big([ids.length]), [1]),
    scales: new ort.Tensor('float32', Float32Array.from([inf.noise_scale != null ? inf.noise_scale : 0.667, (inf.length_scale || 1) * (m.lent || 1), inf.noise_w != null ? inf.noise_w : 0.8]), [3])
  };
  if ((cfg.num_speakers || 0) > 1) feeds.sid = new ort.Tensor('int64', big([m.speaker || 0]), [1]);
  const out = await sess.run(feeds);
  const pcm = new Float32Array(out.output.data);
  return { pcm, rate: (cfg.audio && cfg.audio.sample_rate) || 22050, ms: Math.round(performance.now() - t0) };
}
self.onmessage = async e => {
  const m = e.data || {};
  if (m.base) BASE = m.base;
  if (m.cache) CACHE = m.cache;
  try {
    if (m.type === 'charger'){ await charger(m); self.postMessage({ type:'pret', n:m.n, id:m.id }); }
    else if (m.type === 'dire'){ const r = await dire(m); self.postMessage({ type:'audio', n:m.n, pcm:r.pcm, rate:r.rate, ms:r.ms }, [r.pcm.buffer]); }
  } catch (err) { self.postMessage({ type:'erreur', n:m.n, message:String(err && err.message || err) }); }
};
