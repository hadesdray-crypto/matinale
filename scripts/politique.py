#!/usr/bin/env python3
"""Matinale - rubrique « Politique & monde » : chaque matin, une dizaine de sujets de politique française et internationale.

- Sources : médias de tendances variées et sources officielles (scripts/sources-politique.json).
- Un même événement couvert par plusieurs médias devient UN sujet, avec tous ses liens : on peut tout lire à la source.
- Gemini (gratuit) rédige des fiches neutres : les faits d'abord, puis les positions de chacun, attribuées.
  Garde-fous : un chiffre absent des articles fait retirer la phrase ; sans Gemini, l'édition est faite des titres et résumés.
- Pas d'images (les photos de presse ne sont pas libres de droits).
Sortie : site/data/politique/latest.json et site/data/politique/editions/<date>.json
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build  # noqa: E402
from build import (JUNK, PARIS, STATS, clean_url, fetch, gemini_call, link_status, load_json, log, long_date, norm,  # noqa: E402
                   number_set, numbers_ok, one_line, read_source, s_, sentences, shorten, similar, slugify, summary_md, write_json)

ZONES = ('france', 'monde')
OFF_TOPIC = re.compile(r"\b(football|ligue 1|ligue des champions|rugby|tennis|jeux olympiques|match|people|horoscope|recette|meteo|loto"
                       r"|bons? plans?|promo|soldes|serie tele|telerealite|cinema|box-office|quiz)\b")

PROMPT = """Tu es le rédacteur de la rubrique « Politique et monde » de « La Matinale », une revue de presse quotidienne en français, neutre et fiable, pour le grand public.

Voici des ARTICLES publiés ces dernières heures par des médias de toutes tendances et par des sources officielles.
Choisis les {n} sujets les plus importants de l'actualité politique française et internationale : gouvernement, Parlement, lois, élections, partis, justice touchant la vie publique, Union européenne, diplomatie, conflits, grandes décisions internationales.
Répartis-les selon l'actualité : environ moitié France, moitié monde, mais adapte (par exemple 7 et 3) quand un côté est beaucoup plus chargé.
Écarte les faits divers sans portée politique, le sport, le people, la culture, la météo, la publicité et les tribunes d'opinion.
Un même événement couvert par plusieurs médias forme UN SEUL sujet : mets toutes les références qui en parlent dans "refs", la plus complète ou la plus officielle en premier.

