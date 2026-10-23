#!/usr/bin/env python3
"""Matinale des Sciences - fabrique l'enregistrement audio de l'édition.

Usage :
  python3 make_audio.py --edition site/data/latest.json --tts /chemin/sherpa-onnx-offline-tts \
      --voice /chemin/vits-piper-fr_FR-siwis-medium --out DOSSIER_SORTIE

Produit dans DOSSIER_SORTIE : flash.mp3, full.mp3 et audio.json (chapitres avec début, fin et texte).
Les chapitres sont construits exactement comme dans la page (même ordre, mêmes textes).
"""
import argparse, json, os, re, subprocess, sys, tempfile, wave, datetime

CAT_IDS = ['espace', 'sante', 'cerveau', 'physique', 'terre', 'vivant', 'archeo', 'tech']
LEVELS = {4: 'Établi', 3: 'Solide', 2: 'Préliminaire', 1: 'Hypothèse', 0: 'Non évalué'}
MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre']
JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
GAP_S = 0.8  # silence entre deux chapitres


def arr(v):
    return [x for x in v if x not in (None, '')] if isinstance(v, list) else []


def long_date(d):
    try:
        x = datetime.date.fromisoformat(str(d)[:10])
    except ValueError:
        return ''
    day = '1er' if x.day == 1 else str(x.day)
    return f"{JOURS[x.weekday()]} {day} {MOIS[x.month - 1]} {x.year}"


def lvl(it):
    v = (it.get('evidence') or {}).get('level')
    if v == 0 or v == '0':
        return 0
    try:
        n = int(v)
    except (TypeError, ValueError):
        n = 2
    return n if n in (1, 2, 3, 4) else 2


def item_audio(it):
    if it.get('audio'):
        return it['audio']
    body = it.get('body') if isinstance(it.get('body'), list) else ([it['body']] if it.get('body') else [])
    return ' '.join([it['title'] + '.', it.get('dek', '')] + arr(body) + ['Niveau de preuve : ' + LEVELS[lvl(it)] + '.'])


def item_full_audio(it):
    """Texte complet d'une fiche, pour l'écoute d'un seul sujet (même texte que la page)."""
    body = it.get('body') if isinstance(it.get('body'), list) else ([it['body']] if it.get('body') else [])
    ev = it.get('evidence') or {}
    parts = [it['title'] + '.', it.get('dek', '')] + arr(body)
    if it.get('why'):
        parts.append('Pourquoi c\'est important : ' + it['why'])
    parts.append('Niveau de preuve : ' + LEVELS[lvl(it)] + '.' + (' ' + ev['note'] if ev.get('note') else ''))
    if arr(it.get('sure')):
        parts.append('Ce qui est établi : ' + ' '.join(arr(it['sure'])))
    if arr(it.get('unsure')):
        parts.append('Ce qui reste à prouver : ' + ' '.join(arr(it['unsure'])))
    return ' '.join(str(x) for x in parts if x)


def concept_audio(c):
    return c.get('audio') or ' '.join(['Le concept du jour : ' + c['title'] + '.'] + arr(c.get('text')))


def speechify(s):
    s = str(s or '')
    s = re.sub(r'≈\s?', 'environ ', s)
    s = re.sub(r'×\s?', 'fois ', s)
    s = s.replace('&', ' et ').replace('km²', ' kilomètres carrés').replace('km/h', ' kilomètres à l’heure')
    s = s.replace('10⁻¹⁵', 'dix puissance moins quinze')
    s = re.sub(r'\s[–—]\s', ', ', s)
    s = s.replace('«', '').replace('»', '')
    return re.sub(r'\s+', ' ', s).strip()


def chapters_for(ed, mode):
    items = [dict(it) for it in arr(ed.get('items')) if isinstance(it, dict) and it.get('id') and it.get('title')]
    for it in items:
        if it.get('cat') not in CAT_IDS:
            it['cat'] = 'tech'
    items.sort(key=lambda it: CAT_IDS.index(it['cat']))  # tri stable, comme la page
    pd = ed.get('podcast') or {}
    dt = long_date(ed.get('date'))
    ch = []
    if mode == 'flash':
        ch.append({'title': 'Ouverture', 'text': pd.get('flashIntro') or f'Bonjour, voici le flash de la Matinale des sciences du {dt}.'})
        for it in items:
            ch.append({'key': it['id'], 'title': it['title'], 'text': it.get('flash') or it.get('dek') or it['title']})
        ch.append({'title': 'Clôture', 'text': pd.get('flashOutro') or "Les détails, les vidéos et les sources sont dans l'application. Belle journée !"})
    else:
        ch.append({'title': 'Ouverture', 'text': pd.get('intro') or f'Bonjour et bienvenue dans la Matinale des sciences du {dt}.'})
        for it in items:
            ch.append({'key': it['id'], 'title': it['title'], 'text': item_audio(it)})
        c = ed.get('concept') or {}
        if c.get('title'):
            ch.append({'title': 'Le concept du jour', 'text': concept_audio(c)})
        hls = [h for h in arr((ed.get('francophonie') or {}).get('highlights')) if isinstance(h, dict) and h.get('id') and h.get('title') and h.get('audio')]
        if hls:
            ch.append({'title': 'Francophonie', 'text': ' '.join([pd.get('franco') or 'Place à la francophonie.'] + [h['audio'] for h in hls])})
        ch.append({'title': 'Clôture', 'text': pd.get('outro') or "C'est la fin de cette édition. Rendez-vous demain matin pour de nouvelles découvertes."})
    return [c for c in ch if str(c.get('text') or '').strip()]


