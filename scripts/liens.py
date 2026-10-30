"""Matinale : vérification quotidienne des liens extérieurs et des services utilisés par l'appli.
- Chaque lien est essayé ; s'il est en panne deux jours de suite, il est remplacé par une solution de rechange
  vérifiée, sinon l'IA gratuite (Gemini, modèle léger, une demande au plus par lien) propose des adresses, qui sont
  vérifiées avant d'être gardées. Rien n'est remplacé sans vérification.
- Les services (météo, adresses, itinéraire, prix, bornes, voix, trafic) sont essayés aussi.
- L'édition du jour : faite par l'IA gratuite, ou en secours sans IA.
- Résultat : site/data/liens.json (lu par l'appli : Options > Application > État de l'appli) et, en cas de
  problème qui dure, un signalement (« issue ») sur GitHub, qui prévient par e-mail.
Ne fait jamais échouer la préparation du matin."""
import argparse, concurrent.futures as cf, datetime as dt, json, os, pathlib, re, sys, time, urllib.error, urllib.request
ICI = pathlib.Path(__file__).resolve().parent
UA = 'Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Mobile Safari/537.36'
PROTEGE = re.compile(rb'(just a moment|cf-chl|cloudflare|captcha|datadome|access denied)', re.I)

def essai(url, timeout=20):
    """(etat, code, ms, corps) — etat : ok, protege (anti-robots : marche dans un vrai navigateur), panne."""
    t0 = time.time()
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': 'text/html,application/json,*/*', 'Accept-Language': 'fr-FR,fr;q=0.9'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            corps = r.read(300000)
            return 'ok', r.status, int((time.time() - t0) * 1000), corps
    except urllib.error.HTTPError as e:
        corps = e.read(200000) if hasattr(e, 'read') else b''
        ms = int((time.time() - t0) * 1000)
        if e.code in (401, 403, 429, 503) and (PROTEGE.search(corps or b'') or e.headers.get('cf-ray') or e.headers.get('x-datadome')):
            return 'protege', e.code, ms, corps
        if e.code in (403, 405) and not corps:
            return 'protege', e.code, ms, corps
        return 'panne', e.code, ms, corps
    except Exception as e:
        return 'panne', 0, int((time.time() - t0) * 1000), str(e).encode()[:200]

def maintenant():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

def signaler(titre, corps):
    """Ouvre un signalement sur GitHub (une seule fois tant qu'il est ouvert)."""
    tok, repo = os.environ.get('GITHUB_TOKEN'), os.environ.get('GITHUB_REPOSITORY')
    if not tok or not repo:
        print('  (signalement non envoyé : pas de jeton GitHub) ' + titre); return
    h = {'Authorization': 'Bearer ' + tok, 'Accept': 'application/vnd.github+json', 'User-Agent': 'matinale'}
    try:
        with urllib.request.urlopen(urllib.request.Request(f'https://api.github.com/repos/{repo}/issues?state=open&labels=matinale-diagnostic&per_page=50', headers=h), timeout=20) as r:
            if any(i.get('title') == titre for i in json.load(r)):
                print('  signalement déjà ouvert : ' + titre); return
        data = json.dumps({'title': titre, 'body': corps, 'labels': ['matinale-diagnostic']}).encode()
        with urllib.request.urlopen(urllib.request.Request(f'https://api.github.com/repos/{repo}/issues', data=data, headers=h, method='POST'), timeout=20) as r:
            print('  signalement ouvert : ' + titre + ' → ' + json.load(r).get('html_url', ''))
    except Exception as e:
        print('  signalement impossible (' + str(e)[:120] + ') : ' + titre)

def chercher_ia(lien):
    """Demande à Gemini (modèle léger) des adresses de remplacement ; rien n'est gardé sans vérification."""
    key = os.environ.get('GEMINI_API_KEY')
    if not key:
        return []
    try:
        sys.path.insert(0, str(ICI))
        from build import gemini_call
        q = ('Propose jusqu\'à 4 adresses web (URL complètes, en https) de sites fiables, gratuits et accessibles en France pour : '
             + lien['but'] + '. Le site actuel ne marche plus : ' + lien['url'] + '. Donne l\'adresse de la page exacte qui sert à ça. '
             'Réponds seulement en JSON : {"liens":[{"nom":"…","url":"https://…","desc":"une phrase simple en français"}]}')
        j, _ = gemini_call(q, key, light=True)
        return [x for x in (j or {}).get('liens', []) if isinstance(x, dict) and str(x.get('url', '')).startswith('https://')][:4]
    except Exception as e:
        print('  recherche par l\'IA impossible : ' + str(e)[:120]); return []

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--site', default='site'); a = ap.parse_args()
    site = pathlib.Path(a.site); sortie = site / 'data' / 'liens.json'
    src = json.loads((ICI / 'liens-sources.json').read_text(encoding='utf-8'))
    avant = {}
    try: avant = {l['id']: l for l in json.loads(sortie.read_text(encoding='utf-8')).get('liens', [])}
    except Exception: pass
    try: avant_srv = {s['id']: s for s in json.loads(sortie.read_text(encoding='utf-8')).get('services', [])}
    except Exception: avant_srv = {}
    jour = dt.date.today().isoformat()
    # 1) tous les essais en parallèle (rapide)
    urls = {l['url'] for l in src['liens']} | {s['url'] for s in src['services']} | {p['url'] for l in src['liens'] for p in l.get('alternatives', [])}
    for l in avant.values():
        if l.get('url'): urls.add(l['url'])
    with cf.ThreadPoolExecutor(8) as ex:
        res = dict(zip(urls, ex.map(essai, urls)))
    # Si presque tout est en panne d'un coup, c'est le réseau du serveur qui flanche : on ne compte rien aujourd'hui.
    pannes = sum(1 for v in res.values() if v[0] == 'panne')
    if pannes > len(res) * 0.6:
        print(f'Réseau du serveur indisponible ({pannes} essais sur {len(res)} sans réponse) : vérification remise à demain.')
        return
    liens, problemes = [], []
    for l in src['liens']:
        prev = avant.get(l['id'], {})
        e, code, ms, _ = res[l['url']]
        o = {k: l[k] for k in ('id', 'groupe', 'nom', 'url', 'desc')}
        o.update(etat=e, code=code, verifie=jour)
        if e != 'panne':
            o['echecs'] = 0
        else:
            o['echecs'] = (prev.get('echecs', 0) + 1) if prev.get('verifie') != jour else prev.get('echecs', 1)
            o['depuis'] = prev.get('depuis') or jour
            print(f"  · lien en panne ({code}) : {l['nom']} {l['url']} — {o['echecs']} jour(s)")
            if o['echecs'] >= 2:
                choix = None
                # garder le remplaçant d'hier s'il marche encore
                if prev.get('origine') and prev.get('url') and prev['url'] != l['url']:
                    pe = res.get(prev['url']) or essai(prev['url'])
                    if pe[0] != 'panne':
                        choix = {'nom': prev['nom'], 'url': prev['url'], 'desc': prev.get('desc', l['desc']), 'auto': prev.get('auto', False)}
                for alt in l.get('alternatives', []):
                    if choix: break
                    if res.get(alt['url'], ('panne',))[0] != 'panne':
                        choix = dict(alt, auto=False)
                if not choix:
                    for prop in chercher_ia(l):
                        pe = essai(prop['url'])
                        if pe[0] == 'ok' and prop['url'] != l['url']:
                            choix = {'nom': str(prop.get('nom') or 'Site de remplacement')[:60], 'url': prop['url'], 'desc': str(prop.get('desc') or l['desc'])[:160], 'auto': True}
                            break
                if choix:
                    o.update(nom=choix['nom'], url=choix['url'], desc=choix['desc'], etat='remplace', auto=choix.get('auto', False), origine={'nom': l['nom'], 'url': l['url']})
                    problemes.append((f"Matinale : lien « {l['nom']} » remplacé", f"Lien remplacé : « {l['nom']} » ({l['url']}) ne répond plus depuis le {o['depuis']} ; remplacé par « {choix['nom']} » ({choix['url']})" + (' — trouvé par l\'IA et vérifié, à contrôler' if choix.get('auto') else '') + '.'))
                else:
                    problemes.append((f"Matinale : lien « {l['nom']} » en panne", f"Lien en panne : « {l['nom']} » ({l['url']}) ne répond plus depuis le {o['depuis']}, et aucun remplaçant fiable n'a été trouvé. Il est masqué dans l'appli."))
        liens.append(o)
    services = []
    for s in src['services']:
        e, code, ms, corps = res[s['url']]
        o = {'id': s['id'], 'nom': s['nom'], 'etat': 'ok' if e != 'panne' else 'panne', 'code': code, 'ms': ms, 'verifie': jour}
        if e != 'panne' and s.get('frais_heures'):
            try:
                at = json.loads(corps).get('at', '')
                age = (dt.datetime.now(dt.timezone.utc) - dt.datetime.fromisoformat(at.replace('Z', '+00:00'))).total_seconds() / 3600
                if age > s['frais_heures']: o['etat'] = 'ancien'; o['detail'] = f'dernier relevé il y a {int(age)} h'
            except Exception: pass
        prev = avant_srv.get(s['id'], {})
        o['echecs'] = 0 if o['etat'] == 'ok' else ((prev.get('echecs', 0) + 1) if prev.get('verifie') != jour else prev.get('echecs', 1))
        if o['etat'] != 'ok':
            print(f"  · service en panne ({code}) : {s['nom']}")
            if o['echecs'] >= 2: problemes.append((f"Matinale : service « {s['nom']} » en panne", f"Service en panne : {s['nom']} ({o.get('detail') or code or 'pas de réponse'}) depuis {o['echecs']} jours. L'appli continue avec ses solutions de secours."))
        services.append(o)
    # 2) l'IA gratuite a-t-elle fait les éditions du jour ?
    ia = {}
    for nom, f in (('sciences', site / 'data' / 'latest.json'), ('politique', site / 'data' / 'politique' / 'latest.json')):
        try:
            d = json.loads(f.read_text(encoding='utf-8')); d = d.get('edition', d)
            ia[nom] = {'date': d.get('date'), 'ia': d.get('generator') == 'gemini', 'modele': d.get('model')}
            if d.get('generator') != 'gemini':
                problemes.append((f"Matinale : édition {nom} faite sans IA", f"Édition {nom} du {d.get('date')} faite sans l'IA gratuite (mode secours) : l'appli marche, mais en version simple. Vérifie la clé GEMINI_API_KEY et le quota si ça dure."))
        except Exception:
            ia[nom] = {'date': None, 'ia': False, 'modele': None}
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({'at': maintenant(), 'liens': liens, 'services': services, 'ia': ia}, ensure_ascii=False, indent=1), encoding='utf-8')
    ok = sum(1 for l in liens if l['etat'] in ('ok', 'protege')); print(f'Liens : {ok} sur {len(liens)} en état de marche ; services : {sum(1 for s in services if s["etat"] == "ok")} sur {len(services)}.')
    if os.environ.get('GITHUB_ACTIONS'):
        resume = ' ; '.join([f"{l['nom']} {l['etat']}" for l in liens] + [f"{x['nom']} {x['etat']}" for x in services] + [f"IA {k} {'oui' if v.get('ia') else 'non'}" for k, v in ia.items()])
        print('::notice title=Etat de l appli::' + resume)
    for titre, p in problemes:
        print('  ! ' + p)
        signaler(titre, p + '\n\nSignalé automatiquement par la vérification du matin (scripts/liens.py). L\'état complet est dans l\'appli : Options > Application > État de l\'appli.')

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print('Vérification des liens impossible : ' + str(e)[:200])
    sys.exit(0)
