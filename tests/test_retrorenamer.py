"""Selbsttest mit kuenstlichen ROMs und DATs (keine echten ROMs noetig).

Ausfuehren:  python tests/test_retrorenamer.py
"""
import array, hashlib, io, os, shutil, subprocess, sys, tempfile, zipfile, zlib

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT)
import i18n
i18n.set_language("de")
import retrorenamer as rn
import updater

base = tempfile.mkdtemp(prefix="retrorenamer_test_")
roms, dats = os.path.join(base, "roms"), os.path.join(base, "dats")
os.makedirs(os.path.join(roms, "sub")); os.makedirs(os.path.join(roms, "cd")); os.makedirs(dats)
seven = rn.find_7z()
sep = os.sep


def rnd(n, seed):
    out = bytearray(); h = seed.encode()
    while len(out) < n:
        h = hashlib.sha256(h).digest(); out += h
    return bytes(out[:n])


def h(b):
    return f"{zlib.crc32(b) & 0xffffffff:08x}", hashlib.sha1(b).hexdigest()


def w(name, data):
    open(os.path.join(roms, name), "wb").write(data)


def by_src(items, root=roms):
    return {os.path.relpath(it.src, root): it for it in items}


# ---------------------------------------------------------------- DATs
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

for s, lst in by_sys.items():
    if s == "Nintendo - Game Boy":  # ClrMamePro-Format
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
    if s == "Nintendo - SNES":  # DAT in einer ZIP
        with zipfile.ZipFile(os.path.join(dats, "pack.zip"), "w") as z:
            z.writestr("snes.dat", x)
    else:
        open(os.path.join(dats, s + ".dat"), "w", encoding="utf-8").write(x)

# Redump-artige DAT: zwei Regionen teilen sich einen identischen Audio-Track
T1_US, T1_EU, T2 = rnd(300000, "t1us"), rnd(300000, "t1eu"), rnd(200000, "audio")
cd_dat = '<?xml version="1.0"?>\n<datafile><header><name>Sony - PlayStation</name></header>\n'
for g, t1 in (("Disc Game (USA)", T1_US), ("Disc Game (Europe)", T1_EU)):
    cd_dat += f'<game name="{g}">'
    for n, d in ((f"{g} (Track 1).bin", t1), (f"{g} (Track 2).bin", T2)):
        c, sh = h(d)
        cd_dat += f'<rom name="{n}" size="{len(d)}" crc="{c}" sha1="{sh}"/>'
    cd_dat += f'<rom name="{g}.cue" size="10" crc="00000000" sha1="{"0" * 40}"/></game>\n'
open(os.path.join(dats, "psx.dat"), "w", encoding="utf-8").write(cd_dat + "</datafile>")

# ---------------------------------------------------------------- ROMs
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
# CD-Image mit CUE und zwei Tracks
w(os.path.join("cd", "dg 1.bin"), T1_US)
w(os.path.join("cd", "dg 2.bin"), T2)
CUE = (b'FILE "dg 1.bin" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n'
       b'FILE "dg 2.bin" BINARY\r\n  TRACK 02 AUDIO\r\n    INDEX 01 00:00:00\r\n')
w(os.path.join("cd", "dg.cue"), CUE)
w(os.path.join("cd", "broken.cue"), b'FILE "missing.bin" BINARY\r\n  TRACK 01 MODE1/2352\r\n')
if seven:
    tmp7 = os.path.join(base, "tmp7")
    os.makedirs(tmp7)
    open(os.path.join(tmp7, "x.gba"), "wb").write(G["Seven (Japan)"])
    open(os.path.join(tmp7, "info.txt"), "wb").write(b"info")
    subprocess.run([seven, "a", os.path.join(roms, "weird.7z"), os.path.join(tmp7, "x.gba"),
                    os.path.join(tmp7, "info.txt")], capture_output=True)
    open(os.path.join(tmp7, "y.gb"), "wb").write(G["Tetris (World)"])
    subprocess.run([seven, "a", os.path.join(roms, "mixed.7z"), os.path.join(tmp7, "x.gba"),
                    os.path.join(tmp7, "y.gb")], capture_output=True)
else:
    print("Hinweis: 7-Zip nicht gefunden - .7z-Tests werden uebersprungen")


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


