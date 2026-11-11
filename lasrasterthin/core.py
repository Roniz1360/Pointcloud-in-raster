"""Kern: LAS/LAZ-Punktwolke streamend auf ein Raster ausduennen.

Die Punktwolke wird nie komplett in den Speicher geladen und nie dargestellt.
Sie wird in Bloecken (Chunks) gelesen:

  Durchgang 1: fuer jede Rasterzelle den "besten" Punkt bestimmen
               (nur Zellnummer, Bewertung und Punktnummer werden gemerkt).
  Durchgang 2: Datei erneut lesen und nur die gewaehlten Punkte
               unveraendert (alle Attribute, alle Extra-Bytes) schreiben.

Header, Punktformat, Skalierung, Offset, VLRs (z. B. Koordinatensystem)
und EVLRs werden von der Eingabedatei uebernommen.
"""
from __future__ import annotations

import copy
import math
import os
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

import laspy
import numpy as np

METHODS = {
    "center": "Punkt naechst Zellmitte",
    "first": "Erster Punkt in Zelle",
    "min_z": "Tiefster Punkt (min Z)",
    "max_z": "Hoechster Punkt (max Z)",
}


class Cancelled(Exception):
    """Wird ausgeloest, wenn der Benutzer abbricht."""


@dataclass
class ThinSettings:
    cell_x: float = 0.10
    cell_y: float = 0.10
    cell_z: Optional[float] = None  # None = 2D-Raster, Wert = 3D-Voxel
    origin_x: Optional[float] = None  # None = automatisch (Vielfaches der Zellgroesse)
    origin_y: Optional[float] = None
    origin_z: Optional[float] = None
    method: str = "center"
    chunk_size: int = 1_000_000

    def validate(self) -> None:
        for name in ("cell_x", "cell_y"):
            if not getattr(self, name) or getattr(self, name) <= 0:
                raise ValueError(f"{name} muss > 0 sein")
        if self.cell_z is not None and self.cell_z <= 0:
            raise ValueError("cell_z muss > 0 sein (oder leer fuer 2D)")
        if self.method not in METHODS:
            raise ValueError(f"Unbekannte Methode: {self.method}")
        if self.chunk_size < 10_000:
            raise ValueError("chunk_size muss >= 10000 sein")


@dataclass
class ThinResult:
    input_path: str
    output_path: str
    points_in: int = 0
    points_out: int = 0
    cells: int = 0
    seconds: float = 0.0
    messages: list = field(default_factory=list)

    @property
    def ratio(self) -> float:
        return self.points_out / self.points_in if self.points_in else 0.0


ProgressCb = Callable[[float, str], None]


def _axis_grid(lo: float, hi: float, cell: float, origin: Optional[float]):
    """Liefert (origin, index_offset, anzahl_zellen) fuer eine Achse."""
    if origin is None:
        origin = math.floor(lo / cell) * cell
    i0 = math.floor((lo - origin) / cell)
    i1 = math.floor((hi - origin) / cell)
    return origin, i0, i1 - i0 + 1


def _merge_best(g_keys, g_score, g_idx, c_keys, c_score, c_idx):
    """Fuegt Chunk-Kandidaten (je Zelle schon eindeutig) in die globale,
    nach Zellnummer sortierte Liste ein. Kleinere Bewertung gewinnt."""
    if g_keys.size == 0:
        return c_keys, c_score, c_idx
    pos = np.searchsorted(g_keys, c_keys)
    pos_c = np.minimum(pos, g_keys.size - 1)
    exists = g_keys[pos_c] == c_keys

    # vorhandene Zellen: nur ersetzen, wenn besser
    ep = pos_c[exists]
    better = c_score[exists] < g_score[ep]
    upd = ep[better]
    g_score[upd] = c_score[exists][better]
    g_idx[upd] = c_idx[exists][better]

    # neue Zellen einfuegen (Sortierung bleibt erhalten)
    new = ~exists
    if np.any(new):
        ins = pos[new]
        g_keys = np.insert(g_keys, ins, c_keys[new])
        g_score = np.insert(g_score, ins, c_score[new])
        g_idx = np.insert(g_idx, ins, c_idx[new])
    return g_keys, g_score, g_idx


