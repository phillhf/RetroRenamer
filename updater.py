"""Update-Funktion: holt die neueste Release von GitHub und ersetzt die Programmdateien.

DAT-Dateien, Einstellungen und alles ausserhalb des Programmordners bleiben unberuehrt.
"""

import io
import json
import os
import re
import shutil
import tempfile
import urllib.request
import zipfile

REPO = "phillhf/RetroRenamer"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Diese Pfade gehoeren dem Benutzer und werden bei einem Update nie ueberschrieben
PROTECTED = ("dats/", "retrorenamer_settings.json", ".git/")


def _parse_version(v):
    return tuple(int(x) for x in re.findall(r"\d+", v)[:3]) or (0,)


def is_newer(remote, local):
    return _parse_version(remote) > _parse_version(local)


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "RetroRenamer-Updater",
                                               "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def check_latest(timeout=10):
    """Gibt (version, zip_url, beschreibung, html_url) der neuesten Release zurueck."""
    data = json.loads(_get(API_LATEST, timeout))
    return data["tag_name"].lstrip("vV"), data["zipball_url"], data.get("body") or "", data.get("html_url", "")


def is_git_checkout():
    return os.path.isdir(os.path.join(APP_DIR, ".git"))


def install_from_zip(zip_bytes, target_dir=APP_DIR):
    """Entpackt ein GitHub-Zipball (Wurzelordner 'owner-repo-sha/') nach target_dir.
    Erst wird alles in einen Temp-Ordner entpackt und geprueft, dann kopiert.
    Gibt die Liste der aktualisierten Dateien zurueck."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        if not names or "retrorenamer.py" not in {n.split("/", 1)[-1] for n in names}:
            raise RuntimeError("Das heruntergeladene Paket ist kein gueltiges RetroRenamer-Update.")
        with tempfile.TemporaryDirectory(prefix="retrorenamer_update_") as tmp:
            z.extractall(tmp)
            root = os.path.join(tmp, os.listdir(tmp)[0])
            updated = []
            for dirpath, _, files in os.walk(root):
                for f in files:
                    src = os.path.join(dirpath, f)
                    rel = os.path.relpath(src, root).replace("\\", "/")
                    if rel.startswith(PROTECTED) and rel != "dats/README.md":
                        continue
                    dst = os.path.join(target_dir, rel)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copyfile(src, dst)
                    updated.append(rel)
    return updated


def update(local_version, log=print):
    """Komplettes Update fuer die Kommandozeile. Gibt True zurueck, wenn aktualisiert wurde."""
    version, zip_url, notes, _ = check_latest()
    if not is_newer(version, local_version):
        log(f"RetroRenamer ist aktuell (Version {local_version}).")
        return False
    if is_git_checkout():
        log(f"Version {version} ist verfuegbar. Dieser Ordner ist ein Git-Klon - bitte 'git pull' verwenden.")
        return False
    log(f"Lade Version {version} herunter ...")
    files = install_from_zip(_get(zip_url, timeout=60))
    log(f"Aktualisiert auf Version {version} ({len(files)} Dateien). Bitte RetroRenamer neu starten.")
    if notes:
        log("\nNeu in dieser Version:\n" + notes)
    return True
