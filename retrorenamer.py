#!/usr/bin/env python3
"""RetroRenamer: erkennt ROMs anhand ihres Inhalts (CRC32/SHA1-Pruefsummen) und
benennt sie nach No-Intro-/Redump-DAT-Dateien korrekt um.

Der Dateiname wird fuer die Erkennung NICHT verwendet - nur der Inhalt.

Beispiele:
    python retrorenamer.py "D:\\ROMs"                 # nur Vorschau (aendert nichts)
    python retrorenamer.py "D:\\ROMs" --apply         # wirklich umbenennen
    python retrorenamer.py --undo "D:\\ROMs\\retrorenamer_undo_20261003_120000.csv"
    python retrorenamer.py --update               # neueste Version von GitHub installieren
"""

import argparse
import array
import base64
import contextlib
import csv
import difflib
import hashlib
import io
import os
import pickle
import re
import shutil
import subprocess
import sys
import time
import zipfile
import zlib
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from i18n import tr, all_translations, set_language

VERSION = "1.1.0"


def _app_dir():
    """Programmordner - bei der EXE-Version der Ordner, in dem die EXE liegt."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


SCRIPT_DIR = _app_dir()
DEFAULT_DAT_DIR = os.path.join(SCRIPT_DIR, "dats")

# Sonderordner werden in jeder Sprache beim Scannen uebersprungen
SPECIAL_DIRS = {d.lower() for d in all_translations("dir.unknown") | all_translations("dir.duplicates")}

# Dateien mit diesen Endungen sind sicher keine ROMs und werden uebersprungen.
SKIP_EXTS = {
    ".txt", ".nfo", ".diz", ".dat", ".xml", ".csv", ".jpg", ".jpeg", ".png",
    ".gif", ".bmp", ".webp", ".pdf", ".srm", ".sav", ".state", ".sta", ".cfg",
    ".ini", ".log", ".db", ".url", ".lnk", ".exe", ".dll", ".py", ".pyw",
    ".bat", ".pkl", ".json", ".ips", ".bps", ".ups", ".cht",
    ".mp4", ".mkv", ".avi", ".mp3", ".m3u", ".sbi", ".lsd",
}
SKIP_EXTS.update(f".st{i}" for i in range(10))

SEVENZIP_EXTS = {".7z", ".rar"}

BIG_FILE = 64 * 1024 * 1024  # groessere Dateien werden gestreamt (ohne Header-Varianten)
CHUNK = 4 * 1024 * 1024

# Status-Codes (Anzeige ueber tr("status.<CODE>"))
ST_OK = "OK"                 # Name ist bereits korrekt
ST_RENAME = "RENAME"
ST_UNKNOWN = "UNKNOWN"
ST_DUP = "DUPLICATE"
ST_MIXED = "MIXED"           # Archiv/CUE mit Dateien aus mehreren Spielen
ST_ERROR = "ERROR"
STATUSES = (ST_RENAME, ST_OK, ST_UNKNOWN, ST_DUP, ST_MIXED, ST_ERROR)


def status_text(code):
    return tr(f"status.{code}")


def unknown_dirname():
    return tr("dir.unknown")


def dup_dirname():
    return tr("dir.duplicates")


# --------------------------------------------------------------------------
# DAT-Dateien
# --------------------------------------------------------------------------

class RomEntry:
    __slots__ = ("game", "rom_name", "size", "crc", "sha1", "system")

    def __init__(self, game, rom_name, size, crc, sha1, system):
        self.game = game
        self.rom_name = rom_name
        self.size = size
        self.crc = crc
        self.sha1 = sha1
        self.system = system

    def astuple(self):
        return self.game, self.rom_name, self.size, self.crc, self.sha1, self.system


class DatIndex:
    def __init__(self):
        self.entries = []
        self.by_sha1 = {}
        self.by_crc = {}
        self.dat_files = []

    # Fast jede Pruefsumme gehoert zu genau einem Eintrag. Um Speicher zu sparen, wird dann
    # der Eintrag direkt gespeichert und erst bei mehreren Treffern eine Liste angelegt.
    @staticmethod
    def _put(d, key, e):
        cur = d.get(key)
        if cur is None:
            d[key] = e
        elif isinstance(cur, list):
            cur.append(e)
        else:
            d[key] = [cur, e]

    @staticmethod
    def _get(d, key):
        cur = d.get(key)
        if cur is None:
            return []
        return cur if isinstance(cur, list) else [cur]

    def add(self, e):
        self.entries.append(e)
        if e.sha1:
            self._put(self.by_sha1, e.sha1, e)
        if e.crc:
            self._put(self.by_crc, (e.crc, e.size), e)

    def lookup(self, crc, sha1, size):
        found = self._get(self.by_sha1, sha1)
        if found:
            return found
        return [e for e in self._get(self.by_crc, (crc, size)) if not e.sha1]

    def __len__(self):
        return len(self.entries)


def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _parse_xml_dat(stream, source):
    system = ""
    out = []
    for _, el in ET.iterparse(stream, events=("end",)):
        tag = _local(el.tag)
        if tag == "header":
            for child in el:
                if _local(child.tag) == "name" and child.text:
                    system = child.text.strip()
        elif tag in ("game", "machine"):
            game = el.get("name", "")
            for rom in el:
                if _local(rom.tag) != "rom":
                    continue
                crc = (rom.get("crc") or "").lower()
                sha1 = (rom.get("sha1") or "").lower()
                if not crc and not sha1:
                    continue
                try:
                    size = int(rom.get("size") or -1)
                except ValueError:
                    size = -1
                out.append((game, rom.get("name", game), size, crc, sha1))
            el.clear()
    system = sys.intern(system or os.path.splitext(os.path.basename(source))[0])
    return [RomEntry(g, r, s, c, h, system) for g, r, s, c, h in out]


_CMP_GAME = re.compile(r'^\s*(?:game|machine|resource)\s*\(\s*\n(.*?)^\s*\)', re.M | re.S)
_CMP_ROM = re.compile(r'\brom\s*\(\s*((?:"[^"]*"|[^()"])*)\)')
_CMP_NAME = re.compile(r'\bname\s+"([^"]*)"')


def _parse_cmp_dat(text, source):
    """ClrMamePro-Textformat."""
    system = ""
    m = re.search(r'clrmamepro\s*\((.*?)^\s*\)', text, re.M | re.S)
    if m:
        n = _CMP_NAME.search(m.group(1))
        if n:
            system = n.group(1).strip()
    system = sys.intern(system or os.path.splitext(os.path.basename(source))[0])
    out = []
    for gm in _CMP_GAME.finditer(text):
        block = gm.group(1)
        first_rom = block.find("rom (")
        n = _CMP_NAME.search(block[:first_rom] if first_rom >= 0 else block)
        game = n.group(1) if n else ""
        for rm in _CMP_ROM.finditer(block):
            body = rm.group(1)
            name = _CMP_NAME.search(body)
            size = re.search(r'\bsize\s+(\d+)', body)
            crc = re.search(r'\bcrc\s+([0-9a-fA-F]{8})', body)
            sha1 = re.search(r'\bsha1\s+([0-9a-fA-F]{40})', body)
            if not crc and not sha1:
                continue
            out.append(RomEntry(game, name.group(1) if name else game,
                                int(size.group(1)) if size else -1,
                                crc.group(1).lower() if crc else "",
                                sha1.group(1).lower() if sha1 else "", system))
    return out


def _parse_dat_bytes(raw, source):
    head = raw[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    if head.startswith(b"<"):
        return _parse_xml_dat(io.BytesIO(raw), source)
    return _parse_cmp_dat(raw.decode("utf-8", errors="replace"), source)


def _dat_sources(dat_dir):
    files = []
    for dirpath, _, names in os.walk(dat_dir):
        for n in names:
            if os.path.splitext(n)[1].lower() in (".dat", ".xml", ".zip"):
                files.append(os.path.join(dirpath, n))
    return sorted(files)


def has_dat_files(dat_dir):
    return os.path.isdir(dat_dir) and bool(_dat_sources(dat_dir))


def load_dats(dat_dir, log=print):
    """Laedt alle DATs (.dat/.xml, auch in .zip verpackt) aus dat_dir. Mit Cache."""
    if not os.path.isdir(dat_dir):
        raise FileNotFoundError(tr("dat.not_found", path=dat_dir))
    sources = _dat_sources(dat_dir)
    signature = [(os.path.relpath(p, dat_dir), os.path.getmtime(p), os.path.getsize(p)) for p in sources]
    cache_path = os.path.join(dat_dir, ".retrorenamer_cache.pkl")

    index = DatIndex()
    try:
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        if cached.get("version") == VERSION and cached.get("signature") == signature:
            intern = sys.intern
            for g, r, s, c, h, system in cached["entries"]:
                index.add(RomEntry(g, r, s, c, h, intern(system)))
            index.dat_files = cached["dat_files"]
            log(tr("dat.loaded_cache", files=len(index.dat_files), entries=len(index)))
            return index
    except Exception:
        pass

    for path in sources:
        try:
            if path.lower().endswith(".zip"):
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if os.path.splitext(info.filename)[1].lower() in (".dat", ".xml"):
                            for e in _parse_dat_bytes(z.read(info), info.filename):
                                index.add(e)
                            index.dat_files.append(f"{os.path.basename(path)}/{info.filename}")
            else:
                with open(path, "rb") as f:
                    entries = _parse_dat_bytes(f.read(), path)
                for e in entries:
                    index.add(e)
                index.dat_files.append(os.path.relpath(path, dat_dir))
        except Exception as ex:
            log(tr("dat.warn", path=path, error=ex))

    log(tr("dat.loaded", files=len(index.dat_files), entries=len(index)))
    try:
        with open(cache_path, "wb") as f:
            pickle.dump({"version": VERSION, "signature": signature, "dat_files": index.dat_files,
                         "entries": [e.astuple() for e in index.entries]}, f, protocol=pickle.HIGHEST_PROTOCOL)
    except OSError:
        pass
    return index


# --------------------------------------------------------------------------
# Hashing und Header-Varianten
# --------------------------------------------------------------------------

def hash_bytes(b):
    return f"{zlib.crc32(b) & 0xFFFFFFFF:08x}", hashlib.sha1(b).hexdigest(), len(b)


def hash_fileobj(f):
    crc, sha, size = 0, hashlib.sha1(), 0
    while True:
        chunk = f.read(CHUNK)
        if not chunk:
            break
        crc = zlib.crc32(chunk, crc)
        sha.update(chunk)
        size += len(chunk)
    return f"{crc & 0xFFFFFFFF:08x}", sha.hexdigest(), size


def _smd_deinterleave(body):
    out = bytearray(len(body))
    for i in range(0, len(body), 16384):
        blk = body[i:i + 16384]
        out[i:i + 16384:2] = blk[8192:]
        out[i + 1:i + 16384:2] = blk[:8192]
    return bytes(out)


def variants(data, ext):
    """Liefert (Beschreibungs-Schluessel, Daten, Original-Endung-behalten) fuer alle sinnvollen
    Interpretationen der Datei (mit/ohne Header, umgedrehte Byte-Reihenfolge ...)."""
    out = [("", data, False)]
    n = len(data)
    if n > 16 and data[:4] in (b"NES\x1a", b"FDS\x1a"):
        out.append(("how.header16", data[16:], False))
    elif n > 64 and data[:4] == b"LYNX":
        out.append(("how.lynx", data[64:], False))
    elif n > 128 and data[1:10] == b"ATARI7800":
        out.append(("how.a7800", data[128:], False))
    if n > 512 and n % 1024 == 512:
        body = data[512:]
        out.append(("how.copier", body, False))
        if len(body) % 16384 == 0 and (ext == ".smd" or (data[8] == 0xAA and data[9] == 0xBB)):
            out.append(("how.smd", _smd_deinterleave(body), True))
    if n % 4 == 0:
        if data[:4] == b"\x37\x80\x40\x12":      # N64 .v64 (byteswapped)
            a = array.array("H", data); a.byteswap()
            out.append(("how.v64", a.tobytes(), True))
        elif data[:4] == b"\x40\x12\x37\x80":    # N64 .n64 (little endian)
            a = array.array("I", data); a.byteswap()
            out.append(("how.n64", a.tobytes(), True))
    return out


def _clean(b):
    s = b.decode("latin-1", errors="replace")
    return re.sub(r"[^\x20-\x7e]", "", s).strip()


def header_hint(data):
    """Liest - falls vorhanden - den internen Titel aus dem ROM-Header (nur als Hinweis)."""
    try:
        n = len(data)
        if n > 0xC0 and data[0xB2] == 0x96 and data[4:8] == b"\x24\xff\xae\x51":
            return f"GBA-Header: '{_clean(data[0xA0:0xAC])}' Code {_clean(data[0xAC:0xB0])}"
        if n > 0x150 and data[0x104:0x108] == b"\xce\xed\x66\x66":
            kind = "GBC" if data[0x143] in (0x80, 0xC0) else "GB"
            return f"{kind}-Header: '{_clean(data[0x134:0x143])}'"
        if n > 0x40 and data[:4] in (b"\x80\x37\x12\x40", b"\x37\x80\x40\x12", b"\x40\x12\x37\x80"):
            d = variants(data, "")[-1][1] if data[:4] != b"\x80\x37\x12\x40" else data
            return f"N64-Header: '{_clean(d[0x20:0x34])}' Code {_clean(d[0x3B:0x3F])}"
        if n > 0x200 and data[0xC0:0xC4] == b"\x24\xff\xae\x51" and data[0x15C:0x15E] in (b"\x56\xcf", b"\x56\xCF"):
            return f"NDS-Header: '{_clean(data[0:12])}' Code {_clean(data[12:16])}"
        if data[:4] == b"NES\x1a" and n > 16:
            mapper = (data[6] >> 4) | (data[7] & 0xF0)
            return f"NES-ROM (iNES), Mapper {mapper}, {data[4] * 16} KB PRG"
        if data[:4] == b"FDS\x1a":
            return "Famicom Disk System"
        for base in (0, 512):
            if n > base + 0x180 and (data[base + 0x100:base + 0x104] == b"SEGA"
                                     or data[base + 0x101:base + 0x105] == b"SEGA"):
                name = _clean(data[base + 0x150:base + 0x180]) or _clean(data[base + 0x120:base + 0x150])
                return f"Mega-Drive-Header: '{name}'"
        skip = 512 if n % 1024 == 512 else 0
        for off in (0x7FC0, 0xFFC0, 0x40FFC0):
            o = skip + off
            if n >= o + 0x20:
                chk = data[o + 0x1C] | data[o + 0x1D] << 8
                cmp_ = data[o + 0x1E] | data[o + 0x1F] << 8
                if chk ^ cmp_ == 0xFFFF:
                    return f"SNES-Header: '{_clean(data[o:o + 21])}'"
        if n > 0x7FFF and data[0x7FF0:0x7FF8] == b"TMR SEGA":
            return "Sega Master System / Game Gear"
    except Exception:
        pass
    return ""


@dataclass
class Ident:
    """Ergebnis der Pruefsummen-Suche fuer eine einzelne Datei."""
    cands: list
    how: str = ""
    keep_ext: bool = False
    crc: str = ""
    sha1: str = ""
    hint: str = ""


def identify_data(data, ext, index):
    for how, buf, keep_ext in variants(data, ext):
        crc, sha1, size = hash_bytes(buf)
        cands = index.lookup(crc, sha1, size)
        if cands:
            return Ident(cands, how, keep_ext, crc, sha1)
    crc, sha1, _ = hash_bytes(data)
    return Ident([], crc=crc, sha1=sha1, hint=header_hint(data))


def identify_stream(f, index):
    crc, sha1, size = hash_fileobj(f)
    return Ident(index.lookup(crc, sha1, size), crc=crc, sha1=sha1)


def identify_member(size, opener, ext, index):
    """Kleine Dateien werden komplett gelesen (Header-Varianten moeglich), grosse gestreamt."""
    with opener() as f:
        if 0 <= size <= BIG_FILE:
            return identify_data(f.read(), ext, index)
        return identify_stream(f, index)


def resolve_game(idents, current_name):
    """idents: [(name, Ident)] der erkannten Dateien. Sucht das Spiel, zu dem ALLE Dateien gehoeren.
    Gibt (system, game, {name: (RomEntry, Ident)}, anzahl_alternativen) oder None zurueck."""
    sets = [{(e.system, e.game) for e in ident.cands} for _, ident in idents]
    common = set.intersection(*sets) if sets else set()
    if not common:
        return None
    cur = os.path.splitext(os.path.basename(current_name))[0].lower()
    system, game = max(sorted(common), key=lambda sg: difflib.SequenceMatcher(None, cur, sg[1].lower()).ratio())
    chosen = {}
    for name, ident in idents:
        chosen[name] = (next(e for e in ident.cands if e.system == system and e.game == game), ident)
    return system, game, chosen, len(common) - 1


# --------------------------------------------------------------------------
# 7-Zip (optional, ueber 7z.exe) - fuer .7z und .rar
# --------------------------------------------------------------------------

def find_7z():
    for c in (shutil.which("7z"), shutil.which("7za"), shutil.which("7zz"),
              r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"):
        if c and os.path.isfile(c):
            return c
    return None


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def list_7z(exe, path):
    """Gibt [(name, groesse)] aller Dateien im Archiv zurueck."""
    res = subprocess.run([exe, "l", "-slt", path], capture_output=True, stdin=subprocess.DEVNULL,
                         creationflags=_NO_WINDOW)
    if res.returncode != 0:
        raise RuntimeError(tr("err.7z_read"))
    text = res.stdout.decode("utf-8", errors="replace")
    body = text.split("----------", 1)[-1]
    files = []
    for block in re.split(r"\r?\n\r?\n", body):
        p = re.search(r"^Path = (.*?)\r?$", block, re.M)
        if not p:
            continue
        if re.search(r"^Folder = \+", block, re.M) or re.search(r"^Attributes = [^\r\n]*D", block, re.M):
            continue
        s = re.search(r"^Size = (\d+)", block, re.M)
        files.append((p.group(1), int(s.group(1)) if s else -1))
    return files


@contextlib.contextmanager
def open_7z_member(exe, path, name):
    """Streamt eine einzelne Datei aus dem Archiv (ohne sie komplett in den Speicher zu laden)."""
    proc = subprocess.Popen([exe, "x", "-so", "-spd", path, name], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, creationflags=_NO_WINDOW)
    try:
        yield proc.stdout
    finally:
        proc.stdout.close()
        if proc.poll() is None:
            proc.kill()
        proc.wait()


# --------------------------------------------------------------------------
# CUE-Dateien (CD-Images mit mehreren Tracks)
# --------------------------------------------------------------------------

_CUE_FILE = re.compile(r'^(\s*FILE\s+)(?:"([^"]+)"|(\S+))(\s+\S+[ \t]*\r?)$', re.M | re.I)


def cue_references(cue_bytes):
    text = cue_bytes.decode("latin-1")
    return [m.group(2) or m.group(3) for m in _CUE_FILE.finditer(text)]


def rewrite_cue(cue_bytes, mapping):
    """Ersetzt die Dateinamen in den FILE-Zeilen (mapping: alt -> neu)."""
    text = cue_bytes.decode("latin-1")

    def repl(m):
        old = m.group(2) or m.group(3)
        return f'{m.group(1)}"{mapping.get(old, old)}"{m.group(4)}'
    return _CUE_FILE.sub(repl, text).encode("latin-1")


# --------------------------------------------------------------------------
# Scan / Planung
# --------------------------------------------------------------------------

@dataclass
class Options:
    recursive: bool = True
    sort_by_system: bool = False
    move_unknown: bool = False
    move_duplicates: bool = False
    rename_in_zip: bool = True
    max_size_mb: int = 16384
    workers: int = 0           # 0 = automatisch


@dataclass
class PlanItem:
    src: str
    kind: str = "FILE"         # FILE, ZIP, 7Z, RAR, CUE
    status: str = ""
    system: str = ""
    game: str = ""
    want: str = ""
    dst: str = ""
    inner: list = field(default_factory=list)       # [(alter Eintrag, neuer Eintrag)] in ZIPs
    companions: list = field(default_factory=list)  # [[quelle, gewuenschter_name, ziel]] z. B. Tracks einer CUE
    cue_new: bytes = None                           # neuer Inhalt der CUE-Datei
    note: str = ""
    crc: str = ""
    sha1: str = ""

    @property
    def status_text(self):
        return status_text(self.status)

    @property
    def has_changes(self):
        return bool(self.dst or self.inner or self.cue_new or any(c[2] for c in self.companions))


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name):
    name = _INVALID.sub("_", name).rstrip(" .")
    return name or "_"


def _target_filename(entry, ident, orig_ext):
    base = os.path.basename(entry.rom_name.replace("\\", "/"))
    stem, dat_ext = os.path.splitext(base)
    if not dat_ext:
        return safe_name(base + orig_ext)
    if ident.keep_ext:
        return safe_name(stem + orig_ext)
    return safe_name(base)


def _is_own_file(name):
    return name.startswith(("retrorenamer_", "romnamer_")) or ".retrorenamer_tmp" in name or ".romnamer_tmp" in name


def collect_files(root, recursive):
    files = []
    if recursive:
        for dirpath, dirnames, names in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d.lower() not in SPECIAL_DIRS)
            files += [os.path.join(dirpath, n) for n in names]
    else:
        files = [os.path.join(root, n) for n in os.listdir(root) if os.path.isfile(os.path.join(root, n))]
    out = []
    for f in sorted(files):
        name = os.path.basename(f).lower()
        if os.path.splitext(name)[1] in SKIP_EXTS or _is_own_file(name):
            continue
        out.append(f)
    return out


def _add_match_note(it, ident, alternatives, extra=""):
    notes = [extra] if extra else []
    if ident and ident.how:
        notes.append(tr(ident.how))
    if alternatives:
        notes.append(tr("note.alternatives", n=alternatives))
    it.note = "; ".join(notes)


def _identify_single(path, index, opts):
    it = PlanItem(src=path)
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)
    ident = identify_member(size, lambda: open(path, "rb"), ext, index)
    it.crc, it.sha1 = ident.crc, ident.sha1
    res = resolve_game([(path, ident)], path) if ident.cands else None
    if not res:
        it.status, it.note = ST_UNKNOWN, ident.hint or tr("note.no_match")
        return it
    it.system, it.game, chosen, alternatives = res
    entry, _ = chosen[path]
    it.want = _target_filename(entry, ident, os.path.splitext(path)[1])
    _add_match_note(it, ident, alternatives)
    return it


def _identify_archive(path, kind, members, index):
    """members: [(name, groesse, opener)]. Alle erkannten Dateien muessen zum selben Spiel gehoeren."""
    it = PlanItem(src=path, kind=kind)
    idents, hints = [], []
    for name, size, opener in members:
        ext = os.path.splitext(name)[1].lower()
        if ext in SKIP_EXTS:
            continue
        ident = identify_member(size, opener, ext, index)
        if ident.cands:
            idents.append((name, ident))
        else:
            if ident.hint:
                hints.append(ident.hint)
            it.crc, it.sha1 = it.crc or ident.crc, it.sha1 or ident.sha1
    if not idents:
        it.status, it.note = ST_UNKNOWN, (hints[0] if hints else tr("note.no_match"))
        return it
    res = resolve_game(idents, path)
    if not res:
        n = len({frozenset((e.system, e.game) for e in i.cands) for _, i in idents})
        it.status, it.note = ST_MIXED, tr("note.mixed", n=n)
        return it
    it.system, it.game, chosen, alternatives = res
    it.crc, it.sha1 = idents[0][1].crc, idents[0][1].sha1
    it.want = safe_name(it.game) + os.path.splitext(path)[1].lower()
    renames = []
    for name, (entry, ident) in chosen.items():
        new = _target_filename(entry, ident, os.path.splitext(name)[1])
        if new != name:
            renames.append((name, new))
    extra = ""
    if kind == "ZIP":
        it.inner = renames
    elif renames:
        # In 7z/RAR koennen wir nicht schreiben - nur das Archiv selbst wird umbenannt
        extra = tr("note.inner_kept", ext="." + kind.lower())
    _add_match_note(it, idents[0][1], alternatives, extra)
    return it


def _identify_zip(path, index):
    with zipfile.ZipFile(path) as z:
        members = [(i.filename, i.file_size, (lambda i=i: z.open(i))) for i in z.infolist() if not i.is_dir()]
        return _identify_archive(path, "ZIP", members, index)


def _identify_7z(path, index, sevenzip):
    kind = os.path.splitext(path)[1].lower().lstrip(".").upper()
    if not sevenzip:
        return PlanItem(src=path, kind=kind, status=ST_ERROR,
                        note=tr("note.no7z", ext=os.path.splitext(path)[1].lower()))
    members = [(name, size, (lambda name=name: open_7z_member(sevenzip, path, name)))
               for name, size in list_7z(sevenzip, path)]
    return _identify_archive(path, kind, members, index)


def _identify_cue(cue, tracks, index):
    """Erkennt ein CD-Image (CUE + Track-Dateien) als Ganzes."""
    it = PlanItem(src=cue, kind="CUE")
    folder = os.path.dirname(cue)
    it.companions = [[os.path.join(folder, t), "", ""] for t in tracks]
    idents = []
    for t in tracks:
        p = os.path.join(folder, t)
        ident = identify_member(os.path.getsize(p), lambda p=p: open(p, "rb"), os.path.splitext(t)[1].lower(), index)
        if ident.cands:
            idents.append((t, ident))
        it.crc, it.sha1 = it.crc or ident.crc, it.sha1 or ident.sha1
    if not idents:
        it.status, it.note = ST_UNKNOWN, tr("note.no_match")
        return it
    res = resolve_game(idents, cue)
    if not res:
        it.status, it.note = ST_MIXED, tr("note.mixed", n=len(idents))
        return it
    if len(idents) < len(tracks):
        it.status, it.note = ST_UNKNOWN, tr("note.cue_partial", ok=len(idents), total=len(tracks))
        return it
    it.system, it.game, chosen, alternatives = res
    mapping = {}
    for comp, t in zip(it.companions, tracks):
        entry, ident = chosen[t]
        comp[1] = _target_filename(entry, ident, os.path.splitext(t)[1])
        mapping[t] = comp[1]
    with open(cue, "rb") as f:
        old = f.read()
    new = rewrite_cue(old, mapping)
    it.cue_new = new if new != old else None
    it.want = safe_name(it.game) + ".cue"
    _add_match_note(it, None, alternatives, tr("note.cue_tracks", n=len(tracks)))
    return it


def _plan_jobs(files):
    """Fasst CUE-Dateien mit ihren Tracks zu einem Auftrag zusammen."""
    by_path = {os.path.normcase(f): f for f in files}
    grouped = set()
    jobs = []
    for f in files:
        if not f.lower().endswith(".cue"):
            continue
        try:
            with open(f, "rb") as fh:
                refs = cue_references(fh.read(1024 * 1024))
        except OSError:
            continue
        if not refs:
            continue
        if any(os.path.basename(r) != r or "/" in r for r in refs):
            jobs.append(("error", f, tr("note.cue_subdir")))
            grouped.add(os.path.normcase(f))
            continue
        paths = [os.path.normcase(os.path.join(os.path.dirname(f), r)) for r in refs]
        missing = [r for r, p in zip(refs, paths) if p not in by_path]
        grouped.add(os.path.normcase(f))
        if missing:
            jobs.append(("error", f, tr("note.cue_missing", files=", ".join(missing))))
            continue
        grouped.update(paths)
        jobs.append(("cue", f, list(dict.fromkeys(refs))))
    for f in files:
        if os.path.normcase(f) not in grouped:
            jobs.append(("file", f, None))
    jobs.sort(key=lambda j: j[1].lower())
    return jobs


def _run_job(job, index, opts, sevenzip):
    kind, path, extra = job
    try:
        if kind == "error":
            return PlanItem(src=path, kind="CUE", status=ST_ERROR, note=extra)
        if kind == "cue":
            return _identify_cue(path, extra, index)
        if os.path.getsize(path) > opts.max_size_mb * 1024 * 1024:
            return PlanItem(src=path, status=ST_ERROR, note=tr("note.too_big", mb=opts.max_size_mb))
        ext = os.path.splitext(path)[1].lower()
        if ext == ".zip" and zipfile.is_zipfile(path):
            return _identify_zip(path, index)
        if ext in SEVENZIP_EXTS:
            return _identify_7z(path, index, sevenzip)
        return _identify_single(path, index, opts)
    except Exception as ex:
        return PlanItem(src=path, status=ST_ERROR, note=str(ex))


def default_workers():
    return max(1, min(4, os.cpu_count() or 2))


def _unique(path, reserved):
    stem, ext = os.path.splitext(path)
    cand, i = path, 2
    while os.path.exists(cand) or os.path.normcase(cand) in reserved:
        cand = f"{stem} ({i}){ext}"
        i += 1
    reserved.add(os.path.normcase(cand))
    return cand


def _same_file(a, b):
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def scan(root, index, opts, progress=None, log=print):
    """Erkennt alle Dateien und erstellt einen Plan (aendert nichts auf der Platte)."""
    root = os.path.abspath(root)
    jobs = _plan_jobs(collect_files(root, opts.recursive))
    sevenzip = find_7z()
    items = [None] * len(jobs)
    with ThreadPoolExecutor(max_workers=opts.workers or default_workers()) as pool:
        futures = {pool.submit(_run_job, job, index, opts, sevenzip): i for i, job in enumerate(jobs)}
        for done, fut in enumerate(as_completed(futures), 1):
            i = futures[fut]
            items[i] = fut.result()
            if progress:
                progress(done, len(jobs), os.path.basename(jobs[i][1]))
    if progress:
        progress(len(jobs), len(jobs), "")
    for it in items:
        if not opts.rename_in_zip:
            it.inner = []

    # Zielpfade festlegen
    for it in items:
        if it.want:
            folder = os.path.join(root, safe_name(it.system)) if opts.sort_by_system else os.path.dirname(it.src)
            it.want = os.path.join(folder, it.want)
            for comp in it.companions:
                comp[1] = os.path.join(folder, comp[1]) if comp[1] else ""

    sources = {os.path.normcase(it.src) for it in items}
    for it in items:
        sources.update(os.path.normcase(c[0]) for c in it.companions)
    taken = {}
    reserved = set()
    identified = [it for it in items if it.want]
    # Dateien, die bereits richtig heissen, haben Vorrang (sie bleiben das "Original")
    identified.sort(key=lambda it: (os.path.normcase(it.want) != os.path.normcase(it.src), it.src))
    dup_dir = os.path.join(root, dup_dirname())
    for it in identified:
        targets = [(it.want, it.src)] + [(c[1], c[0]) for c in it.companions]
        clash = None
        for want, src in targets:
            key = os.path.normcase(want)
            if key in taken:
                clash = taken[key].src
            elif os.path.exists(want) and key not in sources and not _same_file(want, src):
                clash = want
            if clash:
                break
        if clash:
            it.status = ST_DUP
            it.note = tr("note.dup_of", path=os.path.relpath(clash, root))
            it.inner, it.cue_new = [], None
            if opts.move_duplicates:
                it.dst = _unique(os.path.join(dup_dir, os.path.basename(it.src)), reserved)
                for c in it.companions:
                    c[2] = _unique(os.path.join(dup_dir, os.path.basename(c[0])), reserved)
            continue
        for want, _ in targets:
            taken[os.path.normcase(want)] = it
        for c in it.companions:
            c[2] = c[1] if c[1] != c[0] else ""
        it.dst = it.want if it.want != it.src else ""
        it.status = ST_RENAME if it.has_changes else ST_OK

    if opts.move_unknown:
        unk_dir = os.path.join(root, unknown_dirname())
        for it in items:
            if it.status == ST_UNKNOWN:
                it.dst = _unique(os.path.join(unk_dir, os.path.basename(it.src)), reserved)
                for c in it.companions:
                    c[2] = _unique(os.path.join(unk_dir, os.path.basename(c[0])), reserved)
    return items


# --------------------------------------------------------------------------
# Ausfuehren / Rueckgaengig
# --------------------------------------------------------------------------

def zip_rename_entries(path, mapping):
    """Benennt Eintraege um. Daten werden unveraendert (ohne neu zu komprimieren) kopiert."""
    tmp = path + ".retrorenamer_tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", allowZip64=True) as zout:
        for info in zin.infolist():
            ni = zipfile.ZipInfo(mapping.get(info.filename, info.filename), info.date_time)
            ni.external_attr = info.external_attr
            ni.compress_type = zipfile.ZIP_DEFLATED
            with zin.open(info) as src, zout.open(ni, "w", force_zip64=info.file_size > 0x7FFFFFFF) as dst:
                shutil.copyfileobj(src, dst, CHUNK)
    os.replace(tmp, path)


def apply_plan(items, root, progress=None, log=print):
    """Fuehrt den Plan aus. Jede Aenderung wird sofort in eine Undo-Datei geschrieben."""
    todo = [it for it in items if it.has_changes]
    if not todo:
        log(tr("apply.nothing"))
        return None, 0
    undo_path = os.path.join(root, f"retrorenamer_undo_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    errors = 0
    failed = set()
    with open(undo_path, "w", newline="", encoding="utf-8") as uf:
        w = csv.writer(uf, delimiter=";")
        w.writerow(["action", "a", "b", "c"])

        def fail(it, ex, key="note.error"):
            nonlocal errors
            errors += 1
            failed.add(id(it))
            it.note = tr(key, error=ex)
            log(tr("apply.error", path=it.src, error=ex))

        # 1) Inhalte anpassen: Dateinamen in ZIPs, Dateinamen in CUE-Dateien
        for it in todo:
            if it.inner:
                try:
                    zip_rename_entries(it.src, dict(it.inner))
                    for old, new in it.inner:
                        w.writerow(["zip", it.src, old, new])
                    uf.flush()
                except Exception as ex:
                    fail(it, ex, "note.zip_error")
            if it.cue_new is not None:
                try:
                    with open(it.src, "rb") as f:
                        old = f.read()
                    w.writerow(["write", it.src, base64.b64encode(old).decode("ascii"), ""])
                    uf.flush()
                    with open(it.src, "wb") as f:
                        f.write(it.cue_new)
                except Exception as ex:
                    fail(it, ex)

        # 2) Zwei Phasen: erst auf temporaere Namen, dann auf Zielnamen
        #    (so funktionieren auch Ringtausch und reine Gross-/Kleinschreibungs-Aenderungen)
        moves = []
        for it in todo:
            if id(it) in failed:
                continue
            if it.dst and it.dst != it.src:
                moves.append((it, it.src, it.dst))
            moves += [(it, c[0], c[2]) for c in it.companions if c[2] and c[2] != c[0]]
        staged = []
        for i, (it, src, dst) in enumerate(moves):
            tmp = f"{src}.retrorenamer_tmp{i}"
            try:
                os.rename(src, tmp)
                w.writerow(["move", src, tmp, ""])
                uf.flush()
                staged.append((it, tmp, dst))
            except Exception as ex:
                fail(it, ex)
        done = set()
        for i, (it, tmp, dst) in enumerate(staged):
            if progress:
                progress(i, len(staged), os.path.basename(dst))
            try:
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                if os.path.exists(dst):
                    new_dst = _unique(dst, set())
                    it.note = (it.note + "; " if it.note else "") + tr("note.target_exists")
                    if dst == it.dst:
                        it.dst = new_dst
                    dst = new_dst
                os.rename(tmp, dst)
                w.writerow(["move", tmp, dst, ""])
                uf.flush()
                done.add(id(it))
            except Exception as ex:
                fail(it, ex)
        done.update(id(it) for it in todo if (it.inner or it.cue_new is not None) and id(it) not in failed)
    if progress:
        progress(1, 1, "")
    log(tr("apply.done", done=len(done), errors=errors, path=undo_path))
    return undo_path, errors


def undo(undo_path, log=print):
    with open(undo_path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter=";"))[1:]
    errors = 0
    for action, a, b, c in reversed(rows):
        try:
            if action == "move":
                os.makedirs(os.path.dirname(a), exist_ok=True)
                os.rename(b, a)
            elif action == "zip":
                zip_rename_entries(a, {c: b})
            elif action == "write":
                with open(a, "wb") as f:
                    f.write(base64.b64decode(b))
        except Exception as ex:
            errors += 1
            log(tr("undo.error", path=b if action == "move" else a, error=ex))
    # leere Ordner, die beim Sortieren entstanden sind, wieder entfernen
    for action, a, b, c in rows:
        if action == "move":
            d = os.path.dirname(b)
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass
    log(tr("undo.done", steps=len(rows) - errors, errors=errors))
    if not errors:
        os.rename(undo_path, undo_path[:-4] + tr("undo.suffix") + ".csv")
    return errors


def write_report(items, path, root):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow([tr("col.status"), tr("col.file"), tr("col.new"), tr("col.system"), tr("col.game"),
                    "CRC32", "SHA1", tr("col.note")])
        for it in items:
            w.writerow([it.status_text, os.path.relpath(it.src, root),
                        os.path.relpath(it.dst, root) if it.dst else "",
                        it.system, it.game, it.crc, it.sha1, it.note])


def summarize(items):
    counts = {}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1
    return counts


def summary_text(items):
    counts = summarize(items)
    return "  ".join(f"{status_text(s)}: {counts[s]}" for s in STATUSES if s in counts)


# --------------------------------------------------------------------------
# Kommandozeile
# --------------------------------------------------------------------------

def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    argv = sys.argv[1:] if argv is None else argv
    # Sprache zuerst festlegen, damit schon die Hilfe uebersetzt ist
    for i, arg in enumerate(argv):
        if arg == "--lang" and i + 1 < len(argv):
            set_language(argv[i + 1])
        elif arg.startswith("--lang="):
            set_language(arg.split("=", 1)[1])

    p = argparse.ArgumentParser(description=tr("cli.description"))
    p.add_argument("folder", nargs="?", help=tr("cli.folder"))
    p.add_argument("--dats", default=DEFAULT_DAT_DIR, help=tr("cli.dats"))
    p.add_argument("--apply", action="store_true", help=tr("cli.apply"))
    p.add_argument("--no-recursive", action="store_true", help=tr("cli.no_recursive"))
    p.add_argument("--sort", action="store_true", help=tr("cli.sort"))
    p.add_argument("--move-unknown", action="store_true", help=tr("cli.move_unknown", dir=unknown_dirname()))
    p.add_argument("--move-duplicates", action="store_true", help=tr("cli.move_dups", dir=dup_dirname()))
    p.add_argument("--no-zip-inner", action="store_true", help=tr("cli.no_zip_inner"))
    p.add_argument("--report", help=tr("cli.report"))
    p.add_argument("--workers", type=int, default=0, help=tr("cli.workers"))
    p.add_argument("--undo", metavar="UNDO_CSV", help=tr("cli.undo"))
    p.add_argument("--update", action="store_true", help=tr("cli.update"))
    p.add_argument("--lang", choices=["de", "en"], help=tr("cli.lang"))
    p.add_argument("--version", action="version", version=f"RetroRenamer {VERSION}")
    a = p.parse_args(argv)

    if a.update:
        import updater
        try:
            updater.update(VERSION)
        except Exception as ex:
            print(tr("cli.update_failed", error=ex))
            return 1
        return 0
    if a.undo:
        return 1 if undo(a.undo) else 0
    if not a.folder:
        p.error(tr("cli.need_folder"))
    root = os.path.abspath(a.folder)
    index = load_dats(a.dats)
    if not len(index):
        print(tr("dat.none", path=a.dats))
        return 2
    opts = Options(recursive=not a.no_recursive, sort_by_system=a.sort, move_unknown=a.move_unknown,
                   move_duplicates=a.move_duplicates, rename_in_zip=not a.no_zip_inner, workers=a.workers)

    def progress(i, n, name):
        print(f"\r[{i}/{n}] {name[:60]:<60}", end="", flush=True)
    items = scan(root, index, opts, progress)
    print("\r" + " " * 80 + "\r", end="")

    pad = " " * 11
    for it in items:
        line = f"{it.status_text:<10} {os.path.relpath(it.src, root)}"
        if it.dst:
            line += f"\n{pad}-> {os.path.relpath(it.dst, root)}"
        for old, new in it.inner:
            line += f"\n{pad}   {tr('cli.in_zip')}: {old} -> {new}"
        for src, _, dst in it.companions:
            if dst:
                line += f"\n{pad}   {tr('cli.track')}: {os.path.basename(src)} -> {os.path.relpath(dst, root)}"
        if it.note and it.status != ST_OK:
            line += f"\n{pad}   ({it.note})"
        print(line)
    print()
    print(f"{tr('cli.summary')}: {summary_text(items)}")
    if a.report:
        write_report(items, a.report, root)
        print(tr("cli.report_saved", path=a.report))
    if a.apply:
        apply_plan(items, root)
    elif any(it.has_changes for it in items):
        print("\n" + tr("cli.preview_only"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
