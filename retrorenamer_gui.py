#!/usr/bin/env python3
"""Grafische Oberflaeche fuer retrorenamer.py"""

import json
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import retrorenamer as rn
import updater

SETTINGS = os.path.join(rn.SCRIPT_DIR, "retrorenamer_settings.json")

STATUS_COLORS = {
    rn.ST_OK: "#2e7d32",
    rn.ST_RENAME: "#1565c0",
    rn.ST_UNKNOWN: "#c62828",
    rn.ST_DUP: "#ef6c00",
    rn.ST_MIXED: "#6a1b9a",
    rn.ST_ERROR: "#c62828",
}


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"RetroRenamer {rn.VERSION} - Erkennung anhand des ROM-Inhalts")
        self.geometry("1200x720")
        self.minsize(900, 500)
        self.q = queue.Queue()
        self.items = []
        self.index = None
        self.index_dir = None
        self.busy = False

        s = self._load_settings()
        self.rom_dir = tk.StringVar(value=s.get("rom_dir", ""))
        self.dat_dir = tk.StringVar(value=s.get("dat_dir", rn.DEFAULT_DAT_DIR))
        self.recursive = tk.BooleanVar(value=s.get("recursive", True))
        self.sort = tk.BooleanVar(value=s.get("sort", False))
        self.move_unknown = tk.BooleanVar(value=s.get("move_unknown", False))
        self.move_dups = tk.BooleanVar(value=s.get("move_dups", False))
        self.zip_inner = tk.BooleanVar(value=s.get("zip_inner", True))
        self.filter = tk.StringVar(value="Alle")

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)
        self.after(1500, lambda: self.check_update(silent=True))

    # ---------------- Aufbau ----------------
    def _build(self):
        pad = {"padx": 6, "pady": 3}
        top = ttk.Frame(self)
        top.pack(fill="x", padx=8, pady=6)
        for row, (label, var) in enumerate((("ROM-Ordner:", self.rom_dir), ("DAT-Ordner:", self.dat_dir))):
            ttk.Label(top, text=label).grid(row=row, column=0, sticky="w", **pad)
            ttk.Entry(top, textvariable=var).grid(row=row, column=1, sticky="ew", **pad)
            ttk.Button(top, text="Durchsuchen...", command=lambda v=var: self._pick(v)).grid(row=row, column=2, **pad)
        top.columnconfigure(1, weight=1)

        opts = ttk.Frame(self)
        opts.pack(fill="x", padx=8)
        for text, var in (("Unterordner einbeziehen", self.recursive),
                          ("In Ordner pro System sortieren", self.sort),
                          (f"Unbekannte nach {rn.UNKNOWN_DIRNAME}", self.move_unknown),
                          (f"Duplikate nach {rn.DUP_DIRNAME}", self.move_dups),
                          ("Dateien in ZIPs umbenennen", self.zip_inner)):
            ttk.Checkbutton(opts, text=text, variable=var).pack(side="left", padx=6)

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=8, pady=6)
        self.btn_scan = ttk.Button(btns, text="1. Scannen (Vorschau)", command=self.do_scan)
        self.btn_apply = ttk.Button(btns, text="2. Änderungen anwenden", command=self.do_apply, state="disabled")
        self.btn_undo = ttk.Button(btns, text="Rückgängig machen...", command=self.do_undo)
        self.btn_report = ttk.Button(btns, text="Bericht speichern (CSV)...", command=self.do_report, state="disabled")
        for b in (self.btn_scan, self.btn_apply, self.btn_undo, self.btn_report):
            b.pack(side="left", padx=4)
        ttk.Label(btns, text="Anzeigen:").pack(side="left", padx=(20, 4))
        cb = ttk.Combobox(btns, textvariable=self.filter, state="readonly", width=14,
                          values=["Alle", "Nur Änderungen", rn.ST_RENAME, rn.ST_OK, rn.ST_UNKNOWN,
                                  rn.ST_DUP, rn.ST_MIXED, rn.ST_ERROR])
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._fill())
        ttk.Button(btns, text="Nach Updates suchen", command=lambda: self.check_update(silent=False)) \
            .pack(side="right", padx=4)

        frame = ttk.Frame(self)
        frame.pack(fill="both", expand=True, padx=8)
        cols = ("status", "alt", "neu", "system", "info")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, t, w in (("status", "Status", 95), ("alt", "Aktuelle Datei", 300), ("neu", "Neuer Name", 330),
                        ("system", "System", 200), ("info", "Hinweis", 260)):
            self.tree.heading(c, text=t)
            self.tree.column(c, width=w, stretch=c != "status")
        for st, col in STATUS_COLORS.items():
            self.tree.tag_configure(st, foreground=col)
        ys = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        xs = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=8, pady=6)
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x")
        self.status = tk.StringVar(value="Bereit. ROM-Ordner wählen und auf 'Scannen' klicken.")
        ttk.Label(bottom, textvariable=self.status).pack(fill="x", pady=(4, 0))

    def report_callback_exception(self, exc, val, tb):
        # Unter pythonw gibt es keine Konsole - Fehler sonst unsichtbar
        import traceback
        messagebox.showerror("Unerwarteter Fehler", "".join(traceback.format_exception(exc, val, tb))[-2000:])

    def _pick(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or None)
        if d:
            var.set(os.path.normpath(d))

    # ---------------- Einstellungen ----------------
    def _load_settings(self):
        try:
            with open(SETTINGS, encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _close(self):
        try:
            with open(SETTINGS, "w", encoding="utf-8") as f:
                json.dump({"rom_dir": self.rom_dir.get(), "dat_dir": self.dat_dir.get(),
                           "recursive": self.recursive.get(), "sort": self.sort.get(),
                           "move_unknown": self.move_unknown.get(), "move_dups": self.move_dups.get(),
                           "zip_inner": self.zip_inner.get()}, f, indent=2)
        except OSError:
            pass
        self.destroy()

    # ---------------- Hintergrund-Aufgaben ----------------
    def _run(self, func):
        self.busy = True
        for b in (self.btn_scan, self.btn_apply, self.btn_undo, self.btn_report):
            b.configure(state="disabled")

        def worker():
            try:
                func()
            except Exception as ex:
                self.q.put(("error", str(ex)))
            finally:
                self.q.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def _log(self, msg):
        self.q.put(("status", msg))

    def _progress(self, i, n, name):
        self.q.put(("progress", (i, n, name)))

    def _poll(self):
        try:
            while True:
                kind, val = self.q.get_nowait()
                if kind == "status":
                    self.status.set(val)
                elif kind == "progress":
                    i, n, name = val
                    self.progress.configure(maximum=max(n, 1), value=i)
                    if name:
                        self.status.set(f"[{i}/{n}] {name}")
                elif kind == "error":
                    messagebox.showerror("Fehler", val)
                elif kind == "fill":
                    self._fill()
                elif kind == "update":
                    self._offer_update(*val)
                elif kind == "restart":
                    self._restart()
                elif kind == "info":
                    messagebox.showinfo("RetroRenamer", val)
                elif kind == "done":
                    self.busy = False
                    self.btn_scan.configure(state="normal")
                    self.btn_undo.configure(state="normal")
                    has_items = bool(self.items)
                    self.btn_report.configure(state="normal" if has_items else "disabled")
                    todo = any(it.dst or it.inner for it in self.items)
                    self.btn_apply.configure(state="normal" if todo else "disabled")
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _scan_options(self):
        return rn.Options(recursive=self.recursive.get(), sort_by_system=self.sort.get(),
                          move_unknown=self.move_unknown.get(), move_duplicates=self.move_dups.get(),
                          rename_in_zip=self.zip_inner.get())

    # ---------------- Aktionen ----------------
    def do_scan(self):
        root, dat = self.rom_dir.get().strip(), self.dat_dir.get().strip()
        if not os.path.isdir(root):
            messagebox.showwarning("RetroRenamer", "Bitte einen gültigen ROM-Ordner wählen.")
            return
        if not os.path.isdir(dat):
            messagebox.showwarning("RetroRenamer", "DAT-Ordner nicht gefunden. Siehe README.md.")
            return
        opts = self._scan_options()
        self.items = []
        self._fill()

        def job():
            self._log("Lade DAT-Dateien...")
            self.index = rn.load_dats(dat, log=self._log)
            if not len(self.index):
                self.q.put(("error", "Im DAT-Ordner wurden keine DAT-Dateien gefunden.\n"
                                     "Bitte No-Intro-DATs herunterladen (siehe README.md)."))
                return
            self.items = rn.scan(root, self.index, opts, self._progress, self._log)
            self.q.put(("fill", None))
            counts = rn.summarize(self.items)
            self._log("Vorschau fertig - noch nichts geändert.  " +
                      "  ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
        self._run(job)

    def do_apply(self):
        n = sum(1 for it in self.items if it.dst or it.inner)
        if not messagebox.askyesno("Änderungen anwenden",
                                   f"{n} Dateien werden umbenannt/verschoben.\n"
                                   "Eine Undo-Datei wird im ROM-Ordner angelegt.\n\nFortfahren?"):
            return
        root = self.rom_dir.get().strip()

        def job():
            undo_path, errors = rn.apply_plan(self.items, root, self._progress, self._log)
            self.items = []
            self.q.put(("fill", None))
            self.q.put(("info", f"Fertig. {errors} Fehler.\n\nRückgängig machen ist möglich mit:\n{undo_path}"))
        self._run(job)

    def do_undo(self):
        path = filedialog.askopenfilename(initialdir=self.rom_dir.get() or None, title="Undo-Datei wählen",
                                          filetypes=[("RetroRenamer Undo", "retrorenamer_undo_*.csv romnamer_undo_*.csv"), ("CSV", "*.csv")])
        if not path or not messagebox.askyesno("Rückgängig", f"Änderungen aus\n{path}\nrückgängig machen?"):
            return

        def job():
            errors = rn.undo(path, log=self._log)
            self.q.put(("info", "Rückgängig gemacht." if not errors else f"Rückgängig mit {errors} Fehlern."))
        self._run(job)

    # ---------------- Updates ----------------
    def check_update(self, silent):
        """Fragt im Hintergrund GitHub nach einer neueren Version. silent=True: nur melden, wenn es eine gibt."""
        def job():
            try:
                version, zip_url, notes, page = updater.check_latest()
            except Exception as ex:
                if not silent:
                    self.q.put(("error", f"Update-Prüfung fehlgeschlagen:\n{ex}"))
                return
            if updater.is_newer(version, rn.VERSION):
                self.q.put(("update", (version, zip_url, notes, page)))
            elif not silent:
                self.q.put(("info", f"RetroRenamer ist aktuell (Version {rn.VERSION})."))
        threading.Thread(target=job, daemon=True).start()

    def _offer_update(self, version, zip_url, notes, page):
        if updater.is_git_checkout():
            messagebox.showinfo("Update verfügbar", f"Version {version} ist verfügbar.\n\n"
                                "Dieser Ordner ist ein Git-Klon. Bitte mit 'git pull' aktualisieren.")
            return
        text = f"Neue Version {version} verfügbar (installiert: {rn.VERSION})."
        if notes:
            text += "\n\nNeu:\n" + notes[:1200]
        text += "\n\nJetzt herunterladen und installieren?\nDAT-Dateien und Einstellungen bleiben erhalten."
        if self.busy or not messagebox.askyesno("Update verfügbar", text):
            return

        def job():
            self._log(f"Lade Version {version} herunter...")
            updater.install_from_zip(updater._get(zip_url, timeout=60))
            self._log(f"Version {version} installiert.")
            self.q.put(("restart", None))
        self._run(job)

    def _restart(self):
        if messagebox.askyesno("Update installiert", "Das Update wurde installiert.\nRetroRenamer jetzt neu starten?"):
            self._close()
            subprocess.Popen([sys.executable, os.path.abspath(__file__)], cwd=rn.SCRIPT_DIR)

    def do_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="retrorenamer_bericht.csv")
        if path:
            rn.write_report(self.items, path, self.rom_dir.get().strip())
            self.status.set(f"Bericht gespeichert: {path}")

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        root = self.rom_dir.get().strip()
        f = self.filter.get()
        for it in self.items:
            if f == "Nur Änderungen" and not (it.dst or it.inner):
                continue
            if f not in ("Alle", "Nur Änderungen") and it.status != f:
                continue
            new = os.path.relpath(it.dst, root) if it.dst else ""
            if it.inner:
                inner = ", ".join(f"{o} → {n}" for o, n in it.inner)
                new = (new + "  " if new else "") + f"[im ZIP: {inner}]"
            self.tree.insert("", "end", values=(it.status, os.path.relpath(it.src, root), new,
                                                it.system, it.note), tags=(it.status,))


if __name__ == "__main__":
    App().mainloop()