Pour chaque sujet, écris en français clair et NEUTRE :
- "refs" : références des articles sur ce sujet (ex. ["a3", "a17"]).
- "zone" : "france" ou "monde".
- "titre" : titre factuel de moins de 90 caractères, sans point d'exclamation ni mot de jugement.
- "chapeau" : 1 ou 2 phrases qui disent l'essentiel.
- "texte" : 2 ou 3 paragraphes courts (liste de chaînes) : les faits, le contexte, la suite.
- "flash" : une phrase pour le bulletin audio.
- "pourquoi" : une phrase sur l'enjeu.
- "faits" : 1 à 3 faits établis (ce qui s'est passé : décision, vote, annonce officielle, bilan officiel).
- "positions" : 0 à 4 phrases qui attribuent clairement la position des principaux acteurs (« Selon le gouvernement… », « Le parti X dénonce… ») ; quand il y a des camps opposés, donne chacun, à égalité.
- "a_suivre" : 0 à 2 prochaines étapes annoncées (vote, sommet, échéance).
- "lieu" : pays ou ville principale, sinon "".

RÈGLES ABSOLUES :
- N'utilise que les informations des textes fournis. N'invente aucun chiffre, nom, date, citation ni bilan.
- Neutralité : ne prends jamais parti, évite les mots chargés, attribue chaque déclaration, accusation ou chiffre contesté à sa source. Une accusation n'est pas un fait établi.
- Les faits avant les réactions. Pas de lien internet. Traduis fidèlement les articles en anglais.

Réponds uniquement avec ce JSON :
{{"titre_edition": "moins de 80 caractères", "intro": "2 phrases qui présentent l'édition", "sujets": [{{"refs": ["a1"], "zone": "france", "titre": "...", "chapeau": "...", "texte": ["..."], "flash": "...", "pourquoi": "...", "faits": ["..."], "positions": ["..."], "a_suivre": ["..."], "lieu": ""}}]}}

ARTICLES :
{articles}
"""

DETAIL_PROMPT = """Tu es le rédacteur de la rubrique « Politique et monde » de « La Matinale », neutre et fiable, pour le grand public francophone.

Pour chaque ARTICLE ci-dessous (texte intégral fourni), écris une FICHE DÉTAILLÉE en français :
- "detail" : 4 à 6 paragraphes (300 à 450 mots au total) écrits dans TES PROPRES MOTS. Ne recopie jamais de phrases de l'article.
  Explique : le contexte, ce qui s'est passé, les chiffres et dates clés, les positions des différents acteurs (attribuées), la suite annoncée.
- "points_cles" : 3 à 5 phrases courtes qui résument l'essentiel.

RÈGLES ABSOLUES :
- N'utilise que les informations présentes dans le texte de l'article. N'invente aucun chiffre, nom, date, institution ou citation.
- Neutralité : ne prends pas parti, évite les mots chargés, attribue chaque déclaration ou accusation à son auteur ; une accusation n'est pas un fait.
- Pas de lien internet. Pas d'opinion personnelle. Traduis fidèlement les articles en anglais ; garde les chiffres tels quels.

Réponds uniquement avec ce JSON :
{{"fiches": [{{"ref": "d1", "detail": ["paragraphe 1", "paragraphe 2"], "points_cles": ["...", "..."]}}]}}

ARTICLES :
{articles}
"""


def collect(sources, now, hours):
    since = now - dt.timedelta(hours=hours)
    import concurrent.futures as cf
    cands = []
    with cf.ThreadPoolExecutor(max_workers=12) as ex:
        futs = {ex.submit(read_source, s): s for s in sources}
        for fut in cf.as_completed(futs):
            src = futs[fut]
            try:
                entries, used = fut.result()
            except Exception:  # noqa: BLE001
                entries, used = [], None
            if not used:
                STATS['feeds_ko'].append(src['name'])
                continue
            STATS['feeds_ok'].append(src['name'])
            for e in entries:
                link, title, d = clean_url(e.get('link')), (e.get('title') or '').strip(), e.get('date')
                if not link or len(title) < 12 or not d or d < since or d > now + dt.timedelta(hours=6):
                    continue
                full = norm(title + ' ' + (e.get('summary') or ''))
                if JUNK.search(full) or OFF_TOPIC.search(full):
                    continue
                score = 3 * int(src.get('priority', 2)) + (2 if d > now - dt.timedelta(hours=12) else 0) + (1 if len(e.get('summary') or '') > 160 else 0)
                cands.append({'title': title, 'link': link, 'date': d, 'summary': e.get('summary') or '', 'zone': src.get('zone', 'france'),
                              'score': score, 'source': src['name'], 'kind': src.get('kind', 'presse'), 'lang': src.get('lang', 'fr'),
                              'priority': int(src.get('priority', 2))})
    # Un sujet repris par plusieurs médias compte davantage.
    for c in cands:
        c['echo'] = sum(1 for o in cands if o is not c and o['source'] != c['source'] and similar(c['title'], o['title']))
        c['score'] += 2 * min(c['echo'], 4)
    cands.sort(key=lambda c: (-c['score'], -c['date'].timestamp()))
    seen, out = set(), []
    for c in cands:
        if c['link'] in seen:
            continue
        seen.add(c['link'])
        out.append(c)
    return out


def clean_list(v, n, ok, size=300):
    return [x.strip() for x in (v or []) if isinstance(x, str) and 0 < len(x.strip()) <= size and ok(x.strip())][:n]


def ai_edition(cands, n, key, used_ids):
    pool, per_src = [], {}
    for c in cands:
        if per_src.get(c['source'], 0) < 6:
            pool.append(c)
            per_src[c['source']] = per_src.get(c['source'], 0) + 1
        if len(pool) >= 90:
            break
    arts = [{'ref': f'a{i}', 'source': c['source'], 'langue': c['lang'], 'zone_probable': c['zone'], 'date': c['date'].astimezone(PARIS).isoformat(timespec='minutes'),
             'titre': c['title'], 'texte': shorten(one_line(c['summary']), 600)} for i, c in enumerate(pool)]
    res, model = gemini_call(PROMPT.format(n=n, articles='\n'.join(json.dumps(a, ensure_ascii=False) for a in arts)), key)
    if not isinstance(res, dict):
        return None
    refs = {a['ref']: c for a, c in zip(arts, pool)}
    items, used_refs = [], set()
    for f in res.get('sujets') or []:
        if not isinstance(f, dict):
            continue
        rs = [r for r in (f.get('refs') or []) if isinstance(r, str) and r in refs and r not in used_refs][:5]
        if not rs:
            continue
        cs = [refs[r] for r in rs]
        allowed = set()
        for c in cs:
            allowed |= number_set(c['title'] + ' ' + c['summary'], variants=True) | {str(c['date'].year), str(c['date'].astimezone(PARIS).day)}

        def ok(txt):
            good = numbers_ok(txt, allowed)
            if not good:
                STATS['ai_sentences_removed'] += 1
            return good
        title, dek = s_(f.get('titre'), 140), s_(f.get('chapeau'), 450)
        if not title or not dek or not ok(title) or not ok(dek):
            continue
        body = [' '.join(x for x in sentences(p.strip()) if ok(x)) for p in (f.get('texte') or []) if isinstance(p, str) and 0 < len(p.strip()) <= 900][:4]
        body = [p for p in body if p]
        zone = f.get('zone') if f.get('zone') in ZONES else cs[0]['zone']
        flash, why = s_(f.get('flash'), 300), s_(f.get('pourquoi'), 400)
        iid, k = slugify(title), 2
        while iid in used_ids:
            iid, k = f'{slugify(title, 52)}-{k}', k + 1
        used_ids.add(iid)
        used_refs.update(rs)
        main = cs[0]
        items.append({
            'id': iid, 'cat': zone, 'pol': True, 'date': main['date'].astimezone(PARIS).date().isoformat(), 'title': title, 'dek': dek, 'body': body,
            'why': why if why and ok(why) else '', 'lieu': s_(f.get('lieu'), 60),
            'sure': clean_list(f.get('faits'), 3, ok), 'positions': clean_list(f.get('positions'), 4, ok, 320), 'next': clean_list(f.get('a_suivre'), 2, ok),
            'unsure': [], 'numbers': [], 'videos': [], 'evidence': {},
            'sources': [{'kind': c['kind'], 'label': f"{c['source']} : {c['title']}", 'url': c['link']} for c in cs],
            'flash': flash if flash and ok(flash) else title, 'videoQuery': title, 'journal': None, 'doi': '', '_src': main,
        })
        if len(items) >= n:
            break
    if len(items) < 4:
        log(f'  · Gemini : seulement {len(items)} sujet(s) valide(s), on passe à la version sans IA.')
        return None
    STATS['mode'], STATS['model'] = 'gemini', model
    allowed_all = set()
    for it in items:
        allowed_all |= number_set(it['_src']['title'] + ' ' + it['_src']['summary'], variants=True)
    t, intro = s_(res.get('titre_edition'), 100), s_(res.get('intro'), 500)
    return {'items': items, 'title': t if t and numbers_ok(t, allowed_all) else '', 'intro': intro if intro and numbers_ok(intro, allowed_all) else ''}


def rss_items(cands, n, used_ids):
    """Sans Gemini : les sujets les plus repris, moitié France, moitié monde, avec le titre et le résumé de la source."""
    out, kept = [], []
    want = {'france': (n + 1) // 2, 'monde': n // 2}
    for c in cands:
        if want.get(c['zone'], 0) <= 0 or any(similar(c['title'], k['title']) for k in kept):
            continue
        kept.append(c)
        want[c['zone']] -= 1
        if len(kept) >= n:
            break
    for c in kept:
        it = build.rss_item(dict(c, cat='tech'), used_ids)
        it.update({'cat': c['zone'], 'pol': True, 'evidence': {}, 'health': False, 'sure': [], 'positions': [], 'next': [], '_src': c})
        it['audio'] = ''
        out.append(it)
    return out


def main():
    ap = argparse.ArgumentParser(description='Rubrique Politique & monde de la Matinale.')
    ap.add_argument('--site', default='site')
    ap.add_argument('--sources', default=os.path.join(HERE, 'sources-politique.json'))
    ap.add_argument('--hours', type=float, default=20)
    ap.add_argument('--max-items', type=int, default=10)
    ap.add_argument('--no-ai', action='store_true')
    ap.add_argument('--no-detail', action='store_true')
    ap.add_argument('--no-link-check', action='store_true')
    a = ap.parse_args()
    STATS.update({'feeds_ok': [], 'feeds_ko': [], 'ai_calls': {}, 'ai_sentences_removed': 0, 'mode': 'rss', 'model': None, 'dropped_links': 0})
    now = dt.datetime.now(dt.timezone.utc)
    today = now.astimezone(PARIS).date().isoformat()
    data_dir = os.path.join(a.site, 'data', 'politique')
    latest = load_json(os.path.join(data_dir, 'latest.json'), {}) or {}
    prev = latest.get('edition') or {}
    key = '' if a.no_ai else (os.environ.get('GEMINI_API_KEY') or '').strip()
    cfg = load_json(a.sources, {}) or {}
    sources = [s for s in cfg.get('feeds', []) if s.get('feed') and (key or s.get('lang', 'fr') == 'fr')]
    log(f'Politique & monde : lecture de {len(sources)} sources' + (' (avec Gemini)' if key else ' (sans IA)') + '…')
    cands = collect(sources, now, a.hours)
    if len(cands) < 15:
        cands = collect(sources, now, 36)
    log(f"Sources lues : {len(STATS['feeds_ok'])} ; muettes : {len(STATS['feeds_ko'])} {STATS['feeds_ko']} ; articles : {len(cands)}")
    used_ids, made = set(), None
    if key and cands:
        made = ai_edition(cands, a.max_items, key, used_ids)
        if not made:
            log('Gemini n\'a pas répondu : nouvel essai dans 40 secondes.')
            time.sleep(40)
            used_ids.clear()
            made = ai_edition(cands, a.max_items, key, used_ids)
    if not made:
        used_ids.clear()
        made = {'items': rss_items([c for c in cands if c['lang'] == 'fr'], a.max_items, used_ids), 'title': '', 'intro': ''}
        STATS['mode'] = 'rss'
    items = made['items']
    if not a.no_link_check and items:
        import concurrent.futures as cf
        with cf.ThreadPoolExecutor(max_workers=8) as ex:
            st = list(ex.map(lambda it: link_status(it['sources'][0]['url']), items))
        items = [it for it, s in zip(items, st) if s != 'mort']
    if len(items) < 3:
        log("Politique & monde : pas assez de sujets vérifiés aujourd'hui, l'édition précédente reste en ligne.")
        return 0
    if key and STATS['mode'] == 'gemini' and not a.no_detail:
        try:
            import detail
            detail.enrich(items, key, fetch, gemini_call, (number_set, numbers_ok, sentences), log, STATS, a.site, today, images=False, prompt=DETAIL_PROMPT)
        except Exception as e:  # noqa: BLE001
            log(f'Fiches détaillées (politique) indisponibles ({type(e).__name__} : {str(e)[:120]}).')
    for it in items:
        it.pop('_src', None)
    items.sort(key=lambda it: ZONES.index(it['cat']))   # la France d'abord, puis le monde (même ordre que le flash)
    nf = sum(1 for it in items if it['cat'] == 'france')
    nm = len(items) - nf
    dl = long_date(today)
    number = prev.get('number') if prev.get('date') == today else (prev.get('number') or 0) + 1
    if not isinstance(number, int):
        number = 1
    ed = {
        'date': today, 'number': number, 'section': 'politique', 'kind': 'Politique & monde', 'title': made['title'],
        'intro': made['intro'] or f"{len(items)} sujets de politique française et internationale, d'après des médias de toutes tendances et des sources officielles. Chaque fiche renvoie aux articles d'origine.",
        'items': items, 'top': items[0]['id'], 'counts': {'france': nf, 'monde': nm},
        'podcast': {'flashIntro': f"Voici le flash politique et monde, ce {dl}. {nf} sujets en France, {nm} dans le monde.",
                    'flashOutro': '', 'intro': '', 'outro': ''},
        'updatedAt': now.astimezone(PARIS).isoformat(timespec='seconds'), 'generator': STATS['mode'], 'model': STATS['model'],
        'sources': sorted({s['label'].split(' : ')[0] for it in items for s in it['sources']}),
    }
    os.makedirs(os.path.join(data_dir, 'editions'), exist_ok=True)
    write_json(os.path.join(data_dir, 'editions', today + '.json'), ed)
    archive = [x for x in (latest.get('archive') or []) if isinstance(x, dict) and x.get('date') and x['date'] != today]
    archive.append({'date': today, 'number': number, 'title': ed['title'] or items[0]['title'], 'count': len(items)})
    archive = sorted(archive, key=lambda x: x['date'], reverse=True)
    archive = [x for x in archive if os.path.exists(os.path.join(data_dir, 'editions', x['date'] + '.json'))][:30]
    keep = {x['date'] + '.json' for x in archive}
    for f in os.listdir(os.path.join(data_dir, 'editions')):
        if f.endswith('.json') and f not in keep:
            os.remove(os.path.join(data_dir, 'editions', f))
    write_json(os.path.join(data_dir, 'latest.json'), {'generatedAt': ed['updatedAt'], 'edition': ed, 'archive': archive})
    mode = f"Gemini ({STATS['model']})" if STATS['mode'] == 'gemini' else 'sans IA'
    log(f"Politique & monde n° {number} du {today} : {len(items)} sujets ({nf} France, {nm} monde), mode {mode}, fiches détaillées : {STATS.get('details', 0)}.")
    log('Demandes à l\'IA (politique) : ' + (', '.join(f'{k} {v}' for k, v in STATS['ai_calls'].items()) or 'aucune'))
    summary_md([f"### Politique & monde du {today}", f"- **{len(items)} sujets** ({nf} France, {nm} monde), mode : {mode}",
                f"- Sources lues : {len(STATS['feeds_ok'])} · muettes : {', '.join(STATS['feeds_ko']) or 'aucune'}"])
    return 0


if __name__ == '__main__':
    sys.exit(main())
