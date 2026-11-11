# PyInstaller-Spezifikation: beide EXE in EINEM Ordner, ohne UPX, mit Versionsinfo.
# Kein "onefile" (Entpacken nach %TEMP% wird von Virenscannern oft falsch gemeldet).
import os
from PyInstaller.utils.hooks import collect_all

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

datas, binaries, hidden = [], [], []
for pkg in ("laspy", "lazrs"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h

def analysis(script):
    return Analysis([os.path.join(ROOT, script)], pathex=[ROOT], datas=datas, binaries=binaries,
                    hiddenimports=hidden, excludes=["matplotlib", "PIL", "pytest"])

a_gui = analysis("run_gui.py")
a_cli = analysis("run_cli.py")

def exe(a, name, console):
    return EXE(PYZ(a.pure), a.scripts, [], exclude_binaries=True, name=name,
               console=console, upx=False, version=os.path.join(ROOT, "build", f"version_{name}.txt"))

e_gui = exe(a_gui, "LasRasterThin", False)
e_cli = exe(a_cli, "lasrasterthin-cli", True)

COLLECT(e_gui, a_gui.binaries, a_gui.datas,
        e_cli, a_cli.binaries, a_cli.datas,
        upx=False, name="LasRasterThin")
