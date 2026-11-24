# Offizielle Tabelle und Ergebnisse der 3. Liga von OpenLigaDB (kostenlos, kein Login).
# SkillCorner-Ergebnisse waren nicht zuverlaessig, deshalb diese Quelle.
# Ergebnis: 02_Daten/liga/tabelle.json und 02_Daten/liga/ergebnisse.json
# Jedes Ergebnis bekommt, wenn moeglich, die passende SkillCorner-Spiel-ID (aus liga/spielplan.json).
#
# Mac:     python3 liga_tabelle.py
# GitHub:  python liga_tabelle.py
import json, os, re, sys, time, unicodedata, urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
LIGA = os.path.join(os.path.dirname(HIER), "02_Daten", "liga")
os.makedirs(LIGA, exist_ok=True)
SAISON = 2026   # Saison 2026/27
URL = f"https://api.openligadb.de/getmatchdata/bl3/{SAISON}"


def hole(url):
    for versuch in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "MSV-Dashboard"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            fehler = e
            time.sleep(5 * (versuch + 1))
    sys.exit(f"OpenLigaDB nicht erreichbar: {fehler}")


def norm(name):
    n = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    n = n.replace("koln", "koeln").replace("cologne", "koeln").replace("munster", "muenster")
    for wort in ["fc ", "sv ", "sc ", "tsv ", "ssv ", "vfb ", "tsg ", "1899 ", "1. ", "04", "1912", "06", "sg ", "fsv "]:
        n = n.replace(wort, " ")
    return set(w for w in re.split(r"[^a-z]+", n) if len(w) >= 3)


def gleich(a, b):
    A, B = norm(a), norm(b)
    if not A or not B:
        return False
    if "ii" in (a or "").lower().split() or " ii" in (a or "").lower():
        pass
    return bool(A & B) or any(x.startswith(y[:5]) or y.startswith(x[:5]) for x in A for y in B)


spiele = hole(URL)
ergebnisse = []
for s in spiele:
    if not s.get("matchIsFinished"):
        continue
    end = [r for r in s.get("matchResults", []) if r.get("resultTypeID") == 2] or \
          sorted(s.get("matchResults", []), key=lambda r: r.get("resultOrderID", 0))[-1:]
    if not end:
        continue
    ergebnisse.append({"spieltag": s["group"]["groupOrderID"], "datum": s["matchDateTime"][:10],
                       "heim": s["team1"]["teamName"], "gast": s["team2"]["teamName"],
                       "heim_kurz": s["team1"].get("shortName") or s["team1"]["teamName"],
                       "gast_kurz": s["team2"].get("shortName") or s["team2"]["teamName"],
                       "tore_heim": end[0]["pointsTeam1"], "tore_gast": end[0]["pointsTeam2"]})

# SkillCorner-Spiel-IDs zuordnen (Datum +-1 Tag, beide Teamnamen passen)
plan_datei = os.path.join(LIGA, "spielplan.json")
plan = json.load(open(plan_datei, encoding="utf-8")) if os.path.exists(plan_datei) else []
from datetime import date
def tage(a, b):
    return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
ohne_id = 0
team_ids = {}
for e in ergebnisse:
    treffer = [p for p in plan if tage(p["datum"][:10], e["datum"]) <= 1 and gleich(p["heim"], e["heim"]) and gleich(p["gast"], e["gast"])]
    if len(treffer) == 1:
        e["skillcorner_id"] = treffer[0]["id"]
        team_ids[e["heim"]] = treffer[0]["heim_id"]; team_ids[e["gast"]] = treffer[0]["gast_id"]
    else:
        ohne_id += 1

# Tabelle
T = {}
for e in sorted(ergebnisse, key=lambda e: (e["datum"], e["spieltag"])):
    for name, kurz, t, g in ((e["heim"], e["heim_kurz"], e["tore_heim"], e["tore_gast"]), (e["gast"], e["gast_kurz"], e["tore_gast"], e["tore_heim"])):
        x = T.setdefault(name, {"name": name, "kurz": kurz, "team_id": None, "spiele": 0, "siege": 0, "unentschieden": 0,
                                "niederlagen": 0, "tore": 0, "gegentore": 0, "punkte": 0, "form": []})
        x["spiele"] += 1; x["tore"] += t; x["gegentore"] += g
        if t > g: x["siege"] += 1; x["punkte"] += 3; x["form"].append("S")
        elif t == g: x["unentschieden"] += 1; x["punkte"] += 1; x["form"].append("U")
        else: x["niederlagen"] += 1; x["form"].append("N")
tab = sorted(T.values(), key=lambda x: (-x["punkte"], -(x["tore"] - x["gegentore"]), -x["tore"], x["name"]))
for i, x in enumerate(tab, 1):
    x["platz"] = i; x["differenz"] = x["tore"] - x["gegentore"]; x["form"] = x["form"][-5:]; x["team_id"] = team_ids.get(x["name"])
stand = max((e["datum"] for e in ergebnisse), default="")
spieltag = max((e["spieltag"] for e in ergebnisse), default=0)
json.dump(ergebnisse, open(os.path.join(LIGA, "ergebnisse.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({"stand": stand, "spieltag": spieltag, "quelle": "OpenLigaDB", "tabelle": tab},
          open(os.path.join(LIGA, "tabelle.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"Tabelle 3. Liga nach dem {spieltag}. Spieltag (Stand {stand}), {len(ergebnisse)} Spiele")
print(f"{'Pl':>2}  {'Team':<26}{'Sp':>3}{'S':>3}{'U':>3}{'N':>3}  {'Tore':>7}{'Diff':>5}{'Pkt':>5}  SkillCorner-ID")
for x in tab:
    print(f"{x['platz']:>2}  {x['name'][:26]:<26}{x['spiele']:>3}{x['siege']:>3}{x['unentschieden']:>3}{x['niederlagen']:>3}  "
          f"{x['tore']:>3}:{x['gegentore']:<3}{x['differenz']:>+5}{x['punkte']:>5}  {x['team_id']}")
print(f"\nSpiele ohne SkillCorner-Zuordnung: {ohne_id}")
