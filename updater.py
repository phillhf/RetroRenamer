"""Update-Funktion: holt die neueste Release von GitHub.

- Python-Version: ersetzt die Programmdateien aus dem Quellcode-Paket der Release.
- EXE-Version: laedt RetroRenamer.exe aus der Release und tauscht die laufende EXE aus.

DAT-Dateien, Einstellungen und alles ausserhalb des Programmordners bleiben unberuehrt.
"""

import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from i18n import tr

REPO = "phillhf/RetroRenamer"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
EXE_ASSET = "RetroRenamer.exe"
SETUP_PREFIX = "RetroRenamer-Setup-"
FROZEN = getattr(sys, "frozen", False)
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))

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


def parse_release(data):
    """Infos zur Release: version, zip_url, exe_url, setup_url (oder None), notes, page."""
    assets = data.get("assets", [])
    exe_url = next((a["browser_download_url"] for a in assets if a.get("name") == EXE_ASSET), None)
    setup_url = next((a["browser_download_url"] for a in assets
                      if a.get("name", "").startswith(SETUP_PREFIX) and a["name"].lower().endswith(".exe")), None)
    return {"version": data["tag_name"].lstrip("vV"), "zip_url": data["zipball_url"], "exe_url": exe_url,
            "setup_url": setup_url, "notes": data.get("body") or "", "page": data.get("html_url", "")}


def check_latest(timeout=10):
    return parse_release(json.loads(_get(API_LATEST, timeout)))


def is_git_checkout():
    return not FROZEN and os.path.isdir(os.path.join(APP_DIR, ".git"))


def installed_by_setup(app_dir=APP_DIR):
    """Wurde RetroRenamer ueber den Installer eingerichtet? (Inno Setup legt unins000.exe ab)"""
    try:
        return any(n.lower().startswith("unins") and n.lower().endswith(".exe") for n in os.listdir(app_dir))
    except OSError:
        return False


def update_method(info, frozen=FROZEN, app_dir=APP_DIR):
    """'setup', 'exe', 'zip' oder None (dann gibt es noch keine passende Datei in der Release)."""
    if not frozen:
        return "zip"
    if installed_by_setup(app_dir):
        # Installer bevorzugen (haelt Versionsnummer und Deinstallationseintrag aktuell)
        return "setup" if info["setup_url"] else ("exe" if info["exe_url"] else None)
    return "exe" if info["exe_url"] else None


def update_possible(info):
    """None wenn installierbar, sonst ein Hinweistext, warum nicht."""
    if is_git_checkout():
        return tr("upd.git", v=info["version"])
    if update_method(info) is None:
        return tr("upd.no_asset", v=info["version"])
    return None


def install_from_zip(zip_bytes, target_dir=APP_DIR):
    """Entpackt ein GitHub-Zipball (Wurzelordner 'owner-repo-sha/') nach target_dir.
    Erst wird alles in einen Temp-Ordner entpackt und geprueft, dann kopiert.
    Gibt die Liste der aktualisierten Dateien zurueck."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as z:
        names = [n for n in z.namelist() if not n.endswith("/")]
        if not names or "retrorenamer.py" not in {n.split("/", 1)[-1] for n in names}:
            raise RuntimeError(tr("upd.invalid"))
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


def replace_executable(new_exe, exe_path):
    """Tauscht eine (evtl. gerade laufende) EXE aus. Windows erlaubt das Umbenennen einer
    laufenden EXE, aber nicht das Ueberschreiben - daher: alt -> .old, neu -> Originalname."""
    if len(new_exe) < 100_000 or new_exe[:2] != b"MZ":
        raise RuntimeError(tr("upd.invalid"))
    new_path, old_path = exe_path + ".new", exe_path + ".old"
    with open(new_path, "wb") as f:
        f.write(new_exe)
    if os.path.exists(old_path):
        try:
            os.remove(old_path)
        except OSError:
            old_path = f"{exe_path}.{os.getpid()}.old"
    os.rename(exe_path, old_path)
    try:
        os.rename(new_path, exe_path)
    except Exception:
        os.rename(old_path, exe_path)  # Ausgangszustand wiederherstellen
        raise
    return [os.path.basename(exe_path)]


def cleanup_old_executables(exe_path=None):
    """Raeumt nach einem EXE-Update die alte Version weg (beim naechsten Start aufgerufen)."""
    exe_path = exe_path or (sys.executable if FROZEN else None)
    if not exe_path:
        return
    folder, base = os.path.split(exe_path)
    for name in os.listdir(folder):
        if name.startswith(base + ".") and name.endswith(".old"):
            try:
                os.remove(os.path.join(folder, name))
            except OSError:
                pass


def run_setup(setup_bytes):
    """Startet den heruntergeladenen Installer still. Er beendet RetroRenamer, aktualisiert es
    und startet es danach wieder (/RESTARTAPP=1)."""
    if len(setup_bytes) < 100_000 or setup_bytes[:2] != b"MZ":
        raise RuntimeError(tr("upd.invalid"))
    path = os.path.join(tempfile.gettempdir(), f"RetroRenamer-Setup-update-{os.getpid()}.exe")
    with open(path, "wb") as f:
        f.write(setup_bytes)
    subprocess.Popen([path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RESTARTAPP=1"],
                     close_fds=True, creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    return path


def install(info):
    """Installiert die Release aus check_latest().
    Gibt 'setup' zurueck, wenn ein Installer gestartet wurde (das Programm muss sich dann beenden),
    sonst die Liste der ersetzten Dateien."""
    method = update_method(info)
    if method == "setup":
        run_setup(_get(info["setup_url"], timeout=180))
        return "setup"
    if method == "exe":
        return replace_executable(_get(info["exe_url"], timeout=120), sys.executable)
    return install_from_zip(_get(info["zip_url"], timeout=60))


def update(local_version, log=print):
    """Komplettes Update fuer die Kommandozeile. Gibt True zurueck, wenn aktualisiert wurde."""
    info = check_latest()
    if not is_newer(info["version"], local_version):
        log(tr("upd.current", v=local_version))
        return False
    reason = update_possible(info)
    if reason:
        log(reason)
        return False
    log(tr("upd.downloading", v=info["version"]))
    files = install(info)
    log(tr("upd.done", v=info["version"], n=len(files)))
    if info["notes"]:
        log("\n" + tr("upd.notes") + "\n" + info["notes"])
    return True
