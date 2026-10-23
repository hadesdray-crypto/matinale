#!/usr/bin/env python3
"""Contrôle ponctuel (depuis GitHub) : adresses candidates et liens de flux trouvés sur les pages d'accueil."""
import json, os, re, urllib.request, urllib.error
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 MatinaleDesSciences/1.0'
URLS = ["https://www.inrae.fr/rss.xml", "https://www.inrae.fr/actualites/rss.xml", "https://www.inrae.fr/rss/actualites", "https://www.inrae.fr/feed",
        "https://www.inrae.fr/", "https://www.inrae.fr/actualites", "https://cnes.fr/rss.xml", "https://cnes.fr/fr/rss.xml", "https://cnes.fr/rss/actualites",
        "https://cnes.fr/actualites/rss.xml", "https://cnes.fr/", "https://cnes.fr/actualites", "https://presse.cnes.fr/", "https://www.inrae.fr/presse"]
os.makedirs('diag', exist_ok=True)
out = []
for u in URLS:
    r = {'url': u}
    try:
        req = urllib.request.Request(u, headers={'User-Agent': UA, 'Accept': 'text/html,application/rss+xml,*/*;q=0.8', 'Accept-Language': 'fr-FR,fr;q=0.9'})
        with urllib.request.urlopen(req, timeout=25) as resp:
            t = resp.read(600000).decode('utf-8', 'replace')
            r.update(status=resp.status, type=resp.headers.get('Content-Type', ''), final=resp.geturl(),
                     items=len(re.findall(r'<(?:item|entry)[\s>]', t)),
                     dates=re.findall(r'<(?:pubDate|published|updated|dc:date)>([^<]+)<', t)[:2],
                     feeds=sorted(set(re.findall(r'<link[^>]+type=["\']application/(?:rss|atom)\+xml["\'][^>]*href=["\']([^"\']+)', t, re.I) +
                                         re.findall(r'href=["\']([^"\']*(?:rss|feed|atom)[^"\']*)["\']', t, re.I)))[:12])
    except urllib.error.HTTPError as e:
        r.update(status=e.code, error=str(e)[:80])
    except Exception as e:
        r['error'] = f'{type(e).__name__}: {str(e)[:80]}'
    out.append(r); print(r.get('status'), r.get('items'), u, r.get('feeds'), flush=True)
json.dump(out, open('diag/feeds.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
