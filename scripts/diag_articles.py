#!/usr/bin/env python3
"""Contrôle ponctuel (depuis GitHub) : pages d'articles du jour (texte, image) et flux « inventions »."""
import json, os, re, html, urllib.request, urllib.error
UA = 'Mozilla/5.0 (compatible; MatinaleBot/1.0; +https://github.com/hadesdray-crypto/matinale)'
os.makedirs('diag', exist_ok=True)

def get(u):
    req = urllib.request.Request(u, headers={'User-Agent': UA, 'Accept': '*/*', 'Accept-Language': 'fr,en;q=0.8'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.headers.get('Content-Type', ''), r.read(900000).decode('utf-8', 'replace')

def meta(t, prop):
    m = re.search(r'<meta[^>]+(?:property|name)=["\']%s["\'][^>]*content=["\']([^"\']*)' % re.escape(prop), t, re.I) or \
        re.search(r'<meta[^>]+content=["\']([^"\']*)["\'][^>]+(?:property|name)=["\']%s["\']' % re.escape(prop), t, re.I)
    return html.unescape(m.group(1)) if m else ''

def body_text(t):
    t = re.sub(r'<(script|style|nav|header|footer|aside|form)[\s\S]*?</\1>', ' ', t, flags=re.I)
    m = re.search(r'<article[\s\S]*?</article>', t, re.I) or re.search(r'<main[\s\S]*?</main>', t, re.I)
    seg = m.group(0) if m else t
    ps = [re.sub(r'<[^>]+>', '', p) for p in re.findall(r'<p[\s>][\s\S]*?</p>', seg, re.I)]
    ps = [html.unescape(re.sub(r'\s+', ' ', p)).strip() for p in ps]
    ps = [p for p in ps if len(p) > 60]
    return ps

rep = {'articles': [], 'feeds': []}
ed = json.load(open('site/data/latest.json', encoding='utf-8'))['edition']
seen = set()
for it in ed['items']:
    s = it['sources'][0]
    src = s['label'].split(' : ')[0]
    if src in seen: continue
    seen.add(src)
    r = {'source': src, 'url': s['url']}
    try:
        st, ct, t = get(s['url'])
        ps = body_text(t)
        r.update(status=st, paragraphs=len(ps), chars=sum(len(p) for p in ps), og_image=meta(t, 'og:image')[:160],
                 og_desc=len(meta(t, 'og:description')), jsonld_article=bool(re.search(r'"articleBody"', t)),
                 paywall=bool(re.search(r'paywall|abonn[ée]s?-vous|subscribe to (read|continue)|réservé aux abonnés', t, re.I)),
                 license=meta(t, 'license')[:80], sample=(ps[0][:160] if ps else ''))
    except Exception as e:
        r['error'] = f'{type(e).__name__}: {str(e)[:80]}'
    rep['articles'].append(r); print(r.get('status'), r.get('chars'), src, flush=True)

FEEDS = [
 "https://www.sciencedaily.com/rss/matter_energy/engineering.xml", "https://www.sciencedaily.com/rss/computers_math/artificial_intelligence.xml",
 "https://techxplore.com/rss-feed/", "https://phys.org/rss-feed/technology-news/", "https://newatlas.com/index.rss",
 "https://spectrum.ieee.org/feeds/feed.rss", "https://www.technologyreview.com/feed/", "https://interestingengineering.com/feed",
 "https://www.futura-sciences.com/rss/tech/actualites.xml", "https://www.numerama.com/feed/", "https://www.nasa.gov/technology/feed/",
 "https://spinoff.nasa.gov/rss.xml", "https://www.freepatentsonline.com/rss.xml", "https://www.wipo.int/pressroom/en/rss.xml",
 "https://www.epo.org/en/rss/news", "https://www.inpi.fr/rss.xml", "https://www.sciencedaily.com/rss/top/technology.xml",
]
for u in FEEDS:
    r = {'url': u}
    try:
        st, ct, t = get(u)
        items = re.findall(r'<(?:item|entry)[\s>][\s\S]*?</(?:item|entry)>', t)
        d = [re.search(r'<(?:pubDate|published|updated|dc:date)>([^<]+)<', i) for i in items[:2]]
        tt = [re.search(r'<title[^>]*>(?:<!\[CDATA\[)?([^<\]]+)', i) for i in items[:2]]
        r.update(status=st, items=len(items), dates=[x.group(1) for x in d if x], titles=[x.group(1)[:80] for x in tt if x],
                 media=bool(re.search(r'<media:(?:content|thumbnail)|<enclosure', t)))
    except Exception as e:
        r['error'] = f'{type(e).__name__}: {str(e)[:80]}'
    rep['feeds'].append(r); print(r.get('status'), r.get('items'), u, flush=True)
json.dump(rep, open('diag/report2.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
