#!/usr/bin/env python3
"""Fabrique « Mon Assistant » (version client, sans les infos) à partir du code de la Matinale.
Usage : python3 scripts/build_assistant.py SORTIE
La Matinale n'est jamais modifiée. Les deux produits restent séparés : autre nom, autres données dans le téléphone
(préfixe « ast. »), autre cache hors ligne, aucun fichier d'infos, d'audio ni de vidéos."""
import json, os, re, shutil, sys

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'site')
OUT = sys.argv[1] if len(sys.argv) > 1 else 'assistant-site'
misses = []

def sub(s, old, new, count=1, regex=False):
    if regex:
        r, n = re.subn(old, new, s, count=0 if count == 0 else count, flags=re.S)
        if n == 0: misses.append(old[:70])
        return r
    if old not in s:
        misses.append(old[:70]); return s
    return s.replace(old, new) if count == 0 else s.replace(old, new, count)

html = open(os.path.join(SRC, 'index.html'), encoding='utf-8').read()

# --- identité
html = sub(html, '<meta name="apple-mobile-web-app-title" content="Matinale">', '<meta name="apple-mobile-web-app-title" content="Assistant">')
html = sub(html, '<title>Matinale des Sciences</title>', '<title>Mon Assistant</title>')
html = sub(html, re.search(r'<meta name="description" content="[^"]*">', html).group(0),
           '<meta name="description" content="Ton assistant personnel : trajets de la semaine à la voix, rendez-vous, météo, alerte de départ en cas de bouchons. Tout reste sur ton téléphone.">')
html = sub(html, 'aria-label="Matinale des Sciences, accueil"', 'aria-label="Mon Assistant, accueil"')
html = sub(html, '<span class="brand-name">Matinale<span class="brand-sub">des Sciences</span></span>', '<span class="brand-name">Assistant<span class="brand-sub">personnel</span></span>')

# --- menus : quatre entrées, claires
top = ('<nav class="top-nav" aria-label="Sections">\n'
       '      <button data-action="tab" data-tab="aujourdhui">Aujourd\'hui</button>\n'
       '      <button data-action="ag-open">Agenda</button>\n'
       '      <button data-action="m-iti">Itinéraire</button>\n'
       '      <button data-action="options">Réglages</button>\n'
       '    </nav>')
html = sub(html, r'<nav class="top-nav" aria-label="Sections">.*?</nav>', top, regex=True)
html = sub(html, '<style>', '<style>\n.fluxbar,.edpill,.hdr-fav{display:none!important}\n', 1)

# --- données du téléphone : préfixe propre au produit
html = html.replace("'mds.", "'ast.").replace('"mds.', '"ast.')
html = sub(html, "const APP_V = 7;", "const APP_V = 1;")

# --- onglets
html = sub(html, "const TABS = ['aujourdhui','videos','franco','ecouter','categories','comprendre','favoris'];", "const TABS = ['aujourdhui'];")
html = sub(html, "const NAV_TABS = TABS.filter(x => x !== 'favoris');", "const NAV_TABS = TABS;")
tabbar_old = re.search(r"\$\('#tabbar'\)\.innerHTML = NAV_TABS\.map\(.*?\)\.join\(''\);", html, re.S).group(0)
tabbar_new = ("$('#tabbar').innerHTML = [['tab','aujourdhui','today',\"Aujourd'hui\"],['ag-open','','calendar','Agenda'],['m-iti','','car','Itinéraire'],['options','','gear','Réglages']]"
              ".map(x => '<button data-action=\"' + x[0] + '\"' + (x[1] ? ' data-tab=\"' + x[1] + '\"' : '') + ' aria-current=\"false\">' + icon(x[2], 22) + '<span>' + esc(x[3]) + '</span></button>').join('');")
html = html.replace(tabbar_old, tabbar_new)