# ---------------------------------------------------------------- Scan mit Sortieren
before = snapshot()
idx = rn.load_dats(dats)
expected_entries = len(games) + 6
assert len(idx) == expected_entries, len(idx)
assert len(rn.load_dats(dats)) == expected_entries  # zweiter Aufruf aus dem Cache

opts = rn.Options(sort_by_system=True, move_unknown=True, move_duplicates=True)
items = rn.scan(roms, idx, opts)
for it in items:
    print(f"{it.status_text:<10} {os.path.relpath(it.src, roms):<26} -> "
          f"{os.path.relpath(it.dst, roms) if it.dst else '':<50} {it.inner} | {it.note}")
st = by_src(items)
assert st["smb.nes"].status == rn.ST_RENAME
assert st["smb.nes"].dst.endswith(f"Nintendo - NES{sep}Super Mario Bros. (World).nes")
assert st["zelda_copier.smc"].dst.endswith("Zelda (USA).sfc")
assert st["sonic.smd"].dst.endswith("Sonic (World).smd")
assert st["sonic_copy.md"].dst.endswith("Sonic (World).md"), "Mega-Drive-.md wurde uebersprungen"
assert st["m64.v64"].dst.endswith("Mario 64 (USA).v64")
assert st[os.path.join("sub", "track01.bin")].dst.endswith(f"Nintendo - Game Boy{sep}Pokemon Red (USA, Europe).gb")
assert st["tetris_copy.gb"].status == rn.ST_DUP and rn.dup_dirname() in st["tetris_copy.gb"].dst
assert st["Tetris (World).gb"].status == rn.ST_RENAME  # wird in den System-Ordner verschoben
assert st["homebrew.gba"].status == rn.ST_UNKNOWN and rn.unknown_dirname() in st["homebrew.gba"].dst
assert st["mf.zip"].dst.endswith("Metroid Fusion (USA).zip")
assert st["mf.zip"].inner == [("metroid.gba", "Metroid Fusion (USA).gba")]
cue = st[os.path.join("cd", "dg.cue")]
assert cue.status == rn.ST_RENAME and cue.game == "Disc Game (USA)", (cue.status, cue.game, cue.note)
assert cue.dst.endswith(f"Sony - PlayStation{sep}Disc Game (USA).cue")
assert [os.path.basename(c[2]) for c in cue.companions] == ["Disc Game (USA) (Track 1).bin",
                                                             "Disc Game (USA) (Track 2).bin"]
assert os.path.join("cd", "dg 1.bin") not in st, "Tracks einer CUE duerfen nicht einzeln erscheinen"
assert st[os.path.join("cd", "broken.cue")].status == rn.ST_ERROR
if seven:
    assert st["weird.7z"].dst.endswith("Seven (Japan).7z"), st["weird.7z"].note
    assert st["mixed.7z"].status == rn.ST_MIXED, st["mixed.7z"].status

undo_path, errors = rn.apply_plan(items, roms)
assert errors == 0
after = snapshot()
assert after[os.path.join("Nintendo - GBA", "Metroid Fusion (USA).zip")] == ["Metroid Fusion (USA).gba", "readme.txt"]
assert not any("_tmp" in k for k in after)
new_cue = open(os.path.join(roms, "Sony - PlayStation", "Disc Game (USA).cue"), "rb").read()
assert b'FILE "Disc Game (USA) (Track 1).bin" BINARY\r\n' in new_cue and b"dg 2.bin" not in new_cue

# Zweiter Scan: alles muss OK sein (Sonderordner werden ignoriert)
items2 = rn.scan(roms, idx, opts)
bad = [(i.src, i.status) for i in items2 if i.status not in (rn.ST_OK, rn.ST_ERROR, rn.ST_MIXED)]
assert not bad, bad

# Undo stellt den Ursprungszustand exakt wieder her (inkl. CUE-Inhalt)
assert rn.undo(undo_path) == 0
assert snapshot() == before, "Undo hat den Ursprungszustand nicht wiederhergestellt"

