import os, csv, json, re, sys
HIER = os.path.dirname(os.path.abspath(__file__))
src=open(os.path.join(HIER,'dashboard_vorlage.html'),encoding='utf-8').read()
style=re.search(r'<style>(.*?)</style>',src,re.S).group(1)
body=src[src.index('<div class="msv">'):src.index('<script>')]
scripts=re.findall(r'<script>(.*?)</script>',src,re.S)
rows=list(csv.DictReader(open(sys.argv[1],encoding='utf-8')))
# Trainingsdaten aus Polar Team Pro (falls vorhanden)
DATEN_ORDNER=os.path.join(os.path.dirname(HIER),'02_Daten')
def lies(name):
    f=os.path.join(DATEN_ORDNER,name)
    return list(csv.DictReader(open(f,encoding='utf-8'))) if os.path.exists(f) else []
def liga_laden():
    """Liga-Kennzahlen (02_Daten/liga_kennzahlen.json) und Spielplan fuer Spielanalyse und Gegneranalyse."""
    f = os.path.join(DATEN_ORDNER, 'liga_kennzahlen.json')
    plan = os.path.join(DATEN_ORDNER, 'liga', 'spielplan.json')
    spiele = json.load(open(f, encoding='utf-8'))['spiele'] if os.path.exists(f) else []
    for sp in spiele:
        sp.pop('quelle', None)
    return spiele, (json.load(open(plan, encoding='utf-8')) if os.path.exists(plan) else [])


def kader_laden():
    """Kader (02_Daten/kader.csv) mit Spielerfotos (02_Daten/spielerfotos/<Name>.jpg)."""
    import base64
    f = os.path.join(DATEN_ORDNER, 'kader.csv')
    if not os.path.exists(f):
        return []
    roh = open(f, encoding='utf-8-sig').read()
    kopf = roh.split('\n')[0]
    trenner = ';' if kopf.count(';') >= kopf.count(',') else ','
    aus = []
    for r in csv.DictReader(roh.splitlines(), delimiter=trenner):
        n = (r.get('name') or '').strip()
        if not n:
            continue
        foto = os.path.join(DATEN_ORDNER, 'spielerfotos', n + '.jpg')
        aus.append({'name': n, 'nummer': (r.get('nummer') or '').strip(), 'position': (r.get('position') or '').strip(),
                    'geburtsdatum': (r.get('geburtsdatum') or '').strip(),
                    'foto': ('data:image/jpeg;base64,' + base64.b64encode(open(foto, 'rb').read()).decode()) if os.path.exists(foto) else ''})
    return aus
daten={'physis':rows,'training_spieler':lies('polar_spieler_einheiten.csv'),'training_drills':lies('polar_drills.csv'),'training_team':lies('polar_team_einheiten.csv')}
daten['kader'] = kader_laden()
daten['liga'], daten['liga_plan'] = liga_laden()
sys.path.insert(0, HIER)
from impect_einlesen import impect_laden
daten['impect'] = impect_laden(daten['liga'])
from liga_aufstellungen import aufstellungen_laden
daten['aufstellungen'] = aufstellungen_laden(3)
_IM_KAT = ['Spielstile','Allgemein','Tore erzielen','Gegentore verhindern','Alle offensiven Spielphasen - Tore','Alle offensiven Spielphasen - Shot-based xG','Alle defensiven Spielphasen - Gegentore','Alle defensiven Spielphasen - Shot-based xG (Gegner)','Übersicht','Standard-Daten - Standard-Daten','Offensiv - Shot-based xG','Defensiv - Shot-based xG (Gegner)']
for _t in (daten['impect'].get('teams') or {}).values():
    _t['w'] = {k: v for k, v in _t['w'].items() if k.split('|')[0] in _IM_KAT}
d3=open(os.path.join(HIER,'d3.min.js'),encoding='utf-8').read()
stand='Datenstand Spiele: '+'.'.join(reversed(max(r['match_date'] for r in rows).split('-')))
if daten['training_team']:
    stand+=' · Training: '+'.'.join(reversed(max(r['datum'] for r in daten['training_team']).split('-')))
