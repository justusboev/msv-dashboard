import os, csv, json, re, sys, os, base64
HIER = os.path.dirname(os.path.abspath(__file__))
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
ITER = 600000
pw = os.environ['MSV_PW'].encode('utf-8')
src = open(os.path.join(HIER,'dashboard_vorlage.html'), encoding='utf-8').read()
style = re.search(r'<style>(.*?)</style>', src, re.S).group(1)
body = src[src.index('<div class="msv">'):src.index('<script>')]
scripts = re.findall(r'<script>(.*?)</script>', src, re.S)
_m = re.search(r'src="(data:image/png;base64,[^"]+)"', src); logo = _m.group(1) if _m else ''
rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8')))
stand = 'Spiele: ' + '.'.join(reversed(max(r['match_date'] for r in rows).split('-')))
# Trainingsdaten aus Polar Team Pro (falls vorhanden)
DATEN_ORDNER = os.path.join(os.path.dirname(HIER), '02_Daten')
def lies(name):
    f = os.path.join(DATEN_ORDNER, name)
    return list(csv.DictReader(open(f, encoding='utf-8'))) if os.path.exists(f) else []
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
daten = {'physis': rows, 'training_spieler': lies('polar_spieler_einheiten.csv'), 'training_drills': lies('polar_drills.csv'), 'training_team': lies('polar_team_einheiten.csv')}
daten['kader'] = kader_laden()
daten['liga'], daten['liga_plan'] = liga_laden()
sys.path.insert(0, HIER)
from impect_einlesen import impect_laden
daten['impect'] = impect_laden(daten['liga'])
from liga_aufstellungen import aufstellungen_laden
daten['aufstellungen'] = aufstellungen_laden(3)
# Gemeinsame Notizen: privates GitHub-Repository, Zugang nur im verschluesselten Teil der Seite
if os.environ.get('NOTIZEN_TOKEN'):
    daten['notizen_cfg'] = {'repo': os.environ.get('NOTIZEN_REPO', 'justusboev/msv-notizen'), 'token': os.environ['NOTIZEN_TOKEN'].strip()}
_IM_KAT = ['Spielstile','Allgemein','Tore erzielen','Gegentore verhindern','Alle offensiven Spielphasen - Tore','Alle offensiven Spielphasen - Shot-based xG','Alle defensiven Spielphasen - Gegentore','Alle defensiven Spielphasen - Shot-based xG (Gegner)','Übersicht','Standard-Daten - Standard-Daten','Offensiv - Shot-based xG','Defensiv - Shot-based xG (Gegner)']
for _t in (daten['impect'].get('teams') or {}).values():
    _t['w'] = {k: v for k, v in _t['w'].items() if k.split('|')[0] in _IM_KAT}
if daten['training_team']:
    stand += ' · Training: ' + '.'.join(reversed(max(r['datum'] for r in daten['training_team']).split('-')))
salt, iv = os.urandom(16), os.urandom(12)
key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITER).derive(pw)
ct = AESGCM(key).encrypt(iv, json.dumps(daten, ensure_ascii=False).encode('utf-8'), None)
b = lambda x: base64.b64encode(x).decode()
d3 = open(os.path.join(HIER,'d3.min.js'), encoding='utf-8').read()
build = open(os.path.join(HIER,'html_ohne_passwort_bauen.py'), encoding='utf-8').read()
vars_css = re.search(r"vars_css='''(.*?)'''", build, re.S).group(1)
shim = re.search(r"shim='''(.*?)'''", build, re.S).group(1)
gate_css = '''
#gate{ min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px; box-sizing:border-box; font-family: var(--font-anthropic-sans); }
.gate-card{ width:100%; max-width:380px; background:rgba(16,28,72,.66); -webkit-backdrop-filter:blur(10px); backdrop-filter:blur(10px); color:#fff; border:1px solid rgba(255,255,255,.16); border-radius:18px; padding:30px 26px; box-shadow:0 16px 48px rgba(0,0,0,.35); text-align:center; }
.gate-wort{ width:220px; max-width:80%; height:auto; display:block; margin:0 auto 18px; }
.gate-card h1{ font-weight:600; font-size:22px; margin:0 0 4px; letter-spacing:.01em; }
.gate-card p{ margin:0 0 18px; font-size:14px; color:var(--color-fg-muted); }
.gate-card input{ width:100%; box-sizing:border-box; font:inherit; font-size:16px; padding:12px 14px; border:1px solid rgba(255,255,255,.25); border-radius:10px; background:rgba(255,255,255,.08); color:#fff; margin-bottom:10px; }
.gate-card input::placeholder{ color:rgba(255,255,255,.55); }
.gate-card button{ width:100%; font:inherit; font-size:16px; font-weight:600; padding:12px; border:0; border-radius:10px; background:#fff; color:#1b2a5c; cursor:pointer; }
.gate-card button[disabled]{ opacity:.6; cursor:wait; }
.gate-err{ min-height:18px; margin-top:10px; font-size:13px; color:var(--color-bad); }
'''
app_js = shim + '\n' + '\n'.join(scripts) + '\nwindow.__msvReady = true; window.__msvRunAll();\n'
gate_js = '''
(function(){
  const E = { salt: "%s", iv: "%s", ct: "%s", iter: %d };
  const dec = (s) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  const inp = document.getElementById('gate-pw'), btn = document.getElementById('gate-btn'), err = document.getElementById('gate-err');
  async function entsperren() {
    err.textContent = ''; btn.disabled = true; btn.textContent = 'Wird geprüft …';
    try {
      const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(inp.value), 'PBKDF2', false, ['deriveKey']);
      const key = await crypto.subtle.deriveKey({ name: 'PBKDF2', salt: dec(E.salt), iterations: E.iter, hash: 'SHA-256' }, base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
      const plain = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: dec(E.iv) }, key, dec(E.ct));
      window.MSV_DATEN = JSON.parse(new TextDecoder().decode(plain));
      window.MSV_PW_EIN = inp.value;
      document.getElementById('gate').remove();
      document.getElementById('app').hidden = false;
      window.msvStart();
    } catch (e) {
      err.textContent = (window.crypto && crypto.subtle) ? 'Falsches Passwort. Bitte erneut versuchen.' : 'Dieser Browser unterstützt die Entschlüsselung nicht.';
      btn.disabled = false; btn.textContent = 'Öffnen'; inp.select();
    }
  }
  btn.addEventListener('click', entsperren);
  inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') { e.preventDefault(); entsperren(); } });
  inp.focus();
})();
''' % (b(salt), b(iv), b(ct), ITER)

