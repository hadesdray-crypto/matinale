#!/usr/bin/env python3
"""Contrôle ponctuel : teste des adresses depuis GitHub et écrit un rapport (diag/report.json + extraits)."""
import json, os, re, sys, time, urllib.request, urllib.error
UA = 'Mozilla/5.0 (compatible; MatinaleBot/1.0; +https://github.com/hadesdray-crypto/matinale)'
URLS = json.load(open(sys.argv[1], encoding='utf-8'))
os.makedirs('diag', exist_ok=True)
rep = []
for i, u in enumerate(URLS):
    r = {'url': u}
    t = time.time()
    try:
        req = urllib.request.Request(u, headers={'User-Agent': UA, 'Accept': '*/*', 'Accept-Language': 'fr,en;q=0.8'})
        with urllib.request.urlopen(req, timeout=25) as resp:
            body = resp.read(400000)
            r.update(status=resp.status, type=resp.headers.get('Content-Type'), final=resp.geturl(), bytes=len(body))
            txt = body.decode('utf-8', 'replace')
            r['items'] = len(re.findall(r'<(?:item|entry)[\s>]', txt))
            r['head'] = re.sub(r'\s+', ' ', txt[:700])
            with open(f'diag/body{i:02d}.txt', 'w', encoding='utf-8') as f:
                f.write(u + '\n\n' + txt[:6000])
    except urllib.error.HTTPError as e:
        r.update(status=e.code, error=str(e))
    except Exception as e:
        r.update(error=f'{type(e).__name__}: {e}')
    r['sec'] = round(time.time() - t, 1)
    rep.append(r)
    print(r.get('status'), r.get('items'), u)
json.dump(rep, open('diag/report.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
