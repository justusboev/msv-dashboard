# SkillCorner-Abholskript fuer das MSV Dashboard
# Holt alle gespielten MSV-Spiele der Saison von der SkillCorner-API und speichert sie
# im Ordner 02_Daten. Bereits geholte Spiele werden uebersprungen.
# Braucht nur Python 3, keine Zusatzpakete.
#
# Start im Terminal:
#   cd ~/"MSV Dashboard/03_Skripte"
#   python3 skillcorner_abholen.py
#   (mit  --neu  am Ende werden alle Physis-Daten neu geholt)
#
# Das Passwort wird bei jedem Start abgefragt und NICHT gespeichert.

import base64, csv, getpass, json, os, sys, urllib.error, urllib.parse, urllib.request

HIER = os.path.dirname(os.path.abspath(__file__))
ORDNER = os.path.dirname(HIER)
DATEN = os.path.join(ORDNER, "02_Daten")
PHYSIS_ORDNER = os.path.join(DATEN, "skillcorner_api_physis")
EVENTS_ORDNER = os.path.join(DATEN, "skillcorner_dynamic_events")
PROTOKOLL = os.path.join(ORDNER, "04_Tests", "abholen_protokoll.txt")
EINSTELLUNGEN = os.path.join(HIER, "einstellungen.json")

BASIS = "https://skillcorner.com/api"
MSV_TEAM_ID = 756
EDITION_ID = 1607   # 3. Liga 2026/27

os.makedirs(PHYSIS_ORDNER, exist_ok=True)
os.makedirs(EVENTS_ORDNER, exist_ok=True)
os.makedirs(os.path.dirname(PROTOKOLL), exist_ok=True)
log_zeilen = []


def log(text):
    print(text)
    log_zeilen.append(text)


# ---- Login ----
AUTO = "--auto" in sys.argv   # automatischer Lauf: Passwort aus dem Schluesselbund, keine Fragen
einst = {}
if os.path.exists(EINSTELLUNGEN):
    einst = json.load(open(EINSTELLUNGEN, encoding="utf-8"))
user = einst.get("benutzer", "")
if AUTO and os.environ.get("SKILLCORNER_PW"):
    user = os.environ.get("SKILLCORNER_USER", user).strip()
    pw = os.environ["SKILLCORNER_PW"].strip()
