"""Laedt Redump-DAT-Dateien (CD/DVD-Systeme) herunter.

Redump bietet fuer jedes System einen festen Download-Link (http://redump.org/datfile/<kuerzel>/)
und erlaubt laut robots.txt automatische Zugriffe. Trotzdem wird hier rücksichtsvoll geladen:
nur auf ausdruecklichen Wunsch des Nutzers und mit Pausen zwischen den Downloads.

No-Intro-DATs werden bewusst NICHT automatisch geladen: Deren Download ist als manueller
Vorgang gestaltet (Formular mit wechselndem Knopf), daher oeffnet RetroRenamer dort nur die Webseite.
"""

import html
import io
import os
import re
import time
import urllib.request
import zipfile

from i18n import tr

REDUMP_BASE = "http://redump.org"
DOWNLOADS_PAGE = f"{REDUMP_BASE}/downloads/"
PAUSE_SECONDS = 5

# Ausweichliste, falls die Download-Seite nicht gelesen werden kann
FALLBACK_SYSTEMS = [
    ("psx", "Sony PlayStation"), ("ps2", "Sony PlayStation 2"), ("ps3", "Sony PlayStation 3"),
    ("psp", "Sony PlayStation Portable"), ("ss", "Sega Saturn"), ("dc", "Sega Dreamcast"),
    ("mcd", "Sega Mega CD & Sega CD"), ("gc", "Nintendo GameCube"), ("wii", "Nintendo Wii"),
    ("pce", "NEC PC Engine CD & TurboGrafx CD"), ("ngcd", "Neo Geo CD"), ("3do", "Panasonic 3DO Interactive Multiplayer"),
    ("xbox", "Microsoft Xbox"), ("xbox360", "Microsoft Xbox 360"), ("cdi", "Philips CD-i"),
    ("pc", "IBM PC compatible"), ("mac", "Apple Macintosh"), ("cd32", "Commodore Amiga CD32"),
]

_ROW = re.compile(r'<tr><td>([^<]+)</td>(?:(?!</tr>).)*?<a href="/datfile/([^/"]+)/">Datfile</a>', re.S)
_FILENAME = re.compile(r'filename="?([^";]+)"?', re.I)


def _user_agent():
    try:
        from retrorenamer import VERSION
    except Exception:
        VERSION = "?"
    return f"RetroRenamer/{VERSION} (+https://github.com/phillhf/RetroRenamer)"


def _get(url, timeout=60):
    """Gibt (inhalt, headers) zurueck."""
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent()})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers


def parse_systems(page_html):
    """Liest [(kuerzel, name)] aus der Redump-Download-Seite."""
    seen, out = set(), []
    for name, code in _ROW.findall(page_html):
        if code not in seen:
            seen.add(code)
            out.append((code, html.unescape(name).strip()))
    return out


def list_systems():
    """Aktuelle Systemliste von redump.org, bei Problemen die eingebaute Ausweichliste."""
    try:
        page, _ = _get(DOWNLOADS_PAGE, timeout=20)
        systems = parse_systems(page.decode("utf-8", errors="replace"))
        if systems:
            return systems, True
    except Exception:
        pass
    return list(FALLBACK_SYSTEMS), False


def _safe(name):
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).strip(" .") or "redump.zip"


def _prefix(filename):
    """'Sony - PlayStation - Datfile (10914) (2026-06-15 11-55-46).zip' -> 'Sony - PlayStation - Datfile ('"""
    i = filename.find(" - Datfile (")
    return filename[:i + len(" - Datfile (")] if i > 0 else None


def download_system(code, dat_dir):
    """Laedt die DAT eines Systems und ersetzt aeltere Versionen derselben DAT.
    Gibt (dateiname, war_schon_aktuell) zurueck."""
    data, headers = _get(f"{REDUMP_BASE}/datfile/{code}/")
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise RuntimeError(tr("redump.not_zip", code=code))
    m = _FILENAME.search(headers.get("Content-Disposition", "") or "")
    filename = _safe(m.group(1)) if m else f"redump_{code}.zip"
    os.makedirs(dat_dir, exist_ok=True)
    target = os.path.join(dat_dir, filename)
    if os.path.exists(target) and os.path.getsize(target) == len(data):
        return filename, True
    tmp = target + ".part"
    with open(tmp, "wb") as f:
        f.write(data)
    os.replace(tmp, target)
    prefix = _prefix(filename)
    if prefix:
        for other in os.listdir(dat_dir):
            if other != filename and other.startswith(prefix) and other.lower().endswith(".zip"):
                try:
                    os.remove(os.path.join(dat_dir, other))
                except OSError:
                    pass
    return filename, False


def download_systems(codes, dat_dir, progress=None, pause=PAUSE_SECONDS):
    """Laedt mehrere Systeme nacheinander mit Pause. Gibt [(kuerzel, dateiname|None, fehler|None, aktuell)] zurueck."""
    results = []
    for i, code in enumerate(codes):
        if progress:
            progress(i, len(codes), code)
        if i:
            time.sleep(pause)
        try:
            name, current = download_system(code, dat_dir)
            results.append((code, name, None, current))
        except Exception as ex:
            results.append((code, None, str(ex), False))
    if progress:
        progress(len(codes), len(codes), "")
    return results
