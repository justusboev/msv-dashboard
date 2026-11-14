# Polar-Team-Pro-Abholskript fuer das MSV Dashboard
# Holt alle Team-Einheiten der 1. Mannschaft von der Polar Team Pro API (keine privaten Einzeleinheiten).
# Je Einheit: Teamwerte, Drills und je Spieler Cardio Load, Muskelbelastung, HF, Distanz, Kalorien,
# Sprints, Topspeed und Meter je Geschwindigkeitszone (gesamt und je Drill).
# Ergebnis: 02_Daten/polar_einheiten/ (je Einheit eine Datei) und die CSVs
#   polar_spieler_einheiten.csv, polar_drills.csv, polar_team_einheiten.csv
# Braucht nur Python 3, keine Zusatzpakete.
#
# EINMALIG anmelden (oeffnet den Browser, dort bei Polar zustimmen):
#   cd ~/"MSV Dashboard/03_Skripte"
#   python3 polar_abholen.py --login
#
# Danach Daten holen:
#   python3 polar_abholen.py            (nur neue Einheiten)
#   python3 polar_abholen.py --neu      (alles neu holen)
#   python3 polar_abholen.py --auto     (fuer die Automatik, keine Fragen)
#   python3 polar_abholen.py --test     (nur die letzten 3 Einheiten, zum Ausprobieren)
#   python3 polar_abholen.py --wochen 5 (nur die letzten 5 Wochen, ab Montag)
#   python3 polar_abholen.py --ab 2026-09-01 (alles ab diesem Datum)
#
# Client ID + Secret liegen im Schluesselbund unter "MSV Polar" (Account = Client ID).
# Der Anmelde-Schluessel (Refresh-Token) liegt im Schluesselbund unter "MSV Polar Token".
# Im Ordner wird nichts Geheimes gespeichert.

import base64, csv, datetime, http.server, json, os, subprocess, sys, time
import urllib.error, urllib.parse, urllib.request, webbrowser

HIER = os.path.dirname(os.path.abspath(__file__))
ORDNER = os.path.dirname(HIER)
DATEN = os.path.join(ORDNER, "02_Daten")
STAND = os.path.join(DATEN, "polar_letzter_abruf.json")
PROTOKOLL = os.path.join(ORDNER, "04_Tests", "polar_protokoll.txt")

AUTH_URL = "https://auth.polar.com/oauth/authorize"
TOKEN_URL = "https://auth.polar.com/oauth/token"
API = "https://teampro.api.polar.com/v1"
REDIRECT = "http://localhost:8765/callback"
SAISON_START = "2026-06-15T00:00:00Z"
NUR_TEAMS = ["1.Mannschaft"]   # nur Teams, deren Name das enthaelt (keine Jugend)
SECURITY = "/usr/bin/security"

os.makedirs(os.path.dirname(PROTOKOLL), exist_ok=True)
log_zeilen = []


def log(text):
    print(text)
    log_zeilen.append(text)


def protokoll_schreiben():
    with open(PROTOKOLL, "a", encoding="utf-8") as f:
        f.write("\n=== " + datetime.datetime.now().strftime("%Y-%m-%d %H:%M") + " ===\n")
        f.write("\n".join(log_zeilen) + "\n")


# ---- Schluesselbund (Mac) oder Umgebungsvariablen (GitHub) ----
TOKEN_DATEI = os.environ.get("MSV_TOKEN_DATEI")


def client_daten():
    if os.environ.get("POLAR_CLIENT_ID") and os.environ.get("POLAR_CLIENT_SECRET"):
        return os.environ["POLAR_CLIENT_ID"].strip(), os.environ["POLAR_CLIENT_SECRET"].strip()
    try:
        r = subprocess.run([SECURITY, "find-generic-password", "-s", "MSV Polar"],
                           capture_output=True, text=True, check=True).stdout
        cid = ""
        for zeile in r.splitlines():
            zeile = zeile.strip()
            if zeile.startswith('"acct"'):
                cid = zeile.split("=", 1)[1].strip().strip('"')
        sec = subprocess.run([SECURITY, "find-generic-password", "-s", "MSV Polar", "-a", cid, "-w"],
                             capture_output=True, text=True, check=True).stdout.strip()
        if not cid or not sec:
            raise ValueError
        return cid, sec
    except Exception:
        log("Keine Polar Client ID / kein Secret im Schluesselbund ('MSV Polar') gefunden.")
        log('Einrichten mit:  security add-generic-password -a "CLIENT_ID" -s "MSV Polar" -w')
        sys.exit(2)