def thin_file(
    input_path: str,
    output_path: str,
    settings: ThinSettings,
    progress: Optional[ProgressCb] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> ThinResult:
    """Duennt eine LAS/LAZ-Datei auf ein Raster/Voxelgitter aus."""
    settings.validate()
    t0 = time.time()
    res = ThinResult(input_path, output_path)

    def report(frac: float, msg: str) -> None:
        if progress:
            progress(max(0.0, min(1.0, frac)), msg)
        if cancel and cancel():
            raise Cancelled()

    if os.path.abspath(input_path) == os.path.abspath(output_path):
        raise ValueError("Ausgabedatei darf nicht gleich der Eingabedatei sein")

    s = settings
    use_z = s.cell_z is not None

    with laspy.open(input_path) as reader:
        hdr = reader.header
        n_total = int(hdr.point_count)
        res.points_in = n_total
        if n_total == 0:
            raise ValueError("Datei enthaelt keine Punkte")

        ox, ix0, nx = _axis_grid(hdr.mins[0], hdr.maxs[0], s.cell_x, s.origin_x)
        oy, iy0, ny = _axis_grid(hdr.mins[1], hdr.maxs[1], s.cell_y, s.origin_y)
        if use_z:
            oz, iz0, nz = _axis_grid(hdr.mins[2], hdr.maxs[2], s.cell_z, s.origin_z)
        else:
            oz, iz0, nz = 0.0, 0, 1
        if float(nx) * float(ny) * float(nz) >= 2**62:
            raise ValueError("Raster zu fein fuer diese Ausdehnung (Zellanzahl zu gross)")
        res.messages.append(
            f"Raster: {nx} x {ny}" + (f" x {nz}" if use_z else "")
            + f" Zellen, Ursprung X={ox:.3f} Y={oy:.3f}" + (f" Z={oz:.3f}" if use_z else "")
        )

        g_keys = np.empty(0, np.int64)
        g_score = np.empty(0, np.float64)
        g_idx = np.empty(0, np.int64)

        # ---------------- Durchgang 1: Zellen bestimmen ----------------
        start = 0
        for chunk in reader.chunk_iterator(s.chunk_size):
            n = len(chunk)
            if n == 0:
                continue
            x = np.asarray(chunk.x, dtype=np.float64)
            y = np.asarray(chunk.y, dtype=np.float64)
            fx = (x - ox) / s.cell_x
            fy = (y - oy) / s.cell_y
            ix = np.clip(np.floor(fx).astype(np.int64) - ix0, 0, nx - 1)
            iy = np.clip(np.floor(fy).astype(np.int64) - iy0, 0, ny - 1)
            key = ix + nx * iy
            z = None
            if use_z or s.method in ("min_z", "max_z"):
                z = np.asarray(chunk.z, dtype=np.float64)
            if use_z:
                fz = (z - oz) / s.cell_z
                iz = np.clip(np.floor(fz).astype(np.int64) - iz0, 0, nz - 1)
                key = key + (nx * ny) * iz

            gidx = np.arange(start, start + n, dtype=np.int64)
            if s.method == "center":
                dx = fx - np.floor(fx) - 0.5
                dy = fy - np.floor(fy) - 0.5
                score = dx * dx + dy * dy
                if use_z:
                    dz = fz - np.floor(fz) - 0.5
                    score += dz * dz
            elif s.method == "first":
                score = gidx.astype(np.float64)
            elif s.method == "min_z":
                score = z
            else:  # max_z
                score = -z

            # pro Zelle besten Punkt im Chunk (sortiert nach Zelle, dann Bewertung)
            order = np.lexsort((gidx, score, key))
            k_sorted = key[order]
            first = np.ones(n, dtype=bool)
            first[1:] = k_sorted[1:] != k_sorted[:-1]
            sel = order[first]
            g_keys, g_score, g_idx = _merge_best(
                g_keys, g_score, g_idx, key[sel], score[sel], gidx[sel]
            )

            start += n
            report(0.5 * start / n_total,
                   f"Durchgang 1/2: {start:,} / {n_total:,} Punkte, {g_keys.size:,} Zellen")

        res.cells = int(g_keys.size)
        del g_keys, g_score

    keep = np.sort(g_idx)
    del g_idx

    # ---------------- Durchgang 2: Punkte schreiben ----------------
    tmp_path = output_path + ".part"
    try:
        with laspy.open(input_path) as reader:
            out_hdr = copy.deepcopy(reader.header)
            evlrs = getattr(reader, "evlrs", None)
            if evlrs:
                out_hdr.evlrs = evlrs
            compress = output_path.lower().endswith(".laz")
            with laspy.open(tmp_path, mode="w", header=out_hdr,
                            do_compress=compress) as writer:
                start = 0
                written = 0
                for chunk in reader.chunk_iterator(s.chunk_size):
                    n = len(chunk)
                    if n == 0:
                        continue
                    a = np.searchsorted(keep, start)
                    b = np.searchsorted(keep, start + n)
                    if b > a:
                        local = keep[a:b] - start
                        writer.write_points(chunk[local])
                        written += int(b - a)
                    start += n
                    report(0.5 + 0.5 * start / n_total,
                           f"Durchgang 2/2: {start:,} / {n_total:,} Punkte gelesen, "
                           f"{written:,} geschrieben")
        res.points_out = written
        if os.path.exists(output_path):
            os.remove(output_path)
        os.replace(tmp_path, output_path)
    except BaseException:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
        raise

    res.seconds = time.time() - t0
    report(1.0, f"Fertig: {res.points_out:,} von {res.points_in:,} Punkten "
                f"({100 * res.ratio:.1f} %)")
    return res


def default_output_path(input_path: str, out_dir: Optional[str], settings: ThinSettings,
                        as_laz: Optional[bool] = None) -> str:
    base, ext = os.path.splitext(os.path.basename(input_path))
    if as_laz is not None:
        ext = ".laz" if as_laz else ".las"
    tag = f"{settings.cell_x:g}".replace(".", "p")
    if settings.cell_y != settings.cell_x:
        tag += "x" + f"{settings.cell_y:g}".replace(".", "p")
    if settings.cell_z is not None:
        tag += "x" + f"{settings.cell_z:g}".replace(".", "p")
    folder = out_dir or os.path.dirname(os.path.abspath(input_path))
    return os.path.join(folder, f"{base}_raster{tag}{ext}")
