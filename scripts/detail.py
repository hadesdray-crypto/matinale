#!/usr/bin/env python3
"""Matinale des Sciences - fiche détaillée et image libre de droits.

Pour chaque fiche retenue, ce module :
  1. lit la page de l'article d'origine (texte seulement) ;
  2. demande à Gemini une fiche détaillée de 300 à 450 mots, écrite dans ses propres mots (jamais une copie) ;
  3. vérifie : un chiffre absent de l'article, une phrase recopiée de l'article ou un lien -> la phrase est retirée ;
  4. pour les sources dont les images sont libres de droits (NASA), garde une image réduite pour la lire sans réseau ;
  5. pour les autres fiches, cherche sur Wikimedia Commons une illustration à licence libre (CC0, domaine public, CC BY, CC BY-SA)
     qui évoque le sujet : elle est présentée comme « illustration », jamais comme l'image de l'article.

Tout est facultatif : si une étape échoue pour une fiche, la fiche garde simplement son résumé.
Bibliothèque standard uniquement (Pillow est utilisé pour réduire les images s'il est installé).
"""
import concurrent.futures as cf
import io
import json
import os
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser

SKIP_TAGS = {'script', 'style', 'noscript', 'nav', 'footer', 'header', 'aside', 'form', 'svg', 'iframe', 'figcaption',
             'button', 'select', 'template', 'dialog'}
BAD_PARA = re.compile(r"(cookie|abonn[ée]|newsletter|inscri[rv]|lire aussi|read more|subscribe|©|copyright|partager|share this|"
                      r"suivez|follow us|all rights|droits réservés|publicité|advertisement|sign up|log in|connexion|"
                      r"accept(er)? (all|les)|politique de confidentialit)", re.I)
NO_FETCH = re.compile(r'(youtube\.com|youtu\.be|dailymotion\.com|doi\.org|twitter\.com|x\.com|facebook\.com)')
MIN_CHARS = 900          # en dessous, la page est sans doute payante ou vide : pas de fiche détaillée
MAX_CHARS = 7000         # texte donné à Gemini par article
BATCH = 3                # articles par appel à Gemini
IMAGE_SOURCES = {'NASA': 'NASA', 'NASA (technologie)': 'NASA'}   # sources dont les images sont libres de droits
MAX_IMG_BYTES = 3_000_000
IMG_WIDTH = 960


class _Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.depth_art = 0
        self.depth_main = 0
        self.in_p = False
        self.buf = []
        self.paras = {'article': [], 'main': [], 'all': []}
        self.og = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'meta':
            key = (a.get('property') or a.get('name') or '').lower()
            if key in ('og:image', 'og:image:url', 'twitter:image') and a.get('content') and not self.og:
                self.og = a['content'].strip()
        if tag in SKIP_TAGS:
            self.skip += 1
        elif tag == 'article':
            self.depth_art += 1
        elif tag == 'main':
            self.depth_main += 1
        elif tag == 'p' and not self.skip:
            self.in_p, self.buf = True, []

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
        elif tag == 'article':
            self.depth_art = max(0, self.depth_art - 1)
        elif tag == 'main':
            self.depth_main = max(0, self.depth_main - 1)
        elif tag == 'p' and self.in_p:
            self.in_p = False
            t = re.sub(r'\s+', ' ', ''.join(self.buf)).strip()
            if len(t) >= 50 and not BAD_PARA.search(t):
                self.paras['all'].append(t)
                if self.depth_main:
                    self.paras['main'].append(t)
                if self.depth_art:
                    self.paras['article'].append(t)

    def handle_data(self, data):
        if self.in_p and not self.skip:
            self.buf.append(data)


def extract_article(data, base_url=''):
    """Renvoie {'text': ..., 'chars': n, 'image': url ou None} à partir du HTML d'une page d'article."""
    txt = data.decode('utf-8', 'replace') if isinstance(data, (bytes, bytearray)) else str(data)
    p = _Extract()
    try:
        p.feed(txt)
        p.close()
    except Exception:  # noqa: BLE001 - HTML cassé : on garde ce qui a été lu
        pass
    paras = []
    for k in ('article', 'main', 'all'):
        if len(p.paras[k]) >= 3 and sum(map(len, p.paras[k])) >= 600:
            paras = p.paras[k]
            break
    seen, out = set(), []
    for t in paras:
        if t not in seen:
            seen.add(t)
            out.append(t)
    text = '\n'.join(out)
    img = urllib.parse.urljoin(base_url, p.og) if p.og else None
    return {'text': text, 'chars': len(text), 'image': img}


