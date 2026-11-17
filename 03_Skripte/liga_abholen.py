# Holt fuer ALLE Spiele der 3. Liga die SkillCorner-Rohdaten (Physis + Dynamic Events)
# und den kompletten Spielplan. Bereits geholte Spiele werden uebersprungen.
# Ergebnis: 02_Daten/liga/spielplan.json, liga/physis/<id>.csv, liga/events/<id>.csv.gz
#
# Mac:     python3 liga_abholen.py          (Passwort aus dem Schluesselbund "MSV SkillCorner")
# GitHub:  python liga_abholen.py --auto    (SKILLCORNER_USER / SKILLCORNER_PW aus Secrets)
# Optional: --nur-neu-auswerten  (holt nur Spiele, deren Auswertung noch fehlt; fuer GitHub)
import base64, csv, gzip, json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
ORDNER = os.path.dirname(HIER)
LIGA = os.path.join(ORDNER, "02_Daten", "liga")
EVENTS = os.path.join(LIGA, "events")
PHYSIS = os.path.join(LIGA, "physis")
SPIELE = os.path.join(LIGA, "spiele")   # Spielinfos (Rueckennummern) je Spiel
BASIS = "https://skillcorner.com/api"
EDITION_ID = 1607   # 3. Liga 2026/27
for d in (EVENTS, PHYSIS, SPIELE):
    os.makedirs(d, exist_ok=True)

if os.environ.get("SKILLCORNER_PW"):
    user, pw = os.environ.get("SKILLCORNER_USER", "").strip(), os.environ["SKILLCORNER_PW"].strip()
else:
    user = json.load(open(os.path.join(HIER, "einstellungen.json"), encoding="utf-8")).get("benutzer", "")
    try:
        pw = subprocess.run(["/usr/bin/security", "find-generic-password", "-a", user, "-s", "MSV SkillCorner", "-w"],
                            capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        sys.exit("Kein SkillCorner-Passwort im Schluesselbund gefunden.")
AUTH = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def hole(url, roh=False):
    for versuch in range(4):
        req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "*/*"})
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                d = r.read()
            return d if roh else json.loads(d.decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(5 * (versuch + 1))
                continue
            raise
        except Exception:
            time.sleep(5 * (versuch + 1))
    raise RuntimeError("Abruf fehlgeschlagen: " + url)


def alle(pfad, params):
    erg = hole(BASIS + pfad + "?" + urllib.parse.urlencode(params))
    if isinstance(erg, list):
        return erg
    z, weiter = list(erg.get("results", [])), erg.get("next")
    while weiter:
        s = hole(weiter)
        z += s.get("results", [])
        weiter = s.get("next")
    return z


print("Spielplan holen ...")
spiele = alle("/matches/", {"competition_edition": EDITION_ID})
plan = [{"id": s["id"], "datum": s["date_time"], "status": s.get("status"),
         "heim_id": s["home_team"]["id"], "heim": s["home_team"]["short_name"],
         "gast_id": s["away_team"]["id"], "gast": s["away_team"]["short_name"]} for s in spiele]
json.dump(plan, open(os.path.join(LIGA, "spielplan.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
gespielt = sorted([p for p in plan if p["status"] == "closed"], key=lambda p: p["datum"])
print(f"{len(plan)} Spiele im Plan, {len(gespielt)} gespielt")

# GitHub: Rohdaten werden nicht gespeichert, nur die Auswertung. Bereits ausgewertete Spiele ueberspringen.
schon = set()
kz = os.path.join(ORDNER, "02_Daten", "liga_kennzahlen.json")
if "--nur-neu" in sys.argv and os.path.exists(kz):
    sys.path.insert(0, HIER)
    from liga_auswerten import VERSION
    d = json.load(open(kz, encoding="utf-8"))
    if d.get("version") == VERSION:
        schon = {s["match_id"] for s in d["spiele"] if s.get("spieler")}
neu = 0
for i, p in enumerate(gespielt, 1):
    mid = p["id"]
    if mid in schon:
        continue
    ev_datei = os.path.join(EVENTS, f"{mid}.csv.gz")
    ph_datei = os.path.join(PHYSIS, f"{mid}.csv")
    sp_datei = os.path.join(SPIELE, f"{mid}.json")
    if os.path.exists(ev_datei) and os.path.exists(ph_datei) and os.path.exists(sp_datei):
        continue
    name = f"{p['datum'][:10]} {p['heim']} v {p['gast']}"
    try:
        if not os.path.exists(ph_datei):
            zeilen = alle("/physical/", {"match": mid, "data_version": 3})
            spalten = []
            for z in zeilen:
                for k in z:
                    if k not in spalten:
                        spalten.append(k)
            with open(ph_datei, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=spalten or ["leer"])
                w.writeheader()
                w.writerows(zeilen)
        if not os.path.exists(sp_datei):
            try:
                info = hole(f"{BASIS}/match/{mid}/")
                spieler = [{"id": x.get("id"), "nummer": x.get("number"), "name": x.get("short_name") or x.get("last_name"),
                            "team_id": x.get("team_id"), "rolle": (x.get("player_role") or {}).get("acronym")} for x in info.get("players", [])]
                json.dump({"match_id": mid, "spieler": spieler}, open(sp_datei, "w", encoding="utf-8"), ensure_ascii=False)
            except Exception as e:
                print(f"   Spielinfo (Rueckennummern) fehlt: {e}")
        if not os.path.exists(ev_datei):
            roh = hole(f"{BASIS}/match/{mid}/dynamic_events/?file_format=csv", roh=True)
            with gzip.open(ev_datei + ".tmp", "wb") as f:
                f.write(roh)
            os.replace(ev_datei + ".tmp", ev_datei)
        neu += 1
        print(f"[{i}/{len(gespielt)}] {name}: OK")
    except Exception as e:
        print(f"[{i}/{len(gespielt)}] {name}: FEHLER {e}")
print(f"Fertig. {neu} Spiele neu geholt.")
sys.exit(10 if neu else 0)