elif AUTO:
    import subprocess
    try:
        pw = subprocess.run(["/usr/bin/security", "find-generic-password", "-a", user, "-s", "MSV SkillCorner", "-w"],
                            capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        print("Kein SkillCorner-Passwort im Schluesselbund gefunden. Bitte einrichten.sh ausfuehren.")
        sys.exit(2)
else:
    eingabe = input(f"SkillCorner Benutzername [{user}]: ").strip() if user else input("SkillCorner Benutzername (E-Mail): ").strip()
    user = eingabe or user
    json.dump({"benutzer": user}, open(EINSTELLUNGEN, "w", encoding="utf-8"))
    pw = getpass.getpass("SkillCorner Passwort (wird nicht angezeigt): ")
AUTH = "Basic " + base64.b64encode(f"{user}:{pw}".encode()).decode()


def hole(pfad, params=None, roh=False):
    url = BASIS + pfad + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers={"Authorization": AUTH, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            daten = r.read()
    except urllib.error.HTTPError as e:
        return None, e.code
    except Exception as e:
        return None, str(e)
    if roh:
        return daten, 200
    try:
        return json.loads(daten.decode("utf-8")), 200
    except Exception:
        return daten, 200


def alle_seiten(pfad, params):
    erg, code = hole(pfad, params)
    if code != 200:
        return None, code
    if isinstance(erg, list):
        return erg, 200
    zeilen = list(erg.get("results", []))
    weiter = erg.get("next")
    while weiter:
        req = urllib.request.Request(weiter, headers={"Authorization": AUTH})
        with urllib.request.urlopen(req, timeout=120) as r:
            seite = json.loads(r.read().decode("utf-8"))
        zeilen += seite.get("results", [])
        weiter = seite.get("next")
    return zeilen, 200


# ---- 1) Spielplan ----
log("\n1) Spielplan holen ...")
spiele, code = alle_seiten("/matches/", {"competition_edition": EDITION_ID, "team": MSV_TEAM_ID})
if code != 200:
    log(f"   Fehler beim Spielplan (Code {code}). Login pruefen.")
    sys.exit(1)
gespielt = sorted([s for s in spiele if s.get("status") == "closed"], key=lambda s: s["date_time"])
log(f"   {len(spiele)} Spiele im Plan, {len(gespielt)} gespielt")


# ---- 2) Physis je Spiel ----
# Varianten: ganzes Spiel, Halbzeiten, mit/gegen Ball. Was die API nicht kennt, wird uebersprungen.
VARIANTEN = [
    ({}, "basis"),
    ({"possession": "tip"}, "tip"), ({"possession": "otip"}, "otip"),
    ({"period": "h1"}, "h1"), ({"period": "h2"}, "h2"),
    ({"period": "h1", "possession": "tip"}, "h1_tip"), ({"period": "h1", "possession": "otip"}, "h1_otip"),
    ({"period": "h2", "possession": "tip"}, "h2_tip"), ({"period": "h2", "possession": "otip"}, "h2_otip"),
]


def physis_spiel(mid):
    basis, code = alle_seiten("/physical/", {"match": mid, "data_version": 3})
    if code != 200 or not basis:
        return None, f"Code {code}"
    zeilen = {r["player_id"]: dict(r) for r in basis}
    for params, name in VARIANTEN[1:]:
        p = {"match": mid, "data_version": 3}
        p.update(params)
        extra, c = alle_seiten("/physical/", p)
        if c != 200 or not extra:
            log(f"      Variante {name}: Code {c}")
            continue
        neue = 0
        for r in extra:
            z = zeilen.get(r.get("player_id"))
            if z is None:
                continue
            for k, v in r.items():
                if k not in z:
                    z[k] = v
                    neue += 1
        log(f"      Variante {name}: {neue} neue Werte")
    return list(zeilen.values()), "ok"


log("\n2) Physis-Daten holen ...")
NEUE_SPIELE = []
for s in gespielt:
    mid = s["id"]
    ziel = os.path.join(PHYSIS_ORDNER, f"{mid}.csv")
    name = f"{s['date_time'][:10]} {s['home_team']['short_name']} v {s['away_team']['short_name']}"
    if os.path.exists(ziel) and "--neu" not in sys.argv:
        log(f"   {name}: schon vorhanden")
        continue
    zeilen, status = physis_spiel(mid)
    if not zeilen:
        log(f"   {name}: FEHLER ({status})")
        continue
    spalten = []
    for z in zeilen:
        for k in z:
            if k not in spalten:
                spalten.append(k)
    with open(ziel, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=spalten)
        w.writeheader()
        w.writerows(zeilen)
    log(f"   {name}: {len(zeilen)} Spieler, {len(spalten)} Spalten gespeichert")
    NEUE_SPIELE.append({"match_id": mid, "spiel": name})


# ---- 3) Dynamic Events je Spiel ----
log("\n3) Dynamic Events holen ...")
for s in ([] if "--ohne-events" in sys.argv else gespielt):
    mid = s["id"]
    ziel = os.path.join(EVENTS_ORDNER, f"{mid}.csv")
    if os.path.exists(ziel):
        continue
    daten, code = hole(f"/match/{mid}/dynamic_events/", {"file_format": "csv"}, roh=True)
    if code != 200:
        log(f"   Spiel {mid}: Fehler (Code {code})")
        continue
    open(ziel, "wb").write(daten)
    log(f"   Spiel {mid}: {len(daten)//1024} KB gespeichert")

import datetime
stempel = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
open(PROTOKOLL, "w", encoding="utf-8").write(f"Lauf vom {stempel}\n" + "\n".join(log_zeilen))
json.dump({"zeit": stempel, "neue_spiele": NEUE_SPIELE},
          open(os.path.join(DATEN, "letzter_abruf.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
log(f"\nFertig! {len(NEUE_SPIELE)} neue Spiele. Die Daten liegen in 02_Daten.")
sys.exit(10 if NEUE_SPIELE else 0)