def _ngrams(s, n=10):
    w = re.findall(r"[a-z0-9àâäçéèêëîïôöùûüœ']+", s.lower())
    return {' '.join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}


PROMPT = """Tu es le rédacteur scientifique de « La Matinale des Sciences », sérieux et sans erreur, pour le grand public francophone.

Pour chaque ARTICLE ci-dessous (texte intégral fourni), écris une FICHE DÉTAILLÉE en français :
- "detail" : 4 à 6 paragraphes (300 à 450 mots au total) écrits dans TES PROPRES MOTS. Ne recopie jamais de phrases de l'article.
  Explique : le contexte, ce qui a été fait ou trouvé, les chiffres clés, la méthode si elle est indiquée, les limites, ce que cela change.
- "points_cles" : 3 à 5 phrases courtes qui résument l'essentiel.

RÈGLES ABSOLUES :
- N'utilise que les informations présentes dans le texte de l'article. N'invente aucun chiffre, nom, date, revue, institution ou citation.
- Une corrélation n'est jamais présentée comme une cause. Pas de lien internet. Pas d'opinion personnelle.
- Traduis fidèlement les articles en anglais ; garde les chiffres tels quels.

Réponds uniquement avec ce JSON :
{{"fiches": [{{"ref": "d1", "detail": ["paragraphe 1", "paragraphe 2"], "points_cles": ["...", "..."]}}]}}

ARTICLES :
{articles}
"""


def _shorten(s, n):
    return s if len(s) <= n else s[:n].rsplit(' ', 1)[0] + '…'


def write_details(batch, key, gemini_call, helpers, stats):
    """batch : liste de (item, page). Remplit item['detail'] et item['keyPoints'] quand la vérification passe."""
    number_set, numbers_ok, sentences = helpers
    arts = [{'ref': f'd{i + 1}', 'source': it['_src']['source'], 'langue': it['_src']['lang'], 'titre': it['_src']['title'],
             'texte': _shorten(pg['text'], MAX_CHARS)} for i, (it, pg) in enumerate(batch)]
    prompt = PROMPT.format(articles='\n'.join(json.dumps(a, ensure_ascii=False) for a in arts))
    res, _model = gemini_call(prompt, key)
    if not isinstance(res, dict):
        return 0
    done = 0
    by_ref = {a['ref']: (it, pg) for a, (it, pg) in zip(arts, batch)}
    for f in res.get('fiches') or []:
        if not isinstance(f, dict) or f.get('ref') not in by_ref:
            continue
        it, pg = by_ref[f['ref']]
        c = it['_src']
        allowed = number_set(c['title'] + ' ' + c['summary'] + ' ' + pg['text'], variants=True) | {str(c['date'].year), str(c['date'].day)}
        grams = _ngrams(pg['text'])
        removed = {'n': 0}

        def good(sent):
            if re.search(r'https?://|www\.', sent) or not numbers_ok(sent, allowed) or (_ngrams(sent) & grams):
                removed['n'] += 1
                return False
            return True
        paras = []
        for p in (f.get('detail') or []):
            if isinstance(p, str) and 0 < len(p.strip()) <= 1400:
                kept = ' '.join(s for s in sentences(p.strip()) if good(s))
                if kept:
                    paras.append(kept)
        points = [x.strip() for x in (f.get('points_cles') or []) if isinstance(x, str) and 0 < len(x.strip()) <= 260 and good(x.strip())][:5]
        stats['detail_sentences_removed'] = stats.get('detail_sentences_removed', 0) + removed['n']
        if len(paras) >= 3 and sum(map(len, paras)) >= 700:
            it['detail'] = paras[:7]
            if points:
                it['keyPoints'] = points
            done += 1
    return done


