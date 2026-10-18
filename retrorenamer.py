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
from dataclasses import dataclass, field

VERSION = "1.0.0"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DAT_DIR = os.path.join(SCRIPT_DIR, "dats")

UNKNOWN_DIRNAME = "_Unbekannt"
DUP_DIRNAME = "_Duplikate"
SPECIAL_DIRS = {UNKNOWN_DIRNAME.lower(), DUP_DIRNAME.lower()}

# Dateien mit diesen Endungen sind sicher keine ROMs und werden uebersprungen.
SKIP_EXTS = {
    ".txt", ".nfo", ".diz", ".dat", ".xml", ".csv", ".jpg", ".jpeg", ".png",
    ".gif", ".bmp", ".webp", ".pdf", ".srm", ".sav", ".state", ".sta", ".cfg",
    ".ini", ".log", ".db", ".url", ".lnk", ".exe", ".dll", ".py", ".pyw",
    ".bat", ".pkl", ".json", ".rar", ".ips", ".bps", ".ups", ".cht",
    ".mp4", ".mkv", ".avi", ".mp3",
}
SKIP_EXTS.update(f".st{i}" for i in range(10))

BIG_FILE = 64 * 1024 * 1024  # groessere Dateien werden nur gestreamt (ohne Header-Varianten)

# Status-Werte
ST_OK = "OK"                 # Name ist bereits korrekt
ST_RENAME = "UMBENENNEN"
ST_UNKNOWN = "UNBEKANNT"
ST_DUP = "DUPLIKAT"
ST_MIXED = "GEMISCHT"        # Archiv mit mehreren verschiedenen Spielen
ST_ERROR = "FEHLER"


# --------------------------------------------------------------------------
# DAT-Dateien
# --------------------------------------------------------------------------

@dataclass
class RomEntry:
    game: str
    rom_name: str
    size: int
    crc: str
    sha1: str
    system: str


class DatIndex:
    def __init__(self):
        self.entries = []
        self.by_sha1 = {}
        self.by_crc = {}
        self.dat_files = []

    def add(self, e):
        self.entries.append(e)
        if e.sha1:
            self.by_sha1.setdefault(e.sha1, []).append(e)
        if e.crc:
            self.by_crc.setdefault((e.crc, e.size), []).append(e)

    def lookup(self, crc, sha1, size):
        if sha1 in self.by_sha1:
            return self.by_sha1[sha1]
        return [e for e in self.by_crc.get((crc, size), []) if not e.sha1]

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
    system = system or os.path.splitext(os.path.basename(source))[0]
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
    system = system or os.path.splitext(os.path.basename(source))[0]
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


def load_dats(dat_dir, log=print):
    """Laedt alle DATs (.dat/.xml, auch in .zip verpackt) aus dat_dir. Mit Cache."""
    if not os.path.isdir(dat_dir):
        raise FileNotFoundError(f"DAT-Ordner nicht gefunden: {dat_dir}")
    sources = _dat_sources(dat_dir)
    signature = [(os.path.relpath(p, dat_dir), os.path.getmtime(p), os.path.getsize(p)) for p in sources]
    cache_path = os.path.join(dat_dir, ".retrorenamer_cache.pkl")

    index = DatIndex()
    try:
        with open(cache_path, "rb") as f:
            cached = pickle.load(f)
        if cached.get("version") == VERSION and cached.get("signature") == signature:
            for t in cached["entries"]:
                index.add(RomEntry(*t))
            index.dat_files = cached["dat_files"]
            log(f"{len(index.dat_files)} DAT-Dateien aus Cache geladen ({len(index)} ROM-Eintraege).")
            return index
    except Exception:
        pass

    for path in sources:
        try:
            if path.lower().endswith(".zip"):
                with zipfile.ZipFile(path) as z:
                    for info in z.infolist():
                        if os.path.splitext(info.filename)[1].lower() in (".dat", ".xml"):
                            entries = _parse_dat_bytes(z.read(info), info.filename)
                            for e in entries:
                                index.add(e)
                            index.dat_files.append(f"{os.path.basename(path)}/{info.filename}")
            else:
                with open(path, "rb") as f:
                    entries = _parse_dat_bytes(f.read(), path)
                for e in entries:
                    index.add(e)
                index.dat_files.append(os.path.relpath(path, dat_dir))
        except Exception as ex:
            log(f"WARNUNG: DAT '{path}' konnte nicht gelesen werden: {ex}")

    log(f"{len(index.dat_files)} DAT-Dateien geladen ({len(index)} ROM-Eintraege).")
    try:
        with open(cache_path, "wb") as f:
            pickle.dump({"version": VERSION, "signature": signature, "dat_files": index.dat_files,
                         "entries": [(e.game, e.rom_name, e.size, e.crc, e.sha1, e.system)
                                     for e in index.entries]}, f, protocol=pickle.HIGHEST_PROTOCOL)
    except OSError:
        pass
    return index


