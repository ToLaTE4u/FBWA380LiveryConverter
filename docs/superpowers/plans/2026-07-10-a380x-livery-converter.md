# FBW A380X Livery Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows-Tool (CLI + GUI, eine Exe), das alte FBW-A380X-Liveries (MSFS 2020, DDS) vollautomatisch in native MSFS-2024-Pakete (KTX2, `liveries/`-Struktur) konvertiert.

**Architecture:** Reines Python orchestriert die Pipeline (Scan → Parse → Rename-Map → Texturkonvertierung → Paketgenerierung). Die BC7-Kompression samt Mipmap-Generierung übernimmt ein gebündeltes `texconv.exe` (DirectXTex); Python parst dessen BC7-DDS-Ausgabe und verpackt die Blöcke in einen selbst geschriebenen, byteweise an der Referenz-Livery kalibrierten KTX2-Container. Damit ist der Spike aus der Spec entschieden: texconv ist das v1-Backend (deterministisch beschaffbar, GPU-beschleunigt), die Schnittstelle `texture/` bleibt austauschbar.

**Tech Stack:** Python 3.12, uv, Pillow, texture2ddecoder (Transparenz-Erkennung + Tests), typer (CLI), Tkinter (GUI), texconv.exe (gebündelt), Nuitka (Exe-Build), pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-10-a380x-livery-converter-design.md` — bei Widerspruch gilt die Spec.
- Python `>=3.12`, uv-Projekt, src-Layout, Paketname `a380x_livery_converter`.
- Alle Kommandos mit `uv run …` ausführen (niemals nacktes `python`/`pytest`).
- KTX2-Ziel: vkFormat 145 (BC7_UNORM), typeSize 1, faceCount 1, volle Mip-Kette, supercompressionScheme 0, Leveldaten im File kleinste Ebene zuerst, 16-Byte-Alignment je Level.
- `livery.cfg` niemals mit `ui_createdby`-Feld erzeugen (FBW-Vorgabe).
- Warnungen statt Abbruch: nicht zuordenbare Texturen, korrupte DDS, Custom-`MODEL.*` → Report; harter Fehler nur wenn Eingabe kein FBW-A380X-Paket ist.
- Git: Imperativ-Commits, keine AI-Attribution (git-config-Skill; user.name/email sind im Repo bereits gesetzt).
- Tests, die echte Beispieldaten brauchen, nutzen `data/` mit `pytest.mark.skipif` (Ordner ist gitignored, lokal vorhanden).
- Windows ist die einzige Zielplattform (texconv.exe, Exe-Build).

## Dateistruktur (Zielbild)

```
pyproject.toml
scripts/build_exe.ps1
src/a380x_livery_converter/
    __init__.py
    __main__.py            # argv-Routing: GUI ohne Argumente, CLI mit
    converter.py           # Orchestrierung, Parallelisierung, Warnungen
    cli.py                 # typer-CLI
    gui.py                 # Tkinter-GUI
    resources/
        rename_list.csv    # Kopie aus dem FBW-Paintkit
        texconv.exe        # DirectXTex, gepinnt
        thumbnails/{thumbnail,thumbnail_button,thumbnail_side}.png  # Platzhalter
    core/
        __init__.py
        aircraft_cfg.py    # toleranter cfg-Parser
        rename_map.py      # Dateinamen-Mapping
        scanner.py         # altes Paket inventarisieren
    texture/
        __init__.py
        dds.py             # DDS-Reader (BC1/BC3/BC7, DX10-Header)
        texconv.py         # texconv.exe-Wrapper
        ktx2.py            # KTX2-Writer + .KTX2.json-Sidecar
        pipeline.py        # DDS → KTX2 für eine Datei
    output/
        __init__.py
        livery_gen.py      # livery.cfg, texture.CFG, Thumbnails
        package_gen.py     # manifest.json, layout.json, Report, Namen
tests/
    helpers.py             # DDS-/Paket-Fixtures
    test_aircraft_cfg.py, test_rename_map.py, test_scanner.py,
    test_dds.py, test_texconv.py, test_ktx2.py, test_pipeline.py,
    test_livery_gen.py, test_package_gen.py, test_converter.py, test_cli.py
```

## Binär-Referenzwerte (aus `data/NewLivery` extrahiert, für Tasks 7/8 verbindlich)

- DFD-Block BC7 (44 Bytes, über alle Referenztexturen identisch):
  `2c00000000000000020028008601010003030000100000000000000000007f000000000000000000ffffffff`
- KVD (184 Bytes): Einträge `ASOBO_flags` = `BILINEAR\0COMPRESSION\0MIPMAP\0REDUCE_LESS\0PLATFORM_FORMAT\0QUALITY_HIGH\0`, `ASOBO_opacities` = leer, `ASOBO_transp` = 1 Byte (0x00 opak / 0x01 transparent — einziger Unterschied zwischen Referenztexturen), `ASOBOtexversion` = u32 1, `KTXwriter` = `ASOBO_FlightSim\0`. Jeder Eintrag: u32-Länge (key+\0+value), auf 4 gepaddet.
- Erste Leveldaten bei Offset 624 (= 80 Header + 13×24 Levelindex + 44 DFD + 184 KVD = 620, auf 16 aligned).
- `.KTX2.json`-Sidecar: `{"Version":2,"SourceFileDate":<FILETIME>,"Flags":["FL_BITMAP_COMPRESSION","FL_BITMAP_MIPMAP","FL_BITMAP_QUALITY_HIGH"]}`
- layout.json: `{"content":[{"path":"<forward slashes>","size":<bytes>,"date":<FILETIME>}]}`; manifest.json und layout.json selbst sind nicht enthalten.
- FILETIME = `int((unix_timestamp + 11644473600) * 10_000_000)`.
- Thumbnails: `thumbnail.png` 720×344, `thumbnail_button.png` 830×260, `thumbnail_side.png` 930×340.
- manifest.json (neu): `content_type "LIVERY"`, `minimum_game_version "1.26.5"`, Dependencies `asobo-vcockpits-instruments-airliners` 0.1.129 und `fs-base-aircraft-common` 0.1.125, `total_package_size` = 20-stellig nullgepaddete Byte-Summe.

---

### Task 1: Projekt-Setup und Ressourcen

**Files:**
- Create: `pyproject.toml`
- Create: `src/a380x_livery_converter/__init__.py`
- Create: `src/a380x_livery_converter/core/__init__.py`, `src/a380x_livery_converter/texture/__init__.py`, `src/a380x_livery_converter/output/__init__.py`
- Create: `src/a380x_livery_converter/resources/` (rename_list.csv, texconv.exe, thumbnails/*.png)
- Test: `tests/test_setup.py`

**Interfaces:**
- Produces: Paket `a380x_livery_converter` importierbar; `a380x_livery_converter.resource_path(name: str) -> Path` liefert Pfad zu gebündelten Ressourcen (funktioniert auch unter Nuitka-onefile, da `__file__`-relativ).

- [ ] **Step 1: pyproject.toml schreiben**

```toml
[project]
name = "a380x-livery-converter"
version = "0.1.0"
description = "Convert FBW A380X MSFS 2020 liveries to native MSFS 2024 packages"
requires-python = ">=3.12"
dependencies = [
    "pillow>=10.0",
    "texture2ddecoder>=1.0.4",
    "typer>=0.12",
]

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/a380x_livery_converter"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 2: Paketskelett anlegen**

`src/a380x_livery_converter/__init__.py`:

```python
from pathlib import Path

def resource_path(name: str) -> Path:
    """Path to a bundled resource file (works from source and Nuitka onefile)."""
    return Path(__file__).parent / "resources" / name
```

Die drei Unterpaket-`__init__.py` bleiben leer. `mkdir` für `src/a380x_livery_converter/resources/thumbnails`, `scripts`, `tests`. Zusätzlich ein leeres `tests/__init__.py` anlegen (nötig, damit `from tests.helpers import …` in den Tests funktioniert).

- [ ] **Step 3: Ressourcen beschaffen**

```powershell
Copy-Item "data/Paintkit/scripts/rename_list.csv" "src/a380x_livery_converter/resources/rename_list.csv"
$tk = "data/Paintkit/A380X-Livery-Project/PackageSources/SimObjects/airplanes/FlyByWire_A380X/liveries/flybywire/A380_Test_Livery/thumbnail"
Copy-Item "$tk/thumbnail.png","$tk/thumbnail_button.png","$tk/thumbnail_side.png" "src/a380x_livery_converter/resources/thumbnails/"
curl.exe -L -o src/a380x_livery_converter/resources/texconv.exe https://github.com/microsoft/DirectXTex/releases/latest/download/texconv.exe
```

- [ ] **Step 4: Smoke-Test schreiben**

`tests/test_setup.py`:

```python
from a380x_livery_converter import resource_path


def test_bundled_resources_exist():
    assert resource_path("rename_list.csv").is_file()
    assert resource_path("texconv.exe").is_file()
    for name in ("thumbnail.png", "thumbnail_button.png", "thumbnail_side.png"):
        assert resource_path(f"thumbnails/{name}").is_file()
```

- [ ] **Step 5: Umgebung aufsetzen und Test ausführen**

Run: `uv sync && uv run pytest tests/test_setup.py -v`
Expected: PASS (1 passed). Zusätzlich prüfen: `uv run python -c "print(1)"` läuft, `src/a380x_livery_converter/resources/texconv.exe` ist > 1 MB (`(Get-Item ...).Length`).

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml uv.lock src tests
git commit -m "Set up uv project skeleton with bundled resources"
```

---

### Task 2: core/aircraft_cfg.py — toleranter cfg-Parser

**Files:**
- Create: `src/a380x_livery_converter/core/aircraft_cfg.py`
- Test: `tests/test_aircraft_cfg.py`

**Interfaces:**
- Produces:
  - `parse_cfg(text: str) -> dict[str, dict[str, str]]` — Sektionsnamen UPPERCASE, Keys lowercase, Werte ohne umschließende Quotes und ohne `;`-Kommentare.
  - `fltsim_sections(sections: dict[str, dict[str, str]]) -> list[tuple[int, dict[str, str]]]` — alle `FLTSIM.N`-Sektionen, nach N sortiert.

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_aircraft_cfg.py`:

```python
from a380x_livery_converter.core.aircraft_cfg import parse_cfg, fltsim_sections

REAL_SNIPPET = """
[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "..\\FlyByWire_A380_842"

;===================== FLTSIM =====================

[FLTSIM.0]
title = "HUES QATAR AIRWAYS A7-APC 2025 A380" ; Variation name
ui_variation = "HUES QATAR AIRWAYS A7-APC 2025 A380"
texture = "A7APC" ; texture folder
model = "QTR" ; model folder
atc_id = "A380X" ; tail number
atc_airline = "Qatar Airways" ; airline name
"""


def test_parses_sections_and_strips_quotes_and_comments():
    cfg = parse_cfg(REAL_SNIPPET)
    assert cfg["VARIATION"]["base_container"] == "..\\FlyByWire_A380_842"
    assert cfg["FLTSIM.0"]["title"] == "HUES QATAR AIRWAYS A7-APC 2025 A380"
    assert cfg["FLTSIM.0"]["texture"] == "A7APC"
    assert cfg["FLTSIM.0"]["atc_airline"] == "Qatar Airways"


def test_section_names_case_insensitive_keys_lowercased():
    cfg = parse_cfg("[fltsim.0]\nTITLE = x\n")
    assert cfg["FLTSIM.0"]["title"] == "x"


def test_semicolon_inside_quotes_is_kept():
    cfg = parse_cfg('[A]\nk = "a;b" ; comment\n')
    assert cfg["A"]["k"] == "a;b"


def test_fltsim_sections_sorted():
    cfg = parse_cfg("[FLTSIM.2]\na=2\n[FLTSIM.0]\na=0\n[FLTSIM.10]\na=10\n[GENERAL]\nx=y\n")
    result = fltsim_sections(cfg)
    assert [n for n, _ in result] == [0, 2, 10]
    assert result[2][1]["a"] == "10"


def test_blank_lines_and_garbage_ignored():
    cfg = parse_cfg("\n\n;only comment\nnokey_novalue\n[S]\nk=v\n")
    assert cfg == {"S": {"k": "v"}}
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_aircraft_cfg.py -v`
Expected: FAIL / ERROR mit `ModuleNotFoundError` bzw. `ImportError`.

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/core/aircraft_cfg.py`:

```python
"""Tolerant parser for MSFS aircraft.cfg / livery.cfg style files."""


