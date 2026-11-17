# Wertet die SkillCorner Dynamic Events aller Ligaspiele aus (Spielphasen, Pressing, Umschalten,
# Tor- und Gegentor-Entstehung) und die Physis-Daten. Ergebnis je Team und Spiel:
#   02_Daten/liga_kennzahlen.json
# Quelle: 02_Daten/liga/events/<id>.csv.gz (+ fuer die Entwicklung skillcorner_dynamic_events/<id>.csv)
import collections, csv, glob, gzip, io, json, os, sys

HIER = os.path.dirname(os.path.abspath(__file__))
DATEN = os.path.join(os.path.dirname(HIER), "02_Daten")
LIGA = os.path.join(DATEN, "liga")
ZIEL = os.path.join(DATEN, "liga_kennzahlen.json")
VERSION = 5
LINKS = ("wide_left", "half_space_left")
RECHTS = ("wide_right", "half_space_right")
REGAIN_START = ("recovery", "pass_interception", "free_kick_interception", "throw_in_interception",
                "goal_kick_interception", "corner_interception")


def seite(ch):
    return "links" if ch in LINKS else "rechts" if ch in RECHTS else "mitte" if ch == "center" else None


def ja(v):
    return str(v) == "True"


def lies(pfad):
    if pfad.endswith(".gz"):
        return list(csv.DictReader(io.TextIOWrapper(gzip.open(pfad), encoding="utf-8")))
    return list(csv.DictReader(open(pfad, encoding="utf-8")))


