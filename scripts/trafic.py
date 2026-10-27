#!/usr/bin/env python3
"""Matinale des Sciences - événements routiers Bison Futé, résumés en un petit fichier pour l'application.

Source : « Événements routiers sur le réseau routier national non concédé » (DIR / Bison Futé, Licence Ouverte 2.0),
         flux DATEX II mis à jour en continu. Routes nationales et autoroutes non concédées (ex. N13, N154).
Sortie : trafic.json = {"at": date ISO, "src": ..., "ev": [{"id", "t", "y", "x", "y2", "x2", "r", "v", "d", "s", "fin"}]}
  t : type en français (accident, bouchon, travaux, route coupée…), y/x : latitude/longitude (y2/x2 : fin du tronçon),
  r : route (N154), v : commune ou repère, d : précision, s : gravité, fin : fin prévue.
Aucune donnée personnelle : ce sont des données publiques, l'application garde seulement celles proches du trajet.

Usage : python3 trafic.py --out dossier [--xml fichier_local]
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
import xml.etree.ElementTree as ET

URL = 'http://tipi.bison-fute.gouv.fr/bison-fute-ouvert/publicationsDIR/Evenementiel-DIR/grt/RRN/content.xml'
NS = '{http://datex2.eu/schema/2/2_0}'
XSI = '{http://www.w3.org/2001/XMLSchema-instance}type'

TRAFIC = {'stationaryTraffic': 'circulation à l\'arrêt', 'queuingTraffic': 'bouchon', 'slowTraffic': 'circulation ralentie',
          'heavyTraffic': 'trafic dense'}
GESTION = {'roadClosed': 'route coupée', 'carriagewayClosures': 'chaussée fermée', 'laneClosures': 'voie fermée',
           'narrowLanes': 'voies rétrécies', 'singleAlternateLineTraffic': 'circulation alternée', 'contraflow': 'circulation à contresens',
           'rampClosures': 'bretelle fermée', 'exitClosures': 'sortie fermée', 'entryClosures': 'entrée fermée',
           'useOfSpecifiedLanesOrCarriagewaysAllowed': 'voie imposée', 'intermittentShortTermClosures': 'coupures ponctuelles',
           'hardShoulderClosed': 'bande d\'arrêt fermée', 'closedPermanentlyForTheWinter': 'route fermée pour l\'hiver'}
DEVIATION = {'doNotUseExit': 'sortie fermée', 'doNotUseEntry': 'entrée fermée', 'followLocalDiversion': 'déviation',
             'followDiversionSigns': 'déviation', 'doNotUseSpecifiedLanesOrCarriageways': 'voie fermée'}
METEO = {'ice': 'verglas', 'blackIce': 'verglas', 'snowOnTheRoad': 'neige sur la chaussée', 'freezingOfWetRoads': 'verglas',
         'fog': 'brouillard', 'denseFog': 'brouillard dense', 'flooding': 'inondation', 'strongWinds': 'vent fort',
         'heavySnowfall': 'fortes chutes de neige', 'snowfall': 'neige', 'heavyRain': 'fortes pluies', 'hail': 'grêle'}
IGNORE_GESTION = {'weightRestrictionInOperation', 'heightRestrictionInOperation', 'widthRestrictionInOperation',
                  'lengthRestrictionInOperation', 'axleWeightRestrictionInOperation', 'overtakingBanInOperation'}


def txt(el, path):
    x = el.find(path)
    return (x.text or '').strip() if x is not None and x.text else ''


def road(s):
    """N0154 -> N154, A0013 -> A13."""
    m = re.match(r'^([A-Z]+)0*(\d+[A-Z]?)$', (s or '').strip().upper())
    return m.group(1) + m.group(2) if m else (s or '').strip()


def kind(rec):
    typ = (rec.get(XSI) or '').split(':')[-1]
    if typ == 'Accident':
        return 'accident', 3
    if typ == 'AbnormalTraffic':
        v = txt(rec, f'{NS}abnormalTrafficType')
        return TRAFIC.get(v, 'ralentissement'), 2
    if typ in ('MaintenanceWorks', 'ConstructionWorks', 'RoadworksAndMaintenance'):
        return 'travaux', 1
    if typ == 'RoadOrCarriagewayOrLaneManagement':
        v = txt(rec, f'{NS}roadOrCarriagewayOrLaneManagementType')
        if v in IGNORE_GESTION or rec.find(f'{NS}forVehiclesWithCharacteristicsOf') is not None:
            return None, 0   # restrictions réservées aux poids lourds : sans intérêt pour une voiture
        return GESTION.get(v, 'restriction de circulation'), 3 if v == 'roadClosed' else 2
    if typ in ('VehicleObstruction', 'GeneralObstruction', 'EnvironmentalObstruction', 'AnimalPresenceObstruction', 'InfrastructureDamageObstruction'):
        return 'obstacle sur la chaussée', 2
    if typ in ('PoorEnvironmentConditions', 'WeatherRelatedRoadConditions'):
        for k in ('poorEnvironmentType', 'weatherRelatedRoadConditionType'):
            v = txt(rec, f'{NS}{k}')
            if v:
                return METEO.get(v, 'conditions difficiles'), 2
        return 'conditions difficiles', 2
    if typ == 'NonWeatherRelatedRoadConditions':
        return 'chaussée dangereuse', 2
    if typ == 'ReroutingManagement':
        return DEVIATION.get(txt(rec, f'{NS}reroutingManagementType'), 'déviation'), 2
    if typ == 'GeneralNetworkManagement':
        return 'perturbation', 1
    if typ == 'SpeedManagement':
        return 'vitesse réduite', 1
    if typ == 'RoadsideServiceDisruption':
        return 'aire de service fermée', 1
    if typ == 'GeneralInstructionOrMessageToRoadUsers':
        return None, 0   # consignes (interdiction de doubler…) : sans intérêt pour l'heure de départ
    if typ in ('Activity', 'PublicEvent', 'DisturbanceActivity'):
        return 'manifestation', 1
    return 'perturbation', 1


def when(s):
    try:
        return dt.datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:  # noqa: BLE001
        return None


def parse(root, now):
    out = []
    sev_w = {'highest': 3, 'high': 3, 'medium': 2, 'low': 1, 'lowest': 1}
    for sit in root.iter(f'{NS}situation'):
        sev = sev_w.get(txt(sit, f'{NS}overallSeverity'), 1)
        for rec in sit.findall(f'{NS}situationRecord'):
            if txt(rec, f'{NS}probabilityOfOccurrence') == 'riskOf':
                continue
            t, w = kind(rec)
            if not t:
                continue
            spec = rec.find(f'{NS}validity/{NS}validityTimeSpecification')
            deb = when(txt(spec, f'{NS}overallStartTime')) if spec is not None else None
            fin = when(txt(spec, f'{NS}overallEndTime')) if spec is not None else None
            if deb and deb > now + dt.timedelta(hours=18):
                continue   # pas encore commencé
            if fin and fin < now:
                continue   # terminé
            if t == 'travaux' and deb and not fin and (now - deb).days > 120:
                continue   # « travaux » ouverts depuis des mois sans fin prévue : souvent un arrêté permanent
            pts = [(float(p.find(f'{NS}latitude').text), float(p.find(f'{NS}longitude').text))
                   for p in rec.iter(f'{NS}pointCoordinates')
                   if p.find(f'{NS}latitude') is not None and p.find(f'{NS}longitude') is not None]
            if not pts:
                continue
            r, ville = '', ''
            for nm in rec.iter(f'{NS}name'):
                kd = txt(nm, f'{NS}tpegOtherPointDescriptorType')
                val = txt(nm, f'{NS}descriptor/{NS}values/{NS}value')
                if kd == 'linkName' and not r:
                    r = road(val)
                elif kd == 'townName' and not ville:
                    ville = val
            if not r:
                r = road(txt(rec, f'.//{NS}roadNumber'))
            desc, lieu = [], []
            for c in rec.findall(f'{NS}generalPublicComment'):
                v = re.sub(r'\s+', ' ', txt(c, f'{NS}comment/{NS}values/{NS}value')).strip()
                if not v or txt(c, f'{NS}commentType') == 'internalNote':
                    continue
                (lieu if txt(c, f'{NS}commentType') == 'locationDescriptor' else desc).append(v)
            d = ' '.join(x for x in desc if not re.match(r'^(arrêté|arrete)\b', x, re.I))[:180]
            if not d and lieu:
                d = lieu[0][:120]
            ev = {'id': rec.get('id') or sit.get('id'), 't': t, 'y': round(pts[0][0], 4), 'x': round(pts[0][1], 4),
                  'r': r, 'v': ville, 'd': d, 's': max(sev, w)}
            if len(pts) > 1 and (abs(pts[-1][0] - pts[0][0]) > 0.002 or abs(pts[-1][1] - pts[0][1]) > 0.002):
                ev['y2'], ev['x2'] = round(pts[-1][0], 4), round(pts[-1][1], 4)
            if fin:
                ev['fin'] = fin.isoformat(timespec='minutes')
            out.append(ev)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True)
    ap.add_argument('--xml')
    a = ap.parse_args()
    if a.xml:
        data = open(a.xml, 'rb').read()
    else:
        req = urllib.request.Request(URL, headers={'User-Agent': 'MatinaleDesSciences/1.0 (github.com/hadesdray-crypto/matinale)'})
        with urllib.request.urlopen(req, timeout=90) as r:
            data = r.read()
    root = ET.fromstring(data)
    now = dt.datetime.now(dt.timezone.utc)
    ev = parse(root, now)
    os.makedirs(a.out, exist_ok=True)
    res = {'at': now.isoformat(timespec='seconds'), 'src': 'Bison Futé (DIR), Licence Ouverte 2.0', 'ev': ev}
    with open(os.path.join(a.out, 'trafic.json'), 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, separators=(',', ':'))
    kinds = {}
    for e in ev:
        kinds[e['t']] = kinds.get(e['t'], 0) + 1
    print(len(ev), 'événements', kinds, os.path.getsize(os.path.join(a.out, 'trafic.json')), 'octets', file=sys.stderr)


if __name__ == '__main__':
    main()