# --- écran « Aujourd'hui » : météo et route, agenda, programme de demain ; pas d'édition
html = sub(html, "  const ed = S.edition;\n  if (S.status !== 'ready' || !ed){ el.innerHTML = stateHTML(); return; }",
           "  el.innerHTML = matinCardHTML() + agCardHTML() + installBannerHTML();\n  return;\n  const ed = S.edition;\n  if (S.status !== 'ready' || !ed){ el.innerHTML = stateHTML(); return; }")
html = sub(html, "  if (S.sec === 'pol'){ if (!S.pol && !S.polLoading) loadPol(); el.innerHTML = matinCardHTML() + polViewHTML(); return; }\n", "")

# --- démarrage : rien à charger côté infos
html = sub(html, r"  setTab\(nid \? 'comprendre' : \(TABS\.includes\(h\) \? h : 'aujourdhui'\), \{ scroll:false \}\);\n  navInit\(\); mediaInit\(\);\n.*?loadAudioIndex\(\); setTimeout\(loadPol, 1200\);\n",
           "  S.status = 'ready'; S.fallback = false;\n  setTab('aujourdhui', { scroll:false });\n  navInit(); mediaInit();\n", regex=True)
html = sub(html, "  loadFallback(true); registerSW(); watchUpdates(); return;", "  registerSW(); watchUpdates(); return;")
html = sub(html, "      if (!S.pol || Date.now() - (S.pol.at || 0) > 30 * 60000) loadPol();\n", "")

# --- le point du matin : météo, route, agenda (pas d'infos)
html = sub(html, "infos:'sci,ask', v:2 };", "infos:'', v:2 };")
html = sub(html, "if (o.v !== 2){ o.infos = 'sci,ask'; o.v = 2; }", "if (o.v !== 2){ o.infos = ''; o.v = 2; }")
html = sub(html, "String(MPget().infos || 'sci,ask')", "String(MPget().infos || '')")
html = sub(html, "const MATIN_SUITE = ' Place aux informations scientifiques.';", "const MATIN_SUITE = ' Bonne journée.';")
html = sub(html, ' Écouter : météo, trajet, sciences', ' Écouter : météo, route, agenda')
html = sub(html, r"    '<section class=\"rg-sec\"><h3>Informations du matin</h3>.*?</select></label></section>' \+\n", "", regex=True)
html = sub(html, "    row('opt-fav', 'star', 'Mes favoris', 'Les découvertes que tu as gardées.') +\n", "")
html = sub(html, "Rappelés chaque matin avant les infos.", "Rappelés chaque matin, avec la météo et ta route.")
html = sub(html, "Météo, lieux, point de départ, trafic, informations du matin.", "Météo, lieux, point de départ, trafic.")
html = sub(html, "Matinale", "Assistant", count=0) if False else html
# --- vocabulaire : plus de « Matinale » ni d'informations
html = sub(html, "(?:matinale?s?|matina|matin al|ma tinale|martinale|matinee)", "(?:assistants?|assistante|assis tant|a sistant|assistance)")
html = sub(html, "bs.textContent = f === 'pol' ? 'Politique & monde' : 'des Sciences';", "bs.textContent = 'personnel';")
html = sub(html, "la Matinale te les rappelle chaque matin, avant les informations.", "l’assistant te les rappelle chaque matin, avec la météo et ta route.")
for a, b in [('La Matinale des Sciences', 'Mon Assistant'), ('la Matinale des Sciences', 'Mon Assistant'), ('Matinale des Sciences', 'Mon Assistant'),
             ('la Matinale des sciences', "l’assistant"), ('La Matinale', "L’assistant"), ('la Matinale', "l’assistant"), ('Matinale', 'Assistant')]:
    html = html.replace(a, b)
os.makedirs(OUT, exist_ok=True)
open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8').write(html)

# --- fichiers : seulement ce qu'il faut
for d in ('fonts', 'icons', 'vendor'):
    dst = os.path.join(OUT, d)
    if os.path.exists(dst): shutil.rmtree(dst)
    shutil.copytree(os.path.join(SRC, d), dst, ignore=shutil.ignore_patterns('piper', 'ocr') if d == 'vendor' else None)