def spiel_auswerten(R):
    """Zaehler je Team fuer ein Spiel."""
    teams = sorted({r["team_shortname"] for r in R if r["team_shortname"]})
    tid = {r["team_shortname"]: r["team_id"] for r in R if r["team_shortname"]}
    Z = {t: collections.Counter() for t in teams}
    gegner = {t: [x for x in teams if x != t][0] for t in teams} if len(teams) == 2 else {}
    pp = [r for r in R if r["event_type"] == "player_possession"]
    ob = [r for r in R if r["event_type"] == "on_ball_engagement"]
    tore = {t: [] for t in teams}
    SP = collections.defaultdict(collections.Counter)   # (team, spieler) -> Zaehler
    POS = {}

    def sp(r):
        k = (r["team_shortname"], r["player_name"])
        if r.get("player_position"):
            POS[k] = r["player_position"]
        return k

    # Phasen = zusammenhaengende Ballbesitze eines Teams
    phasen = collections.OrderedDict()
    for r in pp:
        phasen.setdefault((r["period"], r["phase_index"]), []).append(r)
    for (_, idx), P in phasen.items():
        t = P[0]["team_shortname"]
        if t not in Z:
            continue
        typ = P[0]["team_in_possession_phase_type"]
        nxt = P[-1]["current_team_in_possession_next_phase_type"]
        prev = P[0]["current_team_in_possession_previous_phase_type"]
        verlust = ja(P[-1]["team_possession_loss_in_phase"])
        schuss = any(ja(r["lead_to_shot"]) for r in P)
        tor = any(r["game_interruption_after"] == "goal_for" for r in P)
        Z[t]["phasen"] += 1
        Z[t]["phase_" + typ] += 1
        druck = any(o["phase_index"] == idx and o["team_shortname"] != t for o in ob)

        if typ == "build_up":
            Z[t]["aufbau"] += 1
            if nxt in ("create", "finish") and not verlust:
                Z[t]["aufbau_ausgang"] += 1
                s = seite(P[-1]["channel_end"])
                if s:
                    Z[t]["aufbau_ausgang_" + s] += 1
                start = P[0]["start_type"]
                Z[t]["aufbau_ausgang_" + ("schnell" if start in REGAIN_START else "organisiert")] += 1
            if druck:
                Z[t]["aufbau_druck"] += 1
                if verlust:
                    Z[t]["aufbau_druck_verlust"] += 1
                elif nxt in ("create", "finish"):
                    Z[t]["aufbau_druck_geloest"] += 1
                else:
                    Z[t]["aufbau_druck_gestoert"] += 1
        if typ == "create":
            Z[t]["kreieren"] += 1
            if nxt == "finish":
                Z[t]["kreieren_abschluss"] += 1
                letzte = P[-1]
                if ja(letzte["high_pass"]) or letzte["pass_range"] == "long":
                    Z[t]["prog_ueber"] += 1
                elif letzte["player_targeted_channel_reception"] in ("wide_left", "wide_right"):
                    Z[t]["prog_aussen"] += 1
                else:
                    Z[t]["prog_durch"] += 1
        if typ == "finish":
            Z[t]["abschlussphase"] += 1
            Z[t]["abschlussphase_" + ("kontrolliert" if prev in ("create", "build_up", "set_play") else "umschalten")] += 1
        if typ in ("transition", "quick_break"):
            Z[t]["umschalten"] += 1
            if schuss:
                Z[t]["umschalten_gefaehrlich"] += 1
        if schuss:
            Z[t]["phasen_schuss"] += 1
        # Strafraum-Eintritte
        for r in P:
            if ja(r["penalty_area_end"]) and not ja(r["penalty_area_start"]):
                s = seite(r["channel_start"]) or "mitte"
                Z[t]["strafraum"] += 1
                Z[t]["strafraum_" + s] += 1
        # Spieler: Tore, Vorlagen, Schuesse, Schussvorlagen, Paesse in den Strafraum
        for i, r in enumerate(P):
            if r["end_type"] == "shot":
                SP[sp(r)]["schuesse"] += 1
                if i > 0 and P[i - 1]["end_type"] == "pass" and P[i - 1]["player_name"] != r["player_name"]:
                    SP[sp(P[i - 1])]["schussvorlagen"] += 1
            if r["game_interruption_after"] == "goal_for" and r["end_type"] == "shot":
                SP[sp(r)]["tore"] += 1
                if i > 0 and P[i - 1]["end_type"] == "pass" and P[i - 1]["player_name"] != r["player_name"]:
                    SP[sp(P[i - 1])]["assists"] += 1
                    if i > 1 and P[i - 2]["end_type"] == "pass" and P[i - 2]["player_name"] not in (r["player_name"], P[i - 1]["player_name"]):
                        SP[sp(P[i - 2])]["pre_assists"] += 1
            if (r["end_type"] == "pass" and r.get("pass_outcome") == "successful" and not ja(r["penalty_area_start"])
                    and i + 1 < len(P) and ja(P[i + 1]["penalty_area_start"])):
                SP[sp(r)]["paesse_strafraum"] += 1
        # Schuesse
        for r in P:
            if r["end_type"] == "shot":
                Z[t]["schuesse"] += 1
                Z[t]["schuesse_strafraum" if ja(r["penalty_area_start"]) else "schuesse_ausserhalb"] += 1
        # Tore und ihre Entstehung
        if tor:
            Z[t]["tore"] += 1
            erste = P[0]
            if erste["game_interruption_before"] in ("corner_for", "free_kick_for", "throw_in_for", "goal_kick_for") or typ == "set_play":
                herkunft = "standard"
            elif typ in ("transition", "quick_break") or erste["start_type"] in REGAIN_START:
                herkunft = "ballgewinn"
            elif typ == "direct":
                herkunft = "langer_ball"
            else:
                herkunft = "spielaufbau"
            eintritt = next((seite(r["channel_start"]) or "mitte" for r in P if ja(r["penalty_area_end"]) and not ja(r["penalty_area_start"])), None)
            if not eintritt:
                eintritt = seite(P[-1]["channel_start"]) or "mitte"
            tore[t].append({"minute": int(float(P[-1]["minute_start"] or 0)), "phase": typ, "herkunft": herkunft, "seite": eintritt,
                            "drittel_start": erste["third_start"], "stand": P[-1]["game_state"]})
            Z[t]["tor_" + herkunft] += 1

    # Laeufe in die Tiefe, die angespielt wurden
    for r in R:
        if r["event_type"] == "off_ball_run" and r["event_subtype"] == "behind" and r["team_shortname"] in Z:
            SP[sp(r)]["tiefenlaeufe"] += 1
            if ja(r.get("received")):
                SP[sp(r)]["tiefenlaeufe_angespielt"] += 1

    # Pressing (gegen den Ball)
    ketten = {}
    gegenp = {}
    for o in ob:
        t = o["team_shortname"]
        if t not in Z:
            continue
        block = o["team_out_of_possession_phase_type"]
        if o["event_subtype"] == "counter_press":
            k = (t, o["period"], o["phase_index"])
            gp = gegenp.setdefault(k, False)
            if o["end_type"] in ("direct_regain", "indirect_regain") or o["pressing_chain_end_type"] == "regain":
                gegenp[k] = True
        if block == "high_block" and ja(o["pressing_chain"]):
            key = (o["period"], o["phase_index"])
            ketten.setdefault((t, key), o["pressing_chain_end_type"])
            if o["pressing_chain_end_type"]:
                ketten[(t, key)] = o["pressing_chain_end_type"]
    for (t, _, _), ok in gegenp.items():
        Z[t]["gegenpressing"] += 1
        if ok:
            Z[t]["gegenpressing_erfolg"] += 1
    for (t, _), ende in ketten.items():
        Z[t]["pressing"] += 1
        Z[t]["pressing_" + (ende if ende in ("regain", "disruption") else "ueberspielt")] += 1
    spieler_aktionen = [dict({"team": k[0], "name": k[1], "pos": POS.get(k, "")}, **v) for k, v in SP.items() if k[1]]
    return Z, tore, gegner, tid, spieler_aktionen


