"""Offizielle Ergebnisse (OpenLigaDB, siehe liga_tabelle.py) ins Dashboard einbauen.

- daten['liga_tabelle']: aktuelle Tabelle der 3. Liga
- daten['liga_erg']: alle gespielten Spiele mit offiziellem Ergebnis und Team-IDs
- Tore/Gegentore in Spiel- und Gegneranalyse und in den Aufstellungen werden
  durch die offiziellen Ergebnisse ersetzt (SkillCorner-Ergebnisse sind teils falsch).
"""
import json, os

HIER = os.path.dirname(os.path.abspath(__file__))
LIGA = os.path.join(os.path.dirname(HIER), "02_Daten", "liga")


def _lies(name):
    p = os.path.join(LIGA, name)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def anwenden(daten):
    tab = _lies("tabelle.json")
    erg = _lies("ergebnisse.json")
    if isinstance(erg, dict):
        erg = erg.get("ergebnisse") or erg.get("spiele") or []
    if not tab or not erg:
        print("Offizielle Liga-Ergebnisse fehlen, Tore bleiben wie von SkillCorner.")
        return
    daten["liga_tabelle"] = tab
    # Team-IDs je Spiel aus dem SkillCorner-Spielplan
    plan = {str(s.get("id")): s for s in (daten.get("liga_plan") or [])}
    namen_id = {t.get("name"): str(t.get("team_id")) for t in tab.get("tabelle", []) if t.get("team_id")}
    E, off = [], {}
    for e in erg:
        mid = str(e.get("skillcorner_id") or "")
        p = plan.get(mid, {})
        hid = str(p.get("heim_id") or namen_id.get(e.get("heim")) or "")
        gid = str(p.get("gast_id") or namen_id.get(e.get("gast")) or "")
        E.append({"id": mid, "st": e.get("spieltag"), "datum": e.get("datum"), "heim_id": hid, "gast_id": gid,
                  "heim": e.get("heim"), "gast": e.get("gast"), "th": e.get("tore_heim"), "tg": e.get("tore_gast")})
        if mid and hid and gid:
            off[mid] = {hid: e.get("tore_heim"), gid: e.get("tore_gast")}
    daten["liga_erg"] = E
    abw = 0
    for sp in daten.get("liga") or []:
        o = off.get(str(sp.get("match_id")))
        if not o:
            continue
        for t in (sp.get("teams") or {}).values():
            tid = str(t.get("team_id"))
            if tid not in o:
                continue
            if len(t.get("tore") or []) != o[tid]:
                abw += 1
            t["tore_offiziell"] = o[tid]
            t.setdefault("zaehler", {})["tore"] = o[tid]
    for tid, liste in (daten.get("aufstellungen") or {}).items():
        for sp in liste:
            o = off.get(str(sp.get("match_id")))
            gid = str(sp.get("gegner_id") or "")
            if o and str(tid) in o and gid in o:
                tid = str(tid)
                sp["tore"], sp["gegentore"] = o[tid], o[gid]
    print("Offizielle Ergebnisse: %d Spiele, Tabelle Stand %s, %d SkillCorner-Torzahlen korrigiert."
          % (len(E), tab.get("stand"), abw))
