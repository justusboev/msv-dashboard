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
          "skillcorner_physis_alle_spiele.csv", "polar_spieler_einheiten.csv", "polar_drills.csv", "polar_team_einheiten.csv"]
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


if __name__ == "__main__":
    {"einpacken": einpacken, "auspacken": auspacken}[sys.argv[1]]()
