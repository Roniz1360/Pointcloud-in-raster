"""Erzeugt die Windows-Versionsinfo (Eigenschaften > Details der EXE)."""
import sys

sys.path.insert(0, ".")
from lasrasterthin import __version__  # noqa: E402

v = tuple(int(p) for p in __version__.split(".")) + (0,)
TEMPLATE = f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={v}, prodvers={v}, mask=0x3f, flags=0x0, OS=0x40004,
                    fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040704B0', [
      StringStruct('CompanyName', 'LasRasterThin'),
      StringStruct('FileDescription', '{{desc}}'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', '{{name}}'),
      StringStruct('LegalCopyright', 'LasRasterThin'),
      StringStruct('OriginalFilename', '{{name}}.exe'),
      StringStruct('ProductName', 'LasRasterThin'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [0x0407, 1200])])
  ]
)
"""

for name, desc in [("LasRasterThin", "LAS/LAZ-Punktwolke auf Raster ausduennen"),
                   ("lasrasterthin-cli", "LAS/LAZ-Punktwolke auf Raster ausduennen (Kommandozeile)")]:
    with open(f"build/version_{name}.txt", "w", encoding="utf-8") as f:
        f.write(TEMPLATE.replace("{desc}", desc).replace("{name}", name))
