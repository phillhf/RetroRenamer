# RetroRenamer

**Identify retro game ROMs by their content, not their file name, and rename them to their correct, official names.**

`pkmn_red_FINAL(2).gb` → `Pokemon - Red Version (USA, Europe) (SGB Enhanced).gb`

[🇩🇪 Deutsche Anleitung](README_de.md)

![RetroRenamer screenshot](docs/screenshot.png)

---

## How it works

Every ROM dump has a unique fingerprint: its checksum (CRC32 / SHA1).
Preservation groups such as **No-Intro** and **Redump** publish free databases called **DAT files**. They list the
correct name and checksum of every known dump.

RetroRenamer calculates the checksum of each of your files and looks it up in those DAT files.
**The old file name is never used for identification.** A file named `asdf.zip` is recognized just as well as one with a
perfect name.

> **RetroRenamer does not include any DAT files and no ROMs.** You download the DAT files yourself, for free.
> See [step 1](#1-download-the-dat-files).

## Features

- **Many systems in one run**: Game Boy, Game Boy Color, GBA, NES, SNES, N64, Nintendo DS, Mega Drive/Genesis,
  Master System, Game Gear and every other system with a No-Intro or Redump DAT
- **Scans subfolders**: point it at your whole `ROMs` folder
- **Handles headers and odd formats automatically**:
  - NES (iNES) and FDS headers, SNES copier headers, Atari Lynx and 7800 headers
  - Mega Drive `.smd` (interleaved) files
  - N64 `.v64` (byte-swapped) and `.n64` (little-endian) files
- **ZIP support**: renames the archive *and* the file inside it
- **7z support**: needs [7-Zip](https://www.7-zip.org/) to be installed and only works for archives with a single file
- **Preview first**: nothing is changed until you click *Apply*
- **Full undo**: every change is logged, and one click restores the original names
- **Finds duplicates and unknown files**, and can move them into `_Duplikate` / `_Unbekannt`
- **Optional sorting** into one folder per system
- For unknown ROMs it shows the **internal title from the ROM header** as a hint
- **Built-in updater**: updates itself directly from GitHub with one click
- Graphical user interface and command line
- No dependencies besides Python itself

> ℹ️ The user interface is currently in **German**. The screenshot and the [status table](#status-meanings) explain
> every label.

---

## Installation

1. Install **Python 3.8 or newer** from [python.org](https://www.python.org/downloads/).
   On Windows, tick **"Add python.exe to PATH"** in the installer.
2. Download the latest version from the **[Releases page](https://github.com/phillhf/RetroRenamer/releases/latest)**
   (*Source code (zip)*) and unzip it, or run:
   ```bash
   git clone https://github.com/phillhf/RetroRenamer.git
   ```
3. *(Optional)* Install [7-Zip](https://www.7-zip.org/) if you want `.7z` archives to be recognized.

---

## 1. Download the DAT files

This is the most important step. **Without DAT files, RetroRenamer cannot recognize anything.**
You only need to do it once. Repeat it from time to time to get newly added games.

### Cartridge and handheld systems: No-Intro (recommended)

No-Intro covers almost all cartridge-based and handheld systems: GB, GBC, GBA, NES, SNES, N64, DS, Mega Drive and many more.

**Easiest way: download the complete daily pack (all systems at once)**

1. Open the No-Intro **DAT-o-MATIC** download page:
   **https://datomatic.no-intro.org/index.php?page=download&s=64&op=daily**
   (or go to https://datomatic.no-intro.org → menu **Download** → **Daily**)
2. Leave **Type: DAT** and **Set: No-Intro** selected.
3. Click **Request**. When the pack is ready, a download button appears. Click it to download the ZIP file.
4. Put the downloaded **ZIP file** into RetroRenamer's **`dats`** folder. **There is no need to unzip it.**

**Alternative: download only the systems you need.** On DAT-o-MATIC choose **Download → Standard DAT**, select a
system and download its `.dat` file. Put it into the `dats` folder as well.

### Which DAT do I need for my system?

If you use the complete daily pack, you already have all of them. The names below are how the DATs are called on DAT-o-MATIC:

| Your ROMs | DAT name on DAT-o-MATIC |
|---|---|
| Game Boy (`.gb`) | `Nintendo - Game Boy` |
| Game Boy Color (`.gbc`) | `Nintendo - Game Boy Color` |
| Game Boy Advance (`.gba`) | `Nintendo - Game Boy Advance` |
| NES (`.nes`) | `Nintendo - Nintendo Entertainment System (Headered)` **or** `(Headerless)`, either one works |
| Famicom Disk System (`.fds`) | `Nintendo - Family Computer Disk System` |
| SNES (`.sfc`, `.smc`) | `Nintendo - Super Nintendo Entertainment System` |
| Nintendo 64 (`.z64`, `.v64`, `.n64`) | `Nintendo - Nintendo 64 (BigEndian)`, which also matches `.v64`/`.n64` files |
| Nintendo DS (`.nds`) | `Nintendo - Nintendo DS (Decrypted)` |
| Virtual Boy (`.vb`) | `Nintendo - Virtual Boy` |
| Mega Drive / Genesis (`.md`, `.gen`, `.bin`, `.smd`) | `Sega - Mega Drive - Genesis` |
| Master System (`.sms`) | `Sega - Master System - Mark III` |
| Game Gear (`.gg`) | `Sega - Game Gear` |
| 32X (`.32x`) | `Sega - 32X` |
| Atari 2600 / 7800 / Lynx | `Atari - Atari 2600`, `Atari - Atari 7800 (A78)`, `Atari - Atari Lynx (LNX)` |
| WonderSwan (Color) | `Bandai - WonderSwan`, `Bandai - WonderSwan Color` |
| Neo Geo Pocket Color | `SNK - NeoGeo Pocket Color` |

### Disc-based systems: Redump

For CD/DVD systems (PlayStation, PS2, PSP, Saturn, Dreamcast, Mega-CD, GameCube, ...) download the DAT from
**http://redump.org/downloads/**. Click **Datfile** next to the system and put the file into the `dats` folder.

> ⚠️ RetroRenamer only identifies disc images that consist of **one single file** (e.g. a PS2/PSP `.iso` or a
> single-track `.bin`). Multi-track games (`.cue` + several `.bin` files) are not supported yet.

### Keeping the DATs up to date

Download a new pack from time to time and replace the old files in the `dats` folder. RetroRenamer detects the change
automatically and rebuilds its internal cache on the next scan.

---

## 2. Usage

### Graphical interface

- **Windows:** double-click **`RetroRenamer starten.bat`**
- **Linux / macOS:** run `python3 retrorenamer_gui.py`

Then:

1. **ROM-Ordner** (ROM folder): choose the folder with your ROMs, e.g. `C:\ROMs`. Subfolders are included.
2. **DAT-Ordner** (DAT folder): the `dats` folder is preselected.
3. Click **1. Scannen (Vorschau)** (*scan / preview*). Nothing is changed yet. The list shows the current and the new name of every file.
4. Check the list, then click **2. Änderungen anwenden** (*apply changes*).
5. Changed your mind? Click **Rückgängig machen...** (*undo*) and select the `retrorenamer_undo_<date>.csv` file in your ROM folder.

**Options:**

| Checkbox | Meaning |
|---|---|
| Unterordner einbeziehen | Include subfolders (default: on) |
| In Ordner pro System sortieren | Move files into one folder per system, e.g. `Nintendo - Game Boy\` (default: off, so files stay where they are) |
| Unbekannte nach _Unbekannt | Move unrecognized files into `_Unbekannt` |
| Duplikate nach _Duplikate | Move duplicates into `_Duplikate` |
| Dateien in ZIPs umbenennen | Also rename the file inside ZIP archives (default: on) |

### Command line

```bash
python retrorenamer.py "D:\ROMs"                     # preview only, changes nothing
python retrorenamer.py "D:\ROMs" --apply             # rename
python retrorenamer.py "D:\ROMs" --apply --sort      # rename and sort into one folder per system
python retrorenamer.py --undo "D:\ROMs\retrorenamer_undo_20261018_120000.csv"
```

| Option | Meaning |
|---|---|
| `--dats FOLDER` | DAT folder (default: `./dats`) |
| `--apply` | Actually perform the changes (otherwise preview only) |
| `--no-recursive` | Do not scan subfolders |
| `--sort` | Sort into one folder per system |
| `--move-unknown` | Move unknown files to `_Unbekannt` |
| `--move-duplicates` | Move duplicates to `_Duplikate` |
| `--no-zip-inner` | Do not rename files inside ZIP archives |
| `--report FILE.csv` | Save a CSV report with all checksums |
| `--undo UNDO.csv` | Undo a previous run |

---

## Updating

RetroRenamer checks for a new version on GitHub every time it starts. If one is available, it asks you whether to
install it. You can also check manually with the **Nach Updates suchen** (*check for updates*) button, or run:

```bash
python retrorenamer.py --update
```

Only the program files are replaced. **Your DAT files and settings are kept.**
If you installed RetroRenamer with `git clone`, update with `git pull` instead.

---

## Status meanings

| Status | Meaning |
|---|---|
| **OK** | The file already has the correct name |
| **UMBENENNEN** | Recognized, will be renamed |
| **UNBEKANNT** | Unknown: the checksum is not in any DAT (see [FAQ](#faq)) |
| **DUPLIKAT** | Duplicate: the same game already exists under its correct name |
| **GEMISCHT** | Mixed: the archive contains several different games and is left untouched |
| **FEHLER** | Error: the file could not be read |

---

## FAQ

**A ROM shows up as "UNBEKANNT" (unknown). Why?**
- The DAT for that system is missing from the `dats` folder.
- The ROM is a **hack, translation, homebrew or prototype**. These are not part of the No-Intro main DATs.
- The ROM is a **bad dump** or has been **modified** (patched, trimmed, overdumped).
- **Nintendo DS:** *trimmed* ROMs (unused space removed to save disk space) have a different checksum and cannot be recognized.

For unknown files RetroRenamer shows the internal title from the ROM header, if it can read one. This tells you what
the file probably is.

**Why not just use the file name?**
File names are often wrong, shortened or in another language. The checksum is the only reliable way to know exactly
which version (region, revision) you have.

**Is it safe?**
Nothing happens before you confirm. Every change is written to an undo file immediately, so you can always go back.
For the very first run on a large collection, we still recommend testing it on a copy.

**Where do the names come from?**
Directly from the DAT files. RetroRenamer uses exactly the names published by No-Intro / Redump.

---

## Limitations

- Disc images with multiple tracks (`.cue` + several `.bin` files) are not supported.
- `.7z` archives: only single-file archives, and only the archive itself is renamed (not the file inside).
- `.rar` archives are not supported.
- The user interface is in German.

## Running the tests

The test suite creates artificial ROMs and DATs, so no real ROMs are needed:

```bash
python tests/test_retrorenamer.py
```

## Legal

RetroRenamer is a file management tool. It does **not** contain, download or link to any ROMs.
DAT files are provided by the [No-Intro](https://no-intro.org) and [Redump](http://redump.org) projects. Please respect
their terms of use. Only use ROMs you are legally allowed to own.

## License

[MIT](LICENSE) © Phill (phillhf)
