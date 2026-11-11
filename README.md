# LasRasterThin

Dünnt grosse LAS/LAZ-Punktwolken auf ein frei wählbares Raster aus –
**ohne die Punktwolke zu öffnen oder darzustellen**. Läuft auch auf schwachen Laptops.

## Was macht das Tool?

1. Legt ein Raster (2D) oder Voxelgitter (3D, z. B. für Tunnel) über die Punktwolke.
2. Behält **einen Punkt pro Zelle**.
3. Schreibt diesen Punkt **unverändert** in eine neue Datei:
   alle Attribute (X/Y/Z, Intensität, Klassifizierung, GPS-Zeit, RGB, Return-Nummer,
   Extra-Bytes …), Punktformat, Skalierung, Offset und Koordinatensystem bleiben erhalten.

## Warum braucht es wenig Arbeitsspeicher (RAM)?

Die Datei wird in Blöcken gelesen (Standard: 1 Mio. Punkte), zweimal hintereinander:

| Durchgang | Was passiert |
|---|---|
| 1 | Pro Zelle den besten Punkt merken (nur Zellnummer + Punktnummer) |
| 2 | Nur die gemerkten Punkte in die neue Datei kopieren |

Test: 8 Mio. Punkte (320 MB) → ca. 250 MB RAM. Der RAM-Bedarf hängt von der
Anzahl belegter Zellen ab, nicht von der Dateigrösse. Bei wenig RAM: «Punkte pro Block» verkleinern.

## Installation (Windows)

1. `LasRasterThin-Setup-x.y.z.exe` herunterladen
   (GitHub → *Actions* → letzter Lauf «Windows-Installer bauen» → *Artifacts*, oder unter *Releases*).
2. Doppelklick → Installation → Startmenü «LasRasterThin».

Keine Python-Installation nötig.

### Windows-Warnung «Der Computer wurde durch Windows geschützt»

Die Setup-Datei ist nicht digital signiert. Darum warnt Windows SmartScreen (Schutzfilter für
unbekannte Programme). Jeder Build wird mit Microsoft Defender geprüft (Ergebnis im Build-Log).

- Installieren trotzdem: **Weitere Informationen** → **Trotzdem ausführen**.
- Echtheit prüfen: SHA256-Prüfsumme (digitaler Fingerabdruck) vergleichen:
  `Get-FileHash LasRasterThin-Setup-1.0.0.exe` (PowerShell) muss den Wert aus
  `LasRasterThin-Setup-1.0.0.exe.sha256.txt` ergeben.
- Warnung ganz weg: Code-Signing-Zertifikat kaufen und als Repository-Secrets
  `WINDOWS_CERT_PFX` (PFX-Datei als Base64) und `WINDOWS_CERT_PASSWORD` hinterlegen.
  Der Build signiert dann automatisch.

## Bedienung

1. LAS/LAZ-Dateien oder ganzen Ordner hinzufügen.
2. Zellgrösse eingeben (z. B. `0.10` m). Y leer = wie X. Z leer = 2D-Raster.
3. Wählen, welcher Punkt pro Zelle bleibt:
   - **Punkt nächst Zellmitte** – gleichmässige Verteilung (Standard)
   - **Erster Punkt in Zelle** – am schnellsten
   - **Tiefster / Höchster Punkt** – z. B. Boden bzw. Oberfläche
4. Optional Ursprung X0/Y0/Z0 (leer = Vielfaches der Zellgrösse, z. B. auf LV95-Raster ausgerichtet).
5. **Start**. Ergebnis: `<Name>_raster0p1.las` im gewählten Ordner.

## Kommandozeile

```bash
lasrasterthin-cli.exe C:\Daten\*.laz -c 0.1 -o C:\Daten\duenn
```

```bash
lasrasterthin-cli.exe tunnel.las -c 0.05 --cell-z 0.05 -m center --laz
```

Hilfe: `lasrasterthin-cli.exe --help`

## Selber bauen (Windows)

Benötigt Python 3.10+ und [Inno Setup 6](https://jrsoftware.org/isinfo.php):

```bash
build_windows.bat
```

Ergebnis: `installer\Output\LasRasterThin-Setup-1.0.0.exe`
