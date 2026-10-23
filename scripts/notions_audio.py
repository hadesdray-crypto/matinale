#!/usr/bin/env python3
"""Matinale des Sciences - audio des notions « Comprendre », avec la voix française.

Usage :
  python3 notions_audio.py --bases site/data/bases.json --tts /chemin/sherpa-onnx-offline-tts \
      --voice /chemin/vits-piper-fr_FR-siwis-medium --out site/audio/notions

Léger par construction :
  - chaque notion n'est enregistrée qu'une fois : le nom du fichier contient l'empreinte de son texte,
    donc rien n'est refait tant que le texte ne change pas ; un fichier devenu inutile est supprimé ;
  - fichiers mono à 24 kbit/s (environ 3 Mo par heure de parole) ;
  - dans le téléphone, rien n'est téléchargé tant qu'on n'appuie pas sur « Écouter ».
Sortie : out/<id>-<empreinte>.mp3 et out/index.json ({id: {src, duration, bytes, text}}).
"""
import argparse
import concurrent.futures as cf
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import wave

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from make_audio import WORKERS, speechify, synth  # noqa: E402

BITRATE = '24k'


def notion_text(n):
    """Texte lu : niveaux 1 et 2, « Le savais-tu ? » et l'expérience. Les formules du niveau 3 se lisent à l'écran."""
    parts = [n['title'] + '.', (n.get('tagline') or '') + '.']
    parts += [p for p in n.get('kid') or [] if p]
    if n.get('dyk'):
        parts.append('Le savais-tu ? ' + n['dyk'])
    if n.get('more'):
        parts.append('Pour aller plus loin.')
        parts += [p for p in n['more'] if p]
    exp = n.get('exp') or {}
    if exp.get('steps'):
        parts.append('À essayer chez toi : ' + (exp.get('title') or '') + '.')
        parts += [s for s in exp['steps'] if s]
        if exp.get('safety'):
            parts.append(exp['safety'])
    parts.append("Les formules du niveau ingénieur sont à lire dans l'application.")
    return re.sub(r'\s+', ' ', ' '.join(p for p in parts if p and p != '.')).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--bases', required=True)
    ap.add_argument('--tts')
    ap.add_argument('--voice', default='vits-piper-fr_FR-siwis-medium')
    ap.add_argument('--out', required=True)
    ap.add_argument('--check', action='store_true', help="dit seulement s'il y a quelque chose à fabriquer (code 10), sans aucun outil")
    a = ap.parse_args()
    bases = json.load(open(a.bases, encoding='utf-8'))
    voice = os.path.basename(os.path.normpath(a.voice))
    os.makedirs(a.out, exist_ok=True)
    old = json.load(open(os.path.join(a.out, 'index.json'), encoding='utf-8')) if os.path.exists(os.path.join(a.out, 'index.json')) else {}
    old = old.get('notions') or {}
    index, todo = {}, []
    for n in bases.get('notions') or []:
        if not n.get('id') or not n.get('title'):
            continue
        text = notion_text(n)
        h = hashlib.sha1((voice + '|' + BITRATE + '|' + text).encode('utf-8')).hexdigest()[:10]
        iid = re.sub(r'[^A-Za-z0-9_-]', '-', n['id'])[:60]
        name = f'{iid}-{h}.mp3'
        rec = {'src': f'audio/notions/{name}', 'text': text}
        prev = old.get(n['id']) or {}
        if prev.get('src') == rec['src'] and os.path.exists(os.path.join(a.out, name)) and prev.get('duration'):
            rec.update(duration=prev['duration'], bytes=os.path.getsize(os.path.join(a.out, name)))
        else:
            todo.append((n['id'], name, text))
        index[n['id']] = rec

    if a.check:
        stale = [f for f in os.listdir(a.out) if f.endswith('.mp3') and f not in {os.path.basename(v['src']) for v in index.values()}]
        print(f'Audio des notions : {len(todo)} à fabriquer, {len(stale)} fichier(s) inutile(s).')
        return 10 if todo or stale else 0
    if not a.tts:
        ap.error('--tts est nécessaire pour fabriquer')

    def make(job):
        nid, name, text = job
        with tempfile.TemporaryDirectory() as tmp:
            wav = os.path.join(tmp, 'n.wav')
            synth(a.tts, a.voice, speechify(text), wav, threads=1)
            with wave.open(wav, 'rb') as w:
                dur = w.getnframes() / w.getframerate()
            mp3 = os.path.join(a.out, name)
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-ac', '1', '-ar', '22050', '-codec:a', 'libmp3lame',
                            '-b:a', BITRATE, '-metadata', 'title=' + nid, '-metadata', 'artist=Matinale des Sciences', mp3], check=True)
            return nid, round(dur, 2), os.path.getsize(mp3)
    errors = 0
    with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for fut in [ex.submit(make, j) for j in todo]:
            try:
                nid, dur, size = fut.result()
                index[nid].update(duration=dur, bytes=size)
            except Exception as e:  # noqa: BLE001 - une notion sans audio sera lue par la voix du téléphone
                errors += 1
                print('notion sans audio :', type(e).__name__, str(e)[:160], file=sys.stderr)
    index = {k: v for k, v in index.items() if v.get('duration')}
    keep = {os.path.basename(v['src']) for v in index.values()}
    removed = 0
    for f in os.listdir(a.out):
        if f.endswith('.mp3') and f not in keep:
            os.remove(os.path.join(a.out, f))
            removed += 1
    with open(os.path.join(a.out, 'index.json'), 'w', encoding='utf-8') as f:
        json.dump({'voice': voice, 'notions': index}, f, ensure_ascii=False, separators=(',', ':'))
    total = sum(v['bytes'] for v in index.values())
    print(f'Audio des notions : {len(todo) - errors} fabriquée(s), {len(index)} au total ({total / 1048576:.1f} Mo), '
          f'{removed} fichier(s) inutile(s) supprimé(s), {errors} erreur(s).')
    return 0


if __name__ == '__main__':
    sys.exit(main())
