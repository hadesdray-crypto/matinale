/* Matinale des Sciences : l'appli s'ouvre toujours, même sans aucun réseau.
   - La première ouverture (avec internet) garde dans le téléphone la page, les polices, les icônes et la dernière édition.
   - Ensuite, le réseau est essayé d'abord pour avoir l'édition du jour, mais jamais plus de quelques secondes :
     sans réseau, ou s'il capte mal, l'appli s'ouvre aussitôt avec la copie gardée dans le téléphone.
   - Les 7 éditions précédentes et toutes celles déjà ouvertes restent lisibles hors ligne (60 au plus).
   - L'audio (mp3) n'est gardé que si l'utilisateur le demande (bouton « Garder l'audio ») : les 7 derniers jours restent
     dans le téléphone, les plus anciens sont supprimés. Sinon, sans réseau, la voix du téléphone lit l'édition.
   - Les images libres de droits des fiches sont gardées 8 jours. */
const APPLI = 'matinale-appli-2';      // à changer quand la liste des fichiers de l'appli change
const AUDIO = 'matinale-audio';        // audio gardé à la demande : les 7 derniers jours seulement
const IMAGES = 'matinale-images';      // images libres de droits des fiches : les 8 derniers jours
const JOURS_AUDIO = 7;
const JOURS_IMAGES = 8;
const DONNEES = 'matinale-donnees';    // éditions gardées : ce cache survit aux mises à jour de l'appli
const POLICES = [
  'syne-latin-600-normal', 'syne-latin-700-normal', 'syne-latin-800-normal',
  'spectral-latin-400-normal', 'spectral-latin-600-normal', 'spectral-latin-700-normal', 'spectral-latin-400-italic',
  'dm-mono-latin-400-normal', 'dm-mono-latin-500-normal'
].map(n => './fonts/' + n + '.woff2');
const FICHIERS = ['./manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png', './icons/maskable-512.png', './icons/apple-touch-icon.png'].concat(POLICES);
const ATTENTE_PAGE = 2500;        // au-delà (en millisecondes), on ouvre la copie du téléphone
const ATTENTE_DONNEES = 3000;
const ATTENTE_RESEAU_LENT = 700;  // quand le réseau vient de traîner, on n'attend presque plus
const ABANDON = 15000;            // sans copie dans le téléphone, on n'attend pas le réseau plus longtemps
const EDITIONS_AVANCE = 7;
const EDITIONS_MAX = 60;

const ici = p => new URL(p, self.registration.scope).href;
const RACINE = new URL(self.registration.scope).pathname;
const LATEST = ici('./data/latest.json');
const REPERE = ici('./data/.editions-gardees');
let lentJusqua = 0;               // le réseau a traîné il y a moins de 30 s