# --------------------------------------------------------------------------
# Hashing und Header-Varianten
# --------------------------------------------------------------------------

def hash_bytes(b):
    return f"{zlib.crc32(b) & 0xFFFFFFFF:08x}", hashlib.sha1(b).hexdigest(), len(b)


def hash_stream(path):
    crc, sha = 0, hashlib.sha1()
    size = 0
    with open(path, "rb") as f:
        while chunk := f.read(4 * 1024 * 1024):
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
    """Liefert (Beschreibung, Daten, Original-Endung-behalten) fuer alle sinnvollen
    Interpretationen der Datei (mit/ohne Header, umgedrehte Byte-Reihenfolge ...)."""
    out = [("", data, False)]
    n = len(data)
    if n > 16 and data[:4] in (b"NES\x1a", b"FDS\x1a"):
        out.append(("16-Byte-Header ignoriert", data[16:], False))
    elif n > 64 and data[:4] == b"LYNX":
        out.append(("Lynx-Header ignoriert", data[64:], False))
    elif n > 128 and data[1:10] == b"ATARI7800":
        out.append(("A7800-Header ignoriert", data[128:], False))
    if n > 512 and n % 1024 == 512:
        body = data[512:]
        out.append(("512-Byte-Kopierer-Header ignoriert", body, False))
        if len(body) % 16384 == 0 and (ext == ".smd" or (data[8] == 0xAA and data[9] == 0xBB)):
            out.append(("SMD-Format (interleaved)", _smd_deinterleave(body), True))
    if n % 4 == 0:
        if data[:4] == b"\x37\x80\x40\x12":      # N64 .v64 (byteswapped)
            a = array.array("H", data); a.byteswap()
            out.append(("N64 byteswapped (.v64)", a.tobytes(), True))
        elif data[:4] == b"\x40\x12\x37\x80":    # N64 .n64 (little endian)
            a = array.array("I", data); a.byteswap()
            out.append(("N64 little endian (.n64)", a.tobytes(), True))
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
        if data[:4] == b"NES\x1a" and n > 16:
            mapper = (data[6] >> 4) | (data[7] & 0xF0)
            return f"NES-ROM (iNES), Mapper {mapper}, {data[4] * 16} KB PRG"
        if data[:4] == b"FDS\x1a":
            return "Famicom-Disk-System-Image"
        for base in (0, 512):
            if n > base + 0x180 and data[base + 0x100:base + 0x104] == b"SEGA" or \
                    n > base + 0x180 and data[base + 0x101:base + 0x105] == b"SEGA":
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
            return "Sega-Master-System/Game-Gear-ROM"
    except Exception:
        pass
    return ""


@dataclass
class Match:
    entry: RomEntry
    how: str
    keep_ext: bool
    alternatives: int


def _best(cands, current_name):
    cur = os.path.splitext(os.path.basename(current_name))[0].lower()

    def score(e):
        return difflib.SequenceMatcher(None, cur, e.game.lower()).ratio()
    return max(cands, key=score)


def identify_bytes(data, ext, index, current_name):
    for how, buf, keep_ext in variants(data, ext):
        crc, sha1, size = hash_bytes(buf)
        cands = index.lookup(crc, sha1, size)
        if cands:
            return Match(_best(cands, current_name), how, keep_ext, len({c.game for c in cands}) - 1), crc, sha1
    crc, sha1, _ = hash_bytes(data)
    return None, crc, sha1


# --------------------------------------------------------------------------
# 7-Zip (optional, ueber 7z.exe)
# --------------------------------------------------------------------------

