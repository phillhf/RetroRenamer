"""Selbsttest mit kuenstlichen ROMs und DATs (keine echten ROMs noetig).

Ausfuehren:  python tests/test_retrorenamer.py
"""
import array, hashlib, os, shutil, subprocess, sys, tempfile, zipfile, zlib

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
import retrorenamer as rn

base = tempfile.mkdtemp(prefix="retrorenamer_test_")
roms, dats = os.path.join(base, "roms"), os.path.join(base, "dats")
os.makedirs(os.path.join(roms, "sub")); os.makedirs(dats)


def rnd(n, seed):
    out = bytearray(); h = seed.encode()
    while len(out) < n:
        h = hashlib.sha256(h).digest(); out += h
    return bytes(out[:n])


def h(b):
    return f"{zlib.crc32(b) & 0xffffffff:08x}", hashlib.sha1(b).hexdigest()


games = {
    "Super Mario Bros. (World)": ("Nintendo - NES", ".nes", rnd(40960, "smb")),
    "Zelda (USA)": ("Nintendo - SNES", ".sfc", rnd(1024 * 1024, "zelda")),
    "Sonic (World)": ("Sega - Mega Drive", ".md", rnd(512 * 1024, "sonic")),
    "Mario 64 (USA)": ("Nintendo - N64", ".z64", b"\x80\x37\x12\x40" + rnd(8 * 1024 * 1024 - 4, "m64")),
    "Pokemon Red (USA, Europe)": ("Nintendo - Game Boy", ".gb", rnd(65536, "pkmn")),
    "Tetris (World)": ("Nintendo - Game Boy", ".gb", rnd(32768, "tetris")),
    "Metroid Fusion (USA)": ("Nintendo - GBA", ".gba", rnd(100000, "mf")),
    "Seven (Japan)": ("Nintendo - GBA", ".gba", rnd(5000, "7z")),
    "CaseTest (USA)": ("Nintendo - GBA", ".gba", rnd(3000, "case")),
}
by_sys = {}
for g, (s, e, d) in games.items():
    by_sys.setdefault(s, []).append((g, e, d))

# XML-DATs, eine davon in einer ZIP, eine im ClrMamePro-Format
for s, lst in by_sys.items():
    if s == "Nintendo - Game Boy":
        txt = f'clrmamepro (\n\tname "{s}"\n)\n\n'
        for g, e, d in lst:
            c, sh = h(d)
            txt += (f'game (\n\tname "{g}"\n\tdescription "{g}"\n\trom ( name "{g}{e}" size {len(d)} '
                    f'crc {c.upper()} sha1 {sh.upper()} )\n)\n\n')
        open(os.path.join(dats, "gb.dat"), "w").write(txt)
        continue
    x = f'<?xml version="1.0"?>\n<datafile><header><name>{s}</name></header>\n'
    for g, e, d in lst:
        c, sh = h(d)
        x += (f'<game name="{g}"><description>{g}</description>'
              f'<rom name="{g}{e}" size="{len(d)}" crc="{c}" sha1="{sh}"/></game>\n')
    x += "</datafile>"
    if s == "Nintendo - SNES":
        with zipfile.ZipFile(os.path.join(dats, "pack.zip"), "w") as z:
            z.writestr("snes.dat", x)
    else:
        open(os.path.join(dats, s + ".dat"), "w", encoding="utf-8").write(x)


def w(name, data):
    open(os.path.join(roms, name), "wb").write(data)


G = {k: v[2] for k, v in games.items()}
w("smb.nes", b"NES\x1a" + b"\x02\x01" + bytes(10) + G["Super Mario Bros. (World)"])  # iNES-Header
w("zelda_copier.smc", bytes(512) + G["Zelda (USA)"])                                 # Kopierer-Header
body = G["Sonic (World)"]; smd = bytearray()
for i in range(0, len(body), 16384):
    blk = body[i:i + 16384]; smd += blk[1::2] + blk[0::2]
w("sonic.smd", bytes([0] * 8 + [0xAA, 0xBB] + [0] * 502) + bytes(smd))               # SMD interleaved
a = array.array("H", G["Mario 64 (USA)"]); a.byteswap(); w("m64.v64", a.tobytes())   # N64 .v64
w(os.path.join("sub", "track01.bin"), G["Pokemon Red (USA, Europe)"])                 # falsche Endung
w("Tetris (World).gb", G["Tetris (World)"])                                           # schon korrekt
w("tetris_copy.gb", G["Tetris (World)"])                                              # Duplikat
w("casetest (usa).gba", G["CaseTest (USA)"])                                          # nur Gross/Klein
w("sonic_copy.md", G["Sonic (World)"])                                                # .md = Mega Drive
w("homebrew.gba", rnd(4000, "unknown"))                                               # unbekannt
with zipfile.ZipFile(os.path.join(roms, "mf.zip"), "w") as z:
    z.writestr("metroid.gba", G["Metroid Fusion (USA)"]); z.writestr("readme.txt", "hi")
w("readme.txt", b"ignore me")
seven = rn.find_7z()
if seven:
    w("tmp7.gba", G["Seven (Japan)"])
    subprocess.run([seven, "a", os.path.join(roms, "weird.7z"), os.path.join(roms, "tmp7.gba")], capture_output=True)
    os.remove(os.path.join(roms, "tmp7.gba"))
else:
    print("Hinweis: 7-Zip nicht gefunden - .7z-Test wird uebersprungen")


def snapshot():
    out = {}
    for dp, _, ns in os.walk(roms):
        for n in ns:
            p = os.path.join(dp, n)
            if n.startswith("retrorenamer_undo"):
                continue
            out[os.path.relpath(p, roms)] = (sorted(zipfile.ZipFile(p).namelist()) if n.endswith(".zip")
                                             else hashlib.sha1(open(p, "rb").read()).hexdigest())
    return out


