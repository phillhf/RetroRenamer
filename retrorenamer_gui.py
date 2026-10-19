#!/usr/bin/env python3
"""Grafische Oberflaeche fuer retrorenamer.py"""

import json
import os
import queue
import subprocess
import sys
import threading
import traceback
import webbrowser
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import i18n
from i18n import tr
import retrorenamer as rn
import updater

SETTINGS = os.path.join(rn.SCRIPT_DIR, "retrorenamer_settings.json")
DAT_DOWNLOAD_URL = "https://datomatic.no-intro.org/index.php?page=download&s=64&op=daily"

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
        updater.cleanup_old_executables()
        self.geometry("1250x720")
        self.minsize(950, 500)
        self.q = queue.Queue()
        self.items = []
        self.busy = False

        s = self._load_settings()
        if s.get("lang") in i18n.LANGUAGES:
            i18n.set_language(s["lang"])
        self.rom_dir = tk.StringVar(value=s.get("rom_dir", ""))
        self.dat_dir = tk.StringVar(value=s.get("dat_dir", rn.DEFAULT_DAT_DIR))
        self.recursive = tk.BooleanVar(value=s.get("recursive", True))
        self.sort = tk.BooleanVar(value=s.get("sort", False))
        self.move_unknown = tk.BooleanVar(value=s.get("move_unknown", False))
        self.move_dups = tk.BooleanVar(value=s.get("move_dups", False))
        self.zip_inner = tk.BooleanVar(value=s.get("zip_inner", True))
        self.filter = tk.StringVar()
        self.lang = tk.StringVar(value=i18n.LANGUAGES[i18n.get_language()])
        if not os.path.isdir(rn.DEFAULT_DAT_DIR):
            try:
                os.makedirs(rn.DEFAULT_DAT_DIR)
            except OSError:
                pass

        self._build()
        self.protocol("WM_DELETE_WINDOW", self._close)
        self.after(100, self._poll)
        self.after(1500, lambda: self.check_update(silent=True))

    def report_callback_exception(self, exc, val, tb):
        # Ohne Konsole (pythonw / EXE) waeren Fehler sonst unsichtbar
        messagebox.showerror(tr("gui.unexpected"), "".join(traceback.format_exception(exc, val, tb))[-2000:])

    # ---------------- Aufbau ----------------
    def _build(self):
        self.title(tr("gui.title", v=rn.VERSION))
        self.filter_values = [tr("gui.filter_all"), tr("gui.filter_changes")] + \
            [rn.status_text(s) for s in rn.STATUSES]
        self.filter.set(self.filter_values[0])
        pad = {"padx": 6, "pady": 3}

        self.frame = ttk.Frame(self)
        self.frame.pack(fill="both", expand=True)
        top = ttk.Frame(self.frame)
        top.pack(fill="x", padx=8, pady=6)
        for row, (label, var) in enumerate(((tr("gui.rom_dir"), self.rom_dir), (tr("gui.dat_dir"), self.dat_dir))):
            ttk.Label(top, text=label).grid(row=row, column=0, sticky="w", **pad)
            ttk.Entry(top, textvariable=var).grid(row=row, column=1, sticky="ew", **pad)
            ttk.Button(top, text=tr("gui.browse"), command=lambda v=var: self._pick(v)).grid(row=row, column=2, **pad)
        ttk.Button(top, text=tr("gui.get_dats"), command=self._open_dat_page).grid(row=1, column=3, **pad)
        top.columnconfigure(1, weight=1)

        opts = ttk.Frame(self.frame)
        opts.pack(fill="x", padx=8)
        for text, var in ((tr("gui.opt_recursive"), self.recursive),
                          (tr("gui.opt_sort"), self.sort),
                          (tr("gui.opt_unknown", dir=rn.unknown_dirname()), self.move_unknown),
                          (tr("gui.opt_dups", dir=rn.dup_dirname()), self.move_dups),
                          (tr("gui.opt_zip"), self.zip_inner)):
            ttk.Checkbutton(opts, text=text, variable=var).pack(side="left", padx=6)
        lang_cb = ttk.Combobox(opts, textvariable=self.lang, state="readonly", width=9,
                               values=list(i18n.LANGUAGES.values()))
        lang_cb.pack(side="right", padx=4)
        lang_cb.bind("<<ComboboxSelected>>", lambda e: self._change_language())
        ttk.Label(opts, text=tr("gui.language")).pack(side="right")

        btns = ttk.Frame(self.frame)
        btns.pack(fill="x", padx=8, pady=6)
        self.btn_scan = ttk.Button(btns, text=tr("gui.scan"), command=self.do_scan)
        self.btn_apply = ttk.Button(btns, text=tr("gui.apply"), command=self.do_apply)
        self.btn_undo = ttk.Button(btns, text=tr("gui.undo"), command=self.do_undo)
        self.btn_report = ttk.Button(btns, text=tr("gui.report"), command=self.do_report)
        for b in (self.btn_scan, self.btn_apply, self.btn_undo, self.btn_report):
            b.pack(side="left", padx=4)
        ttk.Label(btns, text=tr("gui.show")).pack(side="left", padx=(20, 4))
        cb = ttk.Combobox(btns, textvariable=self.filter, state="readonly", width=16, values=self.filter_values)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._fill())
        self.btn_update = ttk.Button(btns, text=tr("gui.updates"), command=lambda: self.check_update(silent=False))
        self.btn_update.pack(side="right", padx=4)

        frame = ttk.Frame(self.frame)
        frame.pack(fill="both", expand=True, padx=8)
        cols = ("status", "alt", "neu", "system", "info")
        self.tree = ttk.Treeview(frame, columns=cols, show="headings")
        for c, key, w in (("status", "col.status", 95), ("alt", "col.current", 300), ("neu", "col.new", 340),
                          ("system", "col.system", 220), ("info", "col.note", 260)):
            self.tree.heading(c, text=tr(key))
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

        bottom = ttk.Frame(self.frame)
        bottom.pack(fill="x", padx=8, pady=6)
        self.progress = ttk.Progressbar(bottom, mode="determinate")
        self.progress.pack(fill="x")
        self.status = tk.StringVar(value=tr("gui.ready"))
        ttk.Label(bottom, textvariable=self.status).pack(fill="x", pady=(4, 0))
        self._update_buttons()
        self._fill()

    def _change_language(self):
        code = next(k for k, v in i18n.LANGUAGES.items() if v == self.lang.get())
        if code == i18n.get_language():
            return
        i18n.set_language(code)
        self.frame.destroy()
        self._build()

    def _pick(self, var):
        d = filedialog.askdirectory(initialdir=var.get() or None)
        if d:
            var.set(os.path.normpath(d))

    def _open_dat_page(self):
        webbrowser.open(DAT_DOWNLOAD_URL)
        dat = self.dat_dir.get().strip()
        if os.path.isdir(dat):
            self._open_folder(dat)

    @staticmethod
    def _open_folder(path):
        try:
            if sys.platform == "win32":
                os.startfile(path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", path])
            else:
                subprocess.Popen(["xdg-open", path])
        except Exception:
            pass

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
                           "zip_inner": self.zip_inner.get(), "lang": i18n.get_language()}, f, indent=2)
        except OSError:
            pass
        self.destroy()

    # ---------------- Hintergrund-Aufgaben ----------------
    def _update_buttons(self):
        idle = "disabled" if self.busy else "normal"
        for b in (self.btn_scan, self.btn_undo, self.btn_update):
            b.configure(state=idle)
        self.btn_report.configure(state="normal" if self.items and not self.busy else "disabled")
        todo = any(it.has_changes for it in self.items)
        self.btn_apply.configure(state="normal" if todo and not self.busy else "disabled")

    def _run(self, func):
        self.busy = True
        self._update_buttons()

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
                    messagebox.showerror(tr("gui.error"), val)
                elif kind == "fill":
                    self._fill()
                elif kind == "update":
                    self._offer_update(val)
                elif kind == "restart":
                    self._restart()
                elif kind == "info":
                    messagebox.showinfo("RetroRenamer", val)
                elif kind == "done":
                    self.busy = False
                    self._update_buttons()
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
            messagebox.showwarning("RetroRenamer", tr("gui.invalid_rom_dir"))
            return
        if not os.path.isdir(dat):
            messagebox.showwarning("RetroRenamer", tr("gui.invalid_dat_dir"))
            return
        if not rn.has_dat_files(dat):
            if messagebox.askyesno(tr("gui.no_dats_title"), tr("gui.no_dats", path=dat)):
                self._open_dat_page()
            return
        opts = self._scan_options()
        self.items = []
        self._fill()

        def job():
            self._log(tr("dat.loading"))
            index = rn.load_dats(dat, log=self._log)
            if not len(index):
                self.q.put(("error", tr("dat.none", path=dat)))
                return
            self.items = rn.scan(root, index, opts, self._progress, self._log)
            self.q.put(("fill", None))
            self._log(tr("gui.preview_done") + "  " + rn.summary_text(self.items))
        self._run(job)

    def do_apply(self):
        n = sum(1 for it in self.items if it.has_changes)
        if not messagebox.askyesno(tr("gui.apply_title"), tr("gui.apply_confirm", n=n)):
            return
        root = self.rom_dir.get().strip()

        def job():
            undo_path, errors = rn.apply_plan(self.items, root, self._progress, self._log)
            self.items = []
            self.q.put(("fill", None))
            self.q.put(("info", tr("gui.apply_finished", errors=errors, path=undo_path)))
        self._run(job)

    def do_undo(self):
        path = filedialog.askopenfilename(initialdir=self.rom_dir.get() or None, title=tr("gui.undo_pick"),
                                          filetypes=[("RetroRenamer Undo", "retrorenamer_undo_*.csv romnamer_undo_*.csv"),
                                                     ("CSV", "*.csv")])
        if not path or not messagebox.askyesno(tr("gui.undo_title"), tr("gui.undo_confirm", path=path)):
            return

        def job():
            errors = rn.undo(path, log=self._log)
            self.q.put(("info", tr("gui.undo_ok") if not errors else tr("gui.undo_errors", n=errors)))
        self._run(job)

    def do_report(self):
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="retrorenamer_report.csv")
        if path:
            rn.write_report(self.items, path, self.rom_dir.get().strip())
            self.status.set(tr("gui.report_saved", path=path))

    # ---------------- Updates ----------------
    def check_update(self, silent):
        """Fragt im Hintergrund GitHub nach einer neueren Version. silent=True: nur melden, wenn es eine gibt."""
        def job():
            try:
                info = updater.check_latest()
            except Exception as ex:
                if not silent:
                    self.q.put(("error", tr("gui.update_check_failed", error=ex)))
                return
            if updater.is_newer(info["version"], rn.VERSION):
                self.q.put(("update", info))
            elif not silent:
                self.q.put(("info", tr("upd.current", v=rn.VERSION)))
        threading.Thread(target=job, daemon=True).start()

    def _offer_update(self, info):
        reason = updater.update_possible(info)
        if reason:
            messagebox.showinfo(tr("gui.update_title"), reason)
            return
        text = tr("gui.update_text", v=info["version"], cur=rn.VERSION)
        if info["notes"]:
            text += f"\n\n{tr('gui.update_new')}\n{info['notes'][:1200]}"
        text += "\n\n" + tr("gui.update_question")
        if self.busy or not messagebox.askyesno(tr("gui.update_title"), text):
            return

        def job():
            self._log(tr("upd.downloading", v=info["version"]))
            updater.install(info)
            self._log(tr("gui.update_installed", v=info["version"]))
            self.q.put(("restart", None))
        self._run(job)

    def _restart(self):
        if messagebox.askyesno(tr("gui.restart_title"), tr("gui.restart")):
            self._close()
            if updater.FROZEN:
                subprocess.Popen([sys.executable], cwd=rn.SCRIPT_DIR)
            else:
                subprocess.Popen([sys.executable, os.path.abspath(__file__)], cwd=rn.SCRIPT_DIR)

    def _fill(self):
        self.tree.delete(*self.tree.get_children())
        root = self.rom_dir.get().strip()
        f = self.filter.get()
        status_by_text = {rn.status_text(s): s for s in rn.STATUSES}
        for it in self.items:
            if f == tr("gui.filter_changes") and not it.has_changes:
                continue
            if f in status_by_text and it.status != status_by_text[f]:
                continue
            new = os.path.relpath(it.dst, root) if it.dst else ""
            if it.inner:
                inner = ", ".join(f"{o} → {n}" for o, n in it.inner)
                new = (new + "  " if new else "") + f"[{tr('gui.in_zip')}: {inner}]"
            moved = sum(1 for c in it.companions if c[2])
            if moved:
                new = (new + "  " if new else "") + tr("gui.plus_tracks", n=moved)
            self.tree.insert("", "end", values=(it.status_text, os.path.relpath(it.src, root), new,
                                                it.system, it.note), tags=(it.status,))


if __name__ == "__main__":
    App().mainloop()
