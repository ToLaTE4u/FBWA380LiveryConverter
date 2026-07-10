# Spec: FBW A380X Livery Converter (MSFS 2020 → MSFS 2024)

**Datum:** 2026-07-10
**Status:** Entwurf genehmigt (Brainstorming abgeschlossen)

## 1. Problem & Ziel

Mit dem nativen MSFS-2024-Release des FlyByWire A380X ([Development Update](https://flybywiresim.com/notams/development-update-native-msfs-2024-a380x/)) sind alte Community-Liveries inkompatibel: anderes Paketlayout, anderes Texturformat, andere Dateinamen und Konfigurationsdateien.

Das Tool konvertiert ein altes FBW-A380X-Livery-Paket (MSFS-2020-Format) vollautomatisch in ein installierbares natives MSFS-2024-Paket. Zielgruppe sind Endnutzer der Flightsim-Community (eine Exe, keine Python-Installation, kein SDK, kein DevMode nötig) sowie Painter, die viele Pakete migrieren (CLI).

### Erfolgskriterien

- Das Qatar-Fleet-Pack aus `data/oldLivery` wird ohne manuelle Nacharbeit zu einem Paket konvertiert, das strukturell dem Referenz-Livery in `data/NewLivery` entspricht und in MSFS 2024 lädt.
- Alle 8 Registrierungen erscheinen als eigene Liveries unter einem A380X-Eintrag im Flugzeugmenü.
- Exterior-Texturen sind visuell nicht vom Original unterscheidbar (BC3 → BC7 ist qualitativ verlustarm).
- Nutzer ohne Technikkenntnisse kommen mit Doppelklick + 2 Ordnerauswahlen + 1 Button zum Ergebnis.

## 2. Formatunterschiede (Analyse der Beispieldaten)

| Aspekt | Alt (MSFS 2020) | Neu (MSFS 2024) |
|---|---|---|
| Struktur | `SimObjects/AirPlanes/<Variante>/` mit `aircraft.cfg`, optional `MODEL.X/`, `TEXTURE.X/` | `SimObjects/AirPlanes/FlyByWire_A380X/liveries/flybywire/<LiveryName>/` mit `livery.cfg`, `texture/`, `thumbnail/` |
| Texturformat | DDS, DXT5/BC3 (auch BC1 möglich), 4096², Mipmaps | KTX2, **vkFormat 145 (BC7_UNORM)**, volle Mip-Kette (13 Level bei 4096²), **keine Supercompression** |
| Dateinamen | `A380X_FUSE1_ALBEDO.PNG.DDS`, `A380_EXTERIOR_WING1_ALBEDO.PNG.DDS`, … | `A380X_FUSE1_ALBD.PNG.KTX2`, `A380X_EXT_WING1_ALBD.PNG.KTX2`, … (offizielle Rename-Liste: `data/Paintkit/scripts/rename_list.csv`, ~390 Einträge) |
| Textur-Metadaten | `<name>.DDS.json` mit `Flags: [FL_BITMAP_COMPRESSION, FL_BITMAP_MIPMAP]` | `<name>.KTX2.json` mit zusätzlich `FL_BITMAP_QUALITY_HIGH` |
| Variantenconfig | `aircraft.cfg`: `[VARIATION] base_container` + `[FLTSIM.N]` (title, ui_variation, texture, model, atc_id, atc_airline) | `livery.cfg`: `[version]` + `[GENERAL]` (Name, atc_id, atc_parking_codes, icao_airline, atc_airline). **Kein `ui_createdby`** (laut FBW-README erzeugt das sonst separate Flugzeugeinträge) |
| texture.CFG | Fallbacks u. a. auf `..\..\Common Textures` und `..\..\FlyByWire_A380_842\texture` | Fallbacks auf `..\texture`, `..\..\FlyByWire_A380_842\texture`, `..\..\..\common\texture`, Sim-Basispfade |
| Thumbnails | `thumbnail.JPG`, `thumbnail_small.JPG` | `thumbnail.png`, `thumbnail_button.png`, `thumbnail_side.png` |
| manifest.json | `content_type: "AIRCRAFT"` | `content_type: "LIVERY"`, Dependencies (`asobo-vcockpits-instruments-airliners`, `fs-base-aircraft-common`), `total_package_size` |
| layout.json | Dateiliste mit size/date | identisch, muss für neue Struktur neu berechnet werden |

## 3. Entscheidungen (aus dem Brainstorming)

1. **Direktkonvertierung zu KTX2** — das Tool erzeugt ein fertiges Paket; kein DevMode-/SDK-Workflow.
2. **Fleet-Packs: alle Varianten in ein Ausgabepaket** — jede `[FLTSIM.N]`-Variante wird eine eigene Livery; gemeinsame Texturen werden dedupliziert.
3. **CLI + GUI** — gemeinsamer Konvertierungskern, zwei Frontends.
4. **Architektur C (Hybrid):** Python schreibt den KTX2-Container selbst (byteweise am Referenz-Livery kalibriert); nur die BC7-Blockkompression übernimmt eine native Komponente.

## 4. Architektur

### 4.1 Pipeline

```
Altes Paket ──► Scan ──► Parse ──► Map ──► Texturkonvertierung ──► Generierung ──► Neues Paket + Report
```

1. **Scan:** Variantenordner über `aircraft.cfg` mit `[FLTSIM.*]` finden; zugehörige `TEXTURE.*`-Ordner auflösen; „Common Textures"-Ordner, Thumbnails und altes `manifest.json` erfassen. Eingabe ist ein entpackter Paketordner.
2. **Parse:** `aircraft.cfg` je Variante → title, ui_variation, atc_id, atc_airline, texture-Suffix, model-Suffix. Altes Manifest → Titel, Creator, Version.
3. **Map:** Dateinamen case-insensitiv über die gebündelte Rename-Liste übersetzen; Endung `.PNG.DDS` → `.PNG.KTX2`. Nicht gelistete Namen (Custom-Decals u. ä.) behalten ihren Namen (nur Endung wird angepasst) und erzeugen eine Warnung.
4. **Texturkonvertierung** (parallelisiert über Prozess-/Threadpool, Fleet-Packs haben >100 4K-Texturen):
   - DDS-Header parsen (eigener Reader; unterstützt DXT1/BC1, DXT5/BC3, DX10-Header)
   - Blöcke dekodieren via `texture2ddecoder` → RGBA
   - Mip-Kette frisch in Python generieren (Pillow, Lanczos/Box); vorhandene DDS-Mips werden verworfen
   - BC7-Kompression durch native Komponente (siehe Spike, 4.3)
   - KTX2-Container schreiben: vkFormat 145 (BC7_UNORM), typeSize 1, faceCount 1, volle Mip-Kette, supercompressionScheme 0, DFD für BC7; dazu `<name>.KTX2.json` mit `{"Version":2,"SourceFileDate":<FILETIME>,"Flags":["FL_BITMAP_COMPRESSION","FL_BITMAP_MIPMAP","FL_BITMAP_QUALITY_HIGH"]}`
5. **Generierung:**
   - je Variante `livery.cfg` aus alten Metadaten (Name aus ui_variation/title, atc_airline übernommen, icao_airline soweit ableitbar, kein `ui_createdby`)
   - `texture.CFG` mit der Fallback-Kette des Referenz-Liverys
   - Thumbnails: altes JPG → PNG, als `thumbnail.png`, `thumbnail_button.png`, `thumbnail_side.png` (identisches Bild, ggf. skaliert); fehlt ein Thumbnail → Platzhalter aus dem Paintkit + Warnung
   - Common Textures → `SimObjects/AirPlanes/FlyByWire_A380X/liveries/common/texture/` (von der Fallback-Kette abgedeckt); identische Dateien über Varianten hinweg werden dedupliziert (Hash-Vergleich)
   - Paket-`manifest.json` (`content_type: "LIVERY"`, Titel/Creator aus altem Manifest, Dependencies + `minimum_game_version` wie im Referenz-Paket, `total_package_size` berechnet)
   - `layout.json` selbst berechnen (Pfad, Größe, FILETIME-Datum aller Content-Dateien)
   - `conversion_report.txt` ins Ausgabepaket (alle Warnungen, Zuordnungen, übersprungene Dateien)

### 4.2 Module (src-Layout, Paket `a380x_livery_converter`)

| Modul | Aufgabe | Abhängigkeiten |
|---|---|---|
| `core/scanner.py` | Altes Paket erkennen und inventarisieren (`ScanResult`) | stdlib |
| `core/aircraft_cfg.py` | Tolerantes Parsen der cfg-Dateien (`;`-Kommentare, Quotes, Duplikate) | stdlib |
| `core/rename_map.py` | Gebündelte CSV laden, Lookup case-insensitiv | stdlib |
| `texture/dds.py` | DDS-Reader + Dekodierung nach RGBA | `texture2ddecoder` |
| `texture/mipmap.py` | Mip-Kette generieren | `Pillow` |
| `texture/bc7.py` | BC7-Encoder-Backend hinter stabiler Schnittstelle (`encode_bc7(rgba, w, h) -> bytes`) | Spike-Ergebnis |
| `texture/ktx2.py` | KTX2-Writer + `.json`-Sidecar | stdlib |
| `output/livery_gen.py` | livery.cfg, texture.CFG, Thumbnails | `Pillow` |
| `output/package_gen.py` | Ordnerstruktur, manifest.json, layout.json, Report | stdlib |
| `converter.py` | Orchestrierung, Parallelisierung, Progress-Callback | stdlib |
| `cli.py` | `convert <input> -o <output>`, `--dry-run`, `--verbose` | `typer` |
| `gui.py` | Tkinter-Fenster: 2 Ordner-Picker, Konvertieren-Button, Fortschritt, Log | stdlib |
| `__main__.py` | Ohne Argumente → GUI, mit Argumenten → CLI | — |

Jedes Modul ist ohne die anderen testbar; der `Converter` verdrahtet sie und meldet Fortschritt über einen Callback (`(schritt, gesamt, meldung)`), den CLI (Fortschrittsausgabe) und GUI (Progressbar) jeweils selbst rendern.

### 4.3 Spike: BC7-Encoder (erste Implementierungsaufgabe)

Kandidaten in Prüfreihenfolge:

1. **Intel ISPC TexComp** (`ispc_texcomp.dll`, per ctypes) — schnell, hochwertig, schlanke DLL
2. **bc7enc/bc7e-Bindings** (PyPI oder eigenes ctypes-Binding)
3. **Fallback: gebündeltes `texconv.exe`** (DirectXTex): RGBA-PNG → BC7-DDS, wir verpacken die BC7-Blöcke aus dem DDS in unseren KTX2-Container um

Abnahmekriterium des Spikes: eine 4096²-Textur inkl. Mips in < 30 s auf üblicher Hardware, Ergebnis lädt in MSFS 2024 bzw. entspricht strukturell dem Referenz-KTX2. Die Wahl ist hinter `texture/bc7.py` gekapselt und für den Rest des Systems unsichtbar.

## 5. Fehlerbehandlung & bekannte Grenzen

- **Custom-3D-Modelle:** Alte Pakete mit eigenem `MODEL.*`-Ordner (z. B. Decal-Geometrie im Qatar-Pack) sind im 2024-Livery-Format nicht abbildbar. Das Modell wird verworfen; deutliche Warnung im Report („Decals/3D-Anpassungen gehen verloren"). Zugehörige Custom-Texturen werden trotzdem konvertiert (harmlos, ungenutzt).
- **Nicht zuordenbare Texturen:** konvertieren und Namen beibehalten + Warnung; niemals Abbruch.
- **Korrupte/unlesbare DDS:** Textur überspringen, Warnung, Konvertierung läuft weiter.
- **Nicht-Textur-Dateien** im Texturordner (Readmes, `MSFSLayoutGenerator.exe` u. ä.): ignorieren.
- **Interior-/Cabin-Texturen** aus Common Textures: werden regulär gemappt und konvertiert; ob das native 2024-Modell sie nutzt, liegt außerhalb unserer Kontrolle → Hinweis im Report.
- Eingabe ist kein A380X-Paket (keine `aircraft.cfg` mit FBW-`base_container`): klare Fehlermeldung statt Teilkonvertierung.
- Exit-Codes CLI: 0 = ok, 1 = mit Warnungen, 2 = Fehler/Abbruch.

## 6. Tests & Verifikation

- **TDD mit pytest** für Parser, Mapper, Writer.
- **Golden-Referenz:** `data/NewLivery` — Tests vergleichen KTX2-Headerfelder (vkFormat, levelCount, supercompression), Ordnerstruktur, Namensschema und layout.json-/manifest.json-Form gegen die Referenz.
- **Round-Trip-Test:** konvertierte KTX2 zurückdekodieren und gegen das dekodierte Original-DDS vergleichen (PSNR-Schwelle, z. B. > 35 dB).
- **Integrationstest:** komplettes Qatar-Fleet-Pack aus `data/oldLivery` konvertieren; Struktur- und Report-Validierung.
- Manuelle Abnahme: ein konvertiertes Paket im echten MSFS 2024 laden.

## 7. Projekt & Distribution

- uv-Projekt (`pyproject.toml`), Python 3.12, `src/`-Layout, Abhängigkeiten: `Pillow`, `texture2ddecoder`, `typer`; dev: `pytest`.
- Rename-CSV und native Encoder-Komponente als Paket-Datenressourcen eingebettet.
- **Exe-Build mit Nuitka** (onefile, `--windows-console-mode=attach`: GUI bei Doppelklick ohne Konsole, CLI-Ausgabe im Terminal). Build-Skript im Repo, GitHub-Actions-tauglich.

## 8. Nicht-Ziele (v1)

- Kein Zip-/Archiv-Input (Nutzer entpackt selbst)
- Keine Konvertierung anderer Flugzeuge als des FBW A380X
- Keine Rückkonvertierung 2024 → 2020
- Kein Batch-Modus über mehrere Pakete (CLI-Nutzer können schleifen)
- Keine Bearbeitung/Retusche von Texturinhalten (Registrierungen ändern etc.)