def fetch_image(url, fetch, dest_dir, name):
    """Télécharge une image, la réduit (si Pillow est là) et renvoie (chemin relatif au site, largeur, hauteur) ou None."""
    try:
        data, _ = fetch(url, timeout=25, accept='image/avif,image/webp,image/jpeg,image/png,*/*;q=0.5', limit=MAX_IMG_BYTES)
    except Exception:  # noqa: BLE001
        return None
    if not data or len(data) < 2000:
        return None
    os.makedirs(dest_dir, exist_ok=True)
    path = os.path.join(dest_dir, name + '.jpg')
    try:
        from PIL import Image  # type: ignore
        im = Image.open(io.BytesIO(data))
        im = im.convert('RGB')
        if im.width > IMG_WIDTH:
            im = im.resize((IMG_WIDTH, round(im.height * IMG_WIDTH / im.width)))
        im.save(path, 'JPEG', quality=70, optimize=True, progressive=True)
        return path, im.width, im.height
    except ImportError:
        if len(data) <= 300_000 and data[:3] == b'\xff\xd8\xff':   # JPEG léger : gardé tel quel
            with open(path, 'wb') as fh:
                fh.write(data)
            return path, None, None
    except Exception:  # noqa: BLE001
        return None
    return None


def enrich(items, key, fetch, gemini_call, helpers, log, stats, site_dir, today):
    """Ajoute à chaque fiche : 'detail', 'keyPoints' et, si la source est libre de droits, 'image'."""
    todo = [it for it in items if it.get('_src') and not NO_FETCH.search(it['_src']['link'])]

    def read(it):
        try:
            data, final = fetch(it['_src']['link'], timeout=20, accept='text/html,application/xhtml+xml;q=0.9,*/*;q=0.5', limit=3_000_000)
            return extract_article(data, final)
        except Exception:  # noqa: BLE001
            return None
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        pages = list(ex.map(read, todo))
    ready = [(it, pg) for it, pg in zip(todo, pages) if pg and pg['chars'] >= MIN_CHARS]
    stats['pages_read'] = len(ready)
    log(f'Fiches détaillées : {len(ready)} pages lisibles sur {len(items)} fiches.')
    done = 0
    for i in range(0, len(ready), BATCH):
        try:
            done += write_details(ready[i:i + BATCH], key, gemini_call, helpers, stats)
        except Exception as e:  # noqa: BLE001
            log(f'  · fiche détaillée : {type(e).__name__} {str(e)[:120]}')
    stats['details'] = done
    log(f'Fiches détaillées écrites : {done}.')
    # Images libres de droits (NASA) : gardées pour la lecture sans réseau.
    img_dir = os.path.join(site_dir, 'img', today)
    pg_by_id = {id(it): pg for it, pg in zip(todo, pages)}
    n_img = 0
    for it in items:
        pg = pg_by_id.get(id(it))
        credit = IMAGE_SOURCES.get((it.get('_src') or {}).get('source'))
        if not (pg and pg.get('image') and credit):
            continue
        got = fetch_image(pg['image'], fetch, img_dir, re.sub(r'[^A-Za-z0-9_-]', '-', it['id'])[:60])
        if got:
            path, w, h = got
            it['image'] = {'src': os.path.relpath(path, site_dir).replace(os.sep, '/'), 'credit': credit, 'w': w, 'h': h,
                           'alt': it['title']}
            n_img += 1
    stats['images'] = n_img
    if n_img:
        log(f'Images libres de droits gardées : {n_img}.')
    try:
        n_ill = illustrations([it for it in items if not it.get('image')], key, gemini_call, log, site_dir, today)
        stats['illustrations'] = n_ill
    except Exception as e:  # noqa: BLE001 - l'illustration est un plus : sans elle, la fiche n'a simplement pas d'image
        log(f'  · illustrations indisponibles ({type(e).__name__} : {str(e)[:100]})')



# ---------------------------------------------------------------- Illustrations libres de droits (Wikimedia Commons)