def token_lesen():
    if TOKEN_DATEI:
        if os.path.exists(TOKEN_DATEI):
            t = open(TOKEN_DATEI, encoding="utf-8").read().strip()
            if t:
                return t
        return os.environ.get("POLAR_REFRESH_TOKEN", "").strip()
    try:
        return subprocess.run([SECURITY, "find-generic-password", "-s", "MSV Polar Token", "-a", "refresh", "-w"],
                              capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        return ""


def token_speichern(refresh):
    if TOKEN_DATEI:
        open(TOKEN_DATEI, "w", encoding="utf-8").write(refresh)
        return
    subprocess.run([SECURITY, "add-generic-password", "-U", "-s", "MSV Polar Token", "-a", "refresh", "-w", refresh],
                   capture_output=True, check=True)


def token_anfrage(felder):
    cid, sec = client_daten()
    daten = urllib.parse.urlencode(felder).encode()
    req = urllib.request.Request(TOKEN_URL, data=daten, method="POST")
    req.add_header("Authorization", "Basic " + base64.b64encode((cid + ":" + sec).encode()).decode())
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Accept", "application/json")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())


# ---- Einmalige Anmeldung ----
def login():
    cid, _ = client_daten()
    ergebnis = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            ergebnis["code"] = (q.get("code") or [""])[0]
            ergebnis["fehler"] = (q.get("error") or [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            text = "Fertig. Du kannst dieses Fenster schliessen." if ergebnis["code"] else "Fehler: " + ergebnis["fehler"]
            self.wfile.write(("<html><body style='font-family:sans-serif'><h2>MSV Dashboard - Polar</h2><p>" + text + "</p></body></html>").encode("utf-8"))

        def log_message(self, *a):
            pass

    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": cid, "response_type": "code", "scope": "team_read", "redirect_uri": REDIRECT})
    server = http.server.HTTPServer(("127.0.0.1", 8765), Handler)
    server.timeout = 300
    print("Browser oeffnet sich. Bitte mit dem Polar-Team-Pro-Konto anmelden und zustimmen.")
    print("Falls nichts passiert, diese Adresse im Browser oeffnen:\n" + url)
    webbrowser.open(url)
    server.handle_request()
    server.server_close()
    if not ergebnis.get("code"):
        print("Anmeldung fehlgeschlagen: " + (ergebnis.get("fehler") or "keine Antwort innerhalb von 5 Minuten"))
        sys.exit(3)
    antwort = token_anfrage({"grant_type": "authorization_code", "code": ergebnis["code"], "redirect_uri": REDIRECT})
    if not antwort.get("refresh_token"):
        print("Polar hat keinen Refresh-Token geliefert. Antwort-Felder: " + ", ".join(antwort.keys()))
        sys.exit(3)
    token_speichern(antwort["refresh_token"])
    print("Anmeldung gespeichert. Jetzt Daten holen mit:  python3 polar_abholen.py")


# ---- API ----
ZUGANG = {}


def zugang_holen():
    refresh = token_lesen()
    if not refresh:
        log("Noch nicht bei Polar angemeldet. Bitte einmal:  python3 polar_abholen.py --login")
        sys.exit(2)
    try:
        antwort = token_anfrage({"grant_type": "refresh_token", "refresh_token": refresh})
    except urllib.error.HTTPError as e:
        log("Polar-Anmeldung abgelaufen oder ungueltig (HTTP %s). Bitte erneut:  python3 polar_abholen.py --login" % e.code)
        sys.exit(2)
    ZUGANG["token"] = antwort["access_token"]
    if antwort.get("refresh_token") and antwort["refresh_token"] != refresh:
        token_speichern(antwort["refresh_token"])


def hole(pfad, params=None):
    url = API + pfad
    if params:
        url += "?" + urllib.parse.urlencode(params)
    for versuch in range(5):
        time.sleep(1.1)   # Polar erlaubt ca. 1 Anfrage pro Sekunde
        req = urllib.request.Request(url)
        req.add_header("Authorization", "Bearer " + ZUGANG["token"])
        req.add_header("Accept", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode() or "null")
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(10 * (versuch + 1))
                continue
            raise
    raise RuntimeError("Zu viele Anfragen (429) bei " + pfad)


def liste(antwort):
    if isinstance(antwort, list):
        return antwort
    if isinstance(antwort, dict):
        for k in ("data", "items", "training_sessions", "teams", "players"):
            if isinstance(antwort.get(k), list):
                return antwort[k]
    return []


def alle_seiten(pfad, params=None):
    params = dict(params or {})
    params["per_page"] = 100
    seite, ergebnis = 0, []
    while True:
        params["page"] = seite
        antwort = hole(pfad, params)
        teil = liste(antwort)
        ergebnis += teil
        info = antwort.get("page", {}) if isinstance(antwort, dict) else {}
        gesamt_seiten = info.get("total_pages") or info.get("totalPages")
        seite += 1
        if not teil or len(teil) < 100 or (gesamt_seiten is not None and seite >= int(gesamt_seiten)):
            return ergebnis


EINHEITEN = os.path.join(DATEN, "polar_einheiten")
CSV_SPIELER = os.path.join(DATEN, "polar_spieler_einheiten.csv")
CSV_DRILLS = os.path.join(DATEN, "polar_drills.csv")
CSV_TEAM = os.path.join(DATEN, "polar_team_einheiten.csv")
os.makedirs(EINHEITEN, exist_ok=True)


def zeit(s):
    """ISO-Zeit (ohne oder mit Z) -> datetime ohne Zeitzone."""
    if not s:
        return None
    s = str(s).replace("Z", "")[:23]
    for f in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, f)
        except ValueError:
            pass
    return None


def iso_dauer_s(s):
    """PT1M2.5S -> Sekunden."""
    if not s:
        return 0.0
    import re
    m = re.match(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", str(s))
    if not m:
        return 0.0
    h, mi, se = m.groups()
    return int(h or 0) * 3600 + int(mi or 0) * 60 + float(se or 0)


def proben(samples, start):
    """Samples in eine Liste [(zeit, distanz_m, speed_kmh, hf)] umwandeln, egal in welcher Form Polar sie liefert."""
    if not samples:
        return []
    if isinstance(samples, dict) and isinstance(samples.get("fields"), list) and isinstance(samples.get("values"), list):
        felder = samples["fields"]
        reihen = [dict(zip(felder, v)) for v in samples["values"] if isinstance(v, list)]
    elif isinstance(samples, dict):
        n = max((len(v) for v in samples.values() if isinstance(v, list)), default=0)
        reihen = [{k: (v[i] if isinstance(v, list) and i < len(v) else None) for k, v in samples.items()} for i in range(n)]
    else:
        reihen = [x for x in samples if isinstance(x, dict)]
    out = []
    for i, r in enumerate(reihen):
        t = r.get("time")
        if isinstance(t, str) and t.startswith("P") and start:
            t = start + datetime.timedelta(seconds=iso_dauer_s(t))
        elif isinstance(t, str):
            t = zeit(t)
        elif isinstance(t, (int, float)) and start:
            t = start + datetime.timedelta(milliseconds=t) if t > 100000 else start + datetime.timedelta(seconds=t)
        elif start:
            t = start + datetime.timedelta(seconds=i)
        def zahl(k):
            v = r.get(k)
            try:
                f = float(v) if v is not None else None
            except (TypeError, ValueError):
                return None
            if f is None or f != f or f in (float("inf"), float("-inf")):
                return None   # leere Werte (NaN) von Polar ignorieren
            return f
        out.append((t, zahl("distance"), zahl("speed"), zahl("hr")))
    return out


def auswerten(pr, zonen, von=None, bis=None):
    """Kennzahlen aus den Samples, optional nur zwischen von und bis."""
    teil = [x for x in pr if x[0] is not None and (von is None or x[0] >= von) and (bis is None or x[0] <= bis)] if (von or bis) else pr
    if len(teil) < 2:
        return {}
    dist = [x[1] for x in teil if x[1] is not None]
    speeds = [x[2] for x in teil if x[2] is not None and x[2] < 40]
    hfs = [x[3] for x in teil if x[3]]
    erg = {}
    if dist:
        erg["distanz_m"] = round(max(dist) - min(dist), 1)
    if teil[0][0] and teil[-1][0]:
        erg["dauer_min"] = round((teil[-1][0] - teil[0][0]).total_seconds() / 60, 1)
    if erg.get("dauer_min"):
        erg["m_pro_min"] = round(erg.get("distanz_m", 0) / erg["dauer_min"], 1)
    if speeds:
        erg["speed_max_kmh"] = round(max(speeds), 1)
    if hfs:
        erg["hf_avg"] = round(sum(hfs) / len(hfs))
        erg["hf_max"] = round(max(hfs))
    # Meter je Geschwindigkeitszone (Grenzen aus Polar Team Pro)
    zm = [0.0] * len(zonen)
    vorher = None
    for t, d, sp, hf in teil:
        if d is not None and vorher is not None and sp is not None and d >= vorher:
            for i, (lo, hi) in enumerate(zonen):
                if lo <= sp < hi:
                    zm[i] += d - vorher
                    break
        if d is not None:
            vorher = d
    for i, m in enumerate(zm):
        erg["zone%d_m" % (i + 1)] = round(m)
    return erg


def spieler_namen(tid):
    det = hole("/teams/" + str(tid))
    det = det.get("data", det) if isinstance(det, dict) else {}
    namen = {}
    for sp in det.get("players", []) or []:
        pid = sp.get("player_id") or sp.get("id")
        namen[pid] = " ".join(x for x in [sp.get("first_name"), sp.get("last_name")] if x) or str(pid)
    return namen


def einheit_holen(tid, sid, namen):
    det = hole("/teams/training_sessions/" + sid)
    det = det.get("data", det)
    zonen = [(z.get("lower_limit") or 0, z.get("higher_limit") or 999) for z in (det.get("speed_zones_kmh") or [])]
    if not zonen:
        zonen = [(10.0, 14.4), (14.4, 19.8), (19.8, 25.2), (25.2, 29.0), (29.0, 399.0)]
    marker = [m for m in (det.get("markers") or []) if m.get("start_time") and m.get("end_time")]
    marker.sort(key=lambda m: m["start_time"])
    spieler = []
    for t in det.get("participants") or []:
        psid = t.get("player_session_id")
        eintrag = {"spieler_id": t.get("player_id"), "spieler": namen.get(t.get("player_id"), t.get("player_id")),
                   "nummer": t.get("player_number"), "rolle": t.get("role"), "player_session_id": psid}
        try:
            pd = hole("/training_sessions/%s" % psid, {"samples": "distance,speed,hr"})
            pd = pd.get("data", pd)
        except urllib.error.HTTPError as err:
            eintrag["fehler"] = "HTTP %s" % err.code
            spieler.append(eintrag)
            continue
        try:
            zs = hole("/training_sessions/%s/session_summary" % psid)
            zs = zs.get("data", zs) or {}
        except urllib.error.HTTPError:
            zs = {}
        start = zeit(det.get("start_time"))
        ende = zeit(det.get("end_time"))
        pr = proben(pd.get("samples"), zeit(pd.get("start_time")))
        smp = pd.get("samples")
        eintrag["probe"] = {"format": type(smp).__name__, "anzahl": len(pr),
                            "erste": (smp[:2] if isinstance(smp, list) else {k: (v[:2] if isinstance(v, list) else v) for k, v in (smp or {}).items()}),
                            "start_spieler": pd.get("start_time")}
        # Auf die Einheit zugeschnitten (wie in Team Pro): Dauer, Distanz, Sprints, HRV aus der Zusammenfassung,
        # HF, Topspeed und Zonen aus den Sekundenwerten im Zeitraum der Einheit
        try:
            aus = auswerten(pr, zonen, start, ende)
        except Exception as err:
            log("  %s: Sekundenwerte nicht auswertbar (%s)" % (eintrag["spieler"], err))
            aus = {}
        werte = {
            "dauer_min": round((zs.get("duration_ms") or 0) / 60000, 1) or aus.get("dauer_min"),
            "distanz_m": round(zs["distance_meters"]) if zs.get("distance_meters") is not None else aus.get("distanz_m"),
            "m_pro_min": None,
            "sprints": zs.get("sprint_counter"),
            "hf_avg": aus.get("hf_avg"),
            "hf_max": aus.get("hf_max"),
            "speed_max_kmh": aus.get("speed_max_kmh"),
            "hrv_rmssd": zs.get("rmssd"),
        }
        if werte["dauer_min"] and werte["distanz_m"] is not None:
            werte["m_pro_min"] = round(werte["distanz_m"] / werte["dauer_min"], 1)
        for k in ("zone1_m", "zone2_m", "zone3_m", "zone4_m", "zone5_m"):
            werte[k] = aus.get(k)
        # Nur fuer die ganze Aufzeichnung (inkl. Vor- und Nachlauf) von Polar verfuegbar
        werte.update({
            "cardio_load_gesamt": pd.get("cardio_load"),
            "muscle_load_gesamt": pd.get("muscle_load"),
            "kcal_gesamt": pd.get("calories"),
            "training_load_gesamt": pd.get("training_load"),
            "erholung_h": round((pd.get("recovery_time_ms") or 0) / 3600000, 1),
            "trainingseffekt": pd.get("training_benefit"),
            "aufzeichnung_min": round((pd.get("duration_ms") or 0) / 60000, 1),
        })
        eintrag["werte"] = werte
        eintrag["drills"] = []
        for m in marker:
            try:
                dw = auswerten(pr, zonen, zeit(m["start_time"]), zeit(m["end_time"]))
            except Exception:
                dw = {}
            if dw:
                dw["drill"] = m.get("name") or "Abschnitt"
                eintrag["drills"].append(dw)
        spieler.append(eintrag)
    team = {k: det.get(k) for k in ("id", "type", "name", "note", "start_time", "end_time", "distance", "kilocalories",
                                     "training_load", "heart_rate_average", "cardio_load", "cardio_load_interpretation")}
    team["drills"] = [{"drill": m.get("name"), "start": m.get("start_time"), "ende": m.get("end_time")} for m in marker]
    team["hf_zonen"] = [{"zone": z.get("index"), "von_pct": z.get("lower_limit"), "bis_pct": z.get("higher_limit"),
                          "min": round(iso_dauer_s(z.get("in_zone")) / 60, 1)} for z in (det.get("heart_rate_zones") or [])]
    team["speed_zonen"] = [{"zone": z.get("index"), "von_kmh": z.get("lower_limit"), "bis_kmh": z.get("higher_limit"),
                             "meter": z.get("in_zone_meters")} for z in (det.get("speed_zones_kmh") or [])]
    return {"team_einheit": team, "spieler": spieler}


def csv_schreiben(datei, zeilen):
    spalten = []
    for z in zeilen:
        for k in z:
            if k not in spalten:
                spalten.append(k)
    with open(datei, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=spalten or ["leer"])
        w.writeheader()
        w.writerows(zeilen)


def csv_bauen():
    sp_z, dr_z, te_z = [], [], []
    for name in sorted(os.listdir(EINHEITEN)):
        if not name.endswith(".json"):
            continue
        d = json.load(open(os.path.join(EINHEITEN, name), encoding="utf-8"))
        te = d["team_einheit"]
        datum = str(te.get("start_time", ""))[:10]
        kopf = {"einheit_id": te.get("id"), "datum": datum, "beginn": str(te.get("start_time", ""))[11:16], "art": te.get("type"),
                "einheit": te.get("name") or ""}
        z = dict(kopf)
        z.update({"team_distanz_m": te.get("distance"), "team_kcal": te.get("kilocalories"), "team_training_load": te.get("training_load"),
                  "team_hf_avg_pct": te.get("heart_rate_average"), "team_cardio_load": te.get("cardio_load"),
                  "spieler_anzahl": len(d["spieler"]), "drills": " | ".join(x["drill"] or "" for x in te.get("drills", []))})
        for hz in te.get("hf_zonen", []):
            z["hf_zone%s_min" % hz["zone"]] = hz["min"]
        te_z.append(z)
        for sp in d["spieler"]:
            if not sp.get("werte"):
                continue
            z = dict(kopf)
            z.update({"spieler": sp["spieler"], "nummer": sp.get("nummer"), "rolle": sp.get("rolle")})
            z.update(sp["werte"])
            sp_z.append(z)
            for dr in sp.get("drills", []):
                z2 = dict(kopf)
                z2.update({"spieler": sp["spieler"], "nummer": sp.get("nummer"), "rolle": sp.get("rolle")})
                z2.update(dr)
                dr_z.append(z2)
    csv_schreiben(CSV_SPIELER, sp_z)
    csv_schreiben(CSV_DRILLS, dr_z)
    csv_schreiben(CSV_TEAM, te_z)
    log("CSV geschrieben: %d Einheiten, %d Spieler-Einheiten, %d Drill-Zeilen" % (len(te_z), len(sp_z), len(dr_z)))


def abholen(neu=False):
    zugang_holen()
    vorhanden = set(n[:-5] for n in os.listdir(EINHEITEN) if n.endswith(".json"))
    alle_teams = alle_seiten("/teams")
    teams = [t for t in alle_teams if any(n.lower() in str(t.get("name", "")).lower() for n in NUR_TEAMS)]
    log("Teams bei Polar: " + ", ".join(str(t.get("name")) for t in alle_teams))
    log("Davon geholt: " + (", ".join(str(t.get("name")) for t in teams) or "KEINS (Name pruefen)"))
    neu_gefunden = []
    heute = datetime.date.today().isoformat()
    for team in teams:
        tid = team["id"]
        namen = spieler_namen(tid)
        since = SAISON_START
        if "--wochen" in sys.argv:
            # nur die letzten N Wochen, ab Montag (z. B.  --wochen 5)
            n = int(sys.argv[sys.argv.index("--wochen") + 1])
            heute_d = datetime.date.today()
            montag = heute_d - datetime.timedelta(days=heute_d.weekday()) - datetime.timedelta(weeks=n - 1)
            since = montag.isoformat() + "T00:00:00Z"
            log("Nur Einheiten ab Montag %s (%d Wochen)" % (montag.strftime("%d.%m.%Y"), n))
        if "--ab" in sys.argv:
            # ab einem Datum, z. B.  --ab 2026-09-01
            ab = sys.argv[sys.argv.index("--ab") + 1]
            datetime.date.fromisoformat(ab)
            since = ab + "T00:00:00Z"
            log("Nur Einheiten ab %s" % ".".join(reversed(ab.split("-"))))
        einheiten = alle_seiten("/teams/%s/training_sessions" % tid, {"since": since})
        einheiten.sort(key=lambda e: str(e.get("start_time")))
        if "--test" in sys.argv:
            einheiten = einheiten[-3:]   # nur die letzten 3 Einheiten, zum Ausprobieren
        log("Team %s: %d Einheiten im Zeitraum, %d Spieler" % (team.get("name"), len(einheiten), len(namen)))
        for e in einheiten:
            sid = str(e.get("id"))
            # Einheiten von heute immer neu holen (Trainer bearbeiten sie oft noch)
            if not neu and sid in vorhanden and not str(e.get("start_time", "")).startswith(heute):
                continue
            daten = einheit_holen(tid, sid, namen)
            json.dump(daten, open(os.path.join(EINHEITEN, sid + ".json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            fehler = sum(1 for s in daten["spieler"] if s.get("fehler"))
            log("  %s %s: %d Spieler%s" % (str(e.get("start_time", ""))[:16].replace("T", " "), e.get("type"),
                                           len(daten["spieler"]), (", %d ohne Daten" % fehler) if fehler else ""))
            if sid not in vorhanden:
                neu_gefunden.append(str(e.get("start_time", ""))[:10])
            vorhanden.add(sid)
    log("Neue Einheiten: %d" % len(neu_gefunden))
    csv_bauen()
    json.dump({"zeit": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), "neue_einheiten": len(neu_gefunden),
               "tage": sorted(set(neu_gefunden))}, open(STAND, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return len(neu_gefunden)


if __name__ == "__main__":
    if "--login" in sys.argv:
        login()
        sys.exit(0)
    try:
        anzahl = abholen(neu="--neu" in sys.argv)
    except urllib.error.HTTPError as e:
        log("FEHLER: Polar antwortet mit HTTP %s bei %s" % (e.code, e.url))
        protokoll_schreiben()
        sys.exit(1)
    except Exception as e:
        log("FEHLER: %s" % e)
        protokoll_schreiben()
        sys.exit(1)
    protokoll_schreiben()
    sys.exit(10 if anzahl else 0)
