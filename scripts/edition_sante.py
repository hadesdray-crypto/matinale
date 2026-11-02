"""Matinale : l'édition du jour est-elle complète ?
Le seuil se règle tout seul d'après les derniers jours (70 % du nombre habituel de fiches, entre 8 et 14).
Sert à deux endroits : build.py (refuse de publier une édition trop maigre) et verif_edition.py (contrôle après coup)."""
import datetime as dt
import json
import os
from zoneinfo import ZoneInfo

PARIS = ZoneInfo('Europe/Paris')


def aujourdhui():
    return dt.datetime.now(dt.timezone.utc).astimezone(PARIS).date().isoformat()


def seuil(archive, today, cible=20):
    """Nombre minimum de fiches pour qu'une édition soit jugée complète.
    Médiane des 7 derniers jours (hors aujourd'hui, et hors éditions de secours à moins de 3 fiches) : une mauvaise
    journée ne fait pas baisser l'exigence."""
    recents = [x['count'] for x in sorted((x for x in (archive or []) if isinstance(x, dict) and x.get('date') != today
                                           and isinstance(x.get('count'), int) and x['count'] >= 3),
                                          key=lambda x: x['date'], reverse=True)[:7]]
    if not recents:
        return min(12, cible)
    recents.sort()
    mediane = recents[len(recents) // 2]
    return max(8, min(14, cible, round(0.7 * mediane)))


def etat(site='site', today=None):
    """Renvoie (ok, nombre de fiches, seuil, message)."""
    today = today or aujourdhui()
    try:
        with open(os.path.join(site, 'data', 'latest.json'), encoding='utf-8') as f:
            latest = json.load(f)
    except (OSError, ValueError):
        return False, 0, seuil([], today), "Aucune édition lisible."
    ed = latest.get('edition') or {}
    n = len(ed.get('items') or [])
    s = seuil(latest.get('archive'), today)
    if ed.get('date') != today:
        return False, n, s, f"L'édition en ligne est celle du {ed.get('date')}, pas celle du {today}."
    if not ed.get('generator'):   # rédigée à la main : on la garde telle quelle
        return True, n, s, "Édition rédigée à la main."
    if ed.get('generator') == 'rss' and os.environ.get('GEMINI_API_KEY'):
        return False, n, s, f"Édition du {today} faite sans IA ({n} fiches de secours) alors que Gemini est configuré."
    if n < s:
        return False, n, s, f"Édition du {today} trop maigre : {n} fiche(s) pour un minimum de {s}."
    return True, n, s, f"Édition du {today} complète : {n} fiche(s) (minimum {s})."
