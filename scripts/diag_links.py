#!/usr/bin/env python3
"""Contrôle ponctuel (depuis GitHub) : vidéos YouTube (oEmbed : titre et chaîne) et pages d'encyclopédie."""
import json, os, re, sys, urllib.parse, urllib.request, urllib.error
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 MatinaleDesSciences/1.0'
def get(u, accept='*/*'):
    req = urllib.request.Request(u, headers={'User-Agent': UA, 'Accept': accept, 'Accept-Language': 'fr-FR,fr;q=0.9'})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.status, r.geturl(), r.read(400000).decode('utf-8', 'replace')
out = []
for u in json.load(open(sys.argv[1], encoding='utf-8')):
    r = {'url': u}
    try:
        if 'youtube.com/watch' in u:
            st, _, t = get('https://www.youtube.com/oembed?format=json&url=' + urllib.parse.quote(u, safe=''), 'application/json')
            j = json.loads(t); r.update(status=st, title=j.get('title'), by=j.get('author_name'))
        else:
            st, final, t = get(u, 'text/html')
            m = re.search(r'<title>([^<]+)</title>', t)
            r.update(status=st, final=final, title=m.group(1) if m else '')
    except urllib.error.HTTPError as e:
        r.update(status=e.code)
    except Exception as e:
        r['error'] = f'{type(e).__name__}: {str(e)[:80]}'
    out.append(r); print(r.get('status'), u, r.get('title', ''), flush=True)
os.makedirs('diag', exist_ok=True)
json.dump(out, open('diag/links.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
