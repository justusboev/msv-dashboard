# Fuehrt alle per API geholten Physis-Dateien zu einer Datei zusammen,
# mit genau den Spalten, die das Dashboard braucht.
# Ergebnis: 02_Daten/skillcorner_physis_alle_spiele.csv
import csv, glob, os
HIER = os.path.dirname(os.path.abspath(__file__))
DATEN = os.path.join(os.path.dirname(HIER), "02_Daten")
SPALTEN = ['player_short_name','team_name','match_name','match_id','match_date','competition_name','position','position_group',
 'minutes_full_all','total_distance_full_all','total_metersperminute_full_all','running_distance_full_all','hsr_distance_full_all',
 'sprint_distance_full_all','sprint_count_full_all','hi_distance_full_all','hi_count_full_all','psv99','highaccel_count_full_all',
 'highdecel_count_full_all','minutes_h1_all','total_distance_h1_all','minutes_h2_all','total_distance_h2_all',
 'minutes_full_tip','total_distance_full_tip','minutes_full_otip','total_distance_full_otip']
zeilen = []
for f in sorted(glob.glob(os.path.join(DATEN, "skillcorner_api_physis", "*.csv"))):
    for r in csv.DictReader(open(f, encoding="utf-8")):
        if r.get("player_short_name"):
            zeilen.append({k: " ".join((r.get(k) or "").split()) for k in SPALTEN})
zeilen.sort(key=lambda r: (r["match_date"], r["team_name"]))
ziel = os.path.join(DATEN, "skillcorner_physis_alle_spiele.csv")
with open(ziel, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=SPALTEN); w.writeheader(); w.writerows(zeilen)
print(f"{len(zeilen)} Zeilen aus {len({r['match_id'] for r in zeilen})} Spielen -> {ziel}")