def find_7z():
    for c in (shutil.which("7z"), shutil.which("7za"),
              r"C:\Program Files\7-Zip\7z.exe", r"C:\Program Files (x86)\7-Zip\7z.exe"):
        if c and os.path.isfile(c):
            return c
    return None


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def read_7z(exe, path):
    """Gibt [(name, bytes)] zurueck. Nur Archive mit genau einer Datei werden gelesen."""
    res = subprocess.run([exe, "l", "-slt", path], capture_output=True, creationflags=_NO_WINDOW)
    if res.returncode != 0:
        raise RuntimeError("7z konnte das Archiv nicht lesen")
    text = res.stdout.decode("utf-8", errors="replace")
    body = text.split("----------", 1)[-1]
    files = []
    for block in re.split(r"\r?\n\r?\n", body):
        p = re.search(r"^Path = (.*)$", block, re.M)
        is_dir = re.search(r"^Folder = \+", block, re.M) or re.search(r"^Attributes = D", block, re.M)
        if p and not is_dir:
            files.append(p.group(1).strip())
    if len(files) != 1:
        return [(f, None) for f in files]
    res = subprocess.run([exe, "x", "-so", path], capture_output=True, creationflags=_NO_WINDOW)
    if res.returncode != 0:
        raise RuntimeError("7z konnte das Archiv nicht entpacken")
    return [(files[0], res.stdout)]


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
    max_size_mb: int = 2048


@dataclass
class PlanItem:
    src: str
    kind: str = "Datei"
    status: str = ""
    system: str = ""
    game: str = ""
    want: str = ""
    dst: str = ""
    inner: list = field(default_factory=list)  # [(alter Eintrag, neuer Eintrag)] in ZIPs
    note: str = ""
    crc: str = ""
    sha1: str = ""


_INVALID = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def safe_name(name):
    name = _INVALID.sub("_", name).rstrip(" .")
    return name or "_"


def _target_filename(match, orig_ext):
    base = os.path.basename(match.entry.rom_name.replace("\\", "/"))
    stem, dat_ext = os.path.splitext(base)
    if not dat_ext or match.keep_ext:
        return safe_name(stem + orig_ext) if dat_ext else safe_name(base + orig_ext)
    return safe_name(base)


def collect_files(root, recursive):
    files = []
    if recursive:
        for dirpath, dirnames, names in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in SPECIAL_DIRS]
            files += [os.path.join(dirpath, n) for n in names]
    else:
        files = [os.path.join(root, n) for n in os.listdir(root) if os.path.isfile(os.path.join(root, n))]
    out = []
    for f in sorted(files):
        name = os.path.basename(f).lower()
        if os.path.splitext(name)[1] in SKIP_EXTS or name.startswith(("retrorenamer_", "romnamer_")) \
                or ".retrorenamer_tmp" in name or ".romnamer_tmp" in name:
            continue
        out.append(f)
    return out


def _identify_file(path, index, opts, sevenzip):
    it = PlanItem(src=path)
    ext = os.path.splitext(path)[1].lower()
    size = os.path.getsize(path)
    if size > opts.max_size_mb * 1024 * 1024:
        it.status, it.note = ST_ERROR, f"Datei groesser als {opts.max_size_mb} MB - uebersprungen"
        return it, None

    if ext == ".zip" and zipfile.is_zipfile(path):
        it.kind = "ZIP"
        with zipfile.ZipFile(path) as z:
            members = [(i.filename, z.read(i)) for i in z.infolist()
                       if not i.is_dir() and i.file_size <= opts.max_size_mb * 1024 * 1024]
        return _identify_archive(it, members, index)
    if ext == ".7z":
        it.kind = "7Z"
        if not sevenzip:
            it.status, it.note = ST_ERROR, "7-Zip nicht installiert - .7z kann nicht gelesen werden"
            return it, None
        members = read_7z(sevenzip, path)
        if any(d is None for _, d in members):
            it.status, it.note = ST_ERROR, f".7z mit {len(members)} Dateien wird nicht unterstuetzt"
            return it, None
        return _identify_archive(it, members, index)

    if size > BIG_FILE:
        it.crc, it.sha1, sz = hash_stream(path)
        cands = index.lookup(it.crc, it.sha1, sz)
        match = Match(_best(cands, path), "", False, len({c.game for c in cands}) - 1) if cands else None
        hint = ""
    else:
        with open(path, "rb") as f:
            data = f.read()
        match, it.crc, it.sha1 = identify_bytes(data, ext, index, path)
        hint = "" if match else header_hint(data)
    if not match:
        it.status, it.note = ST_UNKNOWN, hint or "Keine passende Pruefsumme in den DATs"
        return it, None
    it.game, it.system = match.entry.game, match.entry.system
    it.want = _target_filename(match, os.path.splitext(path)[1])
    _add_match_note(it, match)
    return it, match


