# Verschluesselter Datenstand fuer GitHub.
# Packt die Daten aus 02_Daten in daten/zustand.enc (AES-256-GCM) und wieder aus.
# Schluessel: Umgebungsvariable ZUSTAND_SCHLUESSEL (GitHub-Secret), nie im Repository.
#   python 03_Skripte/zustand.py auspacken
#   python 03_Skripte/zustand.py einpacken
import base64, gzip, hashlib, io, os, sys, tarfile
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

HIER = os.path.dirname(os.path.abspath(__file__))
ORDNER = os.path.dirname(HIER)
DATEN = os.environ.get("MSV_DATEN") or os.path.join(ORDNER, "02_Daten")
ZIEL = os.path.join(ORDNER, "daten", "zustand.enc")
PRUEF = os.path.join(ORDNER, "daten", "zustand.pruefsumme")
INHALT = ["polar_einheiten", "skillcorner_api_physis", "letzter_abruf.json", "polar_letzter_abruf.json", "polar_token.txt",
          "skillcorner_physis_alle_spiele.csv", "polar_spieler_einheiten.csv", "polar_drills.csv", "polar_team_einheiten.csv",
          "liga_kennzahlen.json", "liga/spielplan.json", "liga_aufstellungen.json"]
KOPF, ZUSATZ = b"MSV1", b"msv-zustand-v1"


def schluessel():
    k = base64.b64decode(os.environ["ZUSTAND_SCHLUESSEL"].strip())
    if len(k) != 32:
        sys.exit("ZUSTAND_SCHLUESSEL hat die falsche Laenge.")
    return k


def dateien():
    for name in INHALT:
        pfad = os.path.join(DATEN, name)
        if os.path.isdir(pfad):
            for f in sorted(os.listdir(pfad)):
                if os.path.isfile(os.path.join(pfad, f)):
                    yield name + "/" + f
        elif os.path.isfile(pfad):
            yield name


def einpacken():
    roh = io.BytesIO()
    with tarfile.open(fileobj=roh, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel in dateien():
            daten = open(os.path.join(DATEN, rel), "rb").read()
            info = tarfile.TarInfo(rel)
            info.size, info.mtime, info.mode = len(daten), 0, 0o644
            tar.addfile(info, io.BytesIO(daten))
    gz = gzip.compress(roh.getvalue(), mtime=0)
    summe = hashlib.sha256(gz).hexdigest()
    if os.path.exists(PRUEF) and os.path.exists(ZIEL) and open(PRUEF).read().strip() == summe:
        print("Datenstand unveraendert.")
        return
    nonce = os.urandom(12)
    os.makedirs(os.path.dirname(ZIEL), exist_ok=True)
    open(ZIEL, "wb").write(KOPF + nonce + AESGCM(schluessel()).encrypt(nonce, gz, ZUSATZ))
    open(PRUEF, "w").write(summe + "\n")
    print("Datenstand verschluesselt gespeichert (%d KB)." % (os.path.getsize(ZIEL) // 1024))


def auspacken():
    if not os.path.exists(ZIEL):
        print("Noch kein Datenstand vorhanden, starte leer.")
        return
    daten = open(ZIEL, "rb").read()
    if daten[:4] != KOPF:
        sys.exit("zustand.enc hat ein unbekanntes Format.")
    gz = AESGCM(schluessel()).decrypt(daten[4:16], daten[16:], ZUSATZ)
    os.makedirs(DATEN, exist_ok=True)
    anzahl = 0
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(gz)), mode="r") as tar:
        for m in tar.getmembers():
            if not m.isfile() or m.name.startswith("/") or ".." in m.name.split("/"):
                continue
            ziel = os.path.join(DATEN, m.name)
            os.makedirs(os.path.dirname(ziel), exist_ok=True)
            open(ziel, "wb").write(tar.extractfile(m).read())
            anzahl += 1
    print("Datenstand entschluesselt: %d Dateien." % anzahl)


# ---- Stammdaten (Kader und Spielerfotos), verschluesselt mit dem Dashboard-Passwort ----
STAMM = os.path.join(ORDNER, "daten", "stammdaten.enc")
STAMM_INHALT = ["kader.csv", "spielerfotos"]


def stamm_schluessel(salz):
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salz, iterations=600000).derive(os.environ["MSV_PW"].encode("utf-8"))


