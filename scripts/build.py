#!/usr/bin/env python3
"""Matinale des Sciences, version gratuite : prépare l'édition du jour, sans abonnement.

Lancement :  python3 scripts/build.py --site site
Options   :  --hours 36 (fenêtre de publication)  --max-items 20  --no-ai  --force

Ce que fait le script, chaque matin (lancé par GitHub Actions) :
 1. Il lit les flux RSS/Atom des sources de sources.json : organismes de recherche, agences spatiales,
    presse scientifique. Si l'adresse d'un flux ne répond plus, il cherche tout seul le flux sur la page
    d'accueil du site.
 2. Il garde les articles récents, écarte les doublons et les contenus commerciaux, et les classe par catégorie.
 3. Avec une clé GEMINI_API_KEY (gratuite, sur Google AI Studio), Gemini rédige les fiches en français et
    propose un niveau de preuve. Les liens viennent toujours des flux des sources, jamais de l'IA. Une phrase
    de l'IA qui contient un chiffre absent de l'article est retirée.
    Sans clé, ou si Gemini ne répond pas, chaque fiche reprend le titre et le résumé publiés par la source,
    avec la mention « Non évalué ».
 4. Il lit les flux YouTube des chaînes francophones de l'annuaire (section Francophonie).
 5. Il vérifie que chaque lien répond, puis écrit site/data/latest.json, site/data/archive.json et
    site/data/editions/<date>.json.
Si rien de neuf n'est trouvé, l'édition précédente reste en ligne : la page n'est jamais cassée.
Aucune dépendance : uniquement la bibliothèque standard de Python 3.9+.
"""
import threading
import time
import argparse
import concurrent.futures as cf
import datetime as dt
import email.utils
import gzip
import html
import json
import os
import re
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.entities import name2codepoint
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
PARIS = ZoneInfo('Europe/Paris')
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 MatinaleDesSciences/1.0'
CAT_IDS = ['espace', 'sante', 'cerveau', 'physique', 'terre', 'vivant', 'archeo', 'tech', 'inventions']
CAT_LABEL = {'espace': 'Espace', 'sante': 'Santé', 'cerveau': 'Cerveau & psychologie', 'physique': 'Physique & chimie',
             'terre': 'Terre & climat', 'vivant': 'Vivant & nature', 'archeo': 'Archéologie & paléo', 'tech': 'Tech & IA', 'inventions': 'Inventions'}
LEVEL_NAMES = {4: 'Établi', 3: 'Solide', 2: 'Préliminaire', 1: 'Hypothèse', 0: 'Non évalué'}
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
GEMINI_ENDPOINT = os.environ.get('GEMINI_ENDPOINT', 'https://generativelanguage.googleapis.com')
# Modèle « Flash » (quota gratuit très court, ~20 demandes/jour) : seulement pour écrire l'édition.
# Modèle « Flash-Lite » (quota bien plus large) : toutes les petites tâches (détails, mots-clés, contrôle des images).
GEMINI_MODELS = ['gemini-flash-latest', 'gemini-3.8-flash', 'gemini-flash-lite-latest', 'gemini-3.5-flash-lite']
GEMINI_LITE = ['gemini-flash-lite-latest', 'gemini-3.5-flash-lite']
GEMINI_GAP = float(os.environ.get('MATINALE_GEMINI_GAP', '4.5'))   # secondes entre deux demandes (limite par minute)
_AI = {'last': 0.0, 'lock': threading.Lock(), 'exhausted': set()}
NOTIONS = {}   # identifiant -> titre des notions de la section « Comprendre » (site/data/bases.json)

STATS = {'feeds_ok': [], 'feeds_ko': [], 'mode': 'rss', 'model': None, 'dropped_links': 0, 'ai_sentences_removed': 0, 'ai_calls': {}}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


# ---------------------------------------------------------------- Texte

def norm(s):
    s = unicodedata.normalize('NFD', str(s or '').lower().replace('’', "'"))
    return ''.join(c for c in s if unicodedata.category(c) != 'Mn')


def clean(s):
    s = str(s or '')
    s = re.sub(r'<!\[CDATA\[|\]\]>', '', s)
    s = re.sub(r'<(script|style)\b.*?</\1>', ' ', s, flags=re.S | re.I)
    s = re.sub(r'<br\s*/?>|</p>|</div>|</li>|</h\d>', '\n', s, flags=re.I)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(html.unescape(s))
    s = s.replace('\xa0', ' ').replace('​', '').replace('﻿', '')
    s = re.sub(r'[ \t\r\f\v]+', ' ', s)
    s = re.sub(r'\s*\n\s*', '\n', s).strip()
    s = re.sub(r"\s*(L['’]article|Cet article|The post)\s.{0,300}?(est apparu en premier sur|appeared first on)\s.{0,160}$", '', s, flags=re.S | re.I).strip()
    s = re.sub(r"\s*(Lire la suite|Continuer la lecture|Read more|Lire l['’]article|En savoir plus)\W*$", '', s, flags=re.I).strip()
    return s


def one_line(s):
    return re.sub(r'\s+', ' ', clean(s)).strip()


ABBR = re.compile(r"(\b[A-Z]\.|\b(?:M|Mme|Mlle|Dr|Pr|St|Ste|av|apr|env|cf|etc|vol|fig|n°|No|Mr|Mrs|Ms|Prof|al|vs|J\.-C)\.)$")
SPLIT = re.compile(r'(?<=[.!?…»"])\s+(?=[«"“A-ZÀ-ÖØ-Þ0-9])')


def sentences(text):
    parts = [p.strip() for p in SPLIT.split(re.sub(r'\s+', ' ', text or '').strip()) if p.strip()]
    out = []
    for p in parts:
        if out and ABBR.search(out[-1]):
            out[-1] += ' ' + p
        else:
            out.append(p)
    return out


def complete(sents):
    """Retire une dernière phrase coupée par le site (« … », « [...] » ou sans ponctuation finale)."""
    sents = list(sents)
    while sents and not re.search(r'[.!?»"”)]$', sents[-1]):
        sents.pop()
    return sents


def shorten(s, n):
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[:n - 1]
    cut = cut[:cut.rfind(' ')] if ' ' in cut else cut
    return cut.rstrip(' ,;:-–') + '…'


def slugify(s, n=60):
    s = re.sub(r'[^a-z0-9]+', '-', norm(s)).strip('-')
    return (s[:n].rstrip('-') or 'fiche')


def long_date(d):
    x = dt.date.fromisoformat(d)
    return f"{JOURS[x.weekday()]} {'1er' if x.day == 1 else x.day} {MOIS[x.month - 1]} {x.year}"


def period_label(dates):
    ds = sorted({dt.date.fromisoformat(d) for d in dates if d})
    if not ds:
        return ''
    a, b = ds[0], ds[-1]
    fa = '1er' if a.day == 1 else str(a.day)
    fb = '1er' if b.day == 1 else str(b.day)
    if a == b:
        return f'{fb} {MOIS[b.month - 1]} {b.year}'
    if (a.year, a.month) == (b.year, b.month):
        return f'{fa} – {fb} {MOIS[b.month - 1]} {b.year}'
    if a.year == b.year:
        return f'{fa} {MOIS[a.month - 1]} – {fb} {MOIS[b.month - 1]} {b.year}'
    return f'{fa} {MOIS[a.month - 1]} {a.year} – {fb} {MOIS[b.month - 1]} {b.year}'


# ---------------------------------------------------------------- Réseau