def _add_match_note(it, match):
    notes = []
    if match.how:
        notes.append(match.how)
    if match.alternatives:
        notes.append(f"{match.alternatives} weitere Spiele mit identischem Inhalt")
    it.note = "; ".join(notes)


def _identify_archive(it, members, index):
    """Erkennt die Dateien in einem Archiv. Alle erkannten Dateien muessen zum selben Spiel gehoeren."""
    results = []
    unknown_hints = []
    for name, data in members:
        if os.path.splitext(name)[1].lower() in SKIP_EXTS:
            continue
        match, crc, sha1 = identify_bytes(data, os.path.splitext(name)[1].lower(), index,
                                          os.path.basename(it.src))
        if match:
            results.append((name, match, crc, sha1))
        else:
            h = header_hint(data)
            if h:
                unknown_hints.append(h)
            it.crc, it.sha1 = it.crc or crc, it.sha1 or sha1
    if not results:
        it.status = ST_UNKNOWN
        it.note = unknown_hints[0] if unknown_hints else "Keine passende Pruefsumme in den DATs"
        return it, None
    games = {(m.entry.system, m.entry.game) for _, m, _, _ in results}
    if len(games) > 1:
        it.status, it.note = ST_MIXED, f"Archiv enthaelt {len(games)} verschiedene Spiele"
        return it, None
    name, match, it.crc, it.sha1 = results[0]
    it.game, it.system = match.entry.game, match.entry.system
    it.want = safe_name(match.entry.game) + os.path.splitext(it.src)[1].lower()
    if it.kind == "ZIP":
        for n, m, _, _ in results:
            new = _target_filename(m, os.path.splitext(n)[1])
            if new != n:
                it.inner.append((n, new))
    _add_match_note(it, match)
    return it, match


def _unique(path, reserved):
    stem, ext = os.path.splitext(path)
    cand, i = path, 2
    while os.path.exists(cand) or os.path.normcase(cand) in reserved:
        cand = f"{stem} ({i}){ext}"
        i += 1
    reserved.add(os.path.normcase(cand))
    return cand


def scan(root, index, opts, progress=None, log=print):
    """Erkennt alle Dateien und erstellt einen Plan (aendert nichts auf der Platte)."""
    root = os.path.abspath(root)
    files = collect_files(root, opts.recursive)
    sevenzip = find_7z()
    items = []
    for i, path in enumerate(files):
        if progress:
            progress(i, len(files), os.path.basename(path))
        try:
            it, _ = _identify_file(path, index, opts, sevenzip)
        except Exception as ex:
            it = PlanItem(src=path, status=ST_ERROR, note=str(ex))
        if not opts.rename_in_zip:
            it.inner = []
        items.append(it)
    if progress:
        progress(len(files), len(files), "")

    # Zielpfade festlegen
    for it in items:
        if it.want:
            folder = os.path.join(root, safe_name(it.system)) if opts.sort_by_system else os.path.dirname(it.src)
            it.want = os.path.join(folder, it.want)

    sources = {os.path.normcase(it.src) for it in items}
    taken = {}
    reserved = set()
    identified = [it for it in items if it.want]
    # Dateien, die bereits richtig heissen, haben Vorrang (sie bleiben das "Original")
    identified.sort(key=lambda it: (os.path.normcase(it.want) != os.path.normcase(it.src), it.src))
    for it in identified:
        key = os.path.normcase(it.want)
        if key in taken or (os.path.exists(it.want) and key not in sources):
            other = taken[key].src if key in taken else it.want
            it.status = ST_DUP
            it.note = f"Gleiches Spiel wie: {os.path.relpath(other, root)}"
            if opts.move_duplicates:
                it.dst = _unique(os.path.join(root, DUP_DIRNAME, os.path.basename(it.src)), reserved)
            it.inner = []
            continue
        taken[key] = it
        if it.want == it.src and not it.inner:
            it.status = ST_OK
        else:
            it.status = ST_RENAME
            it.dst = it.want if it.want != it.src else ""

    if opts.move_unknown:
        for it in items:
            if it.status == ST_UNKNOWN:
                it.dst = _unique(os.path.join(root, UNKNOWN_DIRNAME, os.path.basename(it.src)), reserved)
    return items