before = snapshot()
idx = rn.load_dats(dats)
assert len(idx) == len(games), len(idx)
assert len(rn.load_dats(dats)) == len(games)  # zweiter Aufruf aus dem Cache

opts = rn.Options(sort_by_system=True, move_unknown=True, move_duplicates=True)
items = rn.scan(roms, idx, opts)
for it in items:
    print(f"{it.status:<10} {os.path.relpath(it.src, roms):<28} -> "
          f"{os.path.relpath(it.dst, roms) if it.dst else '':<55} {it.inner} | {it.note}")
st = {os.path.relpath(it.src, roms): it for it in items}
sep = os.sep
assert st["smb.nes"].status == rn.ST_RENAME
assert st["smb.nes"].dst.endswith(f"Nintendo - NES{sep}Super Mario Bros. (World).nes")
assert st["zelda_copier.smc"].dst.endswith("Zelda (USA).sfc")
assert st["sonic.smd"].dst.endswith("Sonic (World).smd")
assert st["sonic_copy.md"].dst.endswith("Sonic (World).md"), "Mega-Drive-.md wurde uebersprungen"
assert st["m64.v64"].dst.endswith("Mario 64 (USA).v64")
assert st[os.path.join("sub", "track01.bin")].dst.endswith(f"Nintendo - Game Boy{sep}Pokemon Red (USA, Europe).gb")
assert st["tetris_copy.gb"].status == rn.ST_DUP and rn.DUP_DIRNAME in st["tetris_copy.gb"].dst
assert st["Tetris (World).gb"].status == rn.ST_RENAME  # wird in den System-Ordner verschoben
assert st["homebrew.gba"].status == rn.ST_UNKNOWN and rn.UNKNOWN_DIRNAME in st["homebrew.gba"].dst
assert st["mf.zip"].dst.endswith("Metroid Fusion (USA).zip")
assert st["mf.zip"].inner == [("metroid.gba", "Metroid Fusion (USA).gba")]
if seven:
    assert st["weird.7z"].dst.endswith("Seven (Japan).7z"), st["weird.7z"].note

undo_path, errors = rn.apply_plan(items, roms)
assert errors == 0
after = snapshot()
assert after[os.path.join("Nintendo - GBA", "Metroid Fusion (USA).zip")] == ["Metroid Fusion (USA).gba", "readme.txt"]
assert not any("_tmp" in k for k in after)

# Zweiter Scan: alles muss OK sein (_Duplikate/_Unbekannt werden ignoriert)
items2 = rn.scan(roms, idx, opts)
assert all(it.status == rn.ST_OK for it in items2), [(i.src, i.status) for i in items2]

# Undo stellt den Ursprungszustand exakt wieder her
assert rn.undo(undo_path) == 0
assert snapshot() == before, "Undo hat den Ursprungszustand nicht wiederhergestellt"

# Ohne Sortieren: reine Gross-/Kleinschreibungs-Aenderung
items3 = rn.scan(roms, idx, rn.Options())
st3 = {os.path.relpath(it.src, roms): it for it in items3}
assert st3["casetest (usa).gba"].status == rn.ST_RENAME
assert st3["Tetris (World).gb"].status == rn.ST_OK
rn.apply_plan(items3, roms)
assert "CaseTest (USA).gba" in os.listdir(roms)

# Kommandozeile
r = subprocess.run([sys.executable, os.path.join(PROJECT, "retrorenamer.py"), roms, "--dats", dats],
                   capture_output=True, text=True)
assert r.returncode == 0, r.stderr

# Updater
import io
import updater
assert updater.is_newer("1.0.1", "1.0.0") and updater.is_newer("v1.10.0", "1.9.9")
assert not updater.is_newer("1.0.0", "1.0.0") and not updater.is_newer("0.9", "1.0.0")
app = os.path.join(base, "app")
os.makedirs(os.path.join(app, "dats"))
open(os.path.join(app, "retrorenamer.py"), "w").write("alt")
open(os.path.join(app, "dats", "meine.dat"), "w").write("bleibt")
open(os.path.join(app, "retrorenamer_settings.json"), "w").write("bleibt")
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as z:
    z.writestr("phillhf-RetroRenamer-abc123/retrorenamer.py", "neu")
    z.writestr("phillhf-RetroRenamer-abc123/docs/screenshot.png", "bild")
    z.writestr("phillhf-RetroRenamer-abc123/dats/README.md", "readme")
    z.writestr("phillhf-RetroRenamer-abc123/dats/meine.dat", "UEBERSCHRIEBEN")
    z.writestr("phillhf-RetroRenamer-abc123/retrorenamer_settings.json", "UEBERSCHRIEBEN")
updater.install_from_zip(buf.getvalue(), app)
assert open(os.path.join(app, "retrorenamer.py")).read() == "neu"
assert os.path.exists(os.path.join(app, "docs", "screenshot.png"))
assert open(os.path.join(app, "dats", "meine.dat")).read() == "bleibt"
assert open(os.path.join(app, "retrorenamer_settings.json")).read() == "bleibt"
bad = io.BytesIO()
with zipfile.ZipFile(bad, "w") as z:
    z.writestr("x-y-z/irgendwas.txt", "kein RetroRenamer")
try:
    updater.install_from_zip(bad.getvalue(), app)
    raise AssertionError("Ungueltiges Update-Paket wurde akzeptiert")
except RuntimeError:
    pass

shutil.rmtree(base, ignore_errors=True)
print("\nALLE TESTS OK")
