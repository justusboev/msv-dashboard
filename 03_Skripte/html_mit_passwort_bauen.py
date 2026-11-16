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
logo = re.search(r'src="(data:image/png;base64,[^"]+)"', src).group(1)
rows = list(csv.DictReader(open(sys.argv[1], encoding='utf-8')))
stand = 'Spiele: ' + '.'.join(reversed(max(r['match_date'] for r in rows).split('-')))
# Trainingsdaten aus Polar Team Pro (falls vorhanden)
DATEN_ORDNER = os.path.join(os.path.dirname(HIER), '02_Daten')
def lies(name):
    f = os.path.join(DATEN_ORDNER, name)
    return list(csv.DictReader(open(f, encoding='utf-8'))) if os.path.exists(f) else []
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
#gate{ min-height:100vh; display:flex; align-items:center; justify-content:center; padding:20px; box-sizing:border-box;
  background: linear-gradient(160deg, #003d7a 0%, #0058a8 60%, rgba(0,88,168,.85) 100%), repeating-linear-gradient(115deg, #0058a8 0 16px, #ffffff 16px 28px); font-family: var(--font-anthropic-sans); }
.gate-card{ width:100%; max-width:360px; background:var(--color-panel); color:var(--color-fg); border-radius:16px; padding:28px 24px; box-shadow:0 12px 40px rgba(0,0,0,.25); text-align:center; position:relative; overflow:hidden; }
.gate-card::before{ content:""; position:absolute; left:0; right:0; top:0; height:6px; background: repeating-linear-gradient(90deg, #0058a8 0 10px, #ffffff 10px 18px); }
.gate-card img{ width:72px; height:auto; margin:4px auto 10px; display:block; }
.gate-card h1{ font-family:var(--font-anthropic-serif); font-weight:400; font-size:26px; margin:0 0 4px; }
.gate-card p{ margin:0 0 18px; font-size:13px; color:var(--color-fg-muted); }
.gate-card input{ width:100%; box-sizing:border-box; font:inherit; font-size:16px; padding:11px 12px; border:1px solid var(--color-border-line); border-radius:10px; background:var(--color-bg); color:var(--color-fg); margin-bottom:10px; }
.gate-card button{ width:100%; font:inherit; font-size:15px; font-weight:600; padding:11px; border:0; border-radius:10px; background:#0058a8; color:#fff; cursor:pointer; }
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
html = f'''<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>MSV Dashboard</title>
<style>{vars_css}{style}{gate_css}</style>
</head><body>
<div id="gate"><div class="gate-card">
  <img src="{logo}" alt="Wappen MSV Duisburg">
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
open(sys.argv[2], 'w', encoding='utf-8').write(html)
print(len(html))