# --------------------------------------------------------------------------
# Ausfuehren / Rueckgaengig
# --------------------------------------------------------------------------

def zip_rename_entries(path, mapping):
    tmp = path + ".retrorenamer_tmp"
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w") as zout:
        for info in zin.infolist():
            data = zin.read(info)
            ni = zipfile.ZipInfo(mapping.get(info.filename, info.filename), info.date_time)
            ni.external_attr = info.external_attr
            zout.writestr(ni, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    os.replace(tmp, path)


def apply_plan(items, root, progress=None, log=print):
    """Fuehrt den Plan aus. Jede Aenderung wird sofort in eine Undo-Datei geschrieben."""
    todo = [it for it in items if it.dst or it.inner]
    if not todo:
        log("Nichts zu tun.")
        return None, 0
    undo_path = os.path.join(root, f"retrorenamer_undo_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    done = 0
    errors = 0
    with open(undo_path, "w", newline="", encoding="utf-8") as uf:
        w = csv.writer(uf, delimiter=";")
        w.writerow(["aktion", "a", "b", "c"])

        # 1) Dateinamen innerhalb von ZIPs korrigieren
        for it in todo:
            if it.inner:
                try:
                    zip_rename_entries(it.src, dict(it.inner))
                    for old, new in it.inner:
                        w.writerow(["zip", it.src, old, new])
                    uf.flush()
                except Exception as ex:
                    errors += 1
                    it.note = f"Fehler beim ZIP-Umbenennen: {ex}"
                    log(f"FEHLER {it.src}: {ex}")

        # 2) Zwei Phasen: erst auf temporaere Namen, dann auf Zielnamen
        #    (so funktionieren auch Ringtausch und reine Gross-/Kleinschreibungs-Aenderungen)
        moves = [it for it in todo if it.dst and it.dst != it.src]
        staged = []
        for i, it in enumerate(moves):
            tmp = f"{it.src}.retrorenamer_tmp{i}"
            try:
                os.rename(it.src, tmp)
                w.writerow(["move", it.src, tmp, ""])
                uf.flush()
                staged.append((it, tmp))
            except Exception as ex:
                errors += 1
                it.note = f"Fehler: {ex}"
                log(f"FEHLER {it.src}: {ex}")
        for i, (it, tmp) in enumerate(staged):
            if progress:
                progress(i, len(staged), os.path.basename(it.dst))
            try:
                os.makedirs(os.path.dirname(it.dst), exist_ok=True)
                dst = it.dst
                if os.path.exists(dst):
                    dst = _unique(dst, set())
                    it.note = (it.note + "; " if it.note else "") + "Ziel existierte schon - Nummer angehaengt"
                os.rename(tmp, dst)
                it.dst = dst
                w.writerow(["move", tmp, dst, ""])
                uf.flush()
                done += 1
            except Exception as ex:
                errors += 1
                it.note = f"Fehler: {ex}"
                log(f"FEHLER {it.src}: {ex}")
        done += sum(1 for it in todo if it.inner and not (it.dst and it.dst != it.src))
    if progress:
        progress(1, 1, "")
    log(f"{done} Dateien geaendert, {errors} Fehler. Undo-Datei: {undo_path}")
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
        except Exception as ex:
            errors += 1
            log(f"FEHLER beim Rueckgaengigmachen ({b}): {ex}")
    # leere Ordner, die beim Sortieren entstanden sind, wieder entfernen
    for action, a, b, c in rows:
        if action == "move":
            d = os.path.dirname(b)
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass
    log(f"Rueckgaengig gemacht: {len(rows) - errors} Schritte, {errors} Fehler.")
    if not errors:
        os.rename(undo_path, undo_path[:-4] + "_rueckgaengig.csv")
    return errors


def write_report(items, path, root):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Status", "Datei", "Neuer Pfad", "System", "Spiel", "CRC32", "SHA1", "Hinweis"])
        for it in items:
            w.writerow([it.status, os.path.relpath(it.src, root),
                        os.path.relpath(it.dst, root) if it.dst else "",
                        it.system, it.game, it.crc, it.sha1, it.note])


def summarize(items):
    counts = {}
    for it in items:
        counts[it.status] = counts.get(it.status, 0) + 1
    return counts


# --------------------------------------------------------------------------
# Kommandozeile
# --------------------------------------------------------------------------

def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")
    p = argparse.ArgumentParser(description="Erkennt ROMs anhand des Inhalts und benennt sie nach No-Intro-DATs um.")
    p.add_argument("ordner", nargs="?", help="Ordner mit den ROMs")
    p.add_argument("--dats", default=DEFAULT_DAT_DIR, help="Ordner mit DAT-Dateien (Standard: ./dats)")
    p.add_argument("--apply", action="store_true", help="Aenderungen wirklich durchfuehren (sonst nur Vorschau)")
    p.add_argument("--no-recursive", action="store_true", help="Unterordner nicht durchsuchen")
    p.add_argument("--sort", action="store_true", help="In Unterordner pro System einsortieren")
    p.add_argument("--move-unknown", action="store_true", help=f"Unbekannte ROMs nach {UNKNOWN_DIRNAME} verschieben")
    p.add_argument("--move-duplicates", action="store_true", help=f"Duplikate nach {DUP_DIRNAME} verschieben")
    p.add_argument("--no-zip-inner", action="store_true", help="Dateien innerhalb von ZIPs nicht umbenennen")
    p.add_argument("--report", help="Bericht als CSV speichern")
    p.add_argument("--undo", metavar="UNDO_CSV", help="Eine fruehere Umbenennung rueckgaengig machen")
    p.add_argument("--update", action="store_true", help="Neueste Version von GitHub installieren")
    p.add_argument("--version", action="version", version=f"RetroRenamer {VERSION}")
    a = p.parse_args(argv)

    if a.update:
        import updater
        try:
            updater.update(VERSION)
        except Exception as ex:
            print(f"Update fehlgeschlagen: {ex}")
            return 1
        return 0
    if a.undo:
        return 1 if undo(a.undo) else 0
    if not a.ordner:
        p.error("Bitte einen ROM-Ordner angeben.")
    root = os.path.abspath(a.ordner)
    index = load_dats(a.dats)
    if not len(index):
        print(f"Keine DAT-Eintraege gefunden. Bitte DAT-Dateien nach '{a.dats}' legen (siehe README.md).")
        return 2
    opts = Options(recursive=not a.no_recursive, sort_by_system=a.sort, move_unknown=a.move_unknown,
                   move_duplicates=a.move_duplicates, rename_in_zip=not a.no_zip_inner)

    def progress(i, n, name):
        print(f"\r[{i}/{n}] {name[:60]:<60}", end="", flush=True)
    items = scan(root, index, opts, progress)
    print("\r" + " " * 80 + "\r", end="")

    for it in items:
        rel = os.path.relpath(it.src, root)
        line = f"{it.status:<10} {rel}"
        if it.dst:
            line += f"\n{'':<10} -> {os.path.relpath(it.dst, root)}"
        for old, new in it.inner:
            line += f"\n{'':<10}    im ZIP: {old} -> {new}"
        if it.note and it.status != ST_OK:
            line += f"\n{'':<10}    ({it.note})"
        print(line)
    print()
    print("Zusammenfassung: " + ", ".join(f"{k}: {v}" for k, v in sorted(summarize(items).items())))
    if a.report:
        write_report(items, a.report, root)
        print(f"Bericht gespeichert: {a.report}")
    if a.apply:
        apply_plan(items, root)
    elif any(it.dst or it.inner for it in items):
        print("\nDas war nur eine VORSCHAU. Mit --apply werden die Aenderungen durchgefuehrt.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
