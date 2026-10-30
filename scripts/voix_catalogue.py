"""Catalogue des voix téléchargeables de la Matinale (voix Piper, rhasspy/piper-voices v1.0.0).
Usage : python3 scripts/voix_catalogue.py voices.json > site/voix-catalogue.json
(voices.json : https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/voices.json)"""
import json, sys
QUAL = {'x_low': 'très légère', 'low': 'légère', 'medium': 'moyenne', 'high': 'haute'}
FR = {  # id : (nom, genre, description, licence, ordre)
    'fr_FR-siwis-low': ('Siwis légère', 'femme', "La voix des infos enregistrées, en version légère : la plus rapide à télécharger et à lire.", 'CC BY 4.0', 1),
    'fr_FR-siwis-medium': ('Siwis', 'femme', "La voix des infos enregistrées, en meilleure qualité.", 'CC BY 4.0', 2),
    'fr_FR-tom-medium': ('Tom', 'homme', "Voix masculine posée et claire.", 'AGPL-3.0', 3),
    'fr_FR-upmc-medium#0': ('Jessica', 'femme', "Voix féminine naturelle. Même fichier que Pierre : télécharger l'une donne aussi l'autre.", 'CC BY-SA 4.0', 4),
    'fr_FR-upmc-medium#1': ('Pierre', 'homme', "Voix masculine naturelle. Même fichier que Jessica.", 'CC BY-SA 4.0', 5),
    'fr_FR-gilles-low': ('Gilles', 'homme', "Voix masculine, qualité standard.", 'CC0', 6),
    'fr_FR-mls_1840-low': ('Lecteur', 'homme', "Voix d'un lecteur de livres audio, qualité standard.", 'CC BY 4.0', 7),
    'fr_FR-mls-medium': ('Voix variées', '', "Un seul fichier, 125 lecteurs différents (hommes et femmes) : tu choisis le numéro après le téléchargement.", 'CC BY 4.0', 8),
}
def main(path):
    V = json.load(open(path, encoding='utf-8'))
    out = []
    for key, v in sorted(V.items()):
        onnx = next((f for f in v['files'] if f.endswith('.onnx')), None)
        if not onnx: continue
        mo = round(v['files'][onnx]['size_bytes'] / 1e6)
        L = v['language']; parts = onnx.split('/')  # fr/fr_FR/siwis/low/fr_FR-siwis-low.onnx
        ech_dir = '/'.join(parts[:4])
        spk = v.get('speaker_id_map') or {}
        ids = [key + '#0', key + '#1'] if key == 'fr_FR-upmc-medium' else [key]
        for i, vid in enumerate(ids):
            sp = int(vid.split('#')[1]) if '#' in vid else 0
            e = {'id': vid, 'onnx': onnx, 'mo': mo, 'qualite': QUAL.get(v['quality'], v['quality']), 'langue': L['code'],
                 'langueNom': L['name_native'], 'pays': L.get('country_english', ''), 'speaker': sp,
                 'ech': f'{ech_dir}/speaker_{sp}.mp3', 'locuteurs': v.get('num_speakers', 1)}
            if vid in FR:
                nom, genre, desc, lic, ordre = FR[vid]
                e.update(nom=nom, genre=genre, desc=desc, licence=lic, ordre=ordre, fr=True)
            else:
                e.update(nom=v['name'].replace('_', ' ').title(), genre='', desc='', licence='', ordre=100, fr=L['family'] == 'fr')
            out.append(e)
    out.sort(key=lambda e: (e['ordre'], e['langue'], e['nom']))
    json.dump({'source': 'https://huggingface.co/rhasspy/piper-voices (v1.0.0)', 'voix': out}, sys.stdout, ensure_ascii=False, separators=(',', ':'))
if __name__ == '__main__':
    main(sys.argv[1])