# ---------------------------------------------------------------- Ohne Sortieren, Gross/Kleinschreibung
items3 = rn.scan(roms, idx, rn.Options(workers=1))
st3 = by_src(items3)
assert st3["casetest (usa).gba"].status == rn.ST_RENAME
assert st3["Tetris (World).gb"].status == rn.ST_OK
rn.apply_plan(items3, roms)
assert "CaseTest (USA).gba" in os.listdir(roms)

# ---------------------------------------------------------------- Grosse Dateien werden gestreamt
big = os.path.join(base, "big")
os.makedirs(big)
with zipfile.ZipFile(os.path.join(big, "big.zip"), "w", zipfile.ZIP_DEFLATED) as z:
    z.writestr("a.gba", G["Metroid Fusion (USA)"])
shutil.copyfile(os.path.join(roms, "zelda_copier.smc") if os.path.exists(os.path.join(roms, "zelda_copier.smc"))
                else os.path.join(roms, "Zelda (USA).sfc"), os.path.join(big, "z.sfc"))
old_big = rn.BIG_FILE
rn.BIG_FILE = 10_000
try:
    st_big = by_src(rn.scan(big, idx, rn.Options()), big)
    assert st_big["big.zip"].game == "Metroid Fusion (USA)", st_big["big.zip"].note
    rn.apply_plan(list(st_big.values()), big)
    with zipfile.ZipFile(os.path.join(big, "Metroid Fusion (USA).zip")) as z:
        assert z.read("Metroid Fusion (USA).gba") == G["Metroid Fusion (USA)"]
finally:
    rn.BIG_FILE = old_big

# ---------------------------------------------------------------- Englisch
utf8_env = dict(os.environ, PYTHONIOENCODING="utf-8")  # Windows nutzt bei Umleitung sonst cp1252
i18n.set_language("en")
assert rn.status_text(rn.ST_RENAME) == "RENAME" and rn.dup_dirname() == "_Duplicates"
r = subprocess.run([sys.executable, os.path.join(PROJECT, "retrorenamer.py"), roms, "--dats", dats, "--lang", "en"],
                   capture_output=True, text=True, encoding="utf-8", env=utf8_env)
assert r.returncode == 0, r.stderr
assert "Summary:" in r.stdout and "DUPLICATE" in r.stdout, r.stdout[-500:]
i18n.set_language("de")
r = subprocess.run([sys.executable, os.path.join(PROJECT, "retrorenamer.py"), roms, "--dats", dats, "--lang", "de"],
                   capture_output=True, text=True, encoding="utf-8", env=utf8_env)
assert r.returncode == 0 and "Zusammenfassung:" in r.stdout, r.stderr

# ---------------------------------------------------------------- Updater
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
bad_zip = io.BytesIO()
with zipfile.ZipFile(bad_zip, "w") as z:
    z.writestr("x-y-z/irgendwas.txt", "kein RetroRenamer")
try:
    updater.install_from_zip(bad_zip.getvalue(), app)
    raise AssertionError("Ungueltiges Update-Paket wurde akzeptiert")
except RuntimeError:
    pass
# EXE-Austausch
exe = os.path.join(app, "RetroRenamer.exe")
open(exe, "wb").write(b"MZ" + b"alt" * 50000)
updater.replace_executable(b"MZ" + b"neu" * 50000, exe)
assert open(exe, "rb").read()[:5] == b"MZneu" and os.path.exists(exe + ".old")
updater.cleanup_old_executables(exe)
assert not os.path.exists(exe + ".old")
try:
    updater.replace_executable(b"<html>kein exe</html>", exe)
    raise AssertionError("Ungueltige EXE wurde akzeptiert")
except RuntimeError:
    pass
assert open(exe, "rb").read()[:5] == b"MZneu"

# ---------------------------------------------------------------- GUI darf keine Tk-Interna ueberschreiben
try:
    import tkinter
    import retrorenamer_gui
    allowed = {"report_callback_exception"}
    clash = {n for n in vars(retrorenamer_gui.App) if not n.startswith("__")} & set(dir(tkinter.Tk)) - allowed
    assert not clash, f"GUI ueberschreibt Tkinter-Methoden: {clash}"
except ImportError:
    print("Hinweis: tkinter nicht verfuegbar - GUI-Pruefung uebersprungen")

shutil.rmtree(base, ignore_errors=True)
print("\nALLE TESTS OK")