vars_css='''
:root{ color-scheme: dark;
 --color-fg:#ffffff; --color-fg-muted:#b9c8e6; --color-bg:#1b2a5c; --color-panel:rgba(16,28,72,.62); --color-border-line:rgba(255,255,255,.14);
 --color-ok:#5fd394; --color-warn:#f4bd50; --color-bad:#ff7d74;
 --font-anthropic-sans: "Hind", system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; --font-anthropic-serif: "Hind", system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
 --cds-font-size-caption:13px; --cds-font-size-body:15.5px; --cds-font-size-heading:20px; --cds-font-size-title:32px; --cds-font-weight-medium:600;
 --cds-gap-xs:4px; --cds-gap-sm:8px; --cds-gap-md:12px; --cds-gap-lg:20px; --cds-gap-xl:32px;
 --cds-pad-xs:4px; --cds-pad-sm:8px; --cds-pad-md:12px; --cds-pad-lg:16px; --cds-pad-xl:24px; --cds-radius:12px;
 --cds-chart-grid:rgba(255,255,255,.12); --cds-chart-axis:rgba(255,255,255,.35); --cds-chart-muted:rgba(255,255,255,.28); --cds-chart-reference:#c9d6f0; --cds-text-secondary:#b9c8e6;
 --cds-surface-popover:#15235a; --cds-border:rgba(255,255,255,.22); --cds-shadow-popover:0 8px 24px rgba(0,0,0,.35); }
html{ background:#1b2a5c; }
html,body{ margin:0; color:var(--color-fg); }
body{ background:transparent; font-family:var(--font-anthropic-sans); }
body::before{ content:""; position:fixed; inset:0; z-index:-1; background:#1b2a5c url("__HINTERGRUND__") center top / cover no-repeat; }
.msv-wrap{ max-width:1100px; margin:0 auto; padding:20px 16px 40px; position:relative; }
.dash-select{ font:inherit; font-size:14px; padding:8px 32px 8px 10px; border:1px solid var(--color-border-line); border-radius:8px; background-color:#15235a; color:var(--color-fg); }
.msv-stand{ font-family:var(--font-anthropic-sans); font-size:12px; color:var(--color-fg-muted); margin-top:10px; text-align:center; }
'''
shim='''
(function(){
  const D = window.MSV_DATEN || {};
  const store = Array.isArray(D) ? { physis: D } : Object.assign({}, D);
  const draws = {};
  const res = (v) => ({ status: 'ok', data: v, refreshing: false });
  window.dash = {
    data: (id) => res(store[id] !== undefined ? store[id] : []),
    calc: (id, o) => { store[id] = o.fn(...o.inputs.map((i) => store[i])); },
    loader: () => {}, colors: ['var(--msv-blau-chart)'],
    draw: (name, fn) => {
      if (fn) { draws[name] = typeof fn === 'function' ? fn : (fn.update || fn.mount); if (window.__msvReady) run(name); return; }
      run(name);
    },
    onData: (fn) => fn(), setLink: (n) => { try { history.replaceState(null, '', '#' + n); } catch (e) {} setTimeout(runAll, 0); },
    params: () => ({}), setParams: () => {}, resetParams: () => {}, refresh: () => {}
  };
  function run(name) {
    const fn = draws[name]; if (!fn) return;
    document.querySelectorAll('[data-draw="' + name + '"]').forEach((el) => { if (el.closest('[hidden]')) return; try { fn(el); } catch (e) { console.error(name, e); } });
  }
  function runAll() { Object.keys(draws).forEach(run); }
  window.__msvRunAll = runAll;
  let t; window.addEventListener('resize', () => { clearTimeout(t); t = setTimeout(runAll, 120); });
})();
'''
import base64 as _b64
def _uri(n, typ):
    f=os.path.join(HIER,'design',n)
    return ('data:'+typ+';base64,'+_b64.b64encode(open(f,'rb').read()).decode()) if os.path.exists(f) else ''
html=f'''<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MSV Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Hind:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{vars_css}{style}</style>
</head><body><div class="msv-wrap">
{body}
<p class="msv-stand">{stand} · Quellen: SkillCorner, Polar Team Pro · Nur für den internen Gebrauch</p>
</div>
<script>{d3}</script>
<script>window.MSV_DATEN = {json.dumps(daten,ensure_ascii=False)};</script>
<script>{shim}</script>
''' + ''.join(f'<script>{s}</script>\n' for s in scripts) + '''<script>window.__msvReady = true; window.__msvRunAll();</script>
</body></html>'''
html=html.replace('__HINTERGRUND__',_uri('hintergrund.jpg','image/jpeg')).replace('__SCHRIFTZUG__',_uri('schriftzug.png','image/png'))
open(sys.argv[2],'w',encoding='utf-8').write(html)
print(len(html))
