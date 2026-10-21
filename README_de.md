<img src="installer/app_256.png" alt="" width="96" align="right">

# RetroRenamer

[![Tests](https://github.com/phillhf/RetroRenamer/actions/workflows/tests.yml/badge.svg)](https://github.com/phillhf/RetroRenamer/actions/workflows/tests.yml)
[![Neueste Version](https://img.shields.io/github/v/release/phillhf/RetroRenamer)](https://github.com/phillhf/RetroRenamer/releases/latest)
[![Lizenz: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Erkennt Retro-Spiele-ROMs anhand ihres Inhalts statt am Dateinamen und benennt sie mit dem korrekten, offiziellen Namen um.**

`pkmn_rot_FINAL(2).gb` → `Pokemon - Rote Edition (Germany) (SGB Enhanced).gb`

[🇬🇧 English version](README.md)

![RetroRenamer Screenshot](docs/screenshot_de.png)

---

## So funktioniert es

Jedes ROM hat einen eindeutigen Fingerabdruck: seine Prüfsumme (CRC32 / SHA1).
Archivierungsprojekte wie **No-Intro** und **Redump** veröffentlichen kostenlos sogenannte **DAT-Dateien**. Darin
stehen für jedes bekannte Spiel der korrekte Name und die Prüfsumme.

RetroRenamer berechnet die Prüfsumme jeder deiner Dateien und sucht sie in diesen DAT-Dateien.
**Der alte Dateiname wird für die Erkennung nie verwendet.** Eine Datei namens `asdf.zip` wird genauso erkannt wie eine
mit perfektem Namen.

> **RetroRenamer enthält keine DAT-Dateien und keine ROMs.** Die DAT-Dateien lädst du selbst kostenlos herunter,
> siehe [Schritt 2](#2-dat-dateien-herunterladen).

## Funktionen

- **Viele Systeme in einem Durchgang**: Game Boy, Game Boy Color, GBA, NES, SNES, N64, Nintendo DS,
  Mega Drive/Genesis, Master System, Game Gear, PlayStation und jedes weitere System mit einer No-Intro- oder Redump-DAT
- **Durchsucht Unterordner**: Du kannst einfach deinen kompletten `ROMs`-Ordner auswählen.
- **Header und Sonderformate werden automatisch berücksichtigt**:
  - NES- (iNES) und FDS-Header, SNES-Kopierer-Header, Atari-Lynx- und 7800-Header
  - Mega-Drive-Dateien im `.smd`-Format (interleaved)
  - N64-Dateien in `.v64`- (byteswapped) und `.n64`-Byteorder (little endian)
- **CD-Images mit mehreren Tracks** (`.cue` + `.bin`): Alle Tracks werden gemeinsam erkannt und umbenannt, und die
  `.cue`-Datei wird an die neuen Track-Namen angepasst.
- **Archive**:
  - `.zip`: benennt das Archiv *und* die Dateien darin um
  - `.7z` und `.rar`: brauchen ein installiertes [7-Zip](https://www.7-zip.org/). Das Archiv wird umbenannt, die Dateien darin nicht.
  - Große Dateien in Archiven werden stückweise gelesen. Selbst mehrere GB große Disc-Images im ZIP brauchen daher kaum Arbeitsspeicher.
- **Schnell**: prüft mehrere Dateien gleichzeitig
- **Erst Vorschau**: Es wird nichts geändert, bevor du auf *Änderungen anwenden* klickst.
- **Vollständiges Rückgängigmachen**: Jede Änderung wird protokolliert, ein Klick stellt die alten Namen wieder her.
- **Erkennt Duplikate und unbekannte Dateien** und verschiebt sie auf Wunsch nach `_Duplikate` / `_Unbekannt`
- **Optional: Sortieren** in einen Ordner pro System
- Bei unbekannten ROMs wird der **interne Titel aus dem ROM-Header** als Hinweis angezeigt.
- **Deutsch und Englisch**: Die Sprache wird automatisch erkannt und lässt sich im Programm umschalten.
- **Eingebaute Update-Funktion**: aktualisiert sich direkt von GitHub
- Als **Windows-Installer**, als **portable Windows-EXE** oder als Python-Skript (Windows, Linux, macOS)

---

## 1. Installation

### Variante A: Windows-Installer (empfohlen)

1. Die **[neueste Version](https://github.com/phillhf/RetroRenamer/releases/latest)** öffnen und
   **`RetroRenamer-Setup-<Version>.exe`** herunterladen.
2. Ausführen und den Schritten folgen. **Administratorrechte sind nicht nötig.** Standardordner ist
   `C:\Tools\RetroRenamer`. Es gibt einen Startmenü-Eintrag und auf Wunsch eine Desktop-Verknüpfung.
3. RetroRenamer über das Startmenü starten.

Updates werden automatisch über den Installer eingespielt (RetroRenamer fragt vorher). Deinstallieren geht über
*Einstellungen → Apps* oder den Startmenü-Eintrag *RetroRenamer deinstallieren*. Dabei wirst du gefragt, ob deine
DAT-Dateien und Einstellungen erhalten bleiben sollen.

Stille Installation: `RetroRenamer-Setup-<Version>.exe /VERYSILENT [/DIR="D:\RetroRenamer"] [/TASKS="desktopicon"]`

### Variante B: Portable Windows-EXE

1. **`RetroRenamer.exe`** von der **[neuesten Version](https://github.com/phillhf/RetroRenamer/releases/latest)** herunterladen.
2. Einen eigenen Ordner dafür anlegen, z. B. `D:\Tools\RetroRenamer`, und die EXE hineinlegen. RetroRenamer legt den
   Ordner `dats` und seine Einstellungen neben der EXE ab und läuft deshalb auch vom USB-Stick.
3. Doppelklick auf `RetroRenamer.exe`.

> ⚠️ **Windows SmartScreen** warnt eventuell beim ersten Start („Der Computer wurde durch Windows geschützt“), weil
> Installer und EXE nicht digital signiert sind. Dann auf **Weitere Informationen → Trotzdem ausführen** klicken. Beide
> werden automatisch von GitHub aus dem Quellcode dieses Repositorys gebaut ([Build-Workflow](.github/workflows/release.yml)).

### Variante C: Python (Windows, Linux, macOS)

1. **Python 3.9 oder neuer** von [python.org](https://www.python.org/downloads/) installieren.
   Unter Windows im Installer **„Add python.exe to PATH“** anhaken.
2. Die **[neueste Version](https://github.com/phillhf/RetroRenamer/releases/latest)** (*Source code (zip)*)
   herunterladen und entpacken, oder:
   ```bash
   git clone https://github.com/phillhf/RetroRenamer.git
   ```
3. Starten:
   - **Windows:** Doppelklick auf **`RetroRenamer starten.bat`**
   - **Linux / macOS:** `python3 retrorenamer_gui.py`

### Optional: 7-Zip

[7-Zip](https://www.7-zip.org/) installieren, wenn auch `.7z`- und `.rar`-Archive erkannt werden sollen.
Unter Linux das Paket `p7zip-full` bzw. `7zip` installieren, unter macOS `brew install sevenzip`.

---

## 2. DAT-Dateien herunterladen

Das ist der wichtigste Schritt. **Ohne DAT-Dateien kann RetroRenamer nichts erkennen.**
Du musst das nur einmal machen. Wiederhole es ab und zu, damit auch neu erfasste Spiele erkannt werden.

> 💡 In RetroRenamer öffnet der Knopf **No-Intro-DATs (Webseite)** die Download-Seite von No-Intro und deinen DAT-Ordner.
> Redump-DATs lassen sich direkt über **Redump-DATs laden...** herunterladen (siehe unten).

### Modul- und Handheld-Systeme: No-Intro (empfohlen)

No-Intro deckt fast alle Systeme mit Steckmodulen sowie Handhelds ab: GB, GBC, GBA, NES, SNES, N64, DS, Mega Drive und viele mehr.

**Am einfachsten: das komplette Tagespaket herunterladen (alle Systeme auf einmal)**

1. Die Download-Seite von No-Intros **DAT-o-MATIC** öffnen:
   **https://datomatic.no-intro.org/index.php?page=download&s=64&op=daily**
   (oder auf https://datomatic.no-intro.org → Menü **Download** → **Daily**)
2. **Type: DAT** und **Set: No-Intro** ausgewählt lassen.
3. Auf **Request** klicken. Sobald das Paket fertig ist, erscheint ein Download-Knopf. Darüber lädst du die ZIP-Datei herunter.
4. Die heruntergeladene **ZIP-Datei** in den Ordner **`dats`** von RetroRenamer legen. **Entpacken ist nicht nötig.**

**Alternative: nur einzelne Systeme herunterladen.** Auf DAT-o-MATIC **Download → Standard DAT** wählen, das
gewünschte System auswählen und die `.dat`-Datei herunterladen. Auch diese kommt in den Ordner `dats`.

### Welche DAT brauche ich für welches System?

Mit dem kompletten Tagespaket hast du automatisch alle. So heißen die DATs auf DAT-o-MATIC:

| Deine ROMs | Name der DAT auf DAT-o-MATIC |
|---|---|
| Game Boy (`.gb`) | `Nintendo - Game Boy` |
| Game Boy Color (`.gbc`) | `Nintendo - Game Boy Color` |
| Game Boy Advance (`.gba`) | `Nintendo - Game Boy Advance` |
| NES (`.nes`) | `Nintendo - Nintendo Entertainment System (Headered)` **oder** `(Headerless)`, beide funktionieren |
| Famicom Disk System (`.fds`) | `Nintendo - Family Computer Disk System` |
| SNES (`.sfc`, `.smc`) | `Nintendo - Super Nintendo Entertainment System` |
| Nintendo 64 (`.z64`, `.v64`, `.n64`) | `Nintendo - Nintendo 64 (BigEndian)`, passt auch für `.v64`/`.n64` |
| Nintendo DS (`.nds`) | `Nintendo - Nintendo DS (Decrypted)` |
| Virtual Boy (`.vb`) | `Nintendo - Virtual Boy` |
| Mega Drive / Genesis (`.md`, `.gen`, `.bin`, `.smd`) | `Sega - Mega Drive - Genesis` |
| Master System (`.sms`) | `Sega - Master System - Mark III` |
| Game Gear (`.gg`) | `Sega - Game Gear` |
| 32X (`.32x`) | `Sega - 32X` |
| Atari 2600 / 7800 / Lynx | `Atari - Atari 2600`, `Atari - Atari 7800 (A78)`, `Atari - Atari Lynx (LNX)` |
| WonderSwan (Color) | `Bandai - WonderSwan`, `Bandai - WonderSwan Color` |
| Neo Geo Pocket Color | `SNK - NeoGeo Pocket Color` |

### CD-/DVD-Systeme: Redump

Für Disc-Systeme (PlayStation, PS2, PSP, Saturn, Dreamcast, Mega-CD, GameCube usw.) lädt RetroRenamer die DATs
auf Wunsch selbst herunter:

1. Auf **Redump-DATs laden...** klicken.
2. Die gewünschten Systeme auswählen (Mehrfachauswahl per Klick) und auf **Herunterladen** klicken.

Die Dateien kommen von redump.org in deinen Ordner `dats`, ältere Versionen werden ersetzt. Um die Server von Redump zu
schonen, wartet RetroRenamer zwischen zwei Downloads jeweils 5 Sekunden und lädt nur, wenn du es ausdrücklich
anstößt. Die Auswahl wird gespeichert, ein späteres Aktualisieren sind also nur zwei Klicks.

Per Kommandozeile: `python retrorenamer.py --redump psx,ps2`. Alle Kürzel zeigt `--redump list`.

Manuell geht es auch: Auf **http://redump.org/downloads/** neben dem System auf **Datfile** klicken und die Datei in
den Ordner `dats` legen.

Unterstützte Disc-Formate:
- `.cue` + eine oder mehrere `.bin`-Tracks (z. B. PlayStation, Saturn, Mega-CD)
- Images aus einer einzigen Datei wie `.iso` (z. B. PS2, PSP, GameCube)

> ⚠️ Komprimierte Disc-Formate (`.chd`, `.rvz`, `.cso`, `.pbp`) und `.gdi` werden **nicht** unterstützt.
> Redump-Prüfsummen beziehen sich auf die unkomprimierten Daten, solche Dateien müssten also erst zurückgewandelt werden.

### DATs aktuell halten

Lade ab und zu ein neues Paket herunter und ersetze damit die alten Dateien im Ordner `dats`. RetroRenamer bemerkt
das automatisch und baut seinen internen Zwischenspeicher beim nächsten Scan neu auf.

---

## 3. Benutzung

1. **ROM-Ordner:** den Ordner mit deinen ROMs wählen, z. B. `C:\ROMs`. Unterordner werden mit durchsucht.
2. **DAT-Ordner:** Der Ordner `dats` ist schon voreingestellt.
3. **1. Scannen (Vorschau)** klicken. Es wird noch nichts geändert. Die Liste zeigt für jede Datei den aktuellen und den neuen Namen.
4. Liste prüfen, dann auf **2. Änderungen anwenden** klicken.
5. Doch nicht zufrieden? **Rückgängig machen...** klicken und die Datei `retrorenamer_undo_<Datum>.csv` aus dem ROM-Ordner auswählen.

**Optionen:**

| Häkchen | Bedeutung |
|---|---|
| Unterordner einbeziehen | Unterordner mit durchsuchen (Standard: an) |
| In Ordner pro System sortieren | Dateien in einen Ordner pro System verschieben, z. B. `Nintendo - Game Boy\` (Standard: aus, die Dateien bleiben in ihrem Ordner) |
| Unbekannte nach _Unbekannt | Nicht erkannte Dateien nach `_Unbekannt` verschieben |
| Duplikate nach _Duplikate | Duplikate nach `_Duplikate` verschieben |
| Dateien in ZIPs umbenennen | Auch die Dateien innerhalb von ZIP-Archiven umbenennen (Standard: an) |

### Kommandozeile

```bash
python retrorenamer.py "D:\ROMs"                     # nur Vorschau, ändert nichts
python retrorenamer.py "D:\ROMs" --apply             # umbenennen
python retrorenamer.py "D:\ROMs" --apply --sort      # umbenennen und in Ordner pro System sortieren
python retrorenamer.py --undo "D:\ROMs\retrorenamer_undo_20261019_120000.csv"
```

| Option | Bedeutung |
|---|---|
| `--dats ORDNER` | DAT-Ordner (Standard: `./dats`) |
| `--apply` | Änderungen wirklich durchführen (sonst nur Vorschau) |
| `--no-recursive` | Unterordner nicht durchsuchen |
| `--sort` | In einen Ordner pro System sortieren |
| `--move-unknown` | Unbekannte Dateien nach `_Unbekannt` verschieben |
| `--move-duplicates` | Duplikate nach `_Duplikate` verschieben |
| `--no-zip-inner` | Dateien innerhalb von ZIPs nicht umbenennen |
| `--report DATEI.csv` | CSV-Bericht mit allen Prüfsummen speichern |
| `--workers N` | Anzahl gleichzeitig geprüfter Dateien (Standard: automatisch) |
| `--lang de\|en` | Sprache der Ausgabe (Standard: Systemsprache) |
| `--undo UNDO.csv` | Einen früheren Durchlauf rückgängig machen |
| `--redump psx,ps2` | Redump-DATs in den DAT-Ordner laden (`--redump list` zeigt alle Kürzel) |
| `--update` | Neueste Version von GitHub installieren |

---

## Updates

RetroRenamer prüft bei jedem Start, ob es auf GitHub eine neue Version gibt. Wenn ja, fragt es, ob sie installiert
werden soll. Manuell geht es über den Knopf **Nach Updates suchen** oder per `python retrorenamer.py --update`.

- **Installer-Version:** Der neue Installer wird heruntergeladen und läuft still im Hintergrund. RetroRenamer wird dabei beendet und danach automatisch neu gestartet.
- **Portable EXE:** Die neue `RetroRenamer.exe` wird heruntergeladen und ersetzt die alte.
- **Python-Version:** Die Programmdateien werden ersetzt.

**Deine DAT-Dateien und Einstellungen bleiben immer erhalten.** Wenn du RetroRenamer per `git clone` installiert
hast, aktualisiere stattdessen mit `git pull`.

---

## Bedeutung der Status

| Status | Bedeutung |
|---|---|
| **OK** | Die Datei hat bereits den korrekten Namen. |
| **UMBENENNEN** | Erkannt, wird umbenannt. |
| **UNBEKANNT** | Die Prüfsumme steht in keiner DAT (siehe [FAQ](#faq)). |
| **DUPLIKAT** | Dasselbe Spiel liegt schon unter dem korrekten Namen vor. |
| **GEMISCHT** | Das Archiv oder die CUE enthält Dateien aus mehreren verschiedenen Spielen und wird nicht angefasst. |
| **FEHLER** | Die Datei konnte nicht gelesen werden, oder von einer `.cue` referenzierte Dateien fehlen. |

---

## FAQ

**Ein ROM wird als UNBEKANNT angezeigt. Warum?**
- Die DAT für dieses System fehlt im Ordner `dats`.
- Das ROM ist ein **Hack, eine Übersetzung, Homebrew oder ein Prototyp**. Diese sind nicht in den No-Intro-Haupt-DATs enthalten.
- Das ROM ist ein **fehlerhafter Dump (Bad Dump)** oder wurde **verändert** (gepatcht, getrimmt, Overdump).
- **Nintendo DS:** *Getrimmte* ROMs (ungenutzter Speicher entfernt, um Platz zu sparen) haben eine andere Prüfsumme und können nicht erkannt werden.

Bei unbekannten Dateien zeigt RetroRenamer, wenn möglich, den internen Titel aus dem ROM-Header an. Daran siehst du,
um welches Spiel es sich vermutlich handelt.

**Warum nicht einfach den Dateinamen verwenden?**
Dateinamen sind oft falsch, abgekürzt oder in einer anderen Sprache. Nur über die Prüfsumme lässt sich genau sagen,
welche Version (Region, Revision) du hast.

**Ist das sicher?**
Es passiert nichts, bevor du bestätigst. Jede Änderung wird sofort in eine Undo-Datei geschrieben, du kannst also immer
zurück. Beim allerersten Durchlauf über eine große Sammlung empfehlen wir trotzdem, es an einer Kopie zu testen.

**Wie viel Arbeitsspeicher wird gebraucht?**
Mit dem kompletten No-Intro-Tagespaket rund 300 MB. Das Laden der DATs dauert beim ersten Mal ein paar Sekunden,
danach geht es dank Zwischenspeicher schneller.

**Woher kommen die Namen?**
Direkt aus den DAT-Dateien. RetroRenamer verwendet genau die Namen, die No-Intro bzw. Redump veröffentlichen.

---

## Einschränkungen

- Komprimierte Disc-Formate (`.chd`, `.rvz`, `.cso`, `.pbp`) und `.gdi` werden nicht unterstützt.
- `.7z`- und `.rar`-Archive: Nur das Archiv selbst wird umbenannt, nicht die Dateien darin.

## Warum werden No-Intro-DATs nicht automatisch geladen?

Die Datenlizenz von No-Intro erlaubt die freie Nutzung der DATs. Der Download ist bei No-Intro aber bewusst als
manueller Vorgang gestaltet (Anfrage-Formular), und ihre `robots.txt` bittet um höchstens eine Anfrage alle
5 Sekunden. Aus Rücksicht auf das ehrenamtliche Projekt öffnet RetroRenamer dort nur die Download-Seite. Redump bietet
für jedes System einen direkten Download-Link, deshalb kann RetroRenamer diese DATs für dich laden.

## Entwicklung

Tests ausführen. Sie erzeugen künstliche ROMs und DATs, echte ROMs sind also nicht nötig:

```bash
python tests/test_retrorenamer.py
```

Windows-EXE und Installer selbst bauen (braucht `pip install pyinstaller` und
[Inno Setup 6](https://jrsoftware.org/isinfo.php)):

```bash
powershell -ExecutionPolicy Bypass -File installer\build.ps1
```

Die Ergebnisse liegen in `dist\`. Jede veröffentlichte Release bekommt beide Dateien automatisch, gebaut von
GitHub Actions. Das Programmsymbol erzeugt `python installer/make_icon.py`.

## Rechtliches

RetroRenamer ist ein Werkzeug zur Dateiverwaltung. Es enthält **keine** ROMs, lädt keine herunter und verlinkt auf keine.
Die DAT-Dateien stammen von den Projekten [No-Intro](https://no-intro.org) und [Redump](http://redump.org). Bitte
beachte deren Nutzungsbedingungen. Verwende nur ROMs, die du rechtmäßig besitzen darfst.

## Lizenz

[MIT](LICENSE) © Phill (phillhf)