for f in ('voix-piper.js',):
    shutil.copy(os.path.join(SRC, f), os.path.join(OUT, f))

man = json.load(open(os.path.join(SRC, 'manifest.webmanifest'), encoding='utf-8'))
man.update(name='Mon Assistant', short_name='Assistant', categories=['productivity', 'lifestyle'],
           description='Trajets de la semaine à la voix, rendez-vous, météo et alerte de départ. Tout reste sur ton téléphone.')
json.dump(man, open(os.path.join(OUT, 'manifest.webmanifest'), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

open(os.path.join(OUT, 'sw.js'), 'w', encoding='utf-8').write('''/* Mon Assistant : s'ouvre toujours, même sans réseau (la page et les polices sont gardées dans le téléphone). */
const APPLI = 'assistant-appli-1';      // à changer quand la liste des fichiers change
const FICHIERS = ['./', './manifest.webmanifest', './icons/icon-192.png', './icons/icon-512.png', './icons/maskable-512.png', './icons/apple-touch-icon.png',
  './fonts/syne-latin-600-normal.woff2', './fonts/syne-latin-700-normal.woff2', './fonts/syne-latin-800-normal.woff2',
  './fonts/spectral-latin-400-normal.woff2', './fonts/spectral-latin-600-normal.woff2', './fonts/spectral-latin-700-normal.woff2', './fonts/spectral-latin-400-italic.woff2',
  './fonts/dm-mono-latin-400-normal.woff2', './fonts/dm-mono-latin-500-normal.woff2'];
self.addEventListener('install', e => {
  e.waitUntil((async () => { const c = await caches.open(APPLI); await Promise.all(FICHIERS.map(u => c.add(new Request(u, { cache: 'reload' })).catch(() => {}))); await self.skipWaiting(); })());
});
self.addEventListener('activate', e => {
  e.waitUntil((async () => { for (const n of await caches.keys()) if (n.startsWith('assistant-') && n !== APPLI) await caches.delete(n); await self.clients.claim(); })());
});
self.addEventListener('fetch', e => {
  const r = e.request; if (r.method !== 'GET') return;
  const u = new URL(r.url); if (u.origin !== self.location.origin) return;       // météo, trafic : toujours en direct
  if (u.pathname.endsWith('nouveautes.json')) return;                              // la liste des nouveautés est toujours fraîche
  e.respondWith((async () => {
    const c = await caches.open(APPLI);
    try {
      const rep = await Promise.race([fetch(r), new Promise((_, no) => setTimeout(no, 3000))]);
      if (rep && rep.ok) c.put(r, rep.clone());
      return rep;
    } catch (err) { return (await c.match(r, { ignoreSearch: true })) || (await c.match('./')) || Response.error(); }
  })());
});
self.addEventListener('notificationclick', e => {
  e.notification.close();
  e.waitUntil((async () => { const l = await self.clients.matchAll({ type: 'window' }); if (l.length) return l[0].focus(); return self.clients.openWindow('./'); })());
});
''')

nv = [{"v": 1, "date": "2026-11-02", "titre": "Mon Assistant", "points": [
    "Dicte tes trajets de la semaine à la voix, vérifie-les avec l'appli, corrige dans le calendrier (semaine ou mois).",
    "Ajoute tes rendez-vous : ils te sont lus chaque matin et rappelés la veille au soir.",
    "Alerte de départ discrète : elle ne dit rien si la route est normale.",
    "Tout reste sur ton téléphone."]}]
json.dump(nv, open(os.path.join(OUT, 'nouveautes.json'), 'w', encoding='utf-8'), ensure_ascii=False, indent=2)

if misses:
    print('PATCHS NON APPLIQUÉS :'); [print(' -', m) for m in misses]; sys.exit(1)
print('OK :', OUT, round(len(html) / 1024), 'Ko')
