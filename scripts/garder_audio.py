"""Garde les voix des 14 derniers jours (flash, édition complète, fiches) dans le site publié.

Chaque publication repart de zéro : ce script range la voix du jour dans audio/jours/AAAA-MM-JJ/,
reprend sur le site en ligne celles des jours d'avant (13 au plus), puis écrit :
  audio/index/AAAA-MM-JJ.json        même forme que audio/audio.json (lu par l'appli)
  audio/index/AAAA-MM-JJ-court.json  version légère (titres, fichiers, durées) pour les petits appareils
  audio/index/jours.json             la liste des jours disponibles, du plus récent au plus ancien
Usage : python3 scripts/garder_audio.py site https://compte.github.io/depot
"""
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request

JOURS = 14
site, base = sys.argv[1], sys.argv[2].rstrip('/')
aud = os.path.join(site, 'audio')
idx = os.path.join(aud, 'index')
os.makedirs(idx, exist_ok=True)


def lire_json_en_ligne(rel):
    try:
        with urllib.request.urlopen(base + '/' + urllib.parse.quote(rel), timeout=30) as r:
            return json.loads(r.read().decode('utf-8'))
    except Exception:  # noqa: BLE001
        return None


def recuperer(rel):
    if not isinstance(rel, str) or not rel.startswith('audio/') or '..' in rel:
        return False
    dest = os.path.join(site, rel)
    if os.path.exists(dest):
        return True
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        with urllib.request.urlopen(base + '/' + urllib.parse.quote(rel), timeout=90) as r:
            data = r.read()
        with open(dest, 'wb') as f:
            f.write(data)
        return True
    except Exception:  # noqa: BLE001
        return False


def ecrire(jour, a):
    with open(os.path.join(idx, jour + '.json'), 'w', encoding='utf-8') as f:
        json.dump(a, f, ensure_ascii=False, separators=(',', ':'))
    court = {'date': jour, 'sujets': []}
    for mode in ('flash', 'full'):
        m = a.get(mode)
        if isinstance(m, dict) and m.get('src'):
            court[mode] = {'src': m['src'], 'duree': round(m.get('duration') or 0)}
    for it in (a.get('items') or {}).values():
        if not isinstance(it, dict) or not it.get('src'):
            continue
        ch = (it.get('chapters') or [{}])[0]
        court['sujets'].append({'t': ch.get('title') or it.get('title') or '', 's': it['src'], 'd': round(it.get('duration') or 0)})
    with open(os.path.join(idx, jour + '-court.json'), 'w', encoding='utf-8') as f:
        json.dump(court, f, ensure_ascii=False, separators=(',', ':'))


jours = []
# 1) la voix du jour : flash et édition complète copiés dans leur dossier daté
try:
    a = json.load(open(os.path.join(aud, 'audio.json'), encoding='utf-8'))
except Exception:  # noqa: BLE001
    a = None
if isinstance(a, dict) and a.get('date'):
    jour = a['date']
    j = dict(a)
    for mode in ('flash', 'full'):
        m = a.get(mode)
        if isinstance(m, dict) and m.get('src'):
            src = os.path.join(site, m['src'])
            rel = f'audio/jours/{jour}/{mode}.mp3'
            if os.path.exists(src):
                os.makedirs(os.path.dirname(os.path.join(site, rel)), exist_ok=True)
                shutil.copyfile(src, os.path.join(site, rel))
                j[mode] = dict(m, src=rel)
            else:
                j.pop(mode, None)
    ecrire(jour, j)
    jours.append(jour)

# 2) les jours d'avant, repris sur le site en ligne
liste = lire_json_en_ligne('audio/index/jours.json') or {}
for jour in liste.get('jours') or []:
    if jour in jours or len(jours) >= JOURS:
        continue
    j = lire_json_en_ligne(f'audio/index/{jour}.json')
    if not isinstance(j, dict):
        continue
    fichiers = [(j.get(m) or {}).get('src') for m in ('flash', 'full')]
    fichiers += [(it or {}).get('src') for it in (j.get('items') or {}).values() if isinstance(it, dict)]
    ok = sum(1 for rel in fichiers if rel and recuperer(rel))
    if ok:
        ecrire(jour, j)
        jours.append(jour)

jours = sorted(set(jours), reverse=True)[:JOURS]
with open(os.path.join(idx, 'jours.json'), 'w', encoding='utf-8') as f:
    json.dump({'jours': jours}, f, ensure_ascii=False)
print(f'Voix gardées pour {len(jours)} jour(s) : {", ".join(jours)}')