def fetch(url, timeout=20, accept=None, limit=6_000_000):
    req = urllib.request.Request(url, headers={
        'User-Agent': UA,
        'Accept': accept or 'application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.9, */*;q=0.5',
        'Accept-Language': 'fr-FR,fr;q=0.9,en;q=0.8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read(limit)
        if (r.headers.get('Content-Encoding') or '').lower() == 'gzip':
            data = gzip.decompress(data)
        return data, r.geturl()


def link_status(url):
    """Vérifie un lien. Renvoie 'ok', 'mort' (404/410, nom de domaine inconnu) ou 'incertain'."""
    try:
        req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,*/*;q=0.8', 'Accept-Language': 'fr-FR,fr;q=0.9'})
        with urllib.request.urlopen(req, timeout=20) as r:
            r.read(512)
            return 'ok'
    except urllib.error.HTTPError as e:
        return 'mort' if e.code in (404, 410) else 'incertain'
    except urllib.error.URLError as e:
        reason = str(getattr(e, 'reason', e))
        return 'mort' if ('Name or service not known' in reason or 'nodename nor servname' in reason) else 'incertain'
    except Exception:
        return 'incertain'


def clean_url(u):
    u = html.unescape((u or '').strip())
    if u.startswith('//'):
        u = 'https:' + u
    if u.startswith('http://'):
        u = 'https://' + u[7:]
    if not u.startswith('https://'):
        return ''
    try:
        p = urllib.parse.urlsplit(u)
        q = [(k, v) for k, v in urllib.parse.parse_qsl(p.query, keep_blank_values=True)
             if not re.match(r'(utm_|xtor|at_|fbclid|gclid|mc_|ns_|cmp$|ref$|rss$)', k, re.I)]
        return urllib.parse.urlunsplit((p.scheme, p.netloc, p.path, urllib.parse.urlencode(q), ''))
    except ValueError:
        return ''


# ---------------------------------------------------------------- Flux RSS / Atom

def localname(tag):
    return tag.rsplit('}', 1)[-1] if isinstance(tag, str) else ''


def child_text(el, *names):
    for name in names:
        for c in el:
            if localname(c.tag) == name:
                txt = ''.join(c.itertext()).strip()
                if txt:
                    return txt
    return ''


def entry_link(el):
    best = ''
    for c in el:
        if localname(c.tag) == 'link':
            href = c.get('href')
            if href:
                if c.get('rel', 'alternate') == 'alternate':
                    return href.strip()
                best = best or href.strip()
            elif (c.text or '').strip():
                return c.text.strip()
    if best:
        return best
    g = child_text(el, 'guid')
    return g if g.startswith('http') else ''


def parse_date(s):
    s = (s or '').strip()
    if not s:
        return None
    d = None
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError, IndexError):
        d = None
    if d is None:
        try:
            d = dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
        except ValueError:
            m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
            d = dt.datetime.fromisoformat(m.group(1)) if m else None
    if d is None:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def fix_entities(b):
    m = re.match(rb'\s*<\?xml[^>]*encoding=["\']([A-Za-z0-9_.-]+)', b)
    enc = m.group(1).decode() if m else 'utf-8'
    try:
        s = b.decode(enc, 'replace')
    except LookupError:
        s = b.decode('utf-8', 'replace')
    s = re.sub(r'^\s*<\?xml[^>]*\?>', '', s)

    def ent(m):
        n = m.group(1)
        if n in ('amp', 'lt', 'gt', 'quot', 'apos'):
            return m.group(0)
        return '&#%d;' % name2codepoint[n] if n in name2codepoint else '&amp;' + n + ';'
    s = re.sub(r'&([A-Za-z][A-Za-z0-9]*);', ent, s)
    s = re.sub(r'&(?!#?\w+;)', '&amp;', s)
    return s.encode('utf-8')


def regex_feed(b):
    s = b.decode('utf-8', 'replace')
    out = []
    for name, body in re.findall(r'<(item|entry)\b[^>]*>(.*?)</\1>', s, re.S | re.I):
        def tag(t):
            m = re.search(r'<%s\b[^>]*>(.*?)</%s>' % (re.escape(t), re.escape(t)), body, re.S | re.I)
            return re.sub(r'^\s*<!\[CDATA\[(.*?)\]\]>\s*$', r'\1', m.group(1), flags=re.S) if m else ''
        link = tag('link').strip()
        if not link:
            m = re.search(r'<link\b[^>]*href=["\']([^"\']+)', body, re.I)
            link = m.group(1) if m else ''
        out.append({'title': one_line(tag('title')), 'link': link,
                    'date': parse_date(tag('pubDate') or tag('published') or tag('dc:date') or tag('updated')),
                    'summary': clean(tag('description') or tag('summary') or tag('content:encoded') or tag('media:description')),
                    'video_id': one_line(tag('yt:videoId'))})
    return out


def parse_feed(data):
    data = data.lstrip(b'\xef\xbb\xbf \t\r\n')
    root = None
    for attempt in range(2):
        try:
            root = ET.fromstring(data)
            break
        except ET.ParseError:
            if attempt == 0:
                data = fix_entities(data)
    if root is None:
        return regex_feed(data)
    out = []
    for el in root.iter():
        if localname(el.tag) not in ('item', 'entry'):
            continue
        desc = child_text(el, 'description', 'summary')
        enc = child_text(el, 'encoded', 'content')
        summary = desc if len(one_line(desc)) >= 80 or not enc else enc
        if not summary:
            for c in el:
                if localname(c.tag) == 'group':
                    summary = child_text(c, 'description')
        out.append({'title': one_line(child_text(el, 'title')), 'link': entry_link(el),
                    'date': parse_date(child_text(el, 'pubDate', 'published', 'date', 'updated', 'issued')),
                    'summary': clean(summary), 'video_id': child_text(el, 'videoId')})
    return out


def discover_feed(site):
    """Plan B : cherche l'adresse du flux sur la page d'accueil du site."""
    try:
        data, final = fetch(site, accept='text/html')
    except Exception:
        return None
    s = data.decode('utf-8', 'replace')
    for m in re.finditer(r'<link\b[^>]*>', s, re.I):
        tag = m.group(0)
        if re.search(r'type=["\']application/(rss|atom)\+xml', tag, re.I):
            h = re.search(r'href=["\']([^"\']+)', tag, re.I)
            if h:
                return urllib.parse.urljoin(final, html.unescape(h.group(1)))
    return None


def read_source(src):
    """Lit un flux. Si l'adresse ne marche plus, essaie l'adresse trouvée sur la page d'accueil."""
    tried = []
    urls = [src['feed']]
    for attempt in range(2):
        for url in urls:
            if url in tried:
                continue
            tried.append(url)
            try:
                data, _ = fetch(url)
                entries = parse_feed(data)
                if entries:
                    return entries, url
            except Exception as e:
                log(f"  · {src['name']} : {url} ne répond pas ({type(e).__name__})")
        if attempt == 0 and src.get('site'):
            alt = discover_feed(src['site'])
            urls = [alt] if alt else []
    return [], None


# ---------------------------------------------------------------- Classement

KW = {
    'espace': ['astro', 'spatial', 'planete', 'exoplanete', 'galax', 'etoile$', 'etoiles$', 'comete', 'asteroide', 'lune$', 'lunes$', 'lunaire',
               'planete mars', 'sur mars$', 'vers mars$', 'martien', 'jupiter', 'saturne', 'neptune', 'pluton', 'telescope', 'nasa$', 'esa$',
               'cnes$', 'jaxa', 'fusee', 'lanceur', 'ariane', 'satellite', 'orbite', 'orbital', 'cosmo', 'univers$', 'trou noir', 'trous noirs',
               'nebuleuse', 'meteorite', 'spacex', 'artemis', 'station spatiale', 'astronaute', 'sonde$', 'sondes$', 'rover', 'big bang',
               'matiere noire', 'energie noire', 'pulsar', 'supernova', 'quasar', 'james webb', 'hubble', 'euclid', 'eclipse', 'systeme solaire',
               'en:space$', 'en:planet', 'en:galax', 'en:star$', 'en:stars$', 'en:comet', 'en:asteroid', 'en:moon$', 'en:moons$', 'en:lunar',
               'en:mars$', 'en:martian', 'en:telescop', 'en:orbit', 'en:black hole', 'en:universe', 'en:astronaut', 'en:spacecraft', 'en:nebula',
               'en:exoplanet', 'en:solar system', 'en:cosmic', 'en:rocket', 'en:launch'],
    'sante': ['sante$', 'medic', 'maladie', 'cancer', 'tumeur', 'virus$', 'viral', 'vaccin', 'bacterie', 'infection', 'infectieu', 'patient',
              'therap', 'traitement', 'medicament', 'hopital', 'hopitaux', 'essai clinique', 'diabete', 'obesite', 'cardiaque', 'cardio',
              'epidemi', 'pandemi', 'sanguin', 'microbiote', 'nutrition', 'chirurg', 'greffe', 'antibio', 'immunit', 'immunitaire', 'allergi',
              'grossesse', 'covid', 'grippe', 'paludisme', 'vih$', 'sida$', 'hepatite', 'mortalite', 'cholesterol', 'hypertension', 'avc$',
              'inserm', 'clinique', 'soins$', 'en:disease', 'en:health', 'en:patient', 'en:medical', 'en:medicine', 'en:drug$', 'en:drugs$',
              'en:vaccin', 'en:tumor', 'en:tumour', 'en:cancer', 'en:infection', 'en:clinical', 'en:therap', 'en:diabetes', 'en:obesity',
              'en:heart$', 'en:blood$', 'en:surgery', 'en:hospital', 'en:antibiotic', 'en:immune', 'en:pregnan', 'en:virus'],
    'cerveau': ['cerveau', 'cerebr', 'neuro', 'psycholog', 'psychiatr', 'memoire', 'cognit', 'emotion', 'comportement', 'conscience',
                'depression', 'anxiete', 'autisme', 'tdah', 'alzheimer', 'parkinson', 'demence', 'sommeil', 'reve$', 'reves$', 'apprentissage',
                'personnalite', 'addiction', 'en:brain', 'en:neuro', 'en:psycholog', 'en:mental', 'en:memory', 'en:cognit', 'en:behavio',
                'en:sleep', 'en:dementia', 'en:autism', 'en:anxiety', 'en:emotion', 'en:alzheimer', 'en:parkinson'],
    'physique': ['physique', 'physicien', 'quantique', 'particule', 'atome', 'atomique', 'laser', 'photon', 'electron', 'neutrino', 'boson',
                 'cern$', 'accelerateur', 'fusion nucleaire', 'nucleaire', 'chimie', 'chimiste', 'chimique', 'molecul', 'materiau',
                 'supraconduct', 'graphene', 'cristal', 'mathemat', 'equation', 'theoreme', 'relativite', 'gravitation', 'onde gravitationnelle',
                 'optique', 'plasma', 'magnetique', 'en:physic', 'en:quantum', 'en:particle', 'en:atom$', 'en:atoms$', 'en:atomic', 'en:chemi',
                 'en:molecul', 'en:material', 'en:superconduct', 'en:mathemati', 'en:theorem', 'en:magnetic', 'en:nuclear', 'en:crystal',
                 'en:laser', 'en:photon', 'en:neutrino'],
    'terre': ['climat', 'rechauffement', 'glacier', 'banquise', 'calotte', 'ocean', 'seisme', 'sismique', 'volcan', 'eruption', 'tsunami',
              'meteo', 'ouragan', 'cyclone', 'tempete', 'inondation', 'secheresse', 'canicule', 'pollution', 'polluant', 'co2$', 'carbone',
              'effet de serre', 'geolog', 'atmosphere', 'atmospherique', 'ozone', 'pergelisol', 'permafrost', 'antarctique', 'arctique',
              'groenland', 'environnement', 'deforestation', 'incendie', 'erosion', 'niveau de la mer', 'niveau des mers', 'giec',
              'en:climate', 'en:warming', 'en:glacier', 'en:sea ice', 'en:earthquake', 'en:volcan', 'en:hurricane', 'en:flood', 'en:drought',
              'en:heatwave', 'en:heat wave', 'en:emission', 'en:carbon', 'en:geolog', 'en:atmospher', 'en:antarctic', 'en:arctic',
              'en:greenland', 'en:wildfire', 'en:sea level', 'en:ocean', 'en:pollution'],
    'vivant': ['espece', 'animal', 'animaux', 'biodiversite', 'ecosysteme', 'evolution', 'faune', 'flore', 'plante', 'vegetal', 'arbre',
               'foret', 'oiseau', 'insecte', 'abeille', 'poisson', 'mammifere', 'reptile', 'serpent', 'amphibien', 'grenouille', 'baleine',
               'dauphin', 'requin', 'corail', 'coraux', 'champignon', 'genome', 'genetique', 'adn$', 'cellule', 'biolog', 'zoolog', 'botan',
               'extinction', 'predateur', 'primate', 'singe', 'fourmi', 'araignee', 'papillon', 'ecolog', 'en:species', 'en:animal',
               'en:biodiversity', 'en:ecosystem', 'en:evolution', 'en:plant$', 'en:plants$', 'en:tree$', 'en:trees$', 'en:forest', 'en:bird',
               'en:insect', 'en:bee$', 'en:bees$', 'en:fish', 'en:mammal', 'en:reptile', 'en:snake', 'en:frog', 'en:whale', 'en:dolphin',
               'en:shark', 'en:coral', 'en:fungi', 'en:fungus', 'en:genome', 'en:dna$', 'en:biolog', 'en:extinct', 'en:predator',
               'en:primate', 'en:monkey', 'en:spider', 'en:butterfl'],
    'archeo': ['archeolog', 'fouille', 'prehistoire', 'prehistorique', 'neandertal', 'homo sapiens', 'fossile', 'paleo', 'dinosaure',
               'antiquite', 'antique', 'romain', 'romaine', 'egypt', 'pharaon', 'momie', 'tombe$', 'tombeau', 'sepulture', 'vestige',
               'mesopotam', 'maya$', 'mayas$', 'inca$', 'viking', 'medieval', 'moyen age', 'epave', 'ossement', 'hominine', 'hominide',
               'grotte', 'art rupestre', 'inrap', 'necropole', 'en:archaeolog', 'en:archeolog', 'en:excavat', 'en:prehistor', 'en:neanderthal',
               'en:fossil', 'en:dinosaur', 'en:ancient', 'en:roman$', 'en:egypt', 'en:pharaoh', 'en:mummy', 'en:tomb$', 'en:burial',
               'en:skeleton', 'en:shipwreck', 'en:hominin'],
    'inventions': ['invention', 'inventeur', 'inventrice', 'brevet', 'prototype', 'innovation', 'invente ', 'a invente', 'nouveau materiau',
                   'nouvelle technologie', 'dispositif', 'en:invention', 'en:invent', 'en:patent', 'en:prototype', 'en:innovation', 'en:novel device',
                   'en:new device', 'en:breakthrough', 'en:engineers develop', 'en:engineers built', 'en:engineers create'],
    'tech': ['intelligence artificielle', 'ia$', 'algorithme', 'robot', 'ordinateur', 'informatique', 'numerique', 'logiciel', 'puce$',
             'puces$', 'processeur', 'batterie', 'hydrogene', 'eolien', 'photovoltaique', 'panneaux solaires', 'voiture electrique',
             'technolog', 'cyber', 'drone', 'imprimante 3d', 'en:artificial intelligence', 'en:ai$', 'en:machine learning', 'en:algorithm',
             'en:robot', 'en:computer', 'en:computing', 'en:software', 'en:chip$', 'en:chips$', 'en:battery', 'en:batteries',
             'en:hydrogen', 'en:solar panel', 'en:electric vehicle', 'en:technolog', 'en:engineer'],
}


def _kw_regex(lang):
    out = {}
    for cat, kws in KW.items():
        pats = []
        for k in kws:
            if k.startswith('en:'):
                if lang != 'en':
                    continue
                k = k[3:]
            elif lang == 'en':
                continue
            pats.append(re.escape(k[:-1]) + r'\b' if k.endswith('$') else re.escape(k))
        out[cat] = re.compile(r'\b(?:' + '|'.join(pats) + ')')
    return out


KW_RE = {'fr': _kw_regex('fr'), 'en': _kw_regex('en')}
JUNK = re.compile(r"\b(bons? plans?|code promo|promos?\b|soldes|black friday|prime day|french days|cyber monday|prix casse|a prix (?:mini|casse|reduit)"
                  r"|reduction de|meilleurs? prix|moins cher|notre test|notre avis|comparatif|guide d'achat|horoscope|astrolog|quiz"
                  r"|voici ce que cela (?:revele|dit)|ce que cela dit de vous|ce que ca dit de vous|recette|jeu concours|sponsoris|publi-?redactionnel"
                  r"|en partenariat avec|offre speciale|deals?\b|discount|on sale|review:|hands-on|webinaire|webinar|offre d'emploi|newsletter)")
RESEARCH = re.compile(r"\b(etude|chercheu|scientifique|publie|revue|decouv|equipe|resultat|observ|mesur|revele|montre|demontre|analys|experience"
                      r"|essai|modele|study|studies|researcher|scientist|published|journal|discover|finding|reveal|team|measur|experiment"
                      r"|trial|evidence|nature\b|science\b)")


def categorize(text, lang, hint):
    t = norm(text)
    regs = KW_RE['en' if lang == 'en' else 'fr']
    scores = {c: len(r.findall(t)) for c, r in regs.items()}
    if hint in scores:
        scores[hint] += 1.5
    best = max(CAT_IDS, key=lambda c: (scores[c], -CAT_IDS.index(c)))
    return best if scores[best] >= 1 else None


def words(s):
    return {w for w in re.findall(r'[a-z0-9]{4,}', norm(s))}


def similar(a, b):
    wa, wb = words(a), words(b)
    if not wa or not wb:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.6


# ---------------------------------------------------------------- Collecte

def collect(sources, now, hours):
    since = now - dt.timedelta(hours=hours)
    cands = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(read_source, s): s for s in sources}
        for fut in cf.as_completed(futs):
            src = futs[fut]
            try:
                entries, used = fut.result()
            except Exception as e:
                entries, used = [], None
                log(f"  · {src['name']} : erreur {type(e).__name__}")
            if not used:
                STATS['feeds_ko'].append(src['name'])
                continue
            STATS['feeds_ok'].append(src['name'])
            if used != src['feed']:
                log(f"  · {src['name']} : flux trouvé automatiquement à {used} (pense à mettre à jour sources.json)")
            for e in entries:
                link = clean_url(e.get('link'))
                title = e.get('title') or ''
                d = e.get('date')
                if not link or len(title) < 12 or not d or d < since or d > now + dt.timedelta(hours=6):
                    continue
                full = title + ' ' + (e.get('summary') or '')
                if JUNK.search(norm(full)):
                    continue
                cat = src.get('cat') if src.get('cat') in CAT_IDS and src.get('fixed') else categorize(full, src.get('lang', 'fr'), src.get('cat'))
                if not cat:
                    continue
                score = 3 * int(src.get('priority', 2)) + min(3, len(RESEARCH.findall(norm(full))))
                score += 2 if d > now - dt.timedelta(hours=18) else 0
                score += 1 if len(e.get('summary') or '') > 160 else 0
                cands.append({'title': title, 'link': link, 'date': d, 'summary': e.get('summary') or '', 'cat': cat, 'score': score,
                              'source': src['name'], 'kind': src.get('kind', 'presse'), 'lang': src.get('lang', 'fr'),
                              'priority': int(src.get('priority', 2))})
    cands.sort(key=lambda c: (-c['score'], -c['date'].timestamp()))
    kept = []
    for c in cands:
        if any(c['link'] == k['link'] or similar(c['title'], k['title']) for k in kept):
            continue
        kept.append(c)
    return kept


def pick(cands, n, per_cat=4, per_source=3):
    out, by_cat, by_src = [], {}, {}
    for c in cands:
        if len(out) >= n:
            break
        if by_cat.get(c['cat'], 0) >= per_cat or by_src.get(c['source'], 0) >= per_source:
            continue
        out.append(c)
        by_cat[c['cat']] = by_cat.get(c['cat'], 0) + 1
        by_src[c['source']] = by_src.get(c['source'], 0) + 1
    return out


# ---------------------------------------------------------------- YouTube (francophonie)

def channel_id_from_page(url):
    try:
        data, _ = fetch(url, timeout=15, accept='text/html')
    except Exception:
        return None
    s = data.decode('utf-8', 'replace')
    for pat in (r'<link rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"',
                r'"externalId":"(UC[\w-]{22})"', r'<meta itemprop="(?:identifier|channelId)" content="(UC[\w-]{22})"'):
        m = re.search(pat, s)
        if m:
            return m.group(1)
    return None


def youtube_feeds(refs, cache_path):
    base = os.environ.get('MATINALE_YT_FEEDS', 'https://www.youtube.com/feeds/videos.xml')
    cache = load_json(cache_path, {}) or {}
    chans = [ch for ch in (refs or {}).get('channels', [])
             if (ch.get('platform') or 'YouTube') == 'YouTube' and 'results?search_query' not in (ch.get('url') or '')]
    todo = [ch['url'] for ch in chans if not re.search(r'/channel/UC|[?&]list=', ch['url']) and not cache.get(ch['url'])]
    if todo:  # adresses du type youtube.com/@nom : on retrouve l'identifiant de la chaîne une fois, puis on le garde
        with cf.ThreadPoolExecutor(max_workers=10) as ex:
            for url, cid in zip(todo, ex.map(channel_id_from_page, todo)):
                if cid:
                    cache[url] = cid
        write_json(cache_path, cache, pretty=True)
    feeds = []
    for ch in chans:
        url = ch['url']
        m = re.search(r'/channel/(UC[\w-]{22})', url)
        p = re.search(r'[?&]list=([\w-]+)', url)
        if m:
            feeds.append((ch, base + '?channel_id=' + m.group(1)))
        elif p:
            feeds.append((ch, base + '?playlist_id=' + p.group(1)))
        elif cache.get(url):
            feeds.append((ch, base + '?channel_id=' + cache[url]))
    return feeds


def francophone_videos(refs, cache_path, now, days=7, total=12, per_channel=2):
    feeds = youtube_feeds(refs, cache_path)
    since = now - dt.timedelta(days=days)
    vids = []

    def one(item):
        ch, url = item
        try:
            data, _ = fetch(url)
            return ch, parse_feed(data)
        except Exception:
            return ch, []
    with cf.ThreadPoolExecutor(max_workers=10) as ex:
        for ch, entries in ex.map(one, feeds):
            n = 0
            for e in sorted(entries, key=lambda x: x.get('date') or since, reverse=True):
                vid = (e.get('video_id') or '').strip()
                if not vid:
                    m = re.search(r'[?&]v=([\w-]{11})', e.get('link') or '')
                    vid = m.group(1) if m else ''
                d = e.get('date')
                if not re.fullmatch(r'[\w-]{11}', vid) or not d or d < since or d > now + dt.timedelta(hours=6) or not e.get('title'):
                    continue
                if JUNK.search(norm(e['title'])):
                    continue
                note = ''
                sents = complete(sentences(one_line(e.get('summary'))))
                if sents and len(sents[0]) <= 200 and not re.search(r'https?://|#\w', sents[0]):
                    note = sents[0]
                vids.append({'url': 'https://www.youtube.com/watch?v=' + vid, 'title': e['title'], 'by': ch.get('name'),
                             'date': d.astimezone(PARIS).date().isoformat(), 'kind': 'officielle' if ch.get('type') == 'institution' else 'tierce',
                             'lang': 'FR', 'platform': 'YouTube', 'note': note, '_ts': d.timestamp(), '_desc': one_line(e.get('summary'))[:400]})
                n += 1
                if n >= per_channel:
                    break
    vids.sort(key=lambda v: -v['_ts'])
    return vids[:total]


# ---------------------------------------------------------------- Fiches sans IA

def rss_item(c, used_ids):
    title = c['title']
    text = one_line(c['summary'])
    if norm(text).startswith(norm(title)):
        text = text[len(title):].lstrip(' .:–-')
    sents = complete(sentences(text))
    dek, rest = '', []
    if sents:
        dek = sents[0]
        i = 1
        while i < len(sents) and len(dek) < 140 and len(dek) + len(sents[i]) < 330:
            dek += ' ' + sents[i]
            i += 1
        rest = sents[i:]
    elif text:
        dek = shorten(text, 300)
    body, para = [], ''
    for s in rest:
        if len(para) + len(s) > 480 and para:
            body.append(para)
            para = ''
            if len(body) == 2:
                break
        para = (para + ' ' + s).strip()
    if para and len(body) < 2:
        body.append(para)
    if not dek:
        dek = f"Article publié par {c['source']}."
    iid, k = slugify(title), 2
    while iid in used_ids:
        iid, k = f'{slugify(title, 52)}-{k}', k + 1
    used_ids.add(iid)
    return {
        'id': iid, 'cat': c['cat'], 'date': c['date'].astimezone(PARIS).date().isoformat(), 'title': title, 'dek': dek, 'body': body,
        'evidence': {'level': 0, 'type': "Communiqué de l'organisme" if c['kind'] == 'officiel' else 'Article de presse',
                     'status': f"Source : {c['source']}", 'reviewed': None,
                     'note': "Fiche composée automatiquement à partir de l'article : ouvre la source pour juger de la solidité du résultat."},
        'sources': [{'kind': c['kind'], 'label': f"{c['source']} : {title}", 'url': c['link']}],
        'videos': [], 'numbers': [], 'sure': [], 'unsure': [],
        'flash': title + '.' if not re.search(r'[.!?…]$', title) else title,
        'audio': ' '.join(x for x in [title + ('' if re.search(r'[.!?…]$', title) else '.'), dek, f"Source : {c['source']}."] if x),
        'health': c['cat'] == 'sante', 'videoQuery': title, 'journal': None, 'doi': '',
    }


# ---------------------------------------------------------------- Fiches avec Gemini (gratuit)

NUM = re.compile(r'\d+(?:[.,]\d+)?')
NUMBER_WORDS = {'un': 1, 'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6, 'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10,
                'onze': 11, 'douze': 12, 'quinze': 15, 'vingt': 20, 'trente': 30, 'cent': 100, 'mille': 1000, 'one': 1, 'two': 2,
                'three': 3, 'four': 4, 'five': 5, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
                'fifteen': 15, 'twenty': 20, 'thirty': 30, 'hundred': 100, 'thousand': 1000, 'million': 1000000, 'billion': 1000000000,
                'dozen': 12, 'douzaine': 12, 'half': 50, 'moitie': 50, 'quarter': 25, 'quart': 25}


def number_set(s, variants=False):
    s = str(s or '')
    texts = [re.sub(r'(?<=\d)[   ](?=\d{3}\b)', '', s)]
    if variants:
        texts.append(re.sub(r'(?<=\d),(?=\d{3}\b)', '', texts[0]))
        texts.append(re.sub(r'(?<=\d)\.(?=\d{3}\b)', '', texts[0]))
    out = set()
    for t in texts:
        for n in NUM.findall(t):
            n = n.replace(',', '.')
            out.add(n.rstrip('0').rstrip('.') if '.' in n else n)
    if variants:
        for w in re.findall(r'[a-z]+', norm(s)):
            if w in NUMBER_WORDS:
                out.add(str(NUMBER_WORDS[w]))
    return out


def numbers_ok(text, allowed):
    return number_set(text) <= allowed


def _ai_wait():
    """Espace les demandes pour rester sous la limite par minute de l'offre gratuite."""
    with _AI['lock']:
        d = _AI['last'] + GEMINI_GAP - time.time()
        if d > 0:
            time.sleep(d)
        _AI['last'] = time.time()


def gemini_call(prompt, key, images=None, light=False):
    """images : liste facultative de (type MIME, données en base64), jointes à la question.
    light=True : petite tâche, confiée au modèle Flash-Lite pour garder le quota Flash pour l'édition."""
    models = ([os.environ['GEMINI_MODEL']] if os.environ.get('GEMINI_MODEL') and not light else []) + (GEMINI_LITE if light else GEMINI_MODELS)
    parts = [{'text': prompt}] + [{'inline_data': {'mime_type': m, 'data': d}} for m, d in (images or [])]
    body = json.dumps({'contents': [{'role': 'user', 'parts': parts}],
                       'generationConfig': {'temperature': 0.2, 'responseMimeType': 'application/json', 'maxOutputTokens': 32768}}).encode()
    for m in dict.fromkeys(models):
        if m in _AI['exhausted']:
            continue   # quota du jour épuisé pour ce modèle : inutile de redemander
        url = f'{GEMINI_ENDPOINT}/v1beta/models/{m}:generateContent'
        req = urllib.request.Request(url, data=body, headers={'Content-Type': 'application/json', 'x-goog-api-key': key})
        try:
            _ai_wait()
            STATS['ai_calls'][m] = STATS['ai_calls'].get(m, 0) + 1
            with urllib.request.urlopen(req, timeout=240) as r:
                data = json.load(r)
            parts = data['candidates'][0]['content']['parts']
            text = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
            text = re.sub(r'^\s*```(?:json)?\s*|\s*```\s*$', '', text)
            return json.loads(text), m
        except urllib.error.HTTPError as e:
            msg = e.read()[:300].decode('utf-8', 'replace')
            log(f'  · Gemini {m} : HTTP {e.code} {msg}')
            if e.code == 429 and re.search(r'(per day|PerDay|daily|quota)', msg, re.I):
                _AI['exhausted'].add(m)
                log(f'  · {m} : quota du jour épuisé, ce modèle n\'est plus utilisé jusqu\'à demain.')
            if e.code in (400, 401, 403) and ('API key' in msg or 'API_KEY' in msg or 'PERMISSION' in msg):
                log('  · La clé GEMINI_API_KEY est refusée : vérifie-la dans les réglages du dépôt (Secrets).')
                return None, None
        except Exception as e:
            log(f'  · Gemini {m} : {type(e).__name__} {str(e)[:200]}')
    return None, None


PROMPT = """Tu es le rédacteur scientifique de « La Matinale des Sciences », une revue de presse quotidienne en français, sérieuse et sans erreur, pour le grand public.

Voici des ARTICLES publiés ces dernières heures par des sources reconnues, et des VIDEOS récentes de chaînes francophones.
Choisis les {n} articles les plus importants qui annoncent un résultat scientifique nouveau (découverte, étude, mesure, observation, mission spatiale) ou une invention technique nouvelle.
Écarte l'opinion, la politique, l'économie, les produits commerciaux et les conseils pratiques. Au plus 3 articles par catégorie, sauf « inventions » (au plus 5).
Si deux articles parlent du même résultat, garde celui de la source la plus officielle.

Pour chaque article retenu, écris en français clair :
- "ref" : la référence de l'article (ex. "a12").
- "categorie" : une valeur parmi espace, sante, cerveau, physique, terre, vivant, archeo, tech, inventions. La catégorie « inventions » regroupe les nouvelles inventions, prototypes et innovations techniques concrètes (matériaux, machines, robots, batteries, dispositifs) ; garde-en 2 ou 3 par édition quand il y en a de sérieuses.
- "titre" : titre informatif de moins de 90 caractères, sans point d'exclamation.
- "chapeau" : 1 ou 2 phrases qui disent l'essentiel.
- "texte" : 2 ou 3 paragraphes courts (liste de chaînes).
- "flash" : une phrase pour le bulletin audio.
- "pourquoi" : une phrase : pourquoi c'est important.
- "niveau" : niveau de preuve, nombre entier :
   4 = Établi : fait mesuré directement (lancement réussi, observation directe, données officielles) ou consensus scientifique ;
   3 = Solide : étude publiée dans une revue à comité de lecture, avec une méthode robuste, pas encore reproduite ;
   2 = Préliminaire : étude chez l'animal ou en laboratoire, corrélation, petit échantillon, prépublication, congrès ;
   1 = Hypothèse : modèle théorique ou proposition non vérifiée ;
   0 = Non évalué : le texte fourni ne permet pas de juger.
- "type" : type de résultat en moins de 60 caractères (ex. « Étude chez la souris », « Observation au télescope »).
- "statut" : où c'est publié si le texte le dit (ex. « Publié dans Nature »), sinon "".
- "relu" : true si le texte dit que c'est publié dans une revue relue par des pairs, false si c'est une prépublication, null sinon.
- "note" : une phrase qui justifie le niveau de preuve.
- "etabli" : 1 à 3 points sûrs. "a_prouver" : 1 à 3 limites ou questions ouvertes.
- "sante" : true si le sujet touche à la santé humaine.
- "videos" : références ("v3"…) des VIDEOS qui portent clairement sur CE résultat précis ; [] dans le doute.
- "notions" : 0 à 2 identifiants de NOTIONS de base qui aident vraiment à comprendre la fiche, pris UNIQUEMENT dans la liste NOTIONS ; [] si aucune ne convient.

RÈGLES ABSOLUES :
- N'utilise que les informations présentes dans le texte de l'article. N'invente aucun chiffre, nom, date, revue ou institution.
- Une corrélation n'est jamais présentée comme une cause. Pas de lien internet dans tes textes.
- Traduis fidèlement les articles en anglais ; garde les chiffres tels quels.

Réponds uniquement avec ce JSON :
{{"titre_edition": "titre de l'édition, moins de 80 caractères", "intro": "2 phrases qui présentent l'édition", "categories": {{"espace": "une phrase qui résume les fiches retenues dans cette catégorie"}}, "fiches": [{{"ref": "a1", "categorie": "...", "titre": "...", "chapeau": "...", "texte": ["..."], "flash": "...", "pourquoi": "...", "niveau": 3, "type": "...", "statut": "...", "relu": null, "note": "...", "etabli": ["..."], "a_prouver": ["..."], "sante": false, "videos": [], "notions": []}}]}}

NOTIONS (identifiant : titre) :
{notions}

ARTICLES :
{articles}

VIDEOS :
{videos}
"""


def s_(v, n):
    return v.strip() if isinstance(v, str) and 0 < len(v.strip()) <= n else ''


def ai_edition(cands, vids, n, key, used_ids):
    pool, per_src = [], {}
    n_inv = 0
    for c in cands:  # au plus 5 articles par source (et 15 « inventions » en tout), pour garder une édition variée
        if c['cat'] == 'inventions':
            if n_inv >= 15:
                continue
            n_inv += 1
        if per_src.get(c['source'], 0) < 5:
            pool.append(c)
            per_src[c['source']] = per_src.get(c['source'], 0) + 1
        if len(pool) >= 60:
            break
    arts = [{'ref': f'a{i}', 'source': c['source'], 'langue': c['lang'], 'date': c['date'].astimezone(PARIS).date().isoformat(),
             'categorie_probable': c['cat'], 'titre': c['title'], 'texte': shorten(one_line(c['summary']), 900)} for i, c in enumerate(pool)]
    vlist = [{'ref': f'v{i}', 'chaine': v['by'], 'titre': v['title'], 'description': shorten(v['_desc'], 300)} for i, v in enumerate(vids)]
    prompt = PROMPT.format(n=n, notions='\n'.join(f'{k} : {v}' for k, v in NOTIONS.items()) or '(aucune)', articles='\n'.join(json.dumps(a, ensure_ascii=False) for a in arts),
                           videos='\n'.join(json.dumps(v, ensure_ascii=False) for v in vlist) or '(aucune)')
    res, model = gemini_call(prompt, key)
    if not isinstance(res, dict):
        return None
    refs = {a['ref']: c for a, c in zip(arts, pool)}
    vrefs = {v['ref']: vv for v, vv in zip(vlist, vids)}
    items, seen = [], set()
    for f in res.get('fiches') or []:
        if not isinstance(f, dict):
            continue
        c = refs.get(f.get('ref'))
        if not c or f.get('ref') in seen:
            continue
        allowed = number_set(c['title'] + ' ' + c['summary'], variants=True) | {str(c['date'].year), str(c['date'].astimezone(PARIS).day)}

        def ok(txt):
            good = numbers_ok(txt, allowed)
            if not good:
                STATS['ai_sentences_removed'] += 1
            return good
        title, dek = s_(f.get('titre'), 140), s_(f.get('chapeau'), 450)
        if not title or not dek or not ok(title) or not ok(dek):
            continue
        body = [p.strip() for p in (f.get('texte') or []) if isinstance(p, str) and 0 < len(p.strip()) <= 900][:4]
        body = [' '.join(x for x in sentences(p) if ok(x)) for p in body]
        body = [p for p in body if p]
        try:
            level = int(f.get('niveau'))
        except (TypeError, ValueError):
            level = 0
        if level not in LEVEL_NAMES:
            level = 0
        cat = f.get('categorie') if f.get('categorie') in CAT_IDS else c['cat']
        flash = s_(f.get('flash'), 300)
        why = s_(f.get('pourquoi'), 400)
        sure = [x.strip() for x in (f.get('etabli') or []) if isinstance(x, str) and 0 < len(x.strip()) <= 260 and ok(x)][:3]
        unsure = [x.strip() for x in (f.get('a_prouver') or []) if isinstance(x, str) and 0 < len(x.strip()) <= 260 and ok(x)][:3]
        videos = []
        for vr in (f.get('videos') or [])[:2]:
            v = vrefs.get(vr) if isinstance(vr, str) else None
            if v and not any(v['url'] == x['url'] for x in videos):
                videos.append({k: val for k, val in v.items() if not k.startswith('_')})
        reviewed = f.get('relu') if f.get('relu') in (True, False) else None
        iid, k = slugify(title), 2
        while iid in used_ids:
            iid, k = f'{slugify(title, 52)}-{k}', k + 1
        used_ids.add(iid)
        seen.add(f.get('ref'))
        items.append({
            'id': iid, 'cat': cat, 'date': c['date'].astimezone(PARIS).date().isoformat(), 'title': title, 'dek': dek, 'body': body,
            'why': why if why and ok(why) else '',
            'evidence': {'level': level, 'type': s_(f.get('type'), 80) or LEVEL_NAMES[level], 'status': s_(f.get('statut'), 120),
                         'reviewed': reviewed, 'note': s_(f.get('note'), 400) if ok(s_(f.get('note'), 400)) else ''},
            'sources': [{'kind': c['kind'], 'label': f"{c['source']} : {c['title']}", 'url': c['link']}],
            'videos': videos, 'numbers': [], 'sure': sure, 'unsure': unsure,
            'flash': flash if flash and ok(flash) else title, 'health': bool(f.get('sante')) or cat == 'sante',
            'videoQuery': title, 'journal': None, 'doi': '', '_src': c,
            'notions': [x for x in (f.get('notions') or []) if isinstance(x, str) and x in NOTIONS][:2],
        })
        if len(items) >= n:
            break
    if len(items) < 4:
        log(f'  · Gemini : seulement {len(items)} fiche(s) valide(s), on passe à la version sans IA.')
        return None
    STATS['mode'], STATS['model'] = 'gemini', model
    cats = res.get('categories') if isinstance(res.get('categories'), dict) else {}
    present = {it['cat'] for it in items}
    allowed_all = set()
    for it in items:
        allowed_all |= number_set(it['_src']['title'] + ' ' + it['_src']['summary'], variants=True)
    summaries = {k: {'summary': v.strip()} for k, v in cats.items()
                 if k in present and isinstance(v, str) and 0 < len(v.strip()) <= 300 and numbers_ok(v, allowed_all)}
    title = s_(res.get('titre_edition'), 100)
    intro = s_(res.get('intro'), 500)
    return {'items': items, 'categories': summaries, 'title': title if title and numbers_ok(title, allowed_all) else '',
            'intro': intro if intro and numbers_ok(intro, allowed_all) else ''}


# ---------------------------------------------------------------- Fichiers

def check_bases_links(bases, data_dir, today):
    """Vérifie chaque matin les vidéos et liens de la section « Comprendre » ; les liens morts sont écrits dans
    site/data/bases-ok.json et la page les masque. Une vidéo YouTube est vérifiée par son « oEmbed » (404 = supprimée)."""
    urls = set()
    for n in bases.get('notions') or []:
        for key in ('videos', 'links'):
            for x in n.get(key) or []:
                if isinstance(x, dict) and isinstance(x.get('url'), str) and x['url'].startswith('https://'):
                    urls.add(x['url'])
    urls = sorted(urls)
    if not urls:
        return

    def status(u):
        if re.search(r'(youtube\.com/watch|youtu\.be/)', u):
            try:
                fetch('https://www.youtube.com/oembed?format=json&url=' + urllib.parse.quote(u, safe=''), timeout=20, accept='application/json', limit=20000)
                return 'ok'
            except urllib.error.HTTPError as e:
                return 'mort' if e.code in (400, 404) else 'incertain'   # 401/403 : la vidéo existe mais ne s'intègre pas
            except Exception:  # noqa: BLE001
                return 'incertain'
        return link_status(u)
    with cf.ThreadPoolExecutor(max_workers=8) as ex:
        res = list(ex.map(status, urls))
    dead = [u for u, r in zip(urls, res) if r == 'mort']
    write_json(os.path.join(data_dir, 'bases-ok.json'), {'checked': today, 'total': len(urls), 'dead': dead})
    log(f'Liens de « Comprendre » : {len(urls) - len(dead)} valides sur {len(urls)}' + (f' (masqués : {dead})' if dead else '') + '.')


def load_json(path, default=None):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def write_json(path, data, pretty=False):
    os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1 if pretty else None, separators=None if pretty else (',', ':'))
    os.replace(tmp, path)


def summary_md(lines):
    p = os.environ.get('GITHUB_STEP_SUMMARY')
    if p:
        with open(p, 'a', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')


# ---------------------------------------------------------------- Programme principal

def main():
    ap = argparse.ArgumentParser(description="Prépare l'édition du jour de la Matinale des Sciences.")
    ap.add_argument('--site', default='site')
    ap.add_argument('--sources', default=os.path.join(HERE, 'sources.json'))
    ap.add_argument('--refs', default=os.path.join(HERE, 'francophonie.json'))
    ap.add_argument('--hours', type=float, default=36)
    ap.add_argument('--max-items', type=int, default=20)
    ap.add_argument('--no-ai', action='store_true', help="n'utilise pas Gemini, même si une clé est présente")
    ap.add_argument('--force', action='store_true', help="remplace même une édition du jour rédigée à la main")
    ap.add_argument('--now', help='date et heure ISO, pour les essais')
    ap.add_argument('--no-link-check', action='store_true')
    ap.add_argument('--no-detail', action='store_true', help="ne fabrique pas les fiches détaillées ni les images")
    a = ap.parse_args()

    now = dt.datetime.fromisoformat(a.now) if a.now else dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    now = now.astimezone(dt.timezone.utc)
    today = now.astimezone(PARIS).date().isoformat()
    data_dir = os.path.join(a.site, 'data')
    latest = load_json(os.path.join(data_dir, 'latest.json'), {}) or {}
    prev = latest.get('edition') or {}
    refs = load_json(a.refs, None) or latest.get('refs')

    if prev.get('date') == today and not prev.get('generator') and not a.force:
        log(f"L'édition du {today} a été rédigée et vérifiée à la main : on la garde telle quelle.")
        summary_md([f"### Matinale du {today}", "Édition rédigée à la main conservée."])
        return 0

    bases = load_json(os.path.join(data_dir, 'bases.json'), {}) or {}
    NOTIONS.update({n['id']: n['title'] for n in bases.get('notions') or [] if isinstance(n, dict) and n.get('id') and n.get('title')})
    if not a.no_link_check:
        try:
            check_bases_links(bases, data_dir, today)
        except Exception as e:  # noqa: BLE001 - contrôle utile mais pas indispensable
            log(f'Contrôle des liens de « Comprendre » impossible ({type(e).__name__}).')
    cfg = load_json(a.sources, {}) or {}
    key = '' if a.no_ai else (os.environ.get('GEMINI_API_KEY') or '').strip()
    sources = [s for s in cfg.get('feeds', []) if s.get('feed') and (key or s.get('lang', 'fr') == 'fr')]
    log(f'Lecture de {len(sources)} sources' + (' (avec Gemini)' if key else ' (sans IA)') + '…')
    hours = a.hours
    cands = collect(sources, now, hours)
    if len([c for c in cands if c['lang'] == 'fr' or key]) < 6:
        hours = max(hours, 72)
        log(f'Peu de nouveautés : on élargit aux {int(hours)} dernières heures.')
        STATS['feeds_ok'].clear()
        STATS['feeds_ko'].clear()
        cands = collect(sources, now, hours)
    log(f"Sources lues : {len(STATS['feeds_ok'])} ; muettes : {len(STATS['feeds_ko'])} {STATS['feeds_ko']}")
    log(f'Articles retenus après tri : {len(cands)}')

    vids = []
    try:
        vids = francophone_videos(refs, os.path.join(HERE, 'youtube-ids.json'), now)
        log(f'Vidéos francophones récentes : {len(vids)}')
    except Exception as e:
        log(f'Vidéos francophones indisponibles ({type(e).__name__}).')

    used_ids = set()
    made = None
    if key and cands:
        made = ai_edition(cands, vids, a.max_items, key, used_ids)
        if not made:
            log('Gemini n\'a pas répondu : nouvel essai dans 40 secondes.')
            time.sleep(40)
            used_ids.clear()
            made = ai_edition(cands, vids, a.max_items, key, used_ids)
    if not made:
        used_ids.clear()
        fr_cands = [c for c in cands if c['lang'] == 'fr']
        chosen = pick(fr_cands, a.max_items)
        made = {'items': [rss_item(c, used_ids) for c in chosen], 'categories': {}, 'title': '', 'intro': ''}
        STATS['mode'] = 'rss'
        for it, c in zip(made['items'], chosen):
            it['_src'] = c

    items = made['items']
    if not a.no_link_check and items:
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            status = list(ex.map(lambda it: link_status(it['sources'][0]['url']), items))
        dead = [it['title'] for it, st in zip(items, status) if st == 'mort']
        STATS['dropped_links'] = len(dead)
        if dead:
            log(f'Liens morts écartés : {dead}')
        items = [it for it, st in zip(items, status) if st != 'mort']

    if len(items) < 3:
        log("Pas assez de nouveautés vérifiées aujourd'hui : l'édition précédente reste en ligne.")
        summary_md([f"### Matinale du {today}", "Pas assez de nouveautés vérifiées : l'édition précédente reste en ligne.",
                    f"Sources lues : {len(STATS['feeds_ok'])} · muettes : {', '.join(STATS['feeds_ko']) or 'aucune'}"])
        return 0

    if key and STATS['mode'] == 'gemini' and not a.no_detail:
        try:
            import detail
            detail.enrich(items, key, fetch, gemini_call, (number_set, numbers_ok, sentences), log, STATS, a.site, today)
        except Exception as e:  # noqa: BLE001 - la fiche détaillée est un plus : sans elle, la fiche garde son résumé
            log(f'Fiches détaillées indisponibles ({type(e).__name__} : {str(e)[:120]}).')

    srcs_used = sorted({it['_src']['source'] for it in items})
    top = max(items, key=lambda it: (it['_src']['priority'], it['_src']['score'], bool(it['videos'])))
    for it in items:
        it.pop('_src', None)
    items.sort(key=lambda it: CAT_IDS.index(it['cat']))
    number = prev.get('number') if prev.get('date') == today else (prev.get('number') or 0) + 1
    if not isinstance(number, int):
        number = 1
    n = len(items)
    dl = long_date(today)
    intro = made['intro'] or (f"{n} nouvelles de la science publiées ces dernières heures par {len(srcs_used)} sources reconnues : "
                              "organismes de recherche, agences spatiales et presse scientifique. Chaque fiche renvoie à l'article d'origine.")
    linked = {v['url'] for it in items for v in it['videos']}
    fr_videos = [{k: val for k, val in v.items() if not k.startswith('_')} for v in vids if v['url'] not in linked]
    ed = {
        'date': today, 'number': number, 'kind': 'Édition du jour', 'title': made['title'], 'intro': intro,
        'period': period_label([it['date'] for it in items]), 'top': top['id'], 'items': items, 'categories': made['categories'],
        'podcast': {
            'intro': f"Bonjour et bienvenue dans la Matinale des sciences. Nous sommes le {dl}. Au programme : {n} nouvelles de la science.",
            'outro': "C'est la fin de cette édition. Les détails et les sources sont dans l'application. Rendez-vous demain matin !",
            'flashIntro': f"Bonjour, voici le flash de la Matinale des sciences, ce {dl}.",
            'flashOutro': "Les détails, les vidéos et les sources sont dans l'application. Belle journée !",
            'franco': 'Place à la francophonie.'},
        'francophonie': {'intro': "La science en français : les nouvelles vidéos des chaînes francophones de l'annuaire, et les chaînes à suivre.",
                         'highlights': [], 'videos': fr_videos},
        'updatedAt': now.astimezone(PARIS).isoformat(timespec='seconds'),
        'generator': STATS['mode'], 'model': STATS['model'], 'sources': srcs_used,
    }

    os.makedirs(os.path.join(data_dir, 'editions'), exist_ok=True)
    write_json(os.path.join(data_dir, 'editions', today + '.json'), ed)
    archive = [x for x in (latest.get('archive') or []) if isinstance(x, dict) and x.get('date') and x.get('date') != today]
    archive.append({'date': today, 'number': number, 'title': ed['title'] or top['title'], 'count': n, 'headline': top['title']})
    archive = sorted(archive, key=lambda x: x['date'], reverse=True)
    archive = [x for x in archive if os.path.exists(os.path.join(data_dir, 'editions', x['date'] + '.json'))][:120]
    keep = {x['date'] + '.json' for x in archive}
    for f in os.listdir(os.path.join(data_dir, 'editions')):
        if f.endswith('.json') and f not in keep:
            os.remove(os.path.join(data_dir, 'editions', f))
    write_json(os.path.join(data_dir, 'archive.json'), archive)
    write_json(os.path.join(data_dir, 'latest.json'), {'generatedAt': ed['updatedAt'], 'edition': ed, 'refs': refs, 'archive': archive})

    mode = f"Gemini ({STATS['model']})" if STATS['mode'] == 'gemini' else 'sans IA (titres et résumés des sources)'
    log(f"Édition n° {number} du {today} : {n} fiches, mode {mode}, {len(fr_videos)} vidéos francophones.")
    log('Demandes à l\'IA : ' + (', '.join(f'{k} {v}' for k, v in STATS['ai_calls'].items()) or 'aucune'))
    summary_md([f"### Matinale du {today} — édition n° {number}", '', f"- **{n} fiches**, mode : {mode}",
                f"- Sources lues : {len(STATS['feeds_ok'])} · muettes : {', '.join(STATS['feeds_ko']) or 'aucune'}",
                f"- Liens morts écartés : {STATS['dropped_links']} · phrases de l'IA retirées (chiffre absent de la source) : {STATS['ai_sentences_removed']}",
                f"- Vidéos francophones : {len(fr_videos)}",
                f"- Fiches détaillées : {STATS.get('details', 0)} (pages lisibles : {STATS.get('pages_read', 0)}) · images libres de droits : {STATS.get('images', 0)}"])
    return 0


if __name__ == '__main__':
    sys.exit(main())
