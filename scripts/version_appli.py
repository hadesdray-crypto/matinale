"""Met dans la page le numéro de version de l'appli : celui de la première entrée de site/nouveautes.json.
Ainsi la page en ligne et la liste des nouveautés ont toujours le même numéro (sinon la bannière
« Nouvelle mise à jour » reviendrait sans fin)."""
import json, re, pathlib
racine = pathlib.Path(__file__).resolve().parent.parent / 'site'
v = int(json.loads((racine / 'nouveautes.json').read_text(encoding='utf-8'))[0]['v'])
page = racine / 'index.html'
s = page.read_text(encoding='utf-8')
s2, n = re.subn(r'const APP_V = \d+;', f'const APP_V = {v};', s, count=1)
if n != 1:
    raise SystemExit('APP_V introuvable dans site/index.html')
page.write_text(s2, encoding='utf-8')
print(f'Version de l\'appli : {v}')