def synth(tts, voice, text, out_wav):
    model = [f for f in os.listdir(voice) if f.endswith('.onnx')][0]
    cmd = [tts, f'--vits-model={os.path.join(voice, model)}', f'--vits-tokens={os.path.join(voice, "tokens.txt")}',
           f'--vits-data-dir={os.path.join(voice, "espeak-ng-data")}', f'--num-threads={max(1, os.cpu_count() or 1)}',
           f'--output-filename={out_wav}', text]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out_wav):
        raise RuntimeError('synthèse impossible : ' + (r.stderr or r.stdout)[-400:])


def build(ed, mode, tts, voice, out_dir, tmp):
    chs = chapters_for(ed, mode)
    frames, params, t, rate = [], None, 0.0, None
    for i, c in enumerate(chs):
        wav_path = os.path.join(tmp, f'{mode}-{i:02d}.wav')
        synth(tts, voice, speechify(c['text']), wav_path)
        with wave.open(wav_path, 'rb') as w:
            if params is None:
                params, rate = w.getparams(), w.getframerate()
            data = w.readframes(w.getnframes())
            dur = w.getnframes() / w.getframerate()
        c['start'] = round(t, 2)
        t += dur
        c['end'] = round(t, 2)
        frames.append(data)
        if i < len(chs) - 1:
            gap = b'\x00' * int(GAP_S * rate) * params.sampwidth * params.nchannels
            frames.append(gap)
            t += GAP_S
    full_wav = os.path.join(tmp, f'{mode}.wav')
    with wave.open(full_wav, 'wb') as w:
        w.setparams(params)
        for f in frames:
            w.writeframes(f)
    mp3 = os.path.join(out_dir, f'{mode}.mp3')
    title = ('Le flash' if mode == 'flash' else 'Édition complète') + ' – Matinale des Sciences – ' + long_date(ed.get('date'))
    subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', full_wav, '-ac', '1', '-ar', '22050', '-codec:a', 'libmp3lame', '-b:a', '48k',
                    '-metadata', f'title={title}', '-metadata', 'artist=Matinale des Sciences', mp3], check=True)
    return {'src': f'audio/{mode}.mp3', 'duration': round(t, 2), 'bytes': os.path.getsize(mp3), 'chapters': chs}


def build_items(ed, tts, voice, out_dir, tmp):
    """Un enregistrement par fiche (texte complet), dans out_dir/items/. Une fiche qui échoue est simplement ignorée."""
    items_dir = os.path.join(out_dir, 'items')
    os.makedirs(items_dir, exist_ok=True)
    res = {}
    for n, it in enumerate(arr(ed.get('items'))):
        if not isinstance(it, dict) or not it.get('id') or not it.get('title'):
            continue
        iid = re.sub(r'[^A-Za-z0-9_-]', '-', str(it['id']))[:80]
        try:
            text = item_full_audio(it)
            wav = os.path.join(tmp, f'item-{n:02d}.wav')
            synth(tts, voice, speechify(text), wav)
            with wave.open(wav, 'rb') as w:
                dur = w.getnframes() / w.getframerate()
            mp3 = os.path.join(items_dir, iid + '.mp3')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', wav, '-ac', '1', '-ar', '22050', '-codec:a', 'libmp3lame', '-b:a', '32k',
                            '-metadata', 'title=' + it['title'], '-metadata', 'artist=Matinale des Sciences', mp3], check=True)
            res[str(it['id'])] = {'src': f'audio/items/{iid}.mp3', 'duration': round(dur, 2), 'bytes': os.path.getsize(mp3),
                                  'chapters': [{'key': it['id'], 'title': it['title'], 'text': text, 'start': 0, 'end': round(dur, 2)}]}
        except Exception as e:  # noqa: BLE001
            print('fiche ignorée', it.get('id'), type(e).__name__, str(e)[:120], file=sys.stderr)
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--edition', required=True)
    ap.add_argument('--tts', required=True)
    ap.add_argument('--voice', required=True)
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    ed = json.load(open(a.edition, encoding='utf-8'))
    if isinstance(ed, dict) and 'items' not in ed:
        for k in ('edition', 'data'):  # latest.json ou document de la base
            if isinstance(ed.get(k), dict):
                ed = ed[k]
                break
    os.makedirs(a.out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        res = {'date': ed.get('date'), 'voice': os.path.basename(os.path.normpath(a.voice)),
               'generatedAt': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
        for mode in ('flash', 'full'):
            res[mode] = build(ed, mode, a.tts, a.voice, a.out, tmp)
            print(mode, res[mode]['duration'], 's,', res[mode]['bytes'], 'octets,', len(res[mode]['chapters']), 'chapitres', file=sys.stderr)
        try:
            res['items'] = build_items(ed, a.tts, a.voice, a.out, tmp)
            print('fiches', len(res['items']), file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print('enregistrements par fiche indisponibles', type(e).__name__, file=sys.stderr)
    json.dump(res, open(os.path.join(a.out, 'audio.json'), 'w', encoding='utf-8'), ensure_ascii=False, separators=(',', ':'))
    print('OK', os.path.join(a.out, 'audio.json'))


if __name__ == '__main__':
    main()
