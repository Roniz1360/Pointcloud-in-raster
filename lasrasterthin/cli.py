"""Kommandozeile: lasrasterthin eingabe.las [weitere] -c 0.1 [-o ordner]"""
from __future__ import annotations

import argparse
import glob
import os
import sys

from . import __version__
from .core import METHODS, ThinSettings, default_output_path, thin_file


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="LasRasterThin",
        description="LAS/LAZ-Punktwolken auf ein Raster ausduennen (ohne Darstellung, "
                    "alle Attribute bleiben erhalten).",
    )
    p.add_argument("inputs", nargs="+", help="LAS/LAZ-Dateien oder Muster (*.las)")
    p.add_argument("-c", "--cell", type=float, required=True, help="Zellgroesse X und Y [m]")
    p.add_argument("--cell-y", type=float, help="abweichende Zellgroesse Y [m]")
    p.add_argument("--cell-z", type=float, help="Zellgroesse Z [m] -> 3D-Voxelraster")
    p.add_argument("--origin", type=float, nargs=2, metavar=("X0", "Y0"),
                   help="Rasterursprung (Standard: Vielfaches der Zellgroesse)")
    p.add_argument("--origin-z", type=float, help="Rasterursprung Z")
    p.add_argument("-m", "--method", choices=list(METHODS), default="center",
                   help="Welcher Punkt pro Zelle bleibt (Standard: center)")
    p.add_argument("-o", "--out-dir", help="Ausgabeordner (Standard: wie Eingabe)")
    p.add_argument("--laz", action="store_true", help="Ausgabe komprimiert als LAZ")
    p.add_argument("--las", action="store_true", help="Ausgabe unkomprimiert als LAS")
    p.add_argument("--chunk", type=int, default=1_000_000,
                   help="Punkte pro Block (kleiner = weniger RAM)")
    p.add_argument("--version", action="version", version=__version__)
    return p


def main(argv=None) -> int:
    a = build_parser().parse_args(argv)
    files = []
    for pat in a.inputs:
        files.extend(sorted(glob.glob(pat)) or [pat])
    s = ThinSettings(
        cell_x=a.cell, cell_y=a.cell_y or a.cell, cell_z=a.cell_z,
        origin_x=a.origin[0] if a.origin else None,
        origin_y=a.origin[1] if a.origin else None,
        origin_z=a.origin_z, method=a.method, chunk_size=a.chunk,
    )
    as_laz = True if a.laz else (False if a.las else None)
    if a.out_dir:
        os.makedirs(a.out_dir, exist_ok=True)
    rc = 0
    for f in files:
        out = default_output_path(f, a.out_dir, s, as_laz)
        print(f"{f} -> {out}")
        last = [-1]

        def prog(frac, msg):
            pct = int(frac * 100)
            if pct != last[0]:
                last[0] = pct
                print(f"\r  {pct:3d} %  {msg}".ljust(100), end="", flush=True)
        try:
            r = thin_file(f, out, s, prog)
            print()
            for m in r.messages:
                print("  " + m)
            print(f"  {r.points_in:,} -> {r.points_out:,} Punkte "
                  f"({100 * r.ratio:.1f} %) in {r.seconds:.1f} s")
        except Exception as e:  # noqa: BLE001
            print(f"\n  FEHLER: {e}", file=sys.stderr)
            rc = 1
    return rc


if __name__ == "__main__":
    sys.exit(main())