COMMONS = 'https://commons.wikimedia.org/w/api.php'
UA_WIKI = 'MatinaleDesSciences/1.0 (https://github.com/hadesdray-crypto/matinale; revue de presse scientifique non commerciale)'
LICENSE_OK = re.compile(r'^(CC0|CC BY(-SA)? [0-9.]+|Public domain|PD[- ].+)', re.I)
LICENSE_NO = re.compile(r'(NC|ND|GFDL|fair use|non[- ]?free)', re.I)
TITLE_BAD = re.compile(r'(portrait|logo|flag|drapeau|map of|carte|diagram|chart|screenshot|poster|stamp|coat of arms|signature|cover|selfie|'
                       r'statue|mugshot|face of|visage|nude|nu\b|icon)', re.I)
ILL_PROMPT = """Pour chaque fiche scientifique ci-dessous, propose des mots-clés de recherche en ANGLAIS pour trouver sur Wikimedia Commons
une photo d'illustration générique et concrète du sujet (un objet, un paysage, un instrument, un animal, un lieu).
Règles : 2 à 4 mots par requête, 2 requêtes par fiche (la seconde plus générale). Aucun nom de personne, de marque, de logo ni de revue.
Pas de mot abstrait (study, research, discovery). Pour la santé, évite les photos de patients : préfère un instrument, une cellule, un laboratoire.

Réponds uniquement avec ce JSON :
{{"images": [{{"ref": "i1", "requetes": ["requête précise", "requête générale"]}}]}}

FICHES :
{fiches}
"""


def _http(url, timeout=25, accept='application/json', limit=4_000_000):
    req = urllib.request.Request(url, headers={'User-Agent': UA_WIKI, 'Accept': accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(limit), r.geturl()


def _strip(html_text):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html_text or '')).strip()


def commons_search(query, http=None):
    """Renvoie des candidats [{title, thumb, w, h, page, license, artist, desc}] à licence libre, du plus pertinent au moins pertinent."""
    http = http or _http
    params = {'action': 'query', 'generator': 'search', 'gsrnamespace': '6', 'gsrsearch': query + ' filetype:bitmap', 'gsrlimit': '12',
              'prop': 'imageinfo', 'iiprop': 'url|size|mime|extmetadata', 'iiurlwidth': '960', 'format': 'json', 'formatversion': '2'}
    data, _ = http(COMMONS + '?' + urllib.parse.urlencode(params))
    pages = (json.loads(data).get('query') or {}).get('pages') or []
    pages = sorted(pages, key=lambda p: p.get('index', 0))
    words = [w for w in re.findall(r'[a-z]{4,}', query.lower())]
    out = []
    for pg in pages:
        info = (pg.get('imageinfo') or [None])[0]
        if not info:
            continue
        meta = info.get('extmetadata') or {}
        val = lambda k: _strip(str((meta.get(k) or {}).get('value') or ''))
        lic = val('LicenseShortName')
        if not lic or not LICENSE_OK.match(lic) or LICENSE_NO.search(lic) or LICENSE_NO.search(val('UsageTerms')):
            continue
        if val('NonFree').lower() in ('true', '1', 'yes'):
            continue
        if re.search(r'(personality|trademark)', val('Restrictions'), re.I):
            continue
        title = str(pg.get('title') or '')
        if TITLE_BAD.search(title) or info.get('mime') not in ('image/jpeg', 'image/png'):
            continue
        w, h = info.get('width') or 0, info.get('height') or 0
        if w < 1000 or not h or not (1.25 <= w / h <= 2.3) or not info.get('thumburl'):
            continue
        desc = val('ImageDescription')
        if words and not any(x in (title + ' ' + desc).lower() for x in words):
            continue   # le fichier ne parle pas du sujet cherché
        out.append({'title': title, 'thumb': info['thumburl'], 'w': info.get('thumbwidth'), 'h': info.get('thumbheight'),
                    'page': info.get('descriptionurl') or '', 'license': lic, 'artist': _shorten(val('Artist'), 60), 'desc': _shorten(desc, 140)})
    return out


OPENVERSE = 'https://api.openverse.org/v1/images/'
OV_LICENSES = {'cc0': 'CC0', 'pdm': 'Public domain', 'by': 'CC BY', 'by-sa': 'CC BY-SA'}