def parse_cfg(text: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#", "//")):
            continue
        if line.startswith("[") and "]" in line:
            name = line[1 : line.index("]")].strip().upper()
            current = sections.setdefault(name, {})
            continue
        if "=" not in line or current is None:
            continue
        key, _, value = line.partition("=")
        value = _strip_inline_comment(value).strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        current[key.strip().lower()] = value
    return sections


def _strip_inline_comment(value: str) -> str:
    in_quotes = False
    for i, ch in enumerate(value):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ";" and not in_quotes:
            return value[:i]
    return value


def fltsim_sections(sections: dict[str, dict[str, str]]) -> list[tuple[int, dict[str, str]]]:
    result = []
    for name, body in sections.items():
        if name.startswith("FLTSIM."):
            suffix = name.split(".", 1)[1]
            if suffix.isdigit():
                result.append((int(suffix), body))
    return sorted(result, key=lambda pair: pair[0])
```

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_aircraft_cfg.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/core/aircraft_cfg.py tests/test_aircraft_cfg.py
git commit -m "Add tolerant cfg parser for aircraft.cfg files"
```

---

### Task 3: core/rename_map.py — Texturnamen-Mapping

**Files:**
- Create: `src/a380x_livery_converter/core/rename_map.py`
- Test: `tests/test_rename_map.py`

**Interfaces:**
- Consumes: `resource_path` aus Task 1.
- Produces:
  - `load_rename_map() -> dict[str, str]` — Key: alter PNG-Name UPPERCASE (z. B. `A380X_FUSE1_ALBEDO.PNG`), Value: neuer PNG-Name in Originalschreibweise der CSV.
  - `map_texture_filename(filename: str, rename_map: dict[str, str]) -> tuple[str, bool]` — nimmt einen DDS-Dateinamen beliebiger Schreibweise (`X.PNG.DDS`, `x.png.dds`), liefert `(neuer KTX2-Name, was_mapped)`. Unbekannte Namen behalten ihren Basisnamen, Endung wird zu `.KTX2`.

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_rename_map.py`:

```python
from a380x_livery_converter.core.rename_map import load_rename_map, map_texture_filename


def test_map_contains_known_entries_uppercase_keyed():
    m = load_rename_map()
    assert m["A380X_FUSE1_ALBEDO.PNG"] == "A380X_FUSE1_ALBD.PNG"
    assert m["A380_EXTERIOR_WING1_ALBEDO.PNG"] == "A380X_EXT_WING1_ALBD.PNG"
    assert len(m) > 300


def test_mapped_filename_any_case():
    m = load_rename_map()
    assert map_texture_filename("A380X_FUSE1_ALBEDO.PNG.DDS", m) == ("A380X_FUSE1_ALBD.PNG.KTX2", True)
    assert map_texture_filename("A380X_FUSE2_ALBEDO.png.dds", m) == ("A380X_FUSE2_ALBD.PNG.KTX2", True)


def test_unmapped_filename_keeps_base_name():
    m = load_rename_map()
    assert map_texture_filename("HUES_A380_DECALS_ALBD.png.dds", m) == ("HUES_A380_DECALS_ALBD.png.KTX2", False)
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_rename_map.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/core/rename_map.py`:

```python
"""Texture filename mapping old (2020) -> new (2024) based on the FBW paintkit CSV."""

import csv

from a380x_livery_converter import resource_path


def load_rename_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with resource_path("rename_list.csv").open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            old = row["current_name"].strip()
            new = row["new_name"].strip()
            if old and new:
                mapping[old.upper()] = new
    return mapping


def map_texture_filename(filename: str, rename_map: dict[str, str]) -> tuple[str, bool]:
    base = filename
    if base.upper().endswith(".DDS"):
        base = base[: -len(".DDS")]
    new_base = rename_map.get(base.upper())
    if new_base is None:
        return f"{base}.KTX2", False
    return f"{new_base}.KTX2", True
```

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_rename_map.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/core/rename_map.py tests/test_rename_map.py
git commit -m "Add texture rename mapping from paintkit CSV"
```

---

### Task 4: core/scanner.py — altes Paket inventarisieren

**Files:**
- Create: `src/a380x_livery_converter/core/scanner.py`
- Create: `tests/helpers.py`
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `parse_cfg`, `fltsim_sections` (Task 2).
- Produces:
  - `@dataclass Variant`: `folder: Path`, `index: int`, `title: str`, `ui_variation: str`, `atc_id: str`, `atc_airline: str`, `icao_airline: str`, `texture_suffix: str`, `texture_dir: Path | None`, `has_custom_model: bool`
  - `@dataclass OldPackage`: `root: Path`, `title: str`, `creator: str`, `package_version: str`, `variants: list[Variant]`, `common_texture_dir: Path | None`
  - `scan_package(root: Path) -> OldPackage` — wirft `NotAnA380XPackageError`, wenn kein `base_container` auf `FlyByWire_A380*` zeigt.
  - `tests/helpers.py`: `make_old_package(root: Path, suffixes: tuple[str, ...] = ("A7APC", "A7APD"), dds_bytes: bytes = b"", with_common: bool = True, with_model: bool = True) -> Path` — baut ein synthetisches Altpaket, liefert dessen Wurzel.

- [ ] **Step 1: Fixture-Helper schreiben**

`tests/helpers.py`:

```python
import json
from pathlib import Path

from PIL import Image

OLD_MANIFEST = {
    "dependencies": [],
    "content_type": "AIRCRAFT",
    "title": "Test Fleet Pack",
    "manufacturer": "Airbus",
    "creator": "TestCreator",
    "package_version": "2.0",
    "minimum_game_version": "1.26.5.0",
}

AIRCRAFT_CFG_TEMPLATE = """[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "..\\FlyByWire_A380_842"

[FLTSIM.0]
title = "TEST {suffix} A380" ; Variation name
ui_variation = "TEST {suffix} A380"
texture = "{suffix}" ; texture folder
model = "{model}" ; model folder
atc_id = "A380X" ; tail number
atc_airline = "Test Airways" ; airline name
icao_airline = "TST"
"""

OLD_TEXTURE_CFG = """[fltsim]
fallback.1=..\\..\\Common Textures
fallback.2=..\\..\\FlyByWire_A380_842\\texture
fallback.3=..\\..\\..\\..\\texture
"""


def make_old_package(root, suffixes=("A7APC", "A7APD"), dds_bytes=b"",
                     with_common=True, with_model=True):
    pkg = Path(root) / "Old Test Livery"
    airplanes = pkg / "SimObjects" / "AirPlanes"
    for suffix in suffixes:
        variant = airplanes / f"A388_TST_{suffix}"
        tex = variant / f"TEXTURE.{suffix}"
        tex.mkdir(parents=True)
        model_value = "TST" if with_model else ""
        (variant / "aircraft.cfg").write_text(
            AIRCRAFT_CFG_TEMPLATE.format(suffix=suffix, model=model_value))
        if with_model:
            (variant / "MODEL.TST").mkdir()
            (variant / "MODEL.TST" / "A380.xml").write_text("<Model/>")
        (tex / "texture.CFG").write_text(OLD_TEXTURE_CFG)
        (tex / "A380X_FUSE1_ALBEDO.PNG.DDS").write_bytes(dds_bytes)
        (tex / "A380X_FUSE1_ALBEDO.PNG.DDS.json").write_text(
            '{"Version":2,"SourceFileDate":1,"Flags":["FL_BITMAP_COMPRESSION","FL_BITMAP_MIPMAP"]}')
        (tex / "CUSTOM_DECAL.PNG.DDS").write_bytes(dds_bytes)
        Image.new("RGB", (412, 170), "blue").save(tex / "thumbnail.JPG")
    if with_common:
        common = airplanes / "Common Textures"
        common.mkdir(parents=True)
        (common / "A380X_FUSE2_ALBEDO.PNG.DDS").write_bytes(dds_bytes)
    (pkg / "manifest.json").write_text(json.dumps(OLD_MANIFEST))
    (pkg / "layout.json").write_text('{"content": []}')
    return pkg
```

- [ ] **Step 2: Failing Tests schreiben**

`tests/test_scanner.py`:

```python
from pathlib import Path

import pytest

from a380x_livery_converter.core.scanner import (
    NotAnA380XPackageError,
    scan_package,
)
from tests.helpers import make_old_package

QATAR = Path("data/oldLivery/HUES - QatarAirways Fleet  A380 FBW")


def test_scan_synthetic_package(tmp_path):
    pkg = make_old_package(tmp_path)
    result = scan_package(pkg)
    assert result.title == "Test Fleet Pack"
    assert result.creator == "TestCreator"
    assert len(result.variants) == 2
    v = result.variants[0]
    assert v.texture_suffix == "A7APC"
    assert v.texture_dir is not None and v.texture_dir.name == "TEXTURE.A7APC"
    assert v.atc_airline == "Test Airways"
    assert v.icao_airline == "TST"
    assert v.has_custom_model is True
    assert result.common_texture_dir is not None


def test_scan_without_common_and_model(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), with_common=False, with_model=False)
    result = scan_package(pkg)
    assert result.common_texture_dir is None
    assert result.variants[0].has_custom_model is False


def test_scan_rejects_non_a380_package(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",))
    cfg = pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "aircraft.cfg"
    cfg.write_text(cfg.read_text().replace("FlyByWire_A380_842", "Asobo_B747"))
    with pytest.raises(NotAnA380XPackageError):
        scan_package(pkg)


def test_scan_rejects_folder_without_simobjects(tmp_path):
    with pytest.raises(NotAnA380XPackageError):
        scan_package(tmp_path)


@pytest.mark.skipif(not QATAR.exists(), reason="real sample data not present")
def test_scan_real_qatar_pack():
    result = scan_package(QATAR)
    assert len(result.variants) == 8
    assert all(v.has_custom_model for v in result.variants)
    assert result.common_texture_dir is not None
    suffixes = {v.texture_suffix for v in result.variants}
    assert "A7APC" in suffixes
```

- [ ] **Step 3: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_scanner.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 4: Implementierung**

`src/a380x_livery_converter/core/scanner.py`:

```python
"""Inventory of an old-format (MSFS 2020) livery package."""

import json
from dataclasses import dataclass
from pathlib import Path

from a380x_livery_converter.core.aircraft_cfg import fltsim_sections, parse_cfg


class NotAnA380XPackageError(Exception):
    """Input folder is not an FBW A380X livery package."""


@dataclass
class Variant:
    folder: Path
    index: int
    title: str
    ui_variation: str
    atc_id: str
    atc_airline: str
    icao_airline: str
    texture_suffix: str
    texture_dir: Path | None
    has_custom_model: bool


@dataclass
class OldPackage:
    root: Path
    title: str
    creator: str
    package_version: str
    variants: list[Variant]
    common_texture_dir: Path | None


def _find_child(parent: Path, name: str) -> Path | None:
    if parent is None or not parent.is_dir():
        return None
    for child in parent.iterdir():
        if child.name.upper() == name.upper():
            return child
    return None


def scan_package(root: Path) -> OldPackage:
    root = Path(root)
    simobjects = _find_child(root, "SimObjects")
    airplanes = _find_child(simobjects, "AirPlanes") if simobjects else None
    if airplanes is None:
        raise NotAnA380XPackageError(f"No SimObjects/AirPlanes folder found in {root}")

    variants: list[Variant] = []
    common_dir: Path | None = None
    is_a380 = False
    for folder in sorted(airplanes.iterdir()):
        if not folder.is_dir():
            continue
        cfg_path = _find_child(folder, "aircraft.cfg")
        if cfg_path is None:
            if "COMMON" in folder.name.upper():
                common_dir = folder
            continue
        sections = parse_cfg(cfg_path.read_text(encoding="utf-8", errors="replace"))
        base = sections.get("VARIATION", {}).get("base_container", "")
        if "FLYBYWIRE_A380" in base.replace("\\", "/").rsplit("/", 1)[-1].upper():
            is_a380 = True
        for index, body in fltsim_sections(sections):
            suffix = body.get("texture", "")
            texture_dir = _find_child(folder, f"TEXTURE.{suffix}" if suffix else "TEXTURE")
            model = body.get("model", "")
            model_dir = _find_child(folder, f"MODEL.{model}" if model else "MODEL")
            variants.append(Variant(
                folder=folder,
                index=index,
                title=body.get("title", folder.name),
                ui_variation=body.get("ui_variation", body.get("title", folder.name)),
                atc_id=body.get("atc_id", ""),
                atc_airline=body.get("atc_airline", ""),
                icao_airline=body.get("icao_airline", ""),
                texture_suffix=suffix,
                texture_dir=texture_dir,
                has_custom_model=model_dir is not None,
            ))
    if not is_a380 or not variants:
        raise NotAnA380XPackageError(
            f"{root} does not contain FBW A380X variants (base_container check failed)")

    title, creator, version = root.name, "unknown", "1.0"
    manifest_path = _find_child(root, "manifest.json")
    if manifest_path is not None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig", errors="replace"))
            title = manifest.get("title", title)
            creator = manifest.get("creator", creator)
            version = manifest.get("package_version", version)
        except (json.JSONDecodeError, OSError):
            pass
    return OldPackage(root=root, title=title, creator=creator, package_version=version,
                      variants=variants, common_texture_dir=common_dir)
```

- [ ] **Step 5: Tests laufen lassen**

Run: `uv run pytest tests/test_scanner.py -v`
Expected: PASS (5 passed; der Qatar-Test läuft nur, wenn `data/` vorhanden ist).

- [ ] **Step 6: Commit**

```bash
git add src/a380x_livery_converter/core/scanner.py tests/helpers.py tests/test_scanner.py
git commit -m "Add old package scanner with variant inventory"
```

---

### Task 5: texture/dds.py — DDS-Reader

**Files:**
- Create: `src/a380x_livery_converter/texture/dds.py`
- Modify: `tests/helpers.py` (Funktion `make_bc3_dds` ergänzen)
- Test: `tests/test_dds.py`

**Interfaces:**
- Produces:
  - `@dataclass MipLevel`: `width: int`, `height: int`, `data: bytes`
  - `@dataclass DdsFile`: `width: int`, `height: int`, `format: str` (`"BC1" | "BC3" | "BC7"`), `mip_levels: list[MipLevel]`
  - `read_dds(path: Path) -> DdsFile` — wirft `DdsError` bei Magic-/Format-/Längenfehlern.
  - `tests/helpers.py`: `make_bc3_dds(width: int, height: int, alpha: int = 255) -> bytes` — valide einstufige BC3-DDS-Datei (einfarbig rot, optional transparent).

- [ ] **Step 1: DDS-Fixture-Builder in helpers.py ergänzen**

Ans Ende von `tests/helpers.py` anfügen (Import `struct` an den Dateianfang):

```python
import struct


def _bc3_block(r=200, g=30, b=30, alpha=255):
    c565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return struct.pack("<BB6x", alpha, alpha) + struct.pack("<HH4x", c565, c565)


def make_bc3_dds(width, height, alpha=255):
    blocks_x = max(1, (width + 3) // 4)
    blocks_y = max(1, (height + 3) // 4)
    payload = _bc3_block(alpha=alpha) * (blocks_x * blocks_y)
    ddsd_flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000  # CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE
    header = struct.pack("<7I44x", 124, ddsd_flags, height, width, len(payload), 0, 1)
    pixelformat = struct.pack("<II4s20x", 32, 0x4, b"DXT5")  # DDPF_FOURCC
    caps = struct.pack("<I12x", 0x1000)  # DDSCAPS_TEXTURE
    return b"DDS " + header + pixelformat + caps + payload
```

- [ ] **Step 2: Failing Tests schreiben**

`tests/test_dds.py`:

```python
from pathlib import Path

import pytest

from a380x_livery_converter.texture.dds import DdsError, read_dds
from tests.helpers import make_bc3_dds

QATAR_DDS = Path("data/oldLivery/HUES - QatarAirways Fleet  A380 FBW/SimObjects/"
                 "AirPlanes/A388_QTR_A7-APC/TEXTURE.A7APC/A380X_FUSE1_ALBEDO.PNG.DDS")


def test_read_synthetic_bc3(tmp_path):
    p = tmp_path / "t.dds"
    p.write_bytes(make_bc3_dds(8, 8))
    dds = read_dds(p)
    assert (dds.width, dds.height, dds.format) == (8, 8, "BC3")
    assert len(dds.mip_levels) == 1
    assert len(dds.mip_levels[0].data) == 4 * 16  # 2x2 blocks * 16 bytes


def test_rejects_non_dds(tmp_path):
    p = tmp_path / "x.dds"
    p.write_bytes(b"not a dds file at all, definitely not")
    with pytest.raises(DdsError):
        read_dds(p)


def test_rejects_truncated_payload(tmp_path):
    p = tmp_path / "t.dds"
    p.write_bytes(make_bc3_dds(16, 16)[:-8])
    with pytest.raises(DdsError):
        read_dds(p)


@pytest.mark.skipif(not QATAR_DDS.exists(), reason="real sample data not present")
def test_read_real_bc3_texture():
    dds = read_dds(QATAR_DDS)
    assert (dds.width, dds.height, dds.format) == (4096, 4096, "BC3")
    assert len(dds.mip_levels) >= 1
    assert len(dds.mip_levels[0].data) == 1024 * 1024 * 16
```

- [ ] **Step 3: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_dds.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 4: Implementierung**

`src/a380x_livery_converter/texture/dds.py`:

```python
"""Minimal DDS reader for BC1/BC3 (legacy fourCC) and BC7 (DX10 header) files."""

import struct
from dataclasses import dataclass
from pathlib import Path

FOURCC_TO_FORMAT = {b"DXT1": "BC1", b"DXT5": "BC3"}
BLOCK_BYTES = {"BC1": 8, "BC3": 16, "BC7": 16}
DXGI_BC7 = {98, 99}  # BC7_UNORM, BC7_UNORM_SRGB


class DdsError(Exception):
    pass


@dataclass
class MipLevel:
    width: int
    height: int
    data: bytes


@dataclass
class DdsFile:
    width: int
    height: int
    format: str
    mip_levels: list[MipLevel]


def read_dds(path: Path) -> DdsFile:
    data = Path(path).read_bytes()
    if len(data) < 128 or data[:4] != b"DDS ":
        raise DdsError(f"{path}: not a DDS file")
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    mip_count = max(1, struct.unpack_from("<I", data, 28)[0])
    fourcc = data[84:88]
    offset = 128
    if fourcc == b"DX10":
        if len(data) < 148:
            raise DdsError(f"{path}: truncated DX10 header")
        dxgi = struct.unpack_from("<I", data, 128)[0]
        if dxgi not in DXGI_BC7:
            raise DdsError(f"{path}: unsupported DXGI format {dxgi}")
        fmt = "BC7"
        offset = 148
    else:
        fmt = FOURCC_TO_FORMAT.get(fourcc)
        if fmt is None:
            raise DdsError(f"{path}: unsupported fourCC {fourcc!r}")

    levels: list[MipLevel] = []
    w, h = width, height
    for _ in range(mip_count):
        size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * BLOCK_BYTES[fmt]
        chunk = data[offset : offset + size]
        if len(chunk) != size:
            raise DdsError(f"{path}: truncated mip data at level {len(levels)}")
        levels.append(MipLevel(w, h, chunk))
        offset += size
        w, h = max(1, w // 2), max(1, h // 2)
    return DdsFile(width=width, height=height, format=fmt, mip_levels=levels)
```

- [ ] **Step 5: Tests laufen lassen**

Run: `uv run pytest tests/test_dds.py -v`
Expected: PASS (4 passed; Real-Data-Test nur mit `data/`).

- [ ] **Step 6: Commit**

```bash
git add src/a380x_livery_converter/texture/dds.py tests/helpers.py tests/test_dds.py
git commit -m "Add DDS reader for BC1/BC3/BC7 with mip level extraction"
```

---

### Task 6: texture/texconv.py — texconv-Wrapper

**Files:**
- Create: `src/a380x_livery_converter/texture/texconv.py`
- Test: `tests/test_texconv.py`

**Interfaces:**
- Consumes: `resource_path` (Task 1), `read_dds` (Task 5, nur im Test).
- Produces:
  - `dds_to_bc7_dds(src: Path, out_dir: Path) -> Path` — konvertiert eine Bilddatei (DDS oder PNG) via gebündeltem texconv zu BC7-DDS mit voller Mip-Kette; Rückgabe = Pfad der Ausgabedatei; wirft `TexconvError` mit stdout/stderr bei Fehlschlag.

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_texconv.py`:

```python
import pytest
from PIL import Image

from a380x_livery_converter.texture.dds import read_dds
from a380x_livery_converter.texture.texconv import TexconvError, dds_to_bc7_dds
from tests.helpers import make_bc3_dds


def test_png_to_bc7_with_full_mip_chain(tmp_path):
    src = tmp_path / "test.png"
    Image.new("RGBA", (16, 16), (200, 30, 30, 255)).save(src)
    out = dds_to_bc7_dds(src, tmp_path / "out")
    dds = read_dds(out)
    assert dds.format == "BC7"
    assert (dds.width, dds.height) == (16, 16)
    assert len(dds.mip_levels) == 5  # 16,8,4,2,1


def test_bc3_dds_to_bc7(tmp_path):
    src = tmp_path / "A380X_TEST.PNG.DDS"
    src.write_bytes(make_bc3_dds(8, 8))
    out = dds_to_bc7_dds(src, tmp_path / "out")
    dds = read_dds(out)
    assert dds.format == "BC7"
    assert len(dds.mip_levels) == 4  # 8,4,2,1


def test_invalid_input_raises(tmp_path):
    src = tmp_path / "broken.dds"
    src.write_bytes(b"garbage")
    with pytest.raises(TexconvError):
        dds_to_bc7_dds(src, tmp_path / "out")
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_texconv.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/texture/texconv.py`:

```python
"""Wrapper around the bundled DirectXTex texconv.exe."""

import subprocess
from pathlib import Path

from a380x_livery_converter import resource_path


class TexconvError(Exception):
    pass


def dds_to_bc7_dds(src: Path, out_dir: Path) -> Path:
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(resource_path("texconv.exe")),
        "-f", "BC7_UNORM",
        "-m", "0",          # full mip chain
        "-y",               # overwrite
        "-nologo",
        "-o", str(out_dir),
        str(src),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    result = _find_ci(out_dir, src.stem + ".dds")
    if proc.returncode != 0 or result is None:
        raise TexconvError(
            f"texconv failed for {src.name} (exit {proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}")
    return result


def _find_ci(folder: Path, name: str) -> Path | None:
    if not folder.is_dir():
        return None
    for child in folder.iterdir():
        if child.name.upper() == name.upper():
            return child
    return None
```

Hinweis: `_find_ci` fängt ab, dass texconv die Ausgabedatei mit anderer Endungs-Schreibweise (`.dds`/`.DDS`) erzeugen kann. `CREATE_NO_WINDOW` verhindert Konsolen-Popups im GUI-Betrieb. texconv nutzt für BC7 automatisch die GPU (DirectCompute) und fällt auf CPU zurück.

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_texconv.py -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/texture/texconv.py tests/test_texconv.py
git commit -m "Add texconv wrapper for BC7 compression with mip generation"
```

---

### Task 7: texture/ktx2.py — KTX2-Writer

**Files:**
- Create: `src/a380x_livery_converter/texture/ktx2.py`
- Test: `tests/test_ktx2.py`

**Interfaces:**
- Consumes: `DdsFile`, `MipLevel` (Task 5).
- Produces:
  - `write_ktx2(path: Path, dds: DdsFile, transparent: bool) -> None` — schreibt BC7-Mips als MSFS-konformes KTX2 (Referenzformat, siehe Binär-Referenzwerte oben). Wirft `ValueError`, wenn `dds.format != "BC7"`.
  - `build_kvd(transparent: bool) -> bytes` — 184-Byte-KVD-Block.
  - `write_flags_json(ktx2_path: Path, source_file_date: int) -> Path` — schreibt `<name>.KTX2.json`-Sidecar.
  - `filetime_from_unix(ts: float) -> int`

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_ktx2.py`:

```python
import struct
from pathlib import Path

import pytest

from a380x_livery_converter.texture.dds import DdsFile, MipLevel
from a380x_livery_converter.texture.ktx2 import (
    DFD_BC7,
    build_kvd,
    filetime_from_unix,
    write_flags_json,
    write_ktx2,
)

REF_TEX_DIR = Path("data/NewLivery/steffieth-livery-fbw_a380-lufthansa_100Y_2024/SimObjects/"
                   "AirPlanes/FlyByWire_A380X/liveries/flybywire/FlyByWire_A380_842_DLH_100Y/texture")

# 1:1 aus der Referenz-Livery extrahiert (opake Textur, ASOBO_transp = 0x00)
REFERENCE_KVD_OPAQUE = (
    b"Q\x00\x00\x00ASOBO_flags\x00BILINEAR\x00COMPRESSION\x00MIPMAP\x00REDUCE_LESS\x00"
    b"PLATFORM_FORMAT\x00QUALITY_HIGH\x00\x00\x00\x00"
    b"\x10\x00\x00\x00ASOBO_opacities\x00"
    b"\x0e\x00\x00\x00ASOBO_transp\x00\x00\x00\x00"
    b"\x14\x00\x00\x00ASOBOtexversion\x00\x01\x00\x00\x00"
    b"\x1a\x00\x00\x00KTXwriter\x00ASOBO_FlightSim\x00\x00\x00"
)


def _fake_bc7(width, height):
    levels = []
    w, h = width, height
    while True:
        n_blocks = max(1, (w + 3) // 4) * max(1, (h + 3) // 4)
        levels.append(MipLevel(w, h, b"\xAB" * (n_blocks * 16)))
        if w == 1 and h == 1:
            break
        w, h = max(1, w // 2), max(1, h // 2)
    return DdsFile(width=width, height=height, format="BC7", mip_levels=levels)


def test_kvd_matches_reference_bytes():
    assert build_kvd(False) == REFERENCE_KVD_OPAQUE
    assert len(build_kvd(True)) == 184
    assert b"ASOBO_transp\x00\x01" in build_kvd(True)


def test_write_ktx2_header_and_levels(tmp_path):
    out = tmp_path / "t.PNG.KTX2"
    write_ktx2(out, _fake_bc7(16, 16), transparent=False)
    data = out.read_bytes()
    assert data[:12] == bytes.fromhex("ab4b5458203230bb0d0a1a0a")
    vk, ts, w, h, depth, layers, faces, levels = struct.unpack_from("<8I", data, 12)
    assert (vk, ts, w, h, depth, layers, faces, levels) == (145, 1, 16, 16, 0, 0, 1, 5)
    sc, dfd_off, dfd_len, kvd_off, kvd_len = struct.unpack_from("<5I", data, 44)
    assert sc == 0
    assert data[dfd_off:dfd_off + dfd_len] == DFD_BC7
    assert kvd_len == 184
    # Level-Index: Eintrag 0 = größte Ebene, Daten im File kleinste zuerst, 16er-Alignment
    offsets = []
    for i in range(levels):
        off, length, unc = struct.unpack_from("<3Q", data, 80 + i * 24)
        assert length == unc
        assert off % 16 == 0
        offsets.append((off, length))
    assert offsets[0][1] == 16 * 16  # 16x16 -> 16 Blöcke à 16 Byte
    assert offsets[-1][0] < offsets[0][0]  # kleinste Ebene liegt vorne im File
    assert offsets[0][0] + offsets[0][1] == len(data)


def test_write_ktx2_rejects_non_bc7(tmp_path):
    dds = DdsFile(width=4, height=4, format="BC3", mip_levels=[MipLevel(4, 4, b"\0" * 16)])
    with pytest.raises(ValueError):
        write_ktx2(tmp_path / "x.KTX2", dds, transparent=False)


def test_flags_json_sidecar(tmp_path):
    ktx2 = tmp_path / "A.PNG.KTX2"
    ktx2.write_bytes(b"x")
    sidecar = write_flags_json(ktx2, 134271355895062044)
    assert sidecar.name == "A.PNG.KTX2.json"
    text = sidecar.read_text()
    assert '"SourceFileDate":134271355895062044' in text.replace(" ", "")
    assert "FL_BITMAP_QUALITY_HIGH" in text


def test_filetime_epoch():
    assert filetime_from_unix(0) == 116444736000000000


@pytest.mark.skipif(not REF_TEX_DIR.exists(), reason="real sample data not present")
def test_kvd_and_dfd_match_real_reference_files():
    opaque = (REF_TEX_DIR / "A380X_EXT_ENG_LH_ALBD.PNG.KTX2").read_bytes()
    transparent = (REF_TEX_DIR / "A380X_AFT_STAIRS_ALBD.PNG.KTX2").read_bytes()
    for blob, expected_kvd in ((opaque, build_kvd(False)), (transparent, build_kvd(True))):
        dfd_off, dfd_len, kvd_off, kvd_len = struct.unpack_from("<4I", blob, 48)
        assert blob[dfd_off:dfd_off + dfd_len] == DFD_BC7
        assert blob[kvd_off:kvd_off + kvd_len] == expected_kvd
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_ktx2.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/texture/ktx2.py`:

```python
"""KTX2 writer, calibrated byte-for-byte against the FBW 2024 reference livery."""

import json
import struct
from pathlib import Path

from a380x_livery_converter.texture.dds import DdsFile

KTX2_IDENTIFIER = bytes.fromhex("ab4b5458203230bb0d0a1a0a")
VK_FORMAT_BC7_UNORM_BLOCK = 145
LEVEL_ALIGNMENT = 16  # BC7 block byte size
DFD_BC7 = bytes.fromhex(
    "2c000000000000000200280086010100"
    "03030000100000000000000000007f00"
    "0000000000000000ffffffff"
)
_ASOBO_FLAGS = (b"BILINEAR\x00COMPRESSION\x00MIPMAP\x00REDUCE_LESS\x00"
                b"PLATFORM_FORMAT\x00QUALITY_HIGH\x00")
SIDECAR_FLAGS = ["FL_BITMAP_COMPRESSION", "FL_BITMAP_MIPMAP", "FL_BITMAP_QUALITY_HIGH"]

_EPOCH_DIFF = 11644473600  # seconds between 1601-01-01 and 1970-01-01


def filetime_from_unix(ts: float) -> int:
    return int((ts + _EPOCH_DIFF) * 10_000_000)


def build_kvd(transparent: bool) -> bytes:
    entries = [
        (b"ASOBO_flags", _ASOBO_FLAGS),
        (b"ASOBO_opacities", b""),
        (b"ASOBO_transp", b"\x01" if transparent else b"\x00"),
        (b"ASOBOtexversion", struct.pack("<I", 1)),
        (b"KTXwriter", b"ASOBO_FlightSim\x00"),
    ]
    out = bytearray()
    for key, value in entries:
        kv = key + b"\x00" + value
        out += struct.pack("<I", len(kv)) + kv
        out += b"\x00" * (-len(kv) % 4)
    return bytes(out)


def write_ktx2(path: Path, dds: DdsFile, transparent: bool) -> None:
    if dds.format != "BC7":
        raise ValueError(f"KTX2 writer requires BC7 input, got {dds.format}")
    kvd = build_kvd(transparent)
    level_count = len(dds.mip_levels)
    dfd_off = 80 + level_count * 24
    kvd_off = dfd_off + len(DFD_BC7)
    data_start = kvd_off + len(kvd)

    # Daten im File: kleinste Mip-Ebene zuerst (wie Referenz), 16-Byte-aligned
    offsets: dict[int, int] = {}
    pos = data_start
    for i in reversed(range(level_count)):
        pos = -(-pos // LEVEL_ALIGNMENT) * LEVEL_ALIGNMENT
        offsets[i] = pos
        pos += len(dds.mip_levels[i].data)

    header = KTX2_IDENTIFIER + struct.pack(
        "<9I", VK_FORMAT_BC7_UNORM_BLOCK, 1, dds.width, dds.height,
        0, 0, 1, level_count, 0)
    index = struct.pack("<4I2Q", dfd_off, len(DFD_BC7), kvd_off, len(kvd), 0, 0)
    level_index = b"".join(
        struct.pack("<3Q", offsets[i], len(lvl.data), len(lvl.data))
        for i, lvl in enumerate(dds.mip_levels))

    blob = bytearray(header + index + level_index + DFD_BC7 + kvd)
    # Padding + Daten sequenziell schreiben (kleinste Ebene zuerst)
    for i in reversed(range(level_count)):
        blob += b"\x00" * (offsets[i] - len(blob))
        blob += dds.mip_levels[i].data
    Path(path).write_bytes(bytes(blob))


def write_flags_json(ktx2_path: Path, source_file_date: int) -> Path:
    sidecar = Path(str(ktx2_path) + ".json")
    sidecar.write_text(json.dumps(
        {"Version": 2, "SourceFileDate": source_file_date, "Flags": SIDECAR_FLAGS},
        separators=(",", ":")))
    return sidecar
```

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_ktx2.py -v`
Expected: PASS (6 passed; Referenzdaten-Test nur mit `data/`).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/texture/ktx2.py tests/test_ktx2.py
git commit -m "Add MSFS-calibrated KTX2 writer with ASOBO metadata"
```

---

### Task 8: texture/pipeline.py — DDS → KTX2 für eine Datei

**Files:**
- Create: `src/a380x_livery_converter/texture/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `read_dds`/`DdsError` (Task 5), `dds_to_bc7_dds`/`TexconvError` (Task 6), `write_ktx2`/`write_flags_json`/`filetime_from_unix` (Task 7).
- Produces:
  - `convert_texture(src: Path, dest_ktx2: Path, work_dir: Path) -> None` — komplette Konvertierung einer DDS-Datei inkl. Sidecar-JSON; propagiert `DdsError`/`TexconvError` (Aufrufer fängt pro Datei).
  - `has_transparency(dds: DdsFile) -> bool` — dekodiert die kleinste Mip-Ebene ≥ 4×4 (BC1/BC3 via texture2ddecoder) und prüft auf Alpha < 250.

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_pipeline.py`:

```python
import struct

import texture2ddecoder

from a380x_livery_converter.texture.dds import read_dds
from a380x_livery_converter.texture.pipeline import convert_texture, has_transparency
from tests.helpers import make_bc3_dds


def _largest_level(ktx2_bytes):
    levels = struct.unpack_from("<I", ktx2_bytes, 40)[0]
    off, length, _ = struct.unpack_from("<3Q", ktx2_bytes, 80)
    w, h = struct.unpack_from("<2I", ktx2_bytes, 20)
    assert levels >= 1
    return ktx2_bytes[off:off + length], w, h


def test_convert_opaque_texture(tmp_path):
    src = tmp_path / "A380X_TEST.PNG.DDS"
    src.write_bytes(make_bc3_dds(8, 8))
    dest = tmp_path / "out" / "A380X_TEST.PNG.KTX2"
    convert_texture(src, dest, tmp_path / "work")
    blob = dest.read_bytes()
    assert blob[:4] == b"\xabKTX"
    assert struct.unpack_from("<I", blob, 12)[0] == 145
    assert b"ASOBO_transp\x00\x00" in blob
    assert (dest.parent / "A380X_TEST.PNG.KTX2.json").is_file()


def test_convert_transparent_texture_sets_transp_flag(tmp_path):
    src = tmp_path / "T.PNG.DDS"
    src.write_bytes(make_bc3_dds(8, 8, alpha=40))
    dest = tmp_path / "out" / "T.PNG.KTX2"
    convert_texture(src, dest, tmp_path / "work")
    assert b"ASOBO_transp\x00\x01" in dest.read_bytes()


def test_roundtrip_color_survives(tmp_path):
    src = tmp_path / "C.PNG.DDS"
    src.write_bytes(make_bc3_dds(16, 16))
    dest = tmp_path / "out" / "C.PNG.KTX2"
    convert_texture(src, dest, tmp_path / "work")
    data, w, h = _largest_level(dest.read_bytes())
    decoded = texture2ddecoder.decode_bc7(data, w, h)  # BGRA
    pixels = [(decoded[i + 2], decoded[i + 1], decoded[i]) for i in range(0, len(decoded), 4)]
    avg = [sum(c) / len(c) for c in zip(*pixels)]
    assert abs(avg[0] - 200) < 25 and abs(avg[1] - 30) < 25 and abs(avg[2] - 30) < 25


def test_has_transparency(tmp_path):
    opaque = tmp_path / "o.dds"
    opaque.write_bytes(make_bc3_dds(8, 8, alpha=255))
    transparent = tmp_path / "t.dds"
    transparent.write_bytes(make_bc3_dds(8, 8, alpha=0))
    assert has_transparency(read_dds(opaque)) is False
    assert has_transparency(read_dds(transparent)) is True
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/texture/pipeline.py`:

```python
"""Full conversion of one legacy DDS texture into a 2024 KTX2 texture."""

from pathlib import Path

import texture2ddecoder

from a380x_livery_converter.texture.dds import DdsFile, read_dds
from a380x_livery_converter.texture.ktx2 import (
    filetime_from_unix,
    write_flags_json,
    write_ktx2,
)
from a380x_livery_converter.texture.texconv import dds_to_bc7_dds

_ALPHA_THRESHOLD = 250


def has_transparency(dds: DdsFile) -> bool:
    if dds.format not in ("BC1", "BC3"):
        return False
    level = dds.mip_levels[0]
    for candidate in reversed(dds.mip_levels):
        if candidate.width >= 4 and candidate.height >= 4:
            level = candidate
            break
    if dds.format == "BC1":
        decoded = texture2ddecoder.decode_bc1(level.data, level.width, level.height)
    else:
        decoded = texture2ddecoder.decode_bc3(level.data, level.width, level.height)
    return any(a < _ALPHA_THRESHOLD for a in decoded[3::4])


def convert_texture(src: Path, dest_ktx2: Path, work_dir: Path) -> None:
    src = Path(src)
    dest_ktx2 = Path(dest_ktx2)
    source = read_dds(src)  # validates the input file
    transparent = has_transparency(source)
    bc7_dds_path = dds_to_bc7_dds(src, Path(work_dir))
    try:
        bc7 = read_dds(bc7_dds_path)
        dest_ktx2.parent.mkdir(parents=True, exist_ok=True)
        write_ktx2(dest_ktx2, bc7, transparent)
        write_flags_json(dest_ktx2, filetime_from_unix(src.stat().st_mtime))
    finally:
        bc7_dds_path.unlink(missing_ok=True)
```

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_pipeline.py -v`
Expected: PASS (4 passed).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/texture/pipeline.py tests/test_pipeline.py
git commit -m "Add DDS to KTX2 conversion pipeline with transparency detection"
```

---

### Task 9: output/livery_gen.py — livery.cfg, texture.CFG, Thumbnails

**Files:**
- Create: `src/a380x_livery_converter/output/livery_gen.py`
- Test: `tests/test_livery_gen.py`

**Interfaces:**
- Consumes: `Variant` (Task 4), `resource_path` (Task 1).
- Produces:
  - `livery_cfg_text(variant: Variant) -> str`
  - `TEXTURE_CFG: str` (Konstante) und `write_texture_cfg(texture_dir: Path) -> None`
  - `find_old_thumbnail(texture_dir: Path | None) -> Path | None` — sucht `thumbnail.jpg/.png` case-insensitiv.
  - `write_thumbnails(src_image: Path | None, thumb_dir: Path) -> list[str]` — erzeugt die drei PNG-Thumbnails (Cover-Resize mit Center-Crop); bei `None` Paintkit-Platzhalter; Rückgabe = Warnungen.

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_livery_gen.py`:

```python
from pathlib import Path

from PIL import Image

from a380x_livery_converter.core.scanner import Variant
from a380x_livery_converter.output.livery_gen import (
    TEXTURE_CFG,
    find_old_thumbnail,
    livery_cfg_text,
    write_texture_cfg,
    write_thumbnails,
)


def _variant(**overrides):
    defaults = dict(folder=Path("x"), index=0, title="T", ui_variation="HUES QATAR A7-APC",
                    atc_id="A7-APC", atc_airline="Qatar Airways", icao_airline="QTR",
                    texture_suffix="A7APC", texture_dir=None, has_custom_model=False)
    defaults.update(overrides)
    return Variant(**defaults)


def test_livery_cfg_content():
    text = livery_cfg_text(_variant())
    assert '[GENERAL]' in text and '[version]' in text
    assert 'Name = "HUES QATAR A7-APC"' in text
    assert 'atc_airline="Qatar Airways"' in text
    assert 'icao_airline="QTR"' in text
    assert 'atc_parking_codes="QTR"' in text
    assert "ui_createdby" not in text


def test_livery_cfg_falls_back_to_title():
    text = livery_cfg_text(_variant(ui_variation=""))
    assert 'Name = "T"' in text


def test_texture_cfg_written(tmp_path):
    write_texture_cfg(tmp_path)
    content = (tmp_path / "texture.CFG").read_text()
    assert content == TEXTURE_CFG
    assert "fallback.1=..\\..\\..\\common\\texture" in content
    assert "fallback.2=..\\..\\FlyByWire_A380_842\\texture" in content


def test_find_old_thumbnail_case_insensitive(tmp_path):
    Image.new("RGB", (100, 50), "blue").save(tmp_path / "THUMBNAIL.JPG")
    found = find_old_thumbnail(tmp_path)
    assert found is not None and found.name == "THUMBNAIL.JPG"
    assert find_old_thumbnail(None) is None


def test_write_thumbnails_from_source(tmp_path):
    src = tmp_path / "thumbnail.JPG"
    Image.new("RGB", (412, 170), "blue").save(src)
    warnings = write_thumbnails(src, tmp_path / "thumb")
    assert warnings == []
    assert Image.open(tmp_path / "thumb" / "thumbnail.png").size == (720, 344)
    assert Image.open(tmp_path / "thumb" / "thumbnail_button.png").size == (830, 260)
    assert Image.open(tmp_path / "thumb" / "thumbnail_side.png").size == (930, 340)


def test_write_thumbnails_placeholder_when_missing(tmp_path):
    warnings = write_thumbnails(None, tmp_path / "thumb")
    assert len(warnings) == 1
    assert (tmp_path / "thumb" / "thumbnail.png").is_file()
    assert (tmp_path / "thumb" / "thumbnail_side.png").is_file()
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_livery_gen.py -v`
Expected: FAIL mit `ModuleNotFoundError` (bzw. `TypeError` zu `icao_airline`, falls Task 4 das Feld nicht enthält — dann Task-4-Interface prüfen: das Feld ist dort definiert).

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/output/livery_gen.py`:

```python
"""Generation of livery.cfg, texture.CFG and thumbnails for one converted livery."""

from pathlib import Path

from PIL import Image

from a380x_livery_converter import resource_path
from a380x_livery_converter.core.scanner import Variant

TEXTURE_CFG = (
    "[fltsim]\n"
    "fallback.1=..\\..\\..\\common\\texture\n"
    "fallback.2=..\\..\\FlyByWire_A380_842\\texture\n"
    "fallback.3=..\\..\\..\\..\\texture\\DetailMap\n"
    "fallback.4=..\\..\\..\\..\\texture\\Glass\n"
    "fallback.5=..\\..\\..\\..\\texture\\Interiors\n"
    "fallback.6=..\\..\\..\\..\\texture\n"
)

THUMBNAIL_SIZES = {
    "thumbnail.png": (720, 344),
    "thumbnail_button.png": (830, 260),
    "thumbnail_side.png": (930, 340),
}

_THUMBNAIL_NAMES = {"THUMBNAIL.JPG", "THUMBNAIL.PNG", "THUMBNAIL.JPEG"}


def livery_cfg_text(variant: Variant) -> str:
    name = variant.ui_variation or variant.title
    return (
        "[version]\n"
        "major = 1\n"
        "minor = 0\n"
        "\n"
        "[GENERAL]\n"
        f'Name = "{name}"\n'
        f'atc_id="{variant.atc_id}"\n'
        f'atc_parking_codes="{variant.icao_airline}"\n'
        f'icao_airline="{variant.icao_airline}"\n'
        f'atc_airline="{variant.atc_airline}"\n'
    )


def write_texture_cfg(texture_dir: Path) -> None:
    Path(texture_dir).mkdir(parents=True, exist_ok=True)
    (Path(texture_dir) / "texture.CFG").write_text(TEXTURE_CFG, encoding="utf-8")


def find_old_thumbnail(texture_dir: Path | None) -> Path | None:
    if texture_dir is None or not Path(texture_dir).is_dir():
        return None
    for child in Path(texture_dir).iterdir():
        if child.name.upper() in _THUMBNAIL_NAMES:
            return child
    return None


def write_thumbnails(src_image: Path | None, thumb_dir: Path) -> list[str]:
    thumb_dir = Path(thumb_dir)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    if src_image is None:
        warnings.append("No source thumbnail found - using paintkit placeholders")
    for name, size in THUMBNAIL_SIZES.items():
        if src_image is not None:
            img = Image.open(src_image).convert("RGB")
            out = _cover_resize(img, size)
        else:
            out = Image.open(resource_path(f"thumbnails/{name}"))
        out.save(thumb_dir / name)
    return warnings


def _cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))
```

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_livery_gen.py -v`
Expected: PASS (6 passed).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/output/livery_gen.py tests/test_livery_gen.py
git commit -m "Add livery.cfg, texture.CFG and thumbnail generation"
```

---

### Task 10: output/package_gen.py — manifest.json, layout.json, Report, Namen

**Files:**
- Create: `src/a380x_livery_converter/output/package_gen.py`
- Test: `tests/test_package_gen.py`

**Interfaces:**
- Consumes: `OldPackage`, `Variant` (Task 4), `filetime_from_unix` (Task 7).
- Produces:
  - `LIVERIES_SUBPATH: Path` = `SimObjects/AirPlanes/FlyByWire_A380X/liveries`
  - `package_folder_name(old: OldPackage) -> str` — z. B. `testcreator-livery-fbw-a380x-test-fleet-pack`
  - `livery_folder_name(variant: Variant) -> str` — z. B. `FlyByWire_A380_842_A7APC`
  - `write_layout(root: Path) -> None` — layout.json über alle Dateien außer layout.json/manifest.json/conversion_report.txt
  - `write_manifest(root: Path, title: str, creator: str, version: str) -> None` — nach `write_layout` aufrufen (total_package_size zählt layout.json mit)
  - `write_report(root: Path, warnings: list[str], converted: int, skipped: int, source: OldPackage) -> Path`

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_package_gen.py`:

```python
import json
from pathlib import Path

from a380x_livery_converter.core.scanner import OldPackage, Variant
from a380x_livery_converter.output.package_gen import (
    livery_folder_name,
    package_folder_name,
    write_layout,
    write_manifest,
    write_report,
)


def _old_package(title="Fleet Pack: SD & HD!", creator="HUES | Valexyo"):
    return OldPackage(root=Path("x"), title=title, creator=creator,
                      package_version="2.0", variants=[], common_texture_dir=None)


def _variant(suffix="A7APC"):
    return Variant(folder=Path("x"), index=0, title="t", ui_variation="u", atc_id="A380X",
                   atc_airline="a", icao_airline="", texture_suffix=suffix,
                   texture_dir=None, has_custom_model=False)


def test_package_folder_name_sanitized():
    name = package_folder_name(_old_package())
    assert name == "hues-valexyo-livery-fbw-a380x-fleet-pack-sd-hd"
    assert " " not in name and ":" not in name


def test_livery_folder_name():
    assert livery_folder_name(_variant()) == "FlyByWire_A380_842_A7APC"
    assert livery_folder_name(_variant(suffix="")) == "FlyByWire_A380_842_A380X"


def test_layout_excludes_meta_files(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.KTX2").write_bytes(b"12345")
    (tmp_path / "conversion_report.txt").write_text("report")
    write_layout(tmp_path)
    layout = json.loads((tmp_path / "layout.json").read_text())
    paths = [e["path"] for e in layout["content"]]
    assert paths == ["sub/a.KTX2"]
    entry = layout["content"][0]
    assert entry["size"] == 5
    assert entry["date"] > 116444736000000000  # FILETIME after 1970


def test_manifest_content(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 100)
    write_layout(tmp_path)
    write_manifest(tmp_path, "My Livery", "Creator", "2.0")
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["content_type"] == "LIVERY"
    assert manifest["minimum_game_version"] == "1.26.5"
    assert manifest["title"] == "My Livery (MSFS2024)"
    assert {d["name"] for d in manifest["dependencies"]} == {
        "asobo-vcockpits-instruments-airliners", "fs-base-aircraft-common"}
    total = manifest["total_package_size"]
    assert len(total) == 20 and total.isdigit()
    assert int(total) >= 100  # a.bin + layout.json


def test_report_lists_warnings(tmp_path):
    path = write_report(tmp_path, ["warn one", "warn two"], converted=5, skipped=1,
                        source=_old_package())
    text = path.read_text()
    assert "warn one" in text and "warn two" in text
    assert "5" in text and "Fleet Pack" in text
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_package_gen.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/output/package_gen.py`:

```python
"""Package level generation: folder names, manifest.json, layout.json, report."""

import json
import re
from pathlib import Path

from a380x_livery_converter.core.scanner import OldPackage, Variant
from a380x_livery_converter.texture.ktx2 import filetime_from_unix

LIVERIES_SUBPATH = Path("SimObjects") / "AirPlanes" / "FlyByWire_A380X" / "liveries"

MANIFEST_DEPENDENCIES = [
    {"package_version": "0.1.129", "name": "asobo-vcockpits-instruments-airliners"},
    {"package_version": "0.1.125", "name": "fs-base-aircraft-common"},
]

_EXCLUDED_FROM_LAYOUT = {"layout.json", "manifest.json", "conversion_report.txt"}


def _sanitize(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned or "unnamed"


def package_folder_name(old: OldPackage) -> str:
    return _sanitize(f"{old.creator}-livery-fbw-a380x-{old.title}").lower()


def livery_folder_name(variant: Variant) -> str:
    tag = variant.texture_suffix or variant.atc_id or f"VAR{variant.index}"
    return f"FlyByWire_A380_842_{_sanitize(tag)}"


def write_layout(root: Path) -> None:
    root = Path(root)
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in _EXCLUDED_FROM_LAYOUT:
            continue
        stat = path.stat()
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "size": stat.st_size,
            "date": filetime_from_unix(stat.st_mtime),
        })
    (root / "layout.json").write_text(json.dumps({"content": entries}, indent=2))


def write_manifest(root: Path, title: str, creator: str, version: str) -> None:
    root = Path(root)
    total = sum(p.stat().st_size for p in root.rglob("*")
                if p.is_file() and p.name != "manifest.json")
    manifest = {
        "dependencies": MANIFEST_DEPENDENCIES,
        "content_type": "LIVERY",
        "title": f"{title} (MSFS2024)",
        "manufacturer": "Airbus",
        "creator": creator,
        "package_version": version or "1.0.0",
        "minimum_game_version": "1.26.5",
        "total_package_size": f"{total:020d}",
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))


def write_report(root: Path, warnings: list[str], converted: int, skipped: int,
                 source: OldPackage) -> Path:
    lines = [
        "A380X Livery Converter - conversion report",
        "=" * 44,
        "",
        f"Source package  : {source.title} (by {source.creator})",
        f"Variants        : {len(source.variants)}",
        f"Textures OK     : {converted}",
        f"Textures skipped: {skipped}",
        "",
    ]
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {w}" for w in warnings)
    else:
        lines.append("No warnings.")
    lines += ["", "Note: interior/cabin textures are converted as-is; whether the native",
              "2024 model actually uses them is outside this tool's control."]
    path = Path(root) / "conversion_report.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_package_gen.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/output/package_gen.py tests/test_package_gen.py
git commit -m "Add package generation for manifest, layout and report"
```

---

### Task 11: converter.py — Orchestrierung

**Files:**
- Create: `src/a380x_livery_converter/converter.py`
- Test: `tests/test_converter.py`

**Interfaces:**
- Consumes: alles aus Tasks 3–10 (`scan_package`, `load_rename_map`/`map_texture_filename`, `convert_texture`, `livery_gen.*`, `package_gen.*`, Fehlertypen `DdsError`/`TexconvError`).
- Produces:
  - `@dataclass ConversionResult`: `output_root: Path`, `converted: int`, `skipped: int`, `warnings: list[str]`
  - `class Converter` mit `__init__(input_dir: Path, output_dir: Path, progress: Callable[[int, int, str], None] | None = None, dry_run: bool = False, max_workers: int | None = None)` und `run() -> ConversionResult` (wirft `NotAnA380XPackageError` weiter).

**Verhalten (verbindlich):**
- Jede `[FLTSIM]`-Variante wird ein Livery-Ordner `liveries/flybywire/<livery_folder_name>/` mit `livery.cfg`, `texture/` (inkl. `texture.CFG`), `thumbnail/`.
- „Common Textures"-Ordner → `liveries/common/texture/`.
- Cross-Variant-Dedup: identische Quelldateien (gleicher Ziel-Name + SHA1) aus mehreren Varianten werden genau einmal nach `liveries/common/texture/` konvertiert.
- Alte `.DDS.json`-Sidecars, `texture.CFG` und Thumbnails der Quelle werden nicht kopiert (werden neu generiert); sonstige Fremddateien werden ignoriert.
- Custom-`MODEL.*` → Warnung; korrupte DDS → Warnung + `skipped`; unbekannte Texturnamen → Warnung.
- Texturjobs laufen parallel im ThreadPool, jeder Job mit eigenem Work-Unterordner (texconv-Ausgabenamen kollidieren sonst zwischen Varianten).
- `dry_run=True`: nur scannen und planen, nichts schreiben; Warnung `[dry-run] would convert N textures ...` anhängen.

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_converter.py`:

```python
import json

from a380x_livery_converter.converter import Converter
from tests.helpers import make_bc3_dds, make_old_package

LIVERIES = "SimObjects/AirPlanes/FlyByWire_A380X/liveries"


def _convert(tmp_path, **kwargs):
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    out = tmp_path / "out"
    progress_calls = []
    conv = Converter(pkg, out, progress=lambda d, t, m: progress_calls.append((d, t)), **kwargs)
    return conv.run(), out, progress_calls


def test_full_conversion_structure(tmp_path):
    result, out, progress_calls = _convert(tmp_path)
    root = result.output_root
    assert root.parent == out
    for suffix in ("A7APC", "A7APD"):
        livery = root / LIVERIES / "flybywire" / f"FlyByWire_A380_842_{suffix}"
        assert (livery / "livery.cfg").is_file()
        assert (livery / "texture" / "texture.CFG").is_file()
        assert (livery / "thumbnail" / "thumbnail.png").is_file()
    # identische Dateien beider Varianten + Common Textures liegen dedupliziert in common
    common = root / LIVERIES / "common" / "texture"
    assert (common / "A380X_FUSE1_ALBD.PNG.KTX2").is_file()      # dedupliziert
    assert (common / "A380X_FUSE2_ALBD.PNG.KTX2").is_file()      # aus Common Textures
    assert (common / "CUSTOM_DECAL.PNG.KTX2").is_file()          # unbekannt, dedupliziert
    assert (common / "A380X_FUSE1_ALBD.PNG.KTX2.json").is_file()
    assert result.converted == 3
    assert result.skipped == 0
    assert (root / "manifest.json").is_file()
    assert (root / "layout.json").is_file()
    assert (root / "conversion_report.txt").is_file()
    assert progress_calls, "progress callback was never invoked"


def test_warnings_for_model_and_unmapped(tmp_path):
    result, _, _ = _convert(tmp_path)
    joined = "\n".join(result.warnings)
    assert "MODEL" in joined
    assert "CUSTOM_DECAL" in joined


def test_layout_covers_generated_files(tmp_path):
    result, _, _ = _convert(tmp_path)
    layout = json.loads((result.output_root / "layout.json").read_text())
    paths = {e["path"] for e in layout["content"]}
    assert any(p.endswith("livery.cfg") for p in paths)
    assert any(p.endswith(".KTX2") for p in paths)
    assert not any(p.endswith("conversion_report.txt") for p in paths)


def test_corrupt_dds_is_skipped_with_warning(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False)
    bad = pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "TEXTURE.X" / "BROKEN.PNG.DDS"
    bad.write_bytes(b"garbage")
    result = Converter(pkg, tmp_path / "out").run()
    assert result.skipped == 1
    assert any("BROKEN" in w for w in result.warnings)


def test_dry_run_writes_nothing(tmp_path):
    result, out, _ = _convert(tmp_path, dry_run=True)
    assert not out.exists()
    assert result.converted == 0
    assert any("dry-run" in w for w in result.warnings)
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_converter.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/converter.py`:

```python
"""Top-level conversion orchestration."""

import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from a380x_livery_converter.core.rename_map import load_rename_map, map_texture_filename
from a380x_livery_converter.core.scanner import Variant, scan_package
from a380x_livery_converter.output import livery_gen, package_gen
from a380x_livery_converter.texture.dds import DdsError
from a380x_livery_converter.texture.pipeline import convert_texture
from a380x_livery_converter.texture.texconv import TexconvError

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class ConversionResult:
    output_root: Path
    converted: int
    skipped: int
    warnings: list[str]


@dataclass
class _TextureJob:
    src: Path
    dest: Path
    label: str


def _dds_files(folder: Path) -> list[Path]:
    return sorted(p for p in Path(folder).iterdir()
                  if p.is_file() and p.name.upper().endswith(".DDS"))


class Converter:
    def __init__(self, input_dir: Path, output_dir: Path,
                 progress: ProgressCallback | None = None,
                 dry_run: bool = False, max_workers: int | None = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.progress: ProgressCallback = progress or (lambda done, total, msg: None)
        self.dry_run = dry_run
        self.max_workers = max_workers or min(8, os.cpu_count() or 4)

    def run(self) -> ConversionResult:
        old = scan_package(self.input_dir)
        rename_map = load_rename_map()
        warnings: list[str] = []

        out_root = self.output_dir / package_gen.package_folder_name(old)
        flybywire_root = out_root / package_gen.LIVERIES_SUBPATH / "flybywire"
        common_texture = out_root / package_gen.LIVERIES_SUBPATH / "common" / "texture"

        jobs: list[_TextureJob] = []
        if old.common_texture_dir is not None:
            for src in _dds_files(old.common_texture_dir):
                name = self._mapped(src.name, rename_map, warnings)
                jobs.append(_TextureJob(src, common_texture / name, f"common/{src.name}"))

        # Variantentexturen sammeln, identische Dateien über Varianten deduplizieren
        grouped: dict[tuple[str, str], list[tuple[Variant, Path]]] = {}
        for variant in old.variants:
            if variant.has_custom_model:
                warnings.append(f"{variant.title}: custom MODEL folder cannot be converted "
                                f"- decals/3D additions are lost")
            if variant.texture_dir is None:
                warnings.append(f"{variant.title}: no texture folder found - variant skipped")
                continue
            for src in _dds_files(variant.texture_dir):
                name = self._mapped(src.name, rename_map, warnings)
                digest = hashlib.sha1(src.read_bytes()).hexdigest()
                grouped.setdefault((name, digest), []).append((variant, src))
        for (name, _digest), sources in grouped.items():
            variants_involved = {id(v) for v, _ in sources}
            if len(variants_involved) > 1:
                jobs.append(_TextureJob(sources[0][1], common_texture / name, f"common/{name}"))
            else:
                variant, src = sources[0]
                dest = (flybywire_root / package_gen.livery_folder_name(variant)
                        / "texture" / name)
                jobs.append(_TextureJob(src, dest, f"{variant.texture_suffix}/{src.name}"))

        # Ziel-Kollisionen (z. B. Dedup-Name schon aus Common Textures belegt): erster gewinnt
        unique: dict[Path, _TextureJob] = {}
        for job in jobs:
            unique.setdefault(job.dest, job)
        jobs = list(unique.values())

        if self.dry_run:
            warnings.append(f"[dry-run] would convert {len(jobs)} textures into {out_root}")
            return ConversionResult(out_root, 0, 0, warnings)

        total = len(jobs) + len(old.variants) + 2
        done = 0
        converted = skipped = 0
        with tempfile.TemporaryDirectory(prefix="a380xconv_") as tmp, \
                ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for i, job in enumerate(jobs):
                futures[pool.submit(convert_texture, job.src, job.dest,
                                    Path(tmp) / f"job{i}")] = job
            for future in as_completed(futures):
                job = futures[future]
                try:
                    future.result()
                    converted += 1
                except (DdsError, TexconvError, OSError, ValueError) as exc:
                    skipped += 1
                    warnings.append(f"Texture skipped ({job.label}): {exc}")
                done += 1
                self.progress(done, total, f"Texture {job.label}")

        for variant in old.variants:
            livery_dir = flybywire_root / package_gen.livery_folder_name(variant)
            livery_gen.write_texture_cfg(livery_dir / "texture")
            livery_dir.mkdir(parents=True, exist_ok=True)
            (livery_dir / "livery.cfg").write_text(livery_gen.livery_cfg_text(variant),
                                                   encoding="utf-8")
            thumb = livery_gen.find_old_thumbnail(variant.texture_dir)
            for w in livery_gen.write_thumbnails(thumb, livery_dir / "thumbnail"):
                warnings.append(f"{variant.title}: {w}")
            done += 1
            self.progress(done, total, f"Config for {variant.title}")

        package_gen.write_report(out_root, warnings, converted=converted,
                                 skipped=skipped, source=old)
        package_gen.write_layout(out_root)
        done += 1
        self.progress(done, total, "layout.json")
        package_gen.write_manifest(out_root, old.title, old.creator, old.package_version)
        done += 1
        self.progress(done, total, "manifest.json")
        return ConversionResult(out_root, converted, skipped, warnings)

    @staticmethod
    def _mapped(filename: str, rename_map: dict[str, str], warnings: list[str]) -> str:
        name, was_mapped = map_texture_filename(filename, rename_map)
        if not was_mapped:
            warnings.append(f"Unknown texture name kept as-is: {filename}")
        return name
```

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_converter.py -v`
Expected: PASS (5 passed). Danach Gesamtsuite: `uv run pytest -v` — alles grün.

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/converter.py tests/test_converter.py
git commit -m "Add conversion orchestrator with dedup and parallel texture jobs"
```

---

### Task 12: cli.py — Kommandozeilen-Frontend

**Files:**
- Create: `src/a380x_livery_converter/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `Converter`, `ConversionResult` (Task 11), `NotAnA380XPackageError` (Task 4).
- Produces: `app: typer.Typer` mit Command `convert INPUT_DIR -o OUTPUT [--dry-run] [--verbose]`. Exit-Codes: 0 = ok, 1 = fertig mit Warnungen/Skips, 2 = Fehler.

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_cli.py`:

```python
from typer.testing import CliRunner

from a380x_livery_converter.cli import app
from tests.helpers import make_bc3_dds, make_old_package

runner = CliRunner()


def test_convert_success_without_warnings_exits_0(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    (pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "TEXTURE.X" / "CUSTOM_DECAL.PNG.DDS").unlink()
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert "Converted textures: 1" in result.output


def test_convert_with_warnings_exits_1(tmp_path):
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out")])
    assert result.exit_code == 1
    assert "WARNING" in result.output


def test_invalid_package_exits_2(tmp_path):
    (tmp_path / "empty").mkdir()
    result = runner.invoke(app, [str(tmp_path / "empty"), "-o", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_dry_run_writes_nothing(tmp_path):
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--dry-run"])
    assert result.exit_code == 1  # dry-run-Hinweis ist eine Warnung
    assert not (tmp_path / "out").exists()


def test_verbose_shows_progress(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--verbose"])
    assert "[1/" in result.output
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL mit `ModuleNotFoundError`.

- [ ] **Step 3: Implementierung**

`src/a380x_livery_converter/cli.py`:

```python
"""Command line front end."""

from pathlib import Path

import typer

from a380x_livery_converter.converter import Converter
from a380x_livery_converter.core.scanner import NotAnA380XPackageError

app = typer.Typer(add_completion=False,
                  help="Convert FBW A380X MSFS 2020 liveries to native MSFS 2024 packages.")


@app.command()
def convert(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False,
                                     help="Old livery package folder (extracted)"),
    output: Path = typer.Option(..., "--output", "-o", file_okay=False,
                                help="Destination folder, e.g. the Community folder"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Scan and plan only, write nothing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-file progress"),
) -> None:
    def progress(done: int, total: int, message: str) -> None:
        if verbose:
            typer.echo(f"[{done}/{total}] {message}")

    try:
        result = Converter(input_dir, output, progress=progress, dry_run=dry_run).run()
    except NotAnA380XPackageError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    typer.echo(f"Output: {result.output_root}")
    typer.echo(f"Converted textures: {result.converted}, skipped: {result.skipped}")
    for warning in result.warnings:
        typer.secho(f"WARNING: {warning}", fg=typer.colors.YELLOW)
    if result.warnings or result.skipped:
        raise typer.Exit(1)
```

- [ ] **Step 4: Tests laufen lassen**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/cli.py tests/test_cli.py
git commit -m "Add typer CLI with dry-run and exit codes"
```

---

### Task 13: gui.py + __main__.py — Tkinter-GUI und Einstieg

**Files:**
- Create: `src/a380x_livery_converter/gui.py`
- Create: `src/a380x_livery_converter/__main__.py`
- Test: `tests/test_gui.py`

**Interfaces:**
- Consumes: `Converter`, `ConversionResult` (Task 11).
- Produces: `gui.main()` startet das Fenster; `python -m a380x_livery_converter` ohne Argumente → GUI, mit Argumenten → CLI (`cli.app`).

- [ ] **Step 1: Failing Tests schreiben**

`tests/test_gui.py` (Smoke-Tests; volle Bedienung wird in Task 15 manuell geprüft):

```python
import tkinter as tk

import pytest


def _make_root():
    try:
        return tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")


def test_app_builds_widgets():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        assert str(app.convert_button.cget("state")) != "disabled"
        assert app.progressbar is not None
    finally:
        root.destroy()


def test_start_without_folders_logs_hint_and_stays_enabled():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        app.start()
        assert "Bitte beide Ordner" in app.log.get("1.0", "end")
        assert str(app.convert_button.cget("state")) != "disabled"
    finally:
        root.destroy()
```

- [ ] **Step 2: Tests laufen lassen — müssen fehlschlagen**

Run: `uv run pytest tests/test_gui.py -v`
Expected: FAIL mit `ModuleNotFoundError` (bzw. SKIP auf Systemen ohne Display).

- [ ] **Step 3: GUI implementieren**

`src/a380x_livery_converter/gui.py`:

```python
"""Tkinter GUI front end."""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

from a380x_livery_converter.converter import Converter


class ConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("FBW A380X Livery Converter (MSFS 2020 -> 2024)")
        root.geometry("680x440")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.queue: queue.Queue = queue.Queue()
        self._running = False

        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)
        self._folder_row(frame, 0, "Altes Livery-Paket:", self.input_var)
        self._folder_row(frame, 1, "Ausgabeordner (Community):", self.output_var)
        self.convert_button = ttk.Button(frame, text="Konvertieren", command=self.start)
        self.convert_button.grid(row=2, column=0, columnspan=3, pady=8, sticky="ew")
        self.progressbar = ttk.Progressbar(frame, maximum=100)
        self.progressbar.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.log = scrolledtext.ScrolledText(frame, height=14, state="disabled")
        self.log.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

    def _folder_row(self, parent, row, label, var):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=4)
        ttk.Button(parent, text="...", width=4,
                   command=lambda: var.set(filedialog.askdirectory() or var.get())
                   ).grid(row=row, column=2)

    def start(self):
        input_dir, output_dir = self.input_var.get().strip(), self.output_var.get().strip()
        if not input_dir or not output_dir:
            self._append_log("Bitte beide Ordner auswählen.")
            return
        self._running = True
        self.convert_button.config(state="disabled")
        self.progressbar.config(value=0)
        threading.Thread(target=self._work, args=(Path(input_dir), Path(output_dir)),
                         daemon=True).start()
        self.root.after(100, self._poll)

    def _work(self, input_dir: Path, output_dir: Path):
        try:
            result = Converter(
                input_dir, output_dir,
                progress=lambda d, t, m: self.queue.put(("progress", d, t, m)),
            ).run()
            self.queue.put(("done", result))
        except Exception as exc:  # GUI boundary: show any failure instead of crashing
            self.queue.put(("error", exc))

    def _poll(self):
        while not self.queue.empty():
            item = self.queue.get_nowait()
            if item[0] == "progress":
                _, done, total, message = item
                self.progressbar.config(maximum=total, value=done)
                self._append_log(f"[{done}/{total}] {message}")
            elif item[0] == "done":
                result = item[1]
                self._append_log("")
                self._append_log(f"Fertig: {result.converted} Texturen konvertiert, "
                                 f"{result.skipped} übersprungen.")
                for warning in result.warnings:
                    self._append_log(f"WARNUNG: {warning}")
                self._append_log(f"Ausgabe: {result.output_root}")
                self._append_log("Details: conversion_report.txt im Ausgabepaket.")
                self._finish()
            elif item[0] == "error":
                self._append_log(f"FEHLER: {item[1]}")
                self._finish()
        if self._running:
            self.root.after(100, self._poll)

    def _finish(self):
        self._running = False
        self.convert_button.config(state="normal")

    def _append_log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()
```

- [ ] **Step 4: __main__.py implementieren**

`src/a380x_livery_converter/__main__.py`:

```python
import sys


def main() -> None:
    if len(sys.argv) > 1:
        from a380x_livery_converter.cli import app
        app()
    else:
        from a380x_livery_converter.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    main()
```

- [ ] **Step 5: Tests laufen lassen**

Run: `uv run pytest tests/test_gui.py -v` und danach die Gesamtsuite `uv run pytest`
Expected: PASS. Zusätzlich manueller Kurzcheck: `uv run python -m a380x_livery_converter` öffnet das Fenster (wieder schließen), `uv run python -m a380x_livery_converter --help` zeigt die CLI-Hilfe.

- [ ] **Step 6: Commit**

```bash
git add src/a380x_livery_converter/gui.py src/a380x_livery_converter/__main__.py tests/test_gui.py
git commit -m "Add Tkinter GUI and entry point with argv routing"
```

---

### Task 14: Nuitka-Exe-Build + README

> **REQUIRED SUB-SKILL:** Vor diesem Task den Skill `python-nuitka` laden — er enthält die aktuellen Flag-Konventionen. Bei Konflikten zwischen Skill und diesem Task gilt der Skill.

**Files:**
- Create: `scripts/build_exe.ps1`
- Create: `README.md`

**Interfaces:**
- Consumes: gesamtes Paket (Tasks 1–13).
- Produces: `dist/A380XLiveryConverter.exe` (onefile; Doppelklick → GUI, mit Argumenten → CLI).

- [ ] **Step 1: Nuitka als Dev-Dependency**

Run: `uv add --dev nuitka`
Expected: nuitka erscheint in `pyproject.toml` unter dev.

- [ ] **Step 2: Build-Skript schreiben**

`scripts/build_exe.ps1`:

```powershell
# Build the single-file Windows executable.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

uv run python -m nuitka `
    --onefile `
    --assume-yes-for-downloads `
    --enable-plugin=tk-inter `
    --include-package=a380x_livery_converter `
    --include-package-data=a380x_livery_converter `
    --windows-console-mode=attach `
    --output-filename=A380XLiveryConverter.exe `
    --output-dir=dist `
    src/a380x_livery_converter/__main__.py

Write-Host "Built dist/A380XLiveryConverter.exe"
```

`--windows-console-mode=attach`: Doppelklick öffnet kein Konsolenfenster (GUI), aus einem Terminal gestartet erscheint die CLI-Ausgabe dort. `--include-package-data` bündelt `resources/` (texconv.exe, rename_list.csv, Thumbnails).

- [ ] **Step 3: Build ausführen und Exe smoke-testen**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1`
Expected: `dist/A380XLiveryConverter.exe` existiert.

Dann:

```powershell
dist/A380XLiveryConverter.exe convert --help   # Exit 0, zeigt Hilfe
dist/A380XLiveryConverter.exe                  # öffnet GUI-Fenster (manuell schließen)
```

Falls die Exe beim Start `resources`-Dateien nicht findet: prüfen, ob `--include-package-data` gegriffen hat (`--include-data-dir=src/a380x_livery_converter/resources=a380x_livery_converter/resources` als Alternative).

- [ ] **Step 4: README schreiben**

`README.md`:

```markdown
# FBW A380X Livery Converter (MSFS 2020 → MSFS 2024)

Converts legacy FlyByWire A380X liveries (MSFS 2020 format, DDS textures) into
ready-to-install native MSFS 2024 packages (KTX2 textures, `liveries/` layout).

## Usage (GUI)

1. Double-click `A380XLiveryConverter.exe`.
2. Select the extracted old livery folder (the one containing `manifest.json` / `SimObjects`).
3. Select your MSFS 2024 Community folder (or any output folder).
4. Click *Konvertieren* and check the log / `conversion_report.txt` for warnings.

## Usage (CLI)

    A380XLiveryConverter.exe convert "C:\path\to\Old Livery" -o "C:\path\to\Community" [--dry-run] [--verbose]

Exit codes: 0 = ok, 1 = finished with warnings, 2 = error.

## Known limitations

- Custom `MODEL.*` folders (3D decal geometry) cannot be ported to the 2024
  livery format; the affected liveries convert without them (warning in report).
- Fleet packs are merged into one output package; identical textures are
  deduplicated into a shared `common/texture` folder.
- Input must be an extracted folder (no zip support).

## Development

    uv sync
    uv run pytest
    powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1

Texture conversion uses the bundled DirectXTex `texconv.exe` (BC7 + mipmaps);
the KTX2 container writer is calibrated against the official FBW 2024 paintkit
reference livery. Rename mapping comes from the FBW paintkit `rename_list.csv`.
```

- [ ] **Step 5: Gesamtsuite + Commit**

Run: `uv run pytest`
Expected: alle Tests PASS.

```bash
git add scripts/build_exe.ps1 README.md pyproject.toml uv.lock
git commit -m "Add Nuitka onefile build script and README"
```

---

### Task 15: End-to-End-Verifikation mit dem Qatar-Fleet-Pack

> **REQUIRED SUB-SKILL:** Vor Abschluss den Skill `superpowers:verification-before-completion` beachten: alle Behauptungen nur mit ausgeführten Kommandos und echter Ausgabe.

**Files:**
- Keine neuen Quelldateien; Verifikationslauf + ggf. Bugfixes mit eigenen Tests.

**Interfaces:**
- Consumes: die fertige Exe bzw. `uv run python -m a380x_livery_converter` (alles zuvor).

- [ ] **Step 1: Kompletten Qatar-Konvertierungslauf ausführen** (nur wenn `data/` vorhanden)

```powershell
uv run python -m a380x_livery_converter convert "data/oldLivery/HUES - QatarAirways Fleet  A380 FBW" -o "dist/e2e-out" --verbose
```

Expected: Exit-Code 1 (Warnungen wegen Custom-MODEL und HUES-Decals sind korrekt), kein Traceback, Laufzeit im Minutenbereich (>100 4K-Texturen).

- [ ] **Step 2: Ausgabestruktur prüfen**

```powershell
Get-ChildItem -Recurse "dist/e2e-out" -Directory | Select-Object -ExpandProperty FullName
Get-Content "dist/e2e-out/*/conversion_report.txt"
```

Expected:
- 8 Livery-Ordner `FlyByWire_A380_842_A7AP*` unter `liveries/flybywire/`, je mit `livery.cfg`, `texture/texture.CFG`, `thumbnail/` (3 PNGs)
- `liveries/common/texture/` mit den deduplizierten + Common-Texturen als `.PNG.KTX2` + `.json`
- Report warnt vor verlorenen MODEL-Ordnern und listet `HUES_*`-Texturen als unbekannte Namen

- [ ] **Step 3: KTX2-Stichprobe gegen Referenz prüfen**

```powershell
uv run python -c "
import struct, glob
ref = open(glob.glob('data/NewLivery/*/SimObjects/AirPlanes/FlyByWire_A380X/liveries/flybywire/*/texture/A380X_FUSE1_ALBD.PNG.KTX2')[0], 'rb').read()
out = open(glob.glob('dist/e2e-out/*/SimObjects/AirPlanes/FlyByWire_A380X/liveries/*/texture/A380X_FUSE1_ALBD.PNG.KTX2')[0], 'rb').read()
for name, blob in (('ref', ref), ('out', out)):
    vk, ts, w, h, d, l, f, lv = struct.unpack_from('<8I', blob, 12)
    sc = struct.unpack_from('<I', blob, 44)[0]
    print(name, 'vk', vk, 'levels', lv, 'supercomp', sc, 'dims', w, h)
"
```

Expected: beide Zeilen `vk 145`, `supercomp 0`, volle Levelanzahl (13 bei 4096²).

- [ ] **Step 4: Manuelle Abnahme im Sim (Nutzeraufgabe)**

Das Paket aus `dist/e2e-out` in den MSFS-2024-Community-Ordner kopieren und prüfen, dass die Qatar-Liveries unter dem A380X-Eintrag erscheinen und Exterior korrekt aussieht. Dieser Schritt ist explizit dem Nutzer zu übergeben (Sim ist aus der Session heraus nicht startbar) — Ergebnis abwarten, bevor das Projekt als abgeschlossen gilt.

- [ ] **Step 5: Aufräumen + Abschluss-Commit**

```powershell
Remove-Item -Recurse -Force dist/e2e-out
```

```bash
git status   # muss sauber sein (dist/ ist gitignored); sonst vergessene Dateien committen
```

---

## Hinweise für die Ausführung

- Tasks strikt in Reihenfolge 1 → 15; Tasks 2/3 und 5 sind untereinander unabhängig, alles andere baut aufeinander auf.
- Nach jedem Task: Gesamtsuite `uv run pytest` muss grün sein, dann committen.
- Bei Abweichungen zwischen erwarteten und echten Binärwerten (Task 7/15) gilt: die Referenzdateien in `data/NewLivery` sind die Wahrheit — Konstanten im Code anpassen, nicht die Tests aufweichen.