def stammdaten_einpacken():
    roh = io.BytesIO()
    with tarfile.open(fileobj=roh, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for name in STAMM_INHALT:
            pfad = os.path.join(DATEN, name)
            liste = [name + "/" + f for f in sorted(os.listdir(pfad))] if os.path.isdir(pfad) else ([name] if os.path.isfile(pfad) else [])
            for rel in liste:
                daten = open(os.path.join(DATEN, rel), "rb").read()
                info = tarfile.TarInfo(rel)
                info.size, info.mtime, info.mode = len(daten), 0, 0o644
                tar.addfile(info, io.BytesIO(daten))
    salz, nonce = os.urandom(16), os.urandom(12)
    gz = gzip.compress(roh.getvalue(), mtime=0)
    open(STAMM, "wb").write(b"MSS1" + salz + nonce + AESGCM(stamm_schluessel(salz)).encrypt(nonce, gz, b"msv-stammdaten-v1"))
    print("Stammdaten verschluesselt (%d KB)." % (os.path.getsize(STAMM) // 1024))


def stammdaten_auspacken():
    if not os.path.exists(STAMM):
        print("Keine Stammdaten vorhanden.")
        return
    d = open(STAMM, "rb").read()
    if d[:4] != b"MSS1":
        sys.exit("stammdaten.enc hat ein unbekanntes Format.")
    gz = AESGCM(stamm_schluessel(d[4:20])).decrypt(d[20:32], d[32:], b"msv-stammdaten-v1")
    n = 0
    with tarfile.open(fileobj=io.BytesIO(gzip.decompress(gz)), mode="r") as tar:
        for m in tar.getmembers():
            if not m.isfile() or m.name.startswith("/") or ".." in m.name.split("/"):
                continue
            ziel = os.path.join(DATEN, m.name)
            os.makedirs(os.path.dirname(ziel), exist_ok=True)
            open(ziel, "wb").write(tar.extractfile(m).read())
            n += 1
    print("Stammdaten entschluesselt: %d Dateien." % n)


# ---- Impect-Teamwerte (aus dem Excel-Export), verschluesselt mit dem Dashboard-Passwort ----
IMPECT = os.path.join(ORDNER, "daten", "impect.enc")
IMPECT_JSON = os.path.join(DATEN, "impect_teams.json")


def impect_verschluesseln(roh):
    """Bytes von impect_teams.json -> verschluesselte Bytes (Format MSI1)."""
    salz, nonce = os.urandom(16), os.urandom(12)
    return b"MSI1" + salz + nonce + AESGCM(stamm_schluessel(salz)).encrypt(nonce, gzip.compress(roh, mtime=0), b"msv-impect-v1")


def impect_einpacken():
    if not os.path.exists(IMPECT_JSON):
        sys.exit("Keine 02_Daten/impect_teams.json vorhanden.")
    open(IMPECT, "wb").write(impect_verschluesseln(open(IMPECT_JSON, "rb").read()))
    print("Impect-Daten verschluesselt (%d KB)." % (os.path.getsize(IMPECT) // 1024))


def impect_auspacken():
    if not os.path.exists(IMPECT):
        print("Keine Impect-Daten vorhanden.")
        return
    d = open(IMPECT, "rb").read()
    if d[:4] != b"MSI1":
        sys.exit("impect.enc hat ein unbekanntes Format.")
    roh = gzip.decompress(AESGCM(stamm_schluessel(d[4:20])).decrypt(d[20:32], d[32:], b"msv-impect-v1"))
    os.makedirs(DATEN, exist_ok=True)
    open(IMPECT_JSON, "wb").write(roh)
    print("Impect-Daten entschluesselt.")


if __name__ == "__main__":
    {"einpacken": einpacken, "auspacken": auspacken,
     "stammdaten-einpacken": stammdaten_einpacken, "stammdaten-auspacken": stammdaten_auspacken,
     "impect-einpacken": impect_einpacken, "impect-auspacken": impect_auspacken}[sys.argv[1]]()