def openverse_search(query, http=None):
    """Deuxième source ouverte : Openverse (images sous licence Creative Commons de nombreux sites). Mêmes candidats que Commons."""
    http = http or _http
    params = {'q': query, 'license': 'cc0,pdm,by,by-sa', 'extension': 'jpg,png', 'aspect_ratio': 'wide', 'size': 'large',
              'mature': 'false', 'page_size': '10'}
    data, _ = http(OPENVERSE + '?' + urllib.parse.urlencode(params))
    words = re.findall(r'[a-z]{4,}', query.lower())
    out = []
    for r in (json.loads(data).get('results') or []):
        lic = OV_LICENSES.get(str(r.get('license') or '').lower())
        if not lic or r.get('mature') or not r.get('thumbnail'):
            continue
        if lic.startswith('CC BY'):
            lic += ' ' + str(r.get('license_version') or '').strip()
        title = str(r.get('title') or '')
        w, h = r.get('width') or 0, r.get('height') or 0
        if TITLE_BAD.search(title) or w < 1000 or not h or not (1.25 <= w / h <= 2.3):
            continue
        if words and not any(x in (title + ' ' + ' '.join(t.get('name', '') for t in (r.get('tags') or []) if isinstance(t, dict))).lower() for x in words):
            continue
        out.append({'title': title, 'thumb': r['thumbnail'], 'w': None, 'h': None, 'page': r.get('foreign_landing_url') or '',
                    'license': lic.strip(), 'artist': _shorten(_strip(str(r.get('creator') or '')), 60),
                    'desc': '', 'site': str(r.get('source') or '').capitalize()})
    return out


def illustrations(items, key, gemini_call, log, site_dir, today, http=None, pause=1.0):
    """Ajoute 'image' (kind = illustration) aux fiches qui n'en ont pas. Renvoie le nombre d'images gardées."""
    http = http or _http
    todo = [it for it in items if not it.get('image')]
    if not todo:
        return 0
    queries = {}
    for i in range(0, len(todo), 10):
        chunk = todo[i:i + 10]
        fiches = [{'ref': f'i{n + 1}', 'titre': it['title'], 'categorie': it.get('cat')} for n, it in enumerate(chunk)]
        prompt = ILL_PROMPT.format(fiches='\n'.join(json.dumps(f, ensure_ascii=False) for f in fiches))
        res, _m = gemini_call(prompt, key)
        for f in (res or {}).get('images') or [] if isinstance(res, dict) else []:
            idx = f.get('ref') if isinstance(f, dict) else None
            if isinstance(idx, str) and idx[1:].isdigit() and 0 < int(idx[1:]) <= len(chunk):
                qs = [q.strip() for q in (f.get('requetes') or []) if isinstance(q, str) and 3 <= len(q.strip()) <= 60][:2]
                if qs:
                    queries[id(chunk[int(idx[1:]) - 1])] = qs
    img_dir = os.path.join(site_dir, 'img', today)
    used, n_ok = set(), 0
    wfetch = lambda url, **kw: http(url, accept='image/jpeg,image/png,*/*;q=0.5', limit=MAX_IMG_BYTES)
    for it in todo:
        found = None
        for q in queries.get(id(it), []):
            cands = []
            for name, search in (('Commons', commons_search), ('Openverse', openverse_search)):
                try:
                    cands = [c for c in search(q, http) if c['thumb'] not in used]
                except Exception as e:  # noqa: BLE001
                    log(f'  · {name} : {type(e).__name__} {str(e)[:80]}')
                    cands = []
                time.sleep(pause)
                if cands:
                    break
            for c in cands[:3]:
                got = fetch_image(c['thumb'], wfetch, img_dir, re.sub(r'[^A-Za-z0-9_-]', '-', it['id'])[:60])
                if got:
                    found = (c, got)
                    break
            if found:
                break
        if found:
            c, (path, w, h) = found
            used.add(c['thumb'])
            who = c['artist'] or 'auteur non indiqué'
            it['image'] = {'src': os.path.relpath(path, site_dir).replace(os.sep, '/'), 'w': w, 'h': h, 'alt': it['title'], 'kind': 'illustration',
                           'credit': f"{who}, {c['license']}, {c.get('site') or 'Wikimedia Commons'}", 'url': c['page']}
            n_ok += 1
    log(f'Illustrations libres de droits : {n_ok} sur {len(todo)} fiches.')
    return n_ok