self.addEventListener('install', e => {
  e.waitUntil((async () => {
    const appli = await caches.open(APPLI);
    await appli.add(new Request('./', { cache: 'reload' }));   // indispensable : sinon l'installation sera refaite à la prochaine ouverture
    await Promise.all(FICHIERS.map(u => appli.add(new Request(u, { cache: 'reload' })).catch(() => {})));
    try {
      const rep = await fetch(LATEST, { cache: 'no-store' });
      if (rep.ok) {
        await (await caches.open(DONNEES)).put(LATEST, rep.clone());
        await editionsDAvance(await rep.json());
      }
    } catch (err) { /* pas grave : la page la gardera à sa prochaine lecture */ }
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', e => {
  e.waitUntil((async () => {
    const donnees = await caches.open(DONNEES);
    for (const nom of await caches.keys()) {
      if (nom === APPLI || nom === DONNEES || nom === AUDIO || nom === IMAGES || !nom.startsWith('matinale-')) continue;
      // Reprend les éditions gardées par une version précédente de l'appli, puis jette l'ancienne version.
      const ancien = await caches.open(nom);
      for (const req of await ancien.keys()) {
        if (!/\/data\/.+\.json$/.test(new URL(req.url).pathname) || await donnees.match(req, { ignoreSearch: true })) continue;
        const rep = await ancien.match(req);
        if (rep) await donnees.put(req.url.split('?')[0], rep);
      }
      await caches.delete(nom);
    }
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET' || !req.url.startsWith(self.registration.scope)) return;   // vidéos, liens externes : le navigateur s'en charge
  const chemin = new URL(req.url).pathname;
  if (/\/(voix|vendor)\//.test(chemin)) return;   // voix hors connexion : gardée à part par l'appli (cache « matinale-voix »)
  if (/\/img\/\d{4}-\d{2}-\d{2}\//.test(chemin)) return imageGarde(e);                     // images du jour : copie du téléphone d'abord
  if (chemin.endsWith('.mp3')) return audioGarde(e);                                    // audio : la copie gardée d'abord, sinon le réseau
  if (/\/audio\/index\/\d{4}-\d{2}-\d{2}\.json$/.test(chemin)) return audioIndexJour(e);
  if (chemin.endsWith('/audio/audio.json')) return audioIndex(e);
  if (req.mode === 'navigate') {
    if (chemin === RACINE || chemin === RACINE + 'index.html') reseauSinonCopie(e, APPLI, ATTENTE_PAGE, ici('./'));
    return;
  }
  if (/\/data\/.+\.json$/.test(chemin)) return reseauSinonCopie(e, DONNEES, ATTENTE_DONNEES, req.url.split('?')[0]);
  if (/\/(fonts|icons)\//.test(chemin)) return copieDAbord(e);
  reseauSinonCopie(e, APPLI, ATTENTE_PAGE, req.url.split('?')[0]);
});

/* Le réseau d'abord, mais pas plus de quelques secondes ; sinon la copie du téléphone.
   Si le réseau finit par répondre, la copie est mise à jour (et la page prévenue pour l'édition du jour). */
function reseauSinonCopie(e, nomCache, attente, cle) {
  const req = e.request;
  let repondu = false, repondre;
  const reponse = new Promise(r => { repondre = r; });
  const donner = rep => { if (!repondu) { repondu = true; repondre(rep); } };
  const copie = () => caches.open(nomCache).then(c => c.match(cle, { ignoreSearch: true })).catch(() => undefined);
  const delai = Date.now() < lentJusqua ? Math.min(attente, ATTENTE_RESEAU_LENT) : attente;
  const minuteur = setTimeout(() => copie().then(rep => { if (rep) { lentJusqua = Date.now() + 30000; donner(marquer(rep)); } }), delai);
  const abandon = req.mode === 'navigate' ? null : setTimeout(() => donner(Response.error()), ABANDON);
  const reseau = fetch(req).then(async rep => {
    clearTimeout(minuteur); clearTimeout(abandon);
    const tard = repondu;
    if (!tard) lentJusqua = 0;
    const garder = rep.ok && rep.type === 'basic' && !rep.redirected ? rep.clone() : null;
    const lire = garder && cle === LATEST ? rep.clone() : null;
    donner(rep);
    if (!garder) return;
    await (await caches.open(nomCache)).put(cle, garder);
    if (lire) {
      if (tard) await prevenir('maj');
      const json = await lire.json().catch(() => null);
      if (json) await editionsDAvance(json);
    }
  }, async () => {
    clearTimeout(minuteur); clearTimeout(abandon);
    const rep = await copie();
    donner(rep ? marquer(rep) : Response.error());
  });
  e.respondWith(reponse);
  e.waitUntil(reseau.catch(() => {}));
}

/* Polices et icônes ne changent pas : la copie du téléphone d'abord. */
function copieDAbord(e) {
  const req = e.request;
  e.respondWith(caches.match(req, { ignoreSearch: true }).then(hit => hit || fetch(req).then(rep => {
    if (rep.ok && rep.type === 'basic') { const c = rep.clone(); e.waitUntil(caches.open(APPLI).then(x => x.put(req, c)).catch(() => {})); }
    return rep;
  })));
}

/* Signale à la page qu'elle lit la copie gardée dans le téléphone. */
function marquer(rep) {
  const h = new Headers(rep.headers);
  h.set('X-Matinale-Copie', '1');
  return new Response(rep.body, { status: rep.status, statusText: rep.statusText, headers: h });
}

async function prevenir(type) {
  for (const c of await self.clients.matchAll({ type: 'window' })) c.postMessage({ type });
}

/* Une fois par nouvelle édition : garde les 7 précédentes (la veille est toujours reprise, elle a pu changer dans la journée). */
async function editionsDAvance(latest) {
  const donnees = await caches.open(DONNEES);
  const jour = latest && latest.edition && String(latest.edition.date || '');
  const deja = await donnees.match(REPERE);
  if (!jour || (deja && (await deja.text()) === jour)) return;
  const dates = (Array.isArray(latest.archive) ? latest.archive : [])
    .map(a => String((a && a.date) || '')).filter(d => /^\d{4}-\d{2}-\d{2}$/.test(d) && d !== jour)
    .sort().reverse().slice(0, EDITIONS_AVANCE);
  for (let i = 0; i < dates.length; i++) {
    const url = ici('./data/editions/' + dates[i] + '.json');
    if (i > 0 && await donnees.match(url)) continue;
    try {
      const rep = await fetch(url, { cache: 'no-store' });
      if (rep.ok) await donnees.put(url, rep);
    } catch (err) { return; }   // plus de réseau : on reprendra à la prochaine édition
  }
  await donnees.put(REPERE, new Response(jour));
  const eds = (await donnees.keys()).filter(r => /\/data\/editions\/\d{4}-\d{2}-\d{2}\.json$/.test(r.url))
    .sort((a, b) => b.url.localeCompare(a.url));
  await Promise.all(eds.slice(EDITIONS_MAX).map(r => donnees.delete(r)));
}


/* ---------- Audio gardé dans le téléphone (à la demande, 7 derniers jours) ---------- */
const jourDe = url => { const m = /\/(\d{4}-\d{2}-\d{2})(?:\/|\.json$)/.exec(url); return m ? m[1] : ''; };

self.addEventListener('message', e => {
  const d = e.data || {};
  if (d.type === 'audio-garder') e.waitUntil(garderAudio(Array.isArray(d.urls) ? d.urls : [], String(d.date || '')));
  else if (d.type === 'audio-effacer') e.waitUntil(caches.delete(AUDIO).then(() => prevenirAudio()));
  else if (d.type === 'audio-etat') e.waitUntil(prevenirAudio());
});

async function etatAudio(erreur) {
  const c = await caches.open(AUDIO);
  let bytes = 0;
  const srcs = [];
  for (const r of await c.keys()) {
    if (/\.mp3$/.test(r.url)) {
      const rep = await c.match(r);
      if (rep) bytes += (await rep.blob()).size;
      srcs.push(new URL(r.url).pathname.slice(RACINE.length));
    }
  }
  const indexes = [];
  for (const r of await c.keys()) if (/\/audio\/index\/\d{4}-\d{2}-\d{2}\.json$/.test(r.url)) indexes.push(jourDe(r.url));
  indexes.sort();
  return { type: 'audio-etat', date: indexes.length ? indexes[indexes.length - 1] : '', dates: indexes, bytes, srcs, erreur: erreur || '' };
}

async function prevenirAudio(erreur) {
  const msg = await etatAudio(erreur);
  for (const c of await self.clients.matchAll({ type: 'window' })) c.postMessage(msg);
}

/* Télécharge les enregistrements du jour, puis ne garde que les 7 derniers jours. */
async function garderAudio(urls, date) {
  const c = await caches.open(AUDIO);
  let complet = true;
  for (const u of new Set(urls.map(x => ici(x)))) {
    if (await c.match(u)) continue;
    try {
      const rep = await fetch(u, { cache: 'no-store' });
      if (!rep.ok) { complet = false; continue; }
      await c.put(u, rep);
    } catch (err) { complet = false; break; }
  }
  try {
    const rep = await fetch(ici('./audio/audio.json'), { cache: 'no-store' });
    if (rep.ok) {
      const jour = (await rep.clone().json().catch(() => ({}))).date || date;
      if (/^\d{4}-\d{2}-\d{2}$/.test(jour)) await c.put(ici('./audio/index/' + jour + '.json'), rep);
    } else complet = false;
  } catch (err) { complet = false; }
  if (complet) await elaguerAudio(c);
  await prevenirAudio(complet ? '' : 'incomplet');
}

async function elaguerAudio(c) {
  const jours = new Set();
  for (const r of await c.keys()) { const j = jourDe(r.url); if (j) jours.add(j); }
  const gardes = new Set([...jours].sort().reverse().slice(0, JOURS_AUDIO));
  for (const r of await c.keys()) { const j = jourDe(r.url); if (j && !gardes.has(j)) await c.delete(r); }
}

/* Un enregistrement gardé est servi par morceaux (Range), comme le réseau le ferait : la lecture et l'avance rapide marchent. */
function audioGarde(e) {
  const req = e.request;
  e.respondWith((async () => {
    const hit = await (await caches.open(AUDIO)).match(req.url.split('?')[0]);
    if (!hit) return fetch(req);
    const range = req.headers.get('Range');
    if (!range) return hit;
    const buf = await hit.arrayBuffer();
    const total = buf.byteLength;
    const m = /bytes=(\d*)-(\d*)/.exec(range);
    let debut = 0, fin = total - 1;
    if (m && m[1] !== '') { debut = parseInt(m[1], 10); if (m[2] !== '') fin = Math.min(parseInt(m[2], 10), total - 1); }
    else if (m && m[2] !== '') debut = Math.max(0, total - parseInt(m[2], 10));
    if (debut > fin || debut >= total) return new Response(null, { status: 416, headers: { 'Content-Range': 'bytes */' + total } });
    return new Response(buf.slice(debut, fin + 1), { status: 206, headers: {
      'Content-Type': 'audio/mpeg', 'Content-Length': String(fin - debut + 1),
      'Content-Range': 'bytes ' + debut + '-' + fin + '/' + total, 'Accept-Ranges': 'bytes' } });
  })());
}

/* La liste du jour : le réseau d'abord ; sans réseau, la plus récente liste gardée. */
function audioIndex(e) {
  const req = e.request;
  e.respondWith(fetch(req).catch(async () => {
    const c = await caches.open(AUDIO);
    const idx = (await c.keys()).map(r => r.url).filter(u => /\/audio\/index\/\d{4}-\d{2}-\d{2}\.json$/.test(u)).sort();
    return idx.length ? c.match(idx[idx.length - 1]) : Response.error();
  }));
}
/* La liste d'un jour précédent n'existe que dans le téléphone. */
function audioIndexJour(e) {
  e.respondWith((async () => (await (await caches.open(AUDIO)).match(e.request.url.split('?')[0])) || new Response('', { status: 404 }))());
}

/* ---------- Images des fiches (libres de droits) : la copie du téléphone d'abord, 8 derniers jours ---------- */
function imageGarde(e) {
  const req = e.request;
  e.respondWith((async () => {
    const c = await caches.open(IMAGES);
    const hit = await c.match(req.url.split('?')[0]);
    if (hit) return hit;
    const rep = await fetch(req);
    if (rep.ok && rep.type === 'basic') {
      await c.put(req.url.split('?')[0], rep.clone());
      e.waitUntil((async () => {
        const jours = new Set((await c.keys()).map(r => jourDe(r.url)).filter(Boolean));
        const gardes = new Set([...jours].sort().reverse().slice(0, JOURS_IMAGES));
        for (const r of await c.keys()) { const j = jourDe(r.url); if (j && !gardes.has(j)) await c.delete(r); }
      })());
    }
    return rep;
  })());
}