def physis(pfad):
    sum_ = collections.defaultdict(collections.Counter)
    namen, spieler = {}, []
    for r in csv.DictReader(open(pfad, encoding="utf-8")):
        t = r.get("team_id")
        if not t:
            continue
        f = lambda k: float(r.get(k) or 0)
        namen[t] = r.get("team_name") or t
        if r.get("player_name") and f("minutes_full_all") > 0:
            spieler.append({"team_id": t, "name": r.get("player_short_name") or r["player_name"], "pos": r.get("position") or "",
                            "gruppe": r.get("position_group") or "", "min": round(f("minutes_full_all"), 1),
                            "km": round(f("total_distance_full_all") / 1000, 2), "hi": f("hi_distance_full_all"),
                            "sprints": f("sprint_count_full_all"), "psv99": f("psv99")})
        sum_[t]["distanz_m"] += f("total_distance_full_all")
        sum_[t]["intensiv_m"] += f("hi_distance_full_all")
        sum_[t]["sprints"] += f("sprint_count_full_all")
        sum_[t]["topspeed"] = max(sum_[t]["topspeed"], f("psv99"))
    return sum_, namen, spieler


def main():
    plan = {p["id"]: p for p in json.load(open(os.path.join(LIGA, "spielplan.json"), encoding="utf-8"))} if os.path.exists(os.path.join(LIGA, "spielplan.json")) else {}
    dateien = {}
    for f in glob.glob(os.path.join(DATEN, "skillcorner_dynamic_events", "*.csv")):
        dateien[int(os.path.basename(f)[:-4])] = f
    for f in glob.glob(os.path.join(LIGA, "events", "*.csv.gz")):
        dateien[int(os.path.basename(f)[:-7])] = f
    alt = {}
    if os.path.exists(ZIEL):
        d = json.load(open(ZIEL, encoding="utf-8"))
        if d.get("version") == VERSION:
            alt = {s["match_id"]: s for s in d["spiele"]}
    spiele = []
    for mid, f in sorted(dateien.items()):
        ph_da = os.path.exists(os.path.join(LIGA, "physis", f"{mid}.csv"))
        if mid in alt and (alt[mid].get("spieler") or not ph_da) and (alt[mid].get("quelle") == os.path.basename(f)):
            spiele.append(alt[mid])
            continue
        R = lies(f)
        Z, tore, gegner, tid, aktionen = spiel_auswerten(R)
        p = plan.get(mid, {})
        ph_datei = os.path.join(LIGA, "physis", f"{mid}.csv")
        phy, namen, spl = physis(ph_datei) if os.path.exists(ph_datei) else ({}, {}, [])
        datum = (p.get("datum") or "")[:10] or (R[0].get("match_date", "") if R else "")
        eintrag = {"match_id": mid, "datum": datum, "teams": {}, "spieler": spl, "quelle": os.path.basename(f),
                   "aktionen": [dict(a, team_id=str(tid.get(a["team"]))) for a in aktionen]}
        for t in Z:
            eintrag["teams"][t] = {"team_id": tid.get(t), "name": namen.get(str(tid.get(t)), t), "gegner": gegner.get(t), "zaehler": dict(Z[t]), "tore": tore[t],
                                   "gegentore": tore.get(gegner.get(t), []),
                                   "physis": {k: round(v, 1) for k, v in (phy.get(str(tid.get(t))) or {}).items()}}
        spiele.append(eintrag)
        print("ausgewertet:", mid, datum, " v ".join(Z.keys()))
    # Bereits ausgewertete Spiele behalten, auch wenn ihre Rohdaten nicht mehr vorliegen (GitHub)
    da = {s["match_id"] for s in spiele}
    spiele += [s for mid, s in alt.items() if mid not in da]
    spiele.sort(key=lambda s: (s["datum"], s["match_id"]))
    json.dump({"version": VERSION, "spiele": spiele}, open(ZIEL, "w", encoding="utf-8"), ensure_ascii=False)
    print(len(spiele), "Spiele ->", ZIEL)


if __name__ == "__main__":
    main()
