#!/usr/bin/env python3
"""
Echte Aufstellungen aus den SkillCorner-Spieldaten (Dynamic Events) aller Ligaspiele.

Pro Spiel und Team:
  - Startelf mit Durchschnittsposition im eigenen Ballbesitz (x = Richtung gegnerisches Tor, y = links positiv)
  - Einwechselspieler mit Minute
  - Grundordnung gegen den Ball (von SkillCorner erkannt, z. B. 4-4-2), mit Anteil

Quelle: 02_Daten/liga/events/<match_id>.csv.gz, Ergebnisse aus 02_Daten/liga_kennzahlen.json
Ergebnis: 02_Daten/liga_aufstellungen.json (bereits ausgewertete Spiele bleiben erhalten)
"""
import collections, csv, gzip, json, os, statistics, sys

HIER = os.path.dirname(os.path.abspath(__file__))
DATEN = os.environ.get('MSV_DATEN', os.path.join(os.path.dirname(HIER), '02_Daten'))
EVENTS = os.path.join(DATEN, 'liga', 'events')
ZIEL = os.path.join(DATEN, 'liga_aufstellungen.json')
VERSION = 4
SPIELINFO = os.path.join(DATEN, 'liga', 'spiele')
POS_EVENTS = ('player_possession', 'passing_option', 'off_ball_run')
START_BIS_MINUTE = 5


def formation(code):
    code = str(code or '').strip()
    return '-'.join(code) if code.isdigit() else code


def nummern(mid):
    f = os.path.join(SPIELINFO, str(mid) + '.json')
    if not os.path.exists(f):
        return {}
    return {str(x.get('id')): x.get('nummer') for x in json.load(open(f, encoding='utf-8')).get('spieler', []) if x.get('nummer') is not None}


def auswerten(pfad):
    nr = nummern(os.path.basename(pfad).split('.')[0])
    zeilen = list(csv.DictReader(gzip.open(pfad, 'rt', encoding='utf-8')))
    spieler = {}   # player_id -> dict
    struktur = collections.defaultdict(collections.Counter)  # team_id des Ballbesitz-Teams -> Formation des Gegners
    teams = set()
    for e in zeilen:
        tid, pid = e.get('team_id'), e.get('player_id')
        if not tid:
            continue
        teams.add(tid)
        ds = str(e.get('defensive_structure') or '').strip()
        if ds.isdigit() and sum(int(c) for c in ds) == 10:   # nur vollstaendige Ordnungen (10 Feldspieler)
            struktur[tid][formation(ds)] += 1
        if not pid:
            continue
        s = spieler.setdefault(pid, {'team': tid, 'name': e.get('player_name') or '', 'erste': 999, 'xy': [], 'rollen': collections.Counter()})
        try:
            minute = int(float(e.get('minute_start') or 0))
        except ValueError:
            minute = 0
        s['erste'] = min(s['erste'], minute)
        if e.get('player_position'):
            s['rollen'][e['player_position']] += 1
        if e.get('event_type') in POS_EVENTS and e.get('x_start') and e.get('y_start'):
            s['xy'].append((float(e['x_start']), float(e['y_start'])))
    aus = {}
    for tid in teams:
        andere = [t for t in teams if t != tid]
        # Formation dieses Teams gegen den Ball = defensive_structure in den Ballbesitz-Aktionen des Gegners
        zaehler = collections.Counter()
        for t in andere:
            zaehler.update(struktur[t])
        gesamt = sum(zaehler.values())
        forms = [{'f': f, 'anteil': round(n / gesamt, 2)} for f, n in zaehler.most_common(3)] if gesamt else []
        start, wechsel = [], []
        kader = sorted([(s['erste'], pid, s) for pid, s in spieler.items() if s['team'] == tid], key=lambda z: z[0])
        startelf = {pid for _, pid, _ in kader[:11]}   # die 11 Spieler mit der fruehesten ersten Aktion
        for erste, pid, s in kader:
            rolle = s['rollen'].most_common(1)[0][0] if s['rollen'] else ''
            if pid in startelf and len(s['xy']) >= 5:
                start.append({'id': pid, 'name': s['name'], 'rolle': rolle, 'nr': nr.get(pid),
                              'x': round(statistics.mean(p[0] for p in s['xy']), 1),
                              'y': round(statistics.mean(p[1] for p in s['xy']), 1), 'n': len(s['xy'])})
            elif pid not in startelf:
                wechsel.append({'id': pid, 'name': s['name'], 'rolle': rolle, 'nr': nr.get(pid), 'ab': erste})
        start.sort(key=lambda p: p['x'])
        wechsel.sort(key=lambda p: p['ab'])
        aus[tid] = {'gegen_ball': forms, 'start': start, 'wechsel': wechsel}
    return aus


def main():
    kennz = json.load(open(os.path.join(DATEN, 'liga_kennzahlen.json'), encoding='utf-8'))['spiele']
    alt = json.load(open(ZIEL, encoding='utf-8')) if os.path.exists(ZIEL) else {}
    spiele = alt.get('spiele', {}) if alt.get('version') == VERSION else {}
    neu = 0
    for sp in kennz:
        mid = str(sp['match_id'])
        pfad = os.path.join(EVENTS, mid + '.csv.gz')
        hat_info = os.path.exists(os.path.join(SPIELINFO, mid + '.json'))
        if (mid in spiele and (spiele[mid].get('mit_nummern') or not hat_info)) or not os.path.exists(pfad):
            continue
        try:
            teams = auswerten(pfad)
        except Exception as e:
            print('Spiel', mid, 'nicht auswertbar:', e)
            continue
        info = {}
        for kurz, t in (sp.get('teams') or {}).items():
            tid = str(t.get('team_id'))
            anz = lambda v: len(v) if isinstance(v, list) else v
            info[tid] = {'name': t.get('name') or kurz, 'tore': anz(t.get('tore')), 'gegentore': anz(t.get('gegentore'))}
        for tid, a in teams.items():
            a.update(info.get(tid, {}))
        spiele[mid] = {'datum': sp.get('datum'), 'teams': teams, 'mit_nummern': hat_info}
        neu += 1
    json.dump({'version': VERSION, 'spiele': spiele}, open(ZIEL, 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'Aufstellungen: {len(spiele)} Spiele ({neu} neu ausgewertet).')


def aufstellungen_laden(anzahl=3):
    """Fuer die Build-Skripte: je Team die letzten <anzahl> Spiele, neuestes zuerst."""
    if not os.path.exists(ZIEL):
        return {}
    spiele = json.load(open(ZIEL, encoding='utf-8')).get('spiele', {})
    proteam = collections.defaultdict(list)
    for mid, sp in spiele.items():
        for tid, t in sp['teams'].items():
            gegner = [x for k, x in sp['teams'].items() if k != tid]
            proteam[tid].append(dict(t, match_id=mid, datum=sp.get('datum'), gegner=(gegner[0].get('name') if gegner else ''), gegner_id=next((k for k in sp['teams'] if k != tid), '')))
    return {tid: sorted(l, key=lambda x: x['datum'] or '', reverse=True)[:anzahl] for tid, l in proteam.items()}


if __name__ == '__main__':
    main()
