#!/usr/bin/env python3
"""
Impect-Excel-Export (Teamwerte 3. Liga) einlesen.

Die neueste .xlsx-Datei in 02_Daten/impect/ wird gelesen (Unterordner werden ignoriert).
Ergebnis fuer das Dashboard: dict {stand, datei, teams: {skillcorner_team_id: {name, w: {"Kategorie|Spalte": wert}}}}

Direkt aufgerufen schreibt das Skript 02_Daten/impect_teams.json (fuer GitHub) und zeigt die Team-Zuordnung:
  python3 impect_einlesen.py
Benoetigt keine Zusatzpakete.
"""
import datetime, difflib, glob, json, os, re, sys, unicodedata, zipfile
import xml.etree.ElementTree as ET

HIER = os.path.dirname(os.path.abspath(__file__))
DATEN = os.environ.get('MSV_DATEN', os.path.join(os.path.dirname(HIER), '02_Daten'))
NS = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
R_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'


def _spalte(ref):
    s = re.match(r'([A-Z]+)', ref).group(1)
    n = 0
    for ch in s:
        n = n * 26 + ord(ch) - 64
    return n - 1


def xlsx_zeilen(pfad):
    """Erstes Tabellenblatt als Liste von Zeilen (Listen) lesen."""
    z = zipfile.ZipFile(pfad)
    strings = []
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si', NS):
            strings.append(''.join(t.text or '' for t in si.iter('{%s}t' % NS['m'])))
    wb = ET.fromstring(z.read('xl/workbook.xml'))
    erstes = wb.find('m:sheets/m:sheet', NS).get(R_NS)
    rels = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
    ziel = [r.get('Target') for r in rels if r.get('Id') == erstes][0]
    ziel = ziel.lstrip('/')
    ziel = ziel if ziel.startswith('xl/') else 'xl/' + ziel
    blatt = ET.fromstring(z.read(ziel))
    zeilen = []
    for row in blatt.iter('{%s}row' % NS['m']):
        werte = {}
        for c in row.findall('m:c', NS):
            t, v = c.get('t'), c.find('m:v', NS)
            if t == 's' and v is not None and v.text is not None:
                x = strings[int(v.text)]
            elif t == 'inlineStr':
                x = ''.join(e.text or '' for e in c.iter('{%s}t' % NS['m']))
            elif v is not None and v.text is not None:
                try:
                    x = float(v.text)
                except ValueError:
                    x = v.text
            else:
                x = None
            werte[_spalte(c.get('r'))] = x
        if werte:
            zeilen.append([werte.get(i) for i in range(max(werte) + 1)])
    return zeilen


def norm(s):
    s = unicodedata.normalize('NFKD', str(s)).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'\b(fc|sc|sv|tsv|ssv|sg|vfb|tsg|1899|04|06|07|1912|1\.)\b', ' ', s)
    return re.sub(r'[^a-z ]', ' ', s).split()


FEST = {  # Impect-Name -> Teil des SkillCorner-Namens, falls die automatische Zuordnung schwankt
    'FC Viktoria Köln': 'viktoria', 'SC Fortuna Köln': 'fortuna koln', 'Fortuna Düsseldorf': 'dusseldorf',
}


def zuordnen(impect_namen, sc_teams):
    """sc_teams: {team_id: name}. Liefert {impect_name: team_id}."""
    aus = {}
    sc = {tid: ' '.join(norm(n)) for tid, n in sc_teams.items()}
    for name in impect_namen:
        key = ' '.join(norm(name))
        if name in FEST:
            treffer = [tid for tid, n in sc.items() if FEST[name] in n]
            if len(treffer) == 1:
                aus[name] = treffer[0]
                continue
        best, wert = None, 0
        for tid, n in sc.items():
            r = difflib.SequenceMatcher(None, key, n).ratio()
            gemeinsam = len(set(key.split()) & set(n.split()))
            r += 0.3 * gemeinsam
            if r > wert:
                best, wert = tid, r
        if best is not None and wert >= 0.6:
            aus[name] = best
    return aus


def neueste_datei(ordner=None):
    ordner = ordner or os.path.join(DATEN, 'impect')
    dateien = [f for f in glob.glob(os.path.join(ordner, '*.xlsx')) if not os.path.basename(f).startswith('~$')]
    return max(dateien, key=os.path.getmtime) if dateien else None


def lesen(pfad, sc_teams):
    zeilen = xlsx_zeilen(pfad)
    kopf1, kopf2 = zeilen[0], zeilen[1]
    schluessel, kat = [], None
    for i in range(len(kopf2)):
        k = kopf1[i] if i < len(kopf1) else None
        if k:
            kat = str(k).strip()
        n = kopf2[i]
        schluessel.append(f'{kat}|{str(n).strip()}' if (kat and n is not None) else None)
    teams_roh = [z for z in zeilen[2:] if z and z[0]]
    zuo = zuordnen([str(z[0]).strip() for z in teams_roh], sc_teams)
    teams = {}
    for z in teams_roh:
        name = str(z[0]).strip()
        tid = zuo.get(name)
        if not tid:
            continue
        w = {}
        for i, k in enumerate(schluessel):
            if k and i < len(z) and isinstance(z[i], (int, float)):
                w[k] = round(float(z[i]), 4)
        teams[str(tid)] = {'name': name, 'w': w}
    stand = datetime.date.fromtimestamp(os.path.getmtime(pfad)).isoformat()
    return {'stand': stand, 'datei': os.path.basename(pfad), 'teams': teams}, zuo


def sc_teams_aus_liga(liga_spiele):
    t = {}
    for sp in liga_spiele:
        for v in (sp.get('teams') or {}).values():
            t[str(v.get('team_id'))] = v.get('name') or ''
    return t


def impect_laden(liga_spiele):
    """Fuer die Build-Skripte: neueste Excel-Datei, sonst 02_Daten/impect_teams.json, sonst {}."""
    pfad = neueste_datei()
    if pfad:
        try:
            return lesen(pfad, sc_teams_aus_liga(liga_spiele))[0]
        except Exception as e:
            print('Impect-Datei konnte nicht gelesen werden:', e, file=sys.stderr)
    j = os.path.join(DATEN, 'impect_teams.json')
    return json.load(open(j, encoding='utf-8')) if os.path.exists(j) else {}


if __name__ == '__main__':
    pfad = neueste_datei()
    if not pfad:
        print('Keine .xlsx in 02_Daten/impect/ gefunden.')
        sys.exit(1)
    liga = json.load(open(os.path.join(DATEN, 'liga_kennzahlen.json'), encoding='utf-8'))['spiele']
    sc = sc_teams_aus_liga(liga)
    daten, zuo = lesen(pfad, sc)
    print('Datei:', os.path.basename(pfad), '| Stand', daten['stand'])
    for name, tid in sorted(zuo.items()):
        print(f'  {name:28s} -> {sc.get(tid)}')
    fehlt = [z for z in sc.values() if z not in [sc[t] for t in zuo.values()]]
    if fehlt:
        print('Nicht zugeordnet (SkillCorner):', ', '.join(fehlt))
    json.dump(daten, open(os.path.join(DATEN, 'impect_teams.json'), 'w', encoding='utf-8'), ensure_ascii=False)
    print(f'{len(daten["teams"])} Teams gespeichert in 02_Daten/impect_teams.json')
