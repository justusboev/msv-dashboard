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
daten={'physis':rows,'training_spieler':lies('polar_spieler_einheiten.csv'),'training_drills':lies('polar_drills.csv'),'training_team':lies('polar_team_einheiten.csv')}
d3=open(os.path.join(HIER,'d3.min.js'),encoding='utf-8').read()
stand='Datenstand Spiele: '+'.'.join(reversed(max(r['match_date'] for r in rows).split('-')))
if daten['training_team']:
    stand+=' · Training: '+'.'.join(reversed(max(r['datum'] for r in daten['training_team']).split('-')))
vars_css='''
:root{ --color-fg:#14181f; --color-fg-muted:#5b6472; --color-bg:#ffffff; --color-panel:#ffffff; --color-border-line:#e1e5ec;
 --color-ok:#1a7f4b; --color-warn:#b26b00; --color-bad:#c0392b;
 --font-anthropic-sans: system-ui,-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; --font-anthropic-serif: Georgia,"Times New Roman",serif;
 --cds-font-size-caption:12.5px; --cds-font-size-body:15px; --cds-font-size-heading:19px; --cds-font-size-title:30px; --cds-font-weight-medium:600;
 --cds-gap-xs:4px; --cds-gap-sm:8px; --cds-gap-md:12px; --cds-gap-lg:20px; --cds-gap-xl:32px;
 --cds-pad-xs:4px; --cds-pad-sm:8px; --cds-pad-md:12px; --cds-pad-lg:16px; --cds-pad-xl:24px; --cds-radius:10px;
 --cds-chart-grid:#eceff3; --cds-chart-axis:#c3c9d2; --cds-chart-muted:#c8ced8; --cds-chart-reference:#7b8494; --cds-text-secondary:#5b6472;
 --cds-surface-popover:#ffffff; --cds-border:#d6dbe3; --cds-shadow-popover:0 6px 18px rgba(0,0,0,.12); }
@media (prefers-color-scheme: dark){ :root{ --color-fg:#e8ebf0; --color-fg-muted:#9aa3b2; --color-bg:#0f1115; --color-panel:#171a21; --color-border-line:#2a2f3a;
 --cds-chart-grid:#242a33; --cds-chart-axis:#3a414d; --cds-chart-muted:#3d4452; --cds-text-secondary:#9aa3b2; --cds-surface-popover:#1d212a; --cds-border:#333a46; } }
html,body{ margin:0; background:var(--color-bg); color:var(--color-fg); }
.msv-wrap{ max-width:1100px; margin:0 auto; padding:20px 16px 40px; }
.dash-select{ font:inherit; font-size:14px; padding:8px 32px 8px 10px; border:1px solid var(--color-border-line); border-radius:8px; background-color:var(--color-bg); color:var(--color-fg); }
.msv-stand{ font-family:var(--font-anthropic-sans); font-size:12px; color:var(--color-fg-muted); margin-top:10px; text-align:center; }
@media (max-width:600px){ .msv-head{ background: linear-gradient(90deg, var(--msv-blau-dunkel) 0%, var(--msv-blau) 80%, rgba(0,88,168,.6) 100%), repeating-linear-gradient(115deg, var(--msv-blau) 0 16px, #ffffff 16px 28px) !important; } }
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
html=f'''<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MSV Dashboard</title>
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
open(sys.argv[2],'w',encoding='utf-8').write(html)
print(len(html))