def _app_icons(ziel_html):
    """App-Logo, Favicon und Manifest neben die HTML-Datei legen (fuer 'Zum Home-Bildschirm')."""
    import shutil, json as _j
    ordner = os.path.dirname(os.path.abspath(ziel_html))
    for n in ('apple-touch-icon.png', 'icon-192.png', 'icon-512.png', 'favicon-32.png'):
        q = os.path.join(HIER, 'design', n)
        if os.path.exists(q):
            shutil.copyfile(q, os.path.join(ordner, n))
    _j.dump({'name': 'MSV Dashboard', 'short_name': 'MSV Dashboard', 'start_url': './', 'scope': './', 'display': 'standalone',
             'background_color': '#1b2a5c', 'theme_color': '#1b2a5c',
             'icons': [{'src': 'icon-192.png', 'sizes': '192x192', 'type': 'image/png'}, {'src': 'icon-512.png', 'sizes': '512x512', 'type': 'image/png'}]},
            open(os.path.join(ordner, 'manifest.webmanifest'), 'w', encoding='utf-8'), ensure_ascii=False)

html = f'''<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MSV Dashboard</title>
<link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png"><link rel="apple-touch-icon" href="apple-touch-icon.png"><link rel="manifest" href="manifest.webmanifest"><meta name="apple-mobile-web-app-title" content="MSV Dashboard"><meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-status-bar-style" content="black"><meta name="theme-color" content="#1b2a5c">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link href="https://fonts.googleapis.com/css2?family=Hind:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{vars_css}{style}{gate_css}</style>
</head><body>
<div id="gate"><div class="gate-card">
  <img class="gate-wort" src="__SCHRIFTZUG__" alt="MSV Duisburg">
  <h1>MSV Dashboard</h1>
  <p>Geschützter Bereich. Bitte Passwort eingeben.</p>
  <input id="gate-pw" type="password" autocomplete="current-password" aria-label="Passwort" placeholder="Passwort">
  <button id="gate-btn" type="button">Öffnen</button>
  <div class="gate-err" id="gate-err" role="alert"></div>
</div></div>
<div id="app" hidden><div class="msv-wrap">
{body}
<p class="msv-stand">Datenstand {stand} · Quellen: SkillCorner, Polar Team Pro · Nur für den internen Gebrauch</p>
</div></div>
<script>{d3}</script>
<script>window.msvStart = function () {{
{app_js}
}};</script>
<script>{gate_js}</script>
</body></html>'''
def _uri(n, typ):
    f = os.path.join(HIER, 'design', n)
    return ('data:' + typ + ';base64,' + base64.b64encode(open(f, 'rb').read()).decode()) if os.path.exists(f) else ''
html = html.replace('__HINTERGRUND__', _uri('hintergrund.jpg', 'image/jpeg')).replace('__SCHRIFTZUG__', _uri('schriftzug.png', 'image/png'))
open(sys.argv[2], 'w', encoding='utf-8').write(html)
_app_icons(sys.argv[2])
print(len(html))
