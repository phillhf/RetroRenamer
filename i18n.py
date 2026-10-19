"""Uebersetzungen (Deutsch / Englisch). Die Sprache wird automatisch aus dem System erkannt."""

import locale
import os
import sys

LANGUAGES = {"de": "Deutsch", "en": "English"}

STRINGS = {
    "de": {
        # Status
        "status.OK": "OK",
        "status.RENAME": "UMBENENNEN",
        "status.UNKNOWN": "UNBEKANNT",
        "status.DUPLICATE": "DUPLIKAT",
        "status.MIXED": "GEMISCHT",
        "status.ERROR": "FEHLER",
        "dir.unknown": "_Unbekannt",
        "dir.duplicates": "_Duplikate",
        # DATs
        "dat.not_found": "DAT-Ordner nicht gefunden: {path}",
        "dat.loaded_cache": "{files} DAT-Dateien aus dem Cache geladen ({entries} ROM-Einträge).",
        "dat.loaded": "{files} DAT-Dateien geladen ({entries} ROM-Einträge).",
        "dat.loading": "Lade DAT-Dateien...",
        "dat.warn": "WARNUNG: DAT '{path}' konnte nicht gelesen werden: {error}",
        "dat.none": "Keine DAT-Einträge gefunden. Bitte DAT-Dateien in '{path}' ablegen (siehe README).",
        # Erkennung
        "how.header16": "16-Byte-Header ignoriert",
        "how.lynx": "Lynx-Header ignoriert",
        "how.a7800": "A7800-Header ignoriert",
        "how.copier": "512-Byte-Kopierer-Header ignoriert",
        "how.smd": "SMD-Format (interleaved)",
        "how.v64": "N64 byteswapped (.v64)",
        "how.n64": "N64 little endian (.n64)",
        "note.no_match": "Keine passende Prüfsumme in den DATs",
        "note.alternatives": "{n} weitere Spiele mit identischem Inhalt",
        "note.too_big": "Datei größer als {mb} MB – übersprungen",
        "note.no7z": "7-Zip ist nicht installiert – {ext}-Archive können nicht gelesen werden",
        "note.mixed": "Enthält Dateien aus {n} verschiedenen Spielen",
        "note.dup_of": "Gleiches Spiel wie: {path}",
        "note.cue_tracks": "CUE + {n} Track-Datei(en)",
        "note.cue_missing": "Vom CUE referenzierte Dateien fehlen: {files}",
        "note.cue_subdir": "CUE verweist auf Dateien in anderen Ordnern – nicht unterstützt",
        "note.cue_partial": "Nur {ok} von {total} Tracks erkannt",
        "note.target_exists": "Ziel existierte schon – Nummer angehängt",
        "note.error": "Fehler: {error}",
        "note.zip_error": "Fehler beim ZIP-Umbenennen: {error}",
        "note.inner_kept": "Datei im Archiv wird nicht umbenannt ({ext})",
        "err.7z_read": "7-Zip konnte das Archiv nicht lesen",
        # Ausfuehren
        "apply.nothing": "Nichts zu tun.",
        "apply.done": "{done} Dateien geändert, {errors} Fehler. Undo-Datei: {path}",
        "apply.error": "FEHLER {path}: {error}",
        "undo.error": "FEHLER beim Rückgängigmachen ({path}): {error}",
        "undo.done": "Rückgängig gemacht: {steps} Schritte, {errors} Fehler.",
        "undo.suffix": "_rueckgaengig",
        # Bericht
        "col.status": "Status",
        "col.file": "Datei",
        "col.current": "Aktuelle Datei",
        "col.new": "Neuer Name",
        "col.system": "System",
        "col.game": "Spiel",
        "col.note": "Hinweis",
        # Kommandozeile
        "cli.description": "Erkennt ROMs anhand ihres Inhalts und benennt sie nach No-Intro-/Redump-DATs um.",
        "cli.folder": "Ordner mit den ROMs",
        "cli.dats": "Ordner mit DAT-Dateien (Standard: ./dats)",
        "cli.apply": "Änderungen wirklich durchführen (sonst nur Vorschau)",
        "cli.no_recursive": "Unterordner nicht durchsuchen",
        "cli.sort": "In einen Ordner pro System einsortieren",
        "cli.move_unknown": "Unbekannte ROMs nach {dir} verschieben",
        "cli.move_dups": "Duplikate nach {dir} verschieben",
        "cli.no_zip_inner": "Dateien innerhalb von ZIPs nicht umbenennen",
        "cli.report": "Bericht als CSV speichern",
        "cli.undo": "Eine frühere Umbenennung rückgängig machen",
        "cli.update": "Neueste Version von GitHub installieren",
        "cli.lang": "Sprache der Ausgabe (de/en)",
        "cli.workers": "Anzahl gleichzeitig geprüfter Dateien (Standard: automatisch)",
        "cli.need_folder": "Bitte einen ROM-Ordner angeben.",
        "cli.in_zip": "im ZIP",
        "cli.track": "Track",
        "cli.summary": "Zusammenfassung",
        "cli.report_saved": "Bericht gespeichert: {path}",
        "cli.preview_only": "Das war nur eine VORSCHAU. Mit --apply werden die Änderungen durchgeführt.",
        "cli.update_failed": "Update fehlgeschlagen: {error}",
        # Updater
        "upd.current": "RetroRenamer ist aktuell (Version {v}).",
        "upd.git": "Version {v} ist verfügbar. Dieser Ordner ist ein Git-Klon – bitte mit 'git pull' aktualisieren.",
        "upd.downloading": "Lade Version {v} herunter...",
        "upd.done": "Auf Version {v} aktualisiert ({n} Dateien). Bitte RetroRenamer neu starten.",
        "upd.notes": "Neu in dieser Version:",
        "upd.invalid": "Das heruntergeladene Paket ist kein gültiges RetroRenamer-Update.",
        "upd.no_asset": "Für Version {v} gibt es noch keine EXE-Datei. Bitte in ein paar Minuten erneut versuchen.",
        # Oberflaeche
        "gui.title": "RetroRenamer {v} – Erkennung anhand des ROM-Inhalts",
        "gui.rom_dir": "ROM-Ordner:",
        "gui.dat_dir": "DAT-Ordner:",
        "gui.browse": "Durchsuchen...",
        "gui.get_dats": "No-Intro-DATs (Webseite)",
        "gui.opt_recursive": "Unterordner einbeziehen",
        "gui.opt_sort": "In Ordner pro System sortieren",
        "gui.opt_unknown": "Unbekannte nach {dir}",
        "gui.opt_dups": "Duplikate nach {dir}",
        "gui.opt_zip": "Dateien in ZIPs umbenennen",
        "gui.scan": "1. Scannen (Vorschau)",
        "gui.apply": "2. Änderungen anwenden",
        "gui.undo": "Rückgängig machen...",
        "gui.report": "Bericht speichern (CSV)...",
        "gui.show": "Anzeigen:",
        "gui.filter_all": "Alle",
        "gui.filter_changes": "Nur Änderungen",
        "gui.updates": "Nach Updates suchen",
        "gui.language": "Sprache:",
        "gui.ready": "Bereit. ROM-Ordner wählen und auf „Scannen“ klicken.",
        "gui.in_zip": "im ZIP",
        "gui.plus_tracks": "+ {n} Track-Datei(en)",
        "gui.invalid_rom_dir": "Bitte einen gültigen ROM-Ordner wählen.",
        "gui.invalid_dat_dir": "DAT-Ordner nicht gefunden.",
        "gui.no_dats_title": "Keine DAT-Dateien",
        "gui.no_dats": ("Im DAT-Ordner liegen noch keine DAT-Dateien.\n\n"
                        "Ohne DAT-Dateien kann RetroRenamer keine Spiele erkennen. "
                        "Du bekommst sie kostenlos bei No-Intro (DAT-o-MATIC):\n\n"
                        "1. Auf der Seite „Request“ klicken und das ZIP-Paket herunterladen\n"
                        "2. Das ZIP unverändert in diesen Ordner legen:\n{path}\n\n"
                        "Download-Seite jetzt im Browser öffnen?"),
        "gui.preview_done": "Vorschau fertig – noch nichts geändert.",
        "gui.apply_title": "Änderungen anwenden",
        "gui.apply_confirm": ("{n} Dateien werden umbenannt/verschoben.\n"
                              "Eine Undo-Datei wird im ROM-Ordner angelegt.\n\nFortfahren?"),
        "gui.apply_finished": "Fertig. {errors} Fehler.\n\nRückgängig machen ist möglich mit:\n{path}",
        "gui.undo_pick": "Undo-Datei wählen",
        "gui.undo_title": "Rückgängig machen",
        "gui.undo_confirm": "Änderungen aus\n{path}\nrückgängig machen?",
        "gui.undo_ok": "Rückgängig gemacht.",
        "gui.undo_errors": "Rückgängig gemacht, aber mit {n} Fehlern.",
        "gui.report_saved": "Bericht gespeichert: {path}",
        "gui.error": "Fehler",
        "gui.unexpected": "Unerwarteter Fehler",
        "gui.update_title": "Update verfügbar",
        "gui.update_check_failed": "Update-Prüfung fehlgeschlagen:\n{error}",
        "gui.update_text": "Neue Version {v} verfügbar (installiert: {cur}).",
        "gui.update_new": "Neu:",
        "gui.update_question": "Jetzt herunterladen und installieren?\nDAT-Dateien und Einstellungen bleiben erhalten.",
        "gui.update_installed": "Version {v} installiert.",
        "gui.restart_title": "Update installiert",
        "gui.restart": "Das Update wurde installiert.\nRetroRenamer jetzt neu starten?",
        "gui.lang_restart": "Die Sprache wird nach einem Neustart vollständig übernommen.",
        "gui.redump_dats": "Redump-DATs laden...",
        # Redump-Download
        "redump.title": "Redump-DATs herunterladen (CD/DVD-Systeme)",
        "redump.intro": ("Wähle die Systeme aus, deren DAT-Dateien geladen werden sollen (Mehrfachauswahl per Klick).\n"
                         "Die Dateien kommen direkt von redump.org in deinen DAT-Ordner. Ältere Versionen werden ersetzt.\n"
                         "Um die Server zu schonen, wartet RetroRenamer zwischen zwei Downloads jeweils {s} Sekunden."),
        "redump.loading_list": "Lade Systemliste von redump.org...",
        "redump.fallback": "Die Systemliste konnte nicht von redump.org gelesen werden – es wird eine eingebaute Liste angezeigt.",
        "redump.download": "Herunterladen",
        "redump.cancel": "Abbrechen",
        "redump.none_selected": "Bitte mindestens ein System auswählen.",
        "redump.progress": "Lade Redump-DAT: {name}",
        "redump.done": "{ok} DAT-Dateien geladen, davon {current} schon aktuell. {failed} Fehler.",
        "redump.not_zip": "redump.org lieferte keine ZIP-Datei für '{code}'",
        "redump.list_header": "Verfügbare Redump-Systeme (Kürzel – Name):",
        "cli.redump": "Redump-DATs in den DAT-Ordner laden, z. B. psx,ps2 (Übersicht: --redump list)",
    },
    "en": {
        "status.OK": "OK",
        "status.RENAME": "RENAME",
        "status.UNKNOWN": "UNKNOWN",
        "status.DUPLICATE": "DUPLICATE",
        "status.MIXED": "MIXED",
        "status.ERROR": "ERROR",
        "dir.unknown": "_Unknown",
        "dir.duplicates": "_Duplicates",
        "dat.not_found": "DAT folder not found: {path}",
        "dat.loaded_cache": "{files} DAT files loaded from cache ({entries} ROM entries).",
        "dat.loaded": "{files} DAT files loaded ({entries} ROM entries).",
        "dat.loading": "Loading DAT files...",
        "dat.warn": "WARNING: DAT '{path}' could not be read: {error}",
        "dat.none": "No DAT entries found. Please put DAT files into '{path}' (see README).",
        "how.header16": "16-byte header ignored",
        "how.lynx": "Lynx header ignored",
        "how.a7800": "A7800 header ignored",
        "how.copier": "512-byte copier header ignored",
        "how.smd": "SMD format (interleaved)",
        "how.v64": "N64 byte-swapped (.v64)",
        "how.n64": "N64 little-endian (.n64)",
        "note.no_match": "No matching checksum in the DATs",
        "note.alternatives": "{n} other games with identical content",
        "note.too_big": "File larger than {mb} MB – skipped",
        "note.no7z": "7-Zip is not installed – {ext} archives cannot be read",
        "note.mixed": "Contains files from {n} different games",
        "note.dup_of": "Same game as: {path}",
        "note.cue_tracks": "CUE + {n} track file(s)",
        "note.cue_missing": "Files referenced by the CUE are missing: {files}",
        "note.cue_subdir": "CUE references files in other folders – not supported",
        "note.cue_partial": "Only {ok} of {total} tracks recognized",
        "note.target_exists": "Target already existed – number appended",
        "note.error": "Error: {error}",
        "note.zip_error": "Error while renaming inside ZIP: {error}",
        "note.inner_kept": "File inside the archive is not renamed ({ext})",
        "err.7z_read": "7-Zip could not read the archive",
        "apply.nothing": "Nothing to do.",
        "apply.done": "{done} files changed, {errors} errors. Undo file: {path}",
        "apply.error": "ERROR {path}: {error}",
        "undo.error": "ERROR while undoing ({path}): {error}",
        "undo.done": "Undone: {steps} steps, {errors} errors.",
        "undo.suffix": "_undone",
        "col.status": "Status",
        "col.file": "File",
        "col.current": "Current file",
        "col.new": "New name",
        "col.system": "System",
        "col.game": "Game",
        "col.note": "Note",
        "cli.description": "Identifies ROMs by their content and renames them using No-Intro / Redump DATs.",
        "cli.folder": "Folder containing the ROMs",
        "cli.dats": "Folder containing DAT files (default: ./dats)",
        "cli.apply": "Actually perform the changes (otherwise preview only)",
        "cli.no_recursive": "Do not scan subfolders",
        "cli.sort": "Sort into one folder per system",
        "cli.move_unknown": "Move unknown ROMs to {dir}",
        "cli.move_dups": "Move duplicates to {dir}",
        "cli.no_zip_inner": "Do not rename files inside ZIP archives",
        "cli.report": "Save a CSV report",
        "cli.undo": "Undo a previous run",
        "cli.update": "Install the latest version from GitHub",
        "cli.lang": "Output language (de/en)",
        "cli.workers": "Number of files checked in parallel (default: automatic)",
        "cli.need_folder": "Please specify a ROM folder.",
        "cli.in_zip": "in ZIP",
        "cli.track": "Track",
        "cli.summary": "Summary",
        "cli.report_saved": "Report saved: {path}",
        "cli.preview_only": "This was only a PREVIEW. Use --apply to perform the changes.",
        "cli.update_failed": "Update failed: {error}",
        "upd.current": "RetroRenamer is up to date (version {v}).",
        "upd.git": "Version {v} is available. This folder is a git clone – please update with 'git pull'.",
        "upd.downloading": "Downloading version {v}...",
        "upd.done": "Updated to version {v} ({n} files). Please restart RetroRenamer.",
        "upd.notes": "What's new:",
        "upd.invalid": "The downloaded package is not a valid RetroRenamer update.",
        "upd.no_asset": "There is no EXE file for version {v} yet. Please try again in a few minutes.",
        "gui.title": "RetroRenamer {v} – identifies ROMs by their content",
        "gui.rom_dir": "ROM folder:",
        "gui.dat_dir": "DAT folder:",
        "gui.browse": "Browse...",
        "gui.get_dats": "No-Intro DATs (website)",
        "gui.opt_recursive": "Include subfolders",
        "gui.opt_sort": "Sort into one folder per system",
        "gui.opt_unknown": "Move unknown to {dir}",
        "gui.opt_dups": "Move duplicates to {dir}",
        "gui.opt_zip": "Rename files inside ZIPs",
        "gui.scan": "1. Scan (preview)",
        "gui.apply": "2. Apply changes",
        "gui.undo": "Undo...",
        "gui.report": "Save report (CSV)...",
        "gui.show": "Show:",
        "gui.filter_all": "All",
        "gui.filter_changes": "Changes only",
        "gui.updates": "Check for updates",
        "gui.language": "Language:",
        "gui.ready": "Ready. Choose a ROM folder and click “Scan”.",
        "gui.in_zip": "in ZIP",
        "gui.plus_tracks": "+ {n} track file(s)",
        "gui.invalid_rom_dir": "Please choose a valid ROM folder.",
        "gui.invalid_dat_dir": "DAT folder not found.",
        "gui.no_dats_title": "No DAT files",
        "gui.no_dats": ("There are no DAT files in the DAT folder yet.\n\n"
                        "Without DAT files RetroRenamer cannot recognize any games. "
                        "You can get them for free from No-Intro (DAT-o-MATIC):\n\n"
                        "1. Click “Request” on the page and download the ZIP pack\n"
                        "2. Put the ZIP file, unchanged, into this folder:\n{path}\n\n"
                        "Open the download page in your browser now?"),
        "gui.preview_done": "Preview finished – nothing has been changed yet.",
        "gui.apply_title": "Apply changes",
        "gui.apply_confirm": ("{n} files will be renamed/moved.\n"
                              "An undo file will be created in the ROM folder.\n\nContinue?"),
        "gui.apply_finished": "Done. {errors} errors.\n\nYou can undo the changes with:\n{path}",
        "gui.undo_pick": "Choose undo file",
        "gui.undo_title": "Undo",
        "gui.undo_confirm": "Undo the changes from\n{path}\n?",
        "gui.undo_ok": "Changes undone.",
        "gui.undo_errors": "Undone, but with {n} errors.",
        "gui.report_saved": "Report saved: {path}",
        "gui.error": "Error",
        "gui.unexpected": "Unexpected error",
        "gui.update_title": "Update available",
        "gui.update_check_failed": "Could not check for updates:\n{error}",
        "gui.update_text": "New version {v} available (installed: {cur}).",
        "gui.update_new": "What's new:",
        "gui.update_question": "Download and install now?\nYour DAT files and settings are kept.",
        "gui.update_installed": "Version {v} installed.",
        "gui.restart_title": "Update installed",
        "gui.restart": "The update has been installed.\nRestart RetroRenamer now?",
        "gui.lang_restart": "The language will be fully applied after a restart.",
        "gui.redump_dats": "Get Redump DATs...",
        "redump.title": "Download Redump DATs (CD/DVD systems)",
        "redump.intro": ("Select the systems whose DAT files should be downloaded (click to select several).\n"
                         "The files are downloaded directly from redump.org into your DAT folder. Older versions are replaced.\n"
                         "To go easy on the servers, RetroRenamer waits {s} seconds between two downloads."),
        "redump.loading_list": "Loading system list from redump.org...",
        "redump.fallback": "The system list could not be read from redump.org – showing a built-in list instead.",
        "redump.download": "Download",
        "redump.cancel": "Cancel",
        "redump.none_selected": "Please select at least one system.",
        "redump.progress": "Downloading Redump DAT: {name}",
        "redump.done": "{ok} DAT files downloaded, {current} of them already up to date. {failed} errors.",
        "redump.not_zip": "redump.org did not return a ZIP file for '{code}'",
        "redump.list_header": "Available Redump systems (code – name):",
        "cli.redump": "Download Redump DATs into the DAT folder, e.g. psx,ps2 (overview: --redump list)",
    },
}


def detect_language():
    """'de' fuer deutschsprachige Systeme, sonst 'en'."""
    name = ""
    try:
        if sys.platform == "win32":
            import ctypes
            name = locale.windows_locale.get(ctypes.windll.kernel32.GetUserDefaultUILanguage(), "")
        if not name:
            name = os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or ""
        if not name:
            name = locale.getlocale()[0] or ""
    except Exception:
        pass
    return "de" if name.lower().startswith("de") else "en"


_lang = detect_language()


def set_language(lang):
    global _lang
    _lang = lang if lang in STRINGS else "en"


def get_language():
    return _lang


def tr(key, **kw):
    s = STRINGS[_lang].get(key) or STRINGS["en"].get(key) or key
    return s.format(**kw) if kw else s


def all_translations(key):
    """Alle Uebersetzungen eines Schluessels (z. B. um Sonderordner in jeder Sprache zu erkennen)."""
    return {STRINGS[lang][key] for lang in STRINGS if key in STRINGS[lang]}
