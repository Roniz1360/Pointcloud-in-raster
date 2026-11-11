"""Einfache Windows-Oberflaeche (tkinter). Die Punktwolke wird NICHT dargestellt."""
from __future__ import annotations

import os
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .core import METHODS, Cancelled, ThinSettings, default_output_path, thin_file


def _num(var: tk.StringVar, name: str, allow_empty=False):
    t = var.get().strip().replace(",", ".")
    if not t:
        if allow_empty:
            return None
        raise ValueError(f"{name}: Wert fehlt")
    try:
        return float(t)
    except ValueError:
        raise ValueError(f"{name}: keine gueltige Zahl ({t})") from None


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(f"LasRasterThin {__version__} – Punktwolke auf Raster ausdünnen")
        self.minsize(720, 560)
        self.files: list[str] = []
        self.q: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.cancel_flag = threading.Event()
        self._build()
        self.after(100, self._poll)

    # ---------------- Aufbau ----------------
    def _build(self):
        pad = dict(padx=6, pady=4)
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)

        # Dateien
        f1 = ttk.LabelFrame(root, text="1. Eingabe (LAS / LAZ)")
        f1.pack(fill="both", expand=False, **pad)
        self.lst = tk.Listbox(f1, height=6, selectmode="extended")
        self.lst.grid(row=0, column=0, rowspan=3, sticky="nsew", **pad)
        f1.columnconfigure(0, weight=1)
        ttk.Button(f1, text="Dateien hinzufügen…", command=self._add).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(f1, text="Ordner hinzufügen…", command=self._add_dir).grid(row=1, column=1, sticky="ew", **pad)
        ttk.Button(f1, text="Entfernen", command=self._remove).grid(row=2, column=1, sticky="ew", **pad)

        # Raster
        f2 = ttk.LabelFrame(root, text="2. Raster")
        f2.pack(fill="x", **pad)
        self.v_cx = tk.StringVar(value="0.10")
        self.v_cy = tk.StringVar(value="")
        self.v_cz = tk.StringVar(value="")
        self.v_ox = tk.StringVar(value="")
        self.v_oy = tk.StringVar(value="")
        self.v_oz = tk.StringVar(value="")
        rows = [
            ("Zellgrösse X [m]", self.v_cx, "Pflicht"),
            ("Zellgrösse Y [m]", self.v_cy, "leer = wie X"),
            ("Zellgrösse Z [m]", self.v_cz, "leer = 2D-Raster, Wert = 3D-Voxel (z. B. Tunnel)"),
            ("Ursprung X0", self.v_ox, "leer = automatisch"),
            ("Ursprung Y0", self.v_oy, "leer = automatisch"),
            ("Ursprung Z0", self.v_oz, "leer = automatisch"),
        ]
        for r, (lbl, var, hint) in enumerate(rows):
            ttk.Label(f2, text=lbl).grid(row=r, column=0, sticky="w", **pad)
            ttk.Entry(f2, textvariable=var, width=14).grid(row=r, column=1, sticky="w", **pad)
            ttk.Label(f2, text=hint, foreground="#666").grid(row=r, column=2, sticky="w", **pad)
        ttk.Label(f2, text="Punkt pro Zelle").grid(row=6, column=0, sticky="w", **pad)
        self.v_method = tk.StringVar(value=METHODS["center"])
        ttk.Combobox(f2, textvariable=self.v_method, values=list(METHODS.values()),
                     state="readonly", width=28).grid(row=6, column=1, columnspan=2, sticky="w", **pad)

        # Ausgabe
        f3 = ttk.LabelFrame(root, text="3. Ausgabe")
        f3.pack(fill="x", **pad)
        self.v_out = tk.StringVar(value="")
        ttk.Label(f3, text="Ordner").grid(row=0, column=0, sticky="w", **pad)
        ttk.Entry(f3, textvariable=self.v_out).grid(row=0, column=1, sticky="ew", **pad)
        ttk.Button(f3, text="…", width=3, command=self._pick_out).grid(row=0, column=2, **pad)
        f3.columnconfigure(1, weight=1)
        ttk.Label(f3, text="leer = gleicher Ordner wie Eingabe", foreground="#666").grid(
            row=1, column=1, sticky="w", padx=6)
        self.v_fmt = tk.StringVar(value="Wie Eingabe")
        ttk.Label(f3, text="Format").grid(row=2, column=0, sticky="w", **pad)
        ttk.Combobox(f3, textvariable=self.v_fmt, values=["Wie Eingabe", "LAS", "LAZ"],
                     state="readonly", width=14).grid(row=2, column=1, sticky="w", **pad)
        self.v_chunk = tk.StringVar(value="1000000")
        ttk.Label(f3, text="Punkte pro Block").grid(row=3, column=0, sticky="w", **pad)
        ttk.Entry(f3, textvariable=self.v_chunk, width=14).grid(row=3, column=1, sticky="w", **pad)
        ttk.Label(f3, text="kleiner = weniger Arbeitsspeicher (RAM)", foreground="#666").grid(
            row=3, column=2, sticky="w", **pad)

        # Start
        f4 = ttk.Frame(root)
        f4.pack(fill="both", expand=True, **pad)
        bar = ttk.Frame(f4)
        bar.pack(fill="x")
        self.btn_start = ttk.Button(bar, text="Start", command=self._start)
        self.btn_start.pack(side="left")
        self.btn_cancel = ttk.Button(bar, text="Abbrechen", command=self._cancel, state="disabled")
        self.btn_cancel.pack(side="left", padx=6)
        self.pb = ttk.Progressbar(bar, maximum=1000)
        self.pb.pack(side="left", fill="x", expand=True, padx=6)
        self.lbl = ttk.Label(f4, text="Bereit.")
        self.lbl.pack(fill="x", pady=4)
        self.log = tk.Text(f4, height=8, state="disabled")
        self.log.pack(fill="both", expand=True)

    # ---------------- Aktionen ----------------
    def _add(self):
        fs = filedialog.askopenfilenames(
            title="LAS/LAZ wählen", filetypes=[("Punktwolken", "*.las *.laz"), ("Alle", "*.*")])
        self._add_files(fs)

    def _add_dir(self):
        d = filedialog.askdirectory(title="Ordner mit LAS/LAZ wählen")
        if d:
            fs = [os.path.join(d, f) for f in sorted(os.listdir(d))
                  if f.lower().endswith((".las", ".laz"))]
            self._add_files(fs)

    def _add_files(self, fs):
        for f in fs:
            if f not in self.files:
                self.files.append(f)
                self.lst.insert("end", f)

    def _remove(self):
        for i in reversed(self.lst.curselection()):
            self.lst.delete(i)
            del self.files[i]

    def _pick_out(self):
        d = filedialog.askdirectory(title="Ausgabeordner wählen")
        if d:
            self.v_out.set(d)

    def _write(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _settings(self) -> ThinSettings:
        cx = _num(self.v_cx, "Zellgrösse X")
        cy = _num(self.v_cy, "Zellgrösse Y", True) or cx
        method = {v: k for k, v in METHODS.items()}[self.v_method.get()]
        s = ThinSettings(
            cell_x=cx, cell_y=cy, cell_z=_num(self.v_cz, "Zellgrösse Z", True),
            origin_x=_num(self.v_ox, "Ursprung X0", True),
            origin_y=_num(self.v_oy, "Ursprung Y0", True),
            origin_z=_num(self.v_oz, "Ursprung Z0", True),
            method=method, chunk_size=int(_num(self.v_chunk, "Punkte pro Block")),
        )
        s.validate()
        return s

    def _start(self):
        if not self.files:
            messagebox.showwarning("Hinweis", "Bitte zuerst LAS/LAZ-Dateien hinzufügen.")
            return
        try:
            s = self._settings()
        except ValueError as e:
            messagebox.showerror("Eingabefehler", str(e))
            return
        out_dir = self.v_out.get().strip() or None
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        fmt = {"Wie Eingabe": None, "LAS": False, "LAZ": True}[self.v_fmt.get()]
        jobs = [(f, default_output_path(f, out_dir, s, fmt)) for f in self.files]
        self.cancel_flag.clear()
        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.worker = threading.Thread(target=self._run, args=(jobs, s), daemon=True)
        self.worker.start()

    def _cancel(self):
        self.cancel_flag.set()
        self.lbl.configure(text="Wird abgebrochen…")

    def _run(self, jobs, s):
        n = len(jobs)
        for i, (src, dst) in enumerate(jobs):
            self.q.put(("log", f"[{i + 1}/{n}] {os.path.basename(src)} → {dst}"))

            def prog(frac, msg, i=i):
                self.q.put(("prog", (i + frac) / n, f"[{i + 1}/{n}] {msg}"))
            try:
                r = thin_file(src, dst, s, prog, self.cancel_flag.is_set)
                for m in r.messages:
                    self.q.put(("log", "    " + m))
                self.q.put(("log", f"    {r.points_in:,} → {r.points_out:,} Punkte "
                                   f"({100 * r.ratio:.1f} %), {r.seconds:.1f} s"))
            except Cancelled:
                self.q.put(("log", "    Abgebrochen."))
                break
            except Exception as e:  # noqa: BLE001
                self.q.put(("log", f"    FEHLER: {e}"))
        self.q.put(("done",))

    def _poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                if item[0] == "log":
                    self._write(item[1])
                elif item[0] == "prog":
                    self.pb["value"] = item[1] * 1000
                    self.lbl.configure(text=item[2])
                elif item[0] == "done":
                    self.btn_start.configure(state="normal")
                    self.btn_cancel.configure(state="disabled")
                    self.lbl.configure(text="Fertig." if not self.cancel_flag.is_set() else "Abgebrochen.")
        except queue.Empty:
            pass
        self.after(100, self._poll)


def main():
    App().mainloop()


if __name__ == "__main__":
    main()
