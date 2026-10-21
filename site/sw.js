/* Matinale des Sciences : l'appli s'ouvre toujours, même sans aucun réseau.
   - La première ouverture (avec internet) garde dans le téléphone la page, les polices, les icônes et la dernière édition.
   - Ensuite, le réseau est essayé d'abord pour avoir l'édition du jour, mais jamais plus de quelques secondes :
     sans réseau, ou s'il capte mal, l'appli s'ouvre aussitôt avec la copie gardée dans le téléphone.
   - Les 7 éditions précédentes et toutes celles déjà ouvertes restent lisibles hors ligne (60 au plus).
   - L'audio (mp3) n'est pas gardé : sans réseau, la voix du téléphone lit l'édition. */
const APPLI = 'matinale-appli-2';      // à changer quand la liste des fichiers de l'appli change
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
      if (nom === APPLI || nom === DONNEES || !nom.startsWith('matinale-')) continue;
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
  if (chemin.endsWith('.mp3') || chemin.endsWith('/audio/audio.json')) return;          // audio : seulement avec le réseau
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
