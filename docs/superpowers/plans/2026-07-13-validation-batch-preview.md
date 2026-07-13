# Validation, Batch, Preview & Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add robust A380 validation (skip foreign variants/packages), batch conversion of a folder of liveries, a mandatory preview→confirm step, and native-style empty `atc_id` — all English.

**Architecture:** The scanner gains per-variant A380 validation and a `find_packages` discovery helper. The `Converter` is split into a cheap `plan()` phase (scan only, no writes) and the existing `run()` execution. A thin batch layer (`plan_conversion` / `execute_plan`) runs each discovered package through its own `Converter` and aggregates results. CLI and GUI both build a plan, show it, and require confirmation before executing.

**Tech Stack:** Python 3.12, uv, Pillow, texture2ddecoder, typer, Tkinter, texconv.exe, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-13-validation-batch-preview-design.md` — the spec governs on conflict.
- All commands via `uv run …` (never bare `python`/`pytest`).
- All user-facing strings are English. No i18n framework.
- `atc_id` in generated `livery.cfg` is always empty (`atc_id=""`).
- Validation is skip-and-report: foreign variants/subfolders are skipped with a warning; reject only when nothing valid remains, with a message naming the detected aircraft.
- Batch is auto-detected via `find_packages` — no new flag/mode for detection.
- CLI confirmation: default prints the plan and prompts `[y/N]`; `--yes`/`-y` skips the prompt; `--dry-run` prints the plan and exits without converting.
- CLI exit codes: `0` = success or user-cancelled; `1` = finished with warnings/skips; `2` = nothing convertible / invalid input.
- Each package still produces its own output package folder + `conversion_report.txt`. A batch also writes `batch_report.txt` in the output directory.
- Preview must not write any files.
- Git: imperative commit messages, no AI attribution. Branch `feature/validation-batch-preview` (already created; user.name/email already set).
- Real sample data lives in gitignored `data/`; the real Qatar pack tests run locally (present on this machine).

## File structure (target)

```
src/a380x_livery_converter/
    core/scanner.py         # per-variant validation, OldPackage.skipped_foreign, find_packages
    converter.py            # _prepare(), plan(), PackagePlan, ConversionPlan, BatchResult,
                            #   plan_conversion(), execute_plan()  (dry_run removed at the end)
    output/livery_gen.py    # atc_id=""
    output/package_gen.py   # write_batch_report()
    cli.py                  # plan → print → confirm → execute
    gui.py                  # Analyze → Convert/Cancel, English strings
tests/
    helpers.py              # make_old_package gains a `name` parameter
    test_scanner.py, test_converter.py, test_cli.py, test_gui.py,
    test_livery_gen.py, test_package_gen.py   # updated/extended
```

---

### Task 1: Registration — empty `atc_id`

**Files:**
- Modify: `src/a380x_livery_converter/output/livery_gen.py:29-42`
- Test: `tests/test_livery_gen.py`

**Interfaces:**
- Produces: `livery_cfg_text(variant) -> str` unchanged signature; output now always contains `atc_id=""`.

- [ ] **Step 1: Update the failing test**

In `tests/test_livery_gen.py`, add an assertion to `test_livery_cfg_content` (after the `atc_airline` assertion):

```python
    assert 'atc_id=""' in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_livery_gen.py::test_livery_cfg_content -v`
Expected: FAIL (current output is `atc_id="A7-APC"`).

- [ ] **Step 3: Implement**

In `src/a380x_livery_converter/output/livery_gen.py`, change the `atc_id` line in `livery_cfg_text`:

```python
def livery_cfg_text(variant: Variant) -> str:
    name = variant.ui_variation or variant.title
    return (
        "[version]\n"
        "major = 1\n"
        "minor = 0\n"
        "\n"
        "[GENERAL]\n"
        f'Name = "{name}"\n'
        'atc_id=""\n'
        f'atc_parking_codes="{variant.icao_airline}"\n'
        f'icao_airline="{variant.icao_airline}"\n'
        f'atc_airline="{variant.atc_airline}"\n'
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_livery_gen.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/output/livery_gen.py tests/test_livery_gen.py
git commit -m "Write empty atc_id in generated livery.cfg"
```

---

### Task 2: Scanner — per-variant A380 validation

**Files:**
- Modify: `src/a380x_livery_converter/core/scanner.py`
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `parse_cfg`, `fltsim_sections` (unchanged).
- Produces:
  - `OldPackage` gains field `skipped_foreign: list[str]` (default empty list).
  - `scan_package(root)` now skips variant folders whose `base_container` is not FBW A380, records their detected type in `skipped_foreign`, and raises `NotAnA380XPackageError` only when no valid A380 variant remains — with a message naming the detected type(s).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_scanner.py`:

```python
def test_foreign_variant_skipped_not_rejected(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("A7APC", "FOREIGN"))
    cfg = pkg / "SimObjects" / "AirPlanes" / "A388_TST_FOREIGN" / "aircraft.cfg"
    cfg.write_text(cfg.read_text().replace("FlyByWire_A380_842", "FlyByWire_A32NX"))
    result = scan_package(pkg)
    assert {v.texture_suffix for v in result.variants} == {"A7APC"}
    assert any("A32NX" in label for label in result.skipped_foreign)


def test_rejection_message_names_detected_aircraft(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",))
    cfg = pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "aircraft.cfg"
    cfg.write_text(cfg.read_text().replace("FlyByWire_A380_842", "FlyByWire_A32NX"))
    with pytest.raises(NotAnA380XPackageError, match="A32NX"):
        scan_package(pkg)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_scanner.py::test_foreign_variant_skipped_not_rejected tests/test_scanner.py::test_rejection_message_names_detected_aircraft -v`
Expected: FAIL (`skipped_foreign` does not exist; message has no aircraft name).

- [ ] **Step 3: Implement**

In `src/a380x_livery_converter/core/scanner.py`, change the import and the two affected blocks.

Change the dataclass import at the top:

```python
from dataclasses import dataclass, field
```

Add the field to `OldPackage` (after `common_texture_dir`):

```python
@dataclass
class OldPackage:
    root: Path
    title: str
    creator: str
    package_version: str
    variants: list[Variant]
    common_texture_dir: Path | None
    skipped_foreign: list[str] = field(default_factory=list)
```

Replace the scan loop and the rejection block (the current lines from `variants: list[Variant] = []` through the `raise NotAnA380XPackageError(... base_container check failed)`), with:

```python
    variants: list[Variant] = []
    common_dir: Path | None = None
    skipped_foreign: list[str] = []
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
        base_name = base.replace("\\", "/").rsplit("/", 1)[-1]
        if "FLYBYWIRE_A380" not in base_name.upper():
            skipped_foreign.append(base_name or folder.name)
            continue
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
    if not variants:
        detected = ", ".join(sorted(set(skipped_foreign))) or "unknown"
        raise NotAnA380XPackageError(
            f"No FBW A380X livery found in {root} (detected: {detected})")
```

Finally, add `skipped_foreign=skipped_foreign` to the `OldPackage(...)` return at the end:

```python
    return OldPackage(root=root, title=title, creator=creator, package_version=version,
                      variants=variants, common_texture_dir=common_dir,
                      skipped_foreign=skipped_foreign)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_scanner.py -v`
Expected: PASS (including the real Qatar test — 8 variants, `skipped_foreign` empty).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/core/scanner.py tests/test_scanner.py
git commit -m "Skip foreign variants and name detected aircraft on rejection"
```

---

### Task 3: Scanner — package discovery

**Files:**
- Modify: `src/a380x_livery_converter/core/scanner.py`
- Modify: `tests/helpers.py` (add `name` parameter to `make_old_package`)
- Test: `tests/test_scanner.py`

**Interfaces:**
- Consumes: `_find_child` (existing).
- Produces:
  - `find_packages(root: Path) -> tuple[list[Path], list[tuple[Path, str]]]` — returns `(package_roots, skipped)`. A folder is a package if it contains `SimObjects/AirPlanes` (case-insensitive). If `root` is itself a package → `([root], [])`. Otherwise each direct child package is a root and non-package children are skipped with reason `"not a livery package"`. If no package is found anywhere → `([], [(root, "no livery package found")])`.
  - `tests/helpers.py`: `make_old_package(..., name: str = "Old Test Livery")` — the package folder name under `root`.

- [ ] **Step 1: Add the `name` parameter to the fixture**

In `tests/helpers.py`, change the `make_old_package` signature and its first line:

```python
def make_old_package(root, suffixes=("A7APC", "A7APD"), dds_bytes=b"",
                     with_common=True, with_model=True, name="Old Test Livery"):
    pkg = Path(root) / name
```

(The rest of the function body is unchanged.)

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_scanner.py` (add `find_packages` to the import from `a380x_livery_converter.core.scanner`):

```python
def test_find_packages_single(tmp_path):
    pkg = make_old_package(tmp_path)
    roots, skipped = find_packages(pkg)
    assert roots == [pkg]
    assert skipped == []


def test_find_packages_parent_of_multiple(tmp_path):
    parent = tmp_path / "batch"
    parent.mkdir()
    a = make_old_package(parent, suffixes=("A7APC",), name="pkgA")
    b = make_old_package(parent, suffixes=("A7APD",), name="pkgB")
    junk = parent / "notapackage"
    junk.mkdir()
    (junk / "readme.txt").write_text("hi")
    roots, skipped = find_packages(parent)
    assert set(roots) == {a, b}
    assert any("notapackage" in str(p) for p, _ in skipped)


def test_find_packages_none(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    roots, skipped = find_packages(empty)
    assert roots == []
    assert skipped == [(empty, "no livery package found")]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `uv run pytest tests/test_scanner.py -k find_packages -v`
Expected: FAIL (`find_packages` not defined).

- [ ] **Step 4: Implement**

Append to `src/a380x_livery_converter/core/scanner.py`:

```python
def _is_package(path: Path) -> bool:
    simobjects = _find_child(path, "SimObjects")
    return simobjects is not None and _find_child(simobjects, "AirPlanes") is not None


def find_packages(root: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    root = Path(root)
    if _is_package(root):
        return [root], []
    packages: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if _is_package(child):
                packages.append(child)
            else:
                skipped.append((child, "not a livery package"))
    if not packages:
        return [], [(root, "no livery package found")]
    return packages, skipped
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_scanner.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add src/a380x_livery_converter/core/scanner.py tests/helpers.py tests/test_scanner.py
git commit -m "Add package discovery helper find_packages"
```

---

### Task 4: Converter — plan/execute split

**Files:**
- Modify: `src/a380x_livery_converter/converter.py`
- Test: `tests/test_converter.py`

**Interfaces:**
- Consumes: `scan_package`, `Variant` (existing); `package_gen.package_folder_name`.
- Produces:
  - `@dataclass PackagePlan`: `source: Path`, `output_name: str`, `livery_names: list[str]`, `texture_count: int`, `warnings: list[str]`
  - `Converter.plan() -> PackagePlan` — scans and resolves jobs without writing anything.
  - `Converter.run() -> ConversionResult` — unchanged behaviour (still honours `dry_run`), now built on the shared `_prepare()`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_converter.py`:

```python
from a380x_livery_converter.converter import Converter, PackagePlan


def test_plan_lists_liveries_and_writes_nothing(tmp_path):
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    out = tmp_path / "out"
    plan = Converter(pkg, out).plan()
    assert isinstance(plan, PackagePlan)
    assert len(plan.livery_names) == 2
    assert plan.texture_count >= 1
    assert not out.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_converter.py::test_plan_lists_liveries_and_writes_nothing -v`
Expected: FAIL (`PackagePlan` / `plan` not defined).

- [ ] **Step 3: Implement the split**

In `src/a380x_livery_converter/converter.py`, add the `PackagePlan` dataclass after `ConversionResult`:

```python
@dataclass
class PackagePlan:
    source: Path
    output_name: str
    livery_names: list[str]
    texture_count: int
    warnings: list[str]
```

Add a private `_Prepared` dataclass after `PackagePlan`:

```python
@dataclass
class _Prepared:
    old: object
    jobs: list["_TextureJob"]
    warnings: list[str]
    out_root: Path
    flybywire_root: Path
    folder_names: dict[int, str]
```

Add a `_prepare` method to `Converter` (before `run`) that contains the current scan+job-building logic, and surfaces skipped foreign variants as warnings:

```python
    def _prepare(self) -> _Prepared:
        old = scan_package(self.input_dir)
        rename_map = load_rename_map()
        warnings: list[str] = []
        for label in old.skipped_foreign:
            warnings.append(f"Skipped foreign variant: {label}")

        out_root = self.output_dir / package_gen.package_folder_name(old)
        flybywire_root = out_root / package_gen.LIVERIES_SUBPATH / "flybywire"
        common_texture = out_root / package_gen.LIVERIES_SUBPATH / "common" / "texture"
        folder_names = _assign_folder_names(old.variants)

        jobs: list[_TextureJob] = []
        if old.common_texture_dir is not None:
            for src in _dds_files(old.common_texture_dir):
                name = self._mapped(src.name, rename_map, warnings)
                digest = hashlib.sha1(src.read_bytes()).hexdigest()
                jobs.append(_TextureJob(src, common_texture / name, f"common/{src.name}", digest))

        grouped: dict[tuple[str, str], list[tuple[Variant, Path]]] = {}
        for variant in old.variants:
            if variant.has_custom_model:
                warnings.append(f"{variant.title}: custom MODEL folder cannot be converted "
                                f"- decals/3D additions are lost")
            if variant.texture_dir is None:
                warnings.append(f"{variant.title}: no texture folder found - variant has no own textures")
                continue
            for src in _dds_files(variant.texture_dir):
                name = self._mapped(src.name, rename_map, warnings)
                digest = hashlib.sha1(src.read_bytes()).hexdigest()
                grouped.setdefault((name, digest), []).append((variant, src))
        for (name, digest), sources in grouped.items():
            variants_involved = {id(v) for v, _ in sources}
            if len(variants_involved) > 1:
                jobs.append(_TextureJob(sources[0][1], common_texture / name,
                                        f"common/{name}", digest, group=sources))
            else:
                variant, src = sources[0]
                dest = (flybywire_root / folder_names[id(variant)] / "texture" / name)
                jobs.append(_TextureJob(src, dest, f"{variant.texture_suffix}/{src.name}", digest))

        jobs = self._resolve_collisions(jobs, warnings, flybywire_root, folder_names)
        return _Prepared(old, jobs, warnings, out_root, flybywire_root, folder_names)

    def plan(self) -> PackagePlan:
        p = self._prepare()
        livery_names = [p.folder_names[id(v)] for v in p.old.variants]
        return PackagePlan(
            source=self.input_dir,
            output_name=package_gen.package_folder_name(p.old),
            livery_names=livery_names,
            texture_count=len(p.jobs),
            warnings=list(p.warnings),
        )
```

Replace the body of `run` from its start down to (and including) the `jobs = self._resolve_collisions(...)` line with a call to `_prepare`, keeping the execution part unchanged:

```python
    def run(self) -> ConversionResult:
        p = self._prepare()
        old, jobs, warnings = p.old, p.jobs, p.warnings
        out_root, flybywire_root, folder_names = p.out_root, p.flybywire_root, p.folder_names

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
                except Exception as exc:
                    skipped += 1
                    warnings.append(f"Texture skipped ({job.label}): {exc}")
                done += 1
                self.progress(done, total, f"Texture {job.label}")

        for variant in old.variants:
            livery_dir = flybywire_root / folder_names[id(variant)]
            livery_gen.write_texture_cfg(livery_dir / "texture")
            livery_dir.mkdir(parents=True, exist_ok=True)
            (livery_dir / "livery.cfg").write_text(livery_gen.livery_cfg_text(variant),
                                                   encoding="utf-8")
            thumb = livery_gen.find_old_thumbnail(variant.texture_dir)
            for w in livery_gen.write_thumbnails(thumb, livery_dir / "thumbnail"):
                warnings.append(f"{variant.title}: {w}")
            done += 1
            self.progress(done, total, f"Config for {variant.title}")

        mappings = [f"{job.src.name} -> {job.dest.relative_to(out_root).as_posix()}"
                   for job in jobs]
        package_gen.write_report(out_root, warnings, converted=converted,
                                 skipped=skipped, source=old, mappings=mappings)
        package_gen.write_layout(out_root)
        done += 1
        self.progress(done, total, "layout.json")
        package_gen.write_manifest(out_root, old.title, old.creator, old.package_version)
        done += 1
        self.progress(done, total, "manifest.json")
        return ConversionResult(out_root, converted, skipped, warnings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converter.py -v`
Expected: PASS (all existing converter tests plus the new plan test; `test_dry_run_writes_nothing` still passes).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/converter.py tests/test_converter.py
git commit -m "Split Converter into cheap plan phase and execution"
```

---

### Task 5: Batch orchestration

**Files:**
- Modify: `src/a380x_livery_converter/converter.py`
- Modify: `src/a380x_livery_converter/output/package_gen.py`
- Test: `tests/test_converter.py`, `tests/test_package_gen.py`

**Interfaces:**
- Consumes: `find_packages`, `NotAnA380XPackageError` (scanner); `Converter.plan()`/`.run()`; `ConversionResult`.
- Produces:
  - `@dataclass ConversionPlan`: `packages: list[PackagePlan]`, `skipped: list[tuple[Path, str]]`, `output_dir: Path`; properties `package_count`, `livery_count`, `texture_count`.
  - `@dataclass BatchResult`: `results: list[ConversionResult]`, `skipped: list[tuple[Path, str]]`; properties `converted`, `skipped_textures`, `warnings`.
  - `plan_conversion(input_dir, output_dir) -> ConversionPlan`
  - `execute_plan(plan: ConversionPlan, progress: ProgressCallback | None = None) -> BatchResult`
  - `package_gen.write_batch_report(output_dir, results, skipped) -> Path`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_package_gen.py`:

```python
def test_batch_report_lists_packages_and_skips(tmp_path):
    from a380x_livery_converter.converter import ConversionResult
    from a380x_livery_converter.output.package_gen import write_batch_report
    results = [ConversionResult(tmp_path / "pkgA", 5, 0, []),
               ConversionResult(tmp_path / "pkgB", 3, 1, ["w"])]
    path = write_batch_report(tmp_path, results, [(tmp_path / "junk", "not a livery package")])
    text = path.read_text()
    assert "pkgA" in text and "pkgB" in text
    assert "junk" in text and "not a livery package" in text
```

Add to `tests/test_converter.py`:

```python
from a380x_livery_converter.converter import (
    ConversionPlan, plan_conversion, execute_plan,
)

BATCH_LIVERIES = "SimObjects/AirPlanes/FlyByWire_A380X/liveries"


def test_plan_conversion_batch_folder(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgA")
    make_old_package(parent, suffixes=("A7APD",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgB")
    plan = plan_conversion(parent, tmp_path / "out")
    assert plan.package_count == 2
    assert plan.livery_count == 2
    assert not (tmp_path / "out").exists()


def test_plan_conversion_marks_foreign_package_skipped(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="good")
    bad = make_old_package(parent, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False, name="bad")
    cfg = bad / "SimObjects" / "AirPlanes" / "A388_TST_X" / "aircraft.cfg"
    cfg.write_text(cfg.read_text().replace("FlyByWire_A380_842", "FlyByWire_A32NX"))
    plan = plan_conversion(parent, tmp_path / "out")
    assert plan.package_count == 1
    assert any("bad" in str(p) for p, _ in plan.skipped)


def test_execute_plan_batch_writes_two_packages_and_report(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgA")
    make_old_package(parent, suffixes=("A7APD",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgB")
    out = tmp_path / "out"
    plan = plan_conversion(parent, out)
    result = execute_plan(plan)
    assert len(result.results) == 2
    assert result.converted >= 2
    assert (out / "batch_report.txt").is_file()
    for r in result.results:
        assert (r.output_root / "manifest.json").is_file()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_converter.py -k "plan_conversion or execute_plan" tests/test_package_gen.py::test_batch_report_lists_packages_and_skips -v`
Expected: FAIL (names not defined).

- [ ] **Step 3: Implement `write_batch_report`**

Append to `src/a380x_livery_converter/output/package_gen.py`:

```python
def write_batch_report(output_dir, results, skipped) -> Path:
    lines = [
        "A380X Livery Converter - batch report",
        "=" * 38,
        "",
        f"Packages converted: {len(results)}",
    ]
    for r in results:
        lines.append(f"  - {Path(r.output_root).name}: "
                     f"{r.converted} textures, {r.skipped} skipped")
    if skipped:
        lines.append("")
        lines.append("Skipped:")
        for path, reason in skipped:
            lines.append(f"  - {Path(path).name}: {reason}")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / "batch_report.txt"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
```

- [ ] **Step 4: Implement the batch layer**

In `src/a380x_livery_converter/converter.py`, extend the scanner import:

```python
from a380x_livery_converter.core.scanner import (
    NotAnA380XPackageError, Variant, find_packages, scan_package,
)
```

Append the plan/result types and the two functions at the end of the module:

```python
@dataclass
class ConversionPlan:
    packages: list[PackagePlan]
    skipped: list[tuple[Path, str]]
    output_dir: Path

    @property
    def package_count(self) -> int:
        return len(self.packages)

    @property
    def livery_count(self) -> int:
        return sum(len(p.livery_names) for p in self.packages)

    @property
    def texture_count(self) -> int:
        return sum(p.texture_count for p in self.packages)


@dataclass
class BatchResult:
    results: list[ConversionResult]
    skipped: list[tuple[Path, str]]

    @property
    def converted(self) -> int:
        return sum(r.converted for r in self.results)

    @property
    def skipped_textures(self) -> int:
        return sum(r.skipped for r in self.results)

    @property
    def warnings(self) -> list[str]:
        out: list[str] = []
        for r in self.results:
            out.extend(r.warnings)
        return out


def plan_conversion(input_dir: Path, output_dir: Path) -> ConversionPlan:
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    roots, skipped = find_packages(input_dir)
    skipped = list(skipped)
    packages: list[PackagePlan] = []
    for root in roots:
        try:
            packages.append(Converter(root, output_dir).plan())
        except NotAnA380XPackageError as exc:
            skipped.append((root, str(exc)))
    return ConversionPlan(packages, skipped, output_dir)


def execute_plan(plan: ConversionPlan,
                 progress: ProgressCallback | None = None) -> BatchResult:
    report = progress or (lambda done, total, msg: None)
    total = sum(p.texture_count + len(p.livery_names) + 2 for p in plan.packages) or 1
    base = 0
    results: list[ConversionResult] = []
    for pkg in plan.packages:
        def shim(done, _total, msg, _base=base, _name=pkg.output_name):
            report(_base + done, total, f"[{_name}] {msg}")
        results.append(Converter(pkg.source, plan.output_dir, progress=shim).run())
        base += pkg.texture_count + len(pkg.livery_names) + 2
    if len(results) > 1 or plan.skipped:
        package_gen.write_batch_report(plan.output_dir, results, plan.skipped)
    return BatchResult(results, plan.skipped)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_converter.py tests/test_package_gen.py -v`
Expected: PASS (all).

- [ ] **Step 6: Commit**

```bash
git add src/a380x_livery_converter/converter.py src/a380x_livery_converter/output/package_gen.py tests/test_converter.py tests/test_package_gen.py
git commit -m "Add batch orchestration with plan_conversion and execute_plan"
```

---

### Task 6: CLI — plan, confirm, execute

**Files:**
- Modify: `src/a380x_livery_converter/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `plan_conversion`, `execute_plan` (converter).
- Produces: `app` (typer.Typer) with `convert INPUT_DIR -o OUTPUT [--yes/-y] [--dry-run] [--verbose/-v]`; prints the plan, prompts unless `--yes`, exits 0/1/2 per the constraints.

- [ ] **Step 1: Rewrite the CLI tests**

Replace the entire contents of `tests/test_cli.py` with:

```python
from typer.testing import CliRunner

from a380x_livery_converter.cli import app
from tests.helpers import make_bc3_dds, make_old_package

runner = CliRunner()


def _single(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    (pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "TEXTURE.X"
     / "CUSTOM_DECAL.PNG.DDS").unlink()
    return pkg


def test_convert_with_yes_exits_0(tmp_path):
    pkg = _single(tmp_path)
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--yes"])
    assert result.exit_code == 0, result.output
    assert "Converted textures: 1" in result.output


def test_prompt_cancel_writes_nothing(tmp_path):
    pkg = _single(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(app, [str(pkg), "-o", str(out)], input="n\n")
    assert result.exit_code == 0
    assert "Cancelled." in result.output
    assert not out.exists()


def test_prompt_yes_converts(tmp_path):
    pkg = _single(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(app, [str(pkg), "-o", str(out)], input="y\n")
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_dry_run_shows_plan_no_write(tmp_path):
    pkg = _single(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(app, [str(pkg), "-o", str(out), "--dry-run"])
    assert result.exit_code == 0
    assert "Found 1 package" in result.output
    assert not out.exists()


def test_invalid_input_exits_2(tmp_path):
    (tmp_path / "empty").mkdir()
    result = runner.invoke(app, [str(tmp_path / "empty"), "-o", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_batch_folder_converts_all(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgA")
    make_old_package(parent, suffixes=("A7APD",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgB")
    result = runner.invoke(app, [str(parent), "-o", str(tmp_path / "out"), "--yes"])
    assert result.exit_code in (0, 1), result.output
    assert "2 package(s)" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL (old CLI has no `--yes`, no plan output, wrong exit codes).

- [ ] **Step 3: Rewrite the CLI**

Replace the entire contents of `src/a380x_livery_converter/cli.py` with:

```python
"""Command line front end."""

from pathlib import Path

import typer

from a380x_livery_converter.converter import (
    ConversionPlan, execute_plan, plan_conversion,
)

app = typer.Typer(add_completion=False,
                  help="Convert FBW A380X MSFS 2020 liveries to native MSFS 2024 packages.")


def _print_plan(plan: ConversionPlan) -> None:
    typer.echo(f"Found {plan.package_count} package(s), {plan.livery_count} liveries, "
               f"{plan.texture_count} textures:")
    for pkg in plan.packages:
        typer.echo(f"  - {pkg.output_name}: {len(pkg.livery_names)} liveries, "
                   f"{pkg.texture_count} textures")
        for warning in pkg.warnings:
            typer.secho(f"      WARNING: {warning}", fg=typer.colors.YELLOW)
    for path, reason in plan.skipped:
        typer.secho(f"  - skipped {Path(path).name}: {reason}", fg=typer.colors.YELLOW)


@app.command()
def convert(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False,
                                     help="Old livery package or a folder of packages"),
    output: Path = typer.Option(..., "--output", "-o", file_okay=False,
                                help="Destination folder, e.g. the Community folder"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan and exit"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-file progress"),
) -> None:
    try:
        plan = plan_conversion(input_dir, output)
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    _print_plan(plan)
    if not plan.packages:
        typer.secho("No convertible A380X liveries found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    if dry_run:
        raise typer.Exit(0)
    if not yes and not typer.confirm(
            f"Convert {plan.livery_count} liveries in {plan.package_count} package(s)?"):
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    def progress(done: int, total: int, message: str) -> None:
        if verbose:
            typer.echo(f"[{done}/{total}] {message}")

    result = execute_plan(plan, progress=progress)
    for res in result.results:
        typer.echo(f"Output: {res.output_root}")
    typer.echo(f"Converted textures: {result.converted}, skipped: {result.skipped_textures}")
    for warning in result.warnings:
        typer.secho(f"WARNING: {warning}", fg=typer.colors.YELLOW)
    if result.warnings or result.skipped_textures or plan.skipped:
        raise typer.Exit(1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/cli.py tests/test_cli.py
git commit -m "Add plan preview and confirmation to the CLI"
```

---

### Task 7: GUI — Analyze/Convert/Cancel, English

**Files:**
- Modify: `src/a380x_livery_converter/gui.py`
- Test: `tests/test_gui.py`

**Interfaces:**
- Consumes: `plan_conversion`, `execute_plan` (converter).
- Produces: `ConverterApp` with `analyze_button`, `convert_button`, `cancel_button`, `progressbar`, `log`; methods `analyze()`, `convert()`, `cancel()`.

- [ ] **Step 1: Rewrite the GUI smoke tests**

Replace the two test bodies in `tests/test_gui.py` with:

```python
def test_app_builds_widgets():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        assert str(app.analyze_button.cget("state")) != "disabled"
        assert str(app.convert_button.cget("state")) == "disabled"
        assert app.progressbar is not None
    finally:
        root.destroy()


def test_analyze_without_folders_logs_hint():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        app.analyze()
        assert "Please select both folders." in app.log.get("1.0", "end")
        assert str(app.analyze_button.cget("state")) != "disabled"
    finally:
        root.destroy()
```

(The `_make_root()` helper and imports at the top of the file are unchanged.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_gui.py -v`
Expected: FAIL (`analyze_button` not defined) or SKIP if no display.

- [ ] **Step 3: Rewrite the GUI**

Replace the entire contents of `src/a380x_livery_converter/gui.py` with:

```python
"""Tkinter GUI front end."""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

from a380x_livery_converter.converter import execute_plan, plan_conversion


class ConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("FBW A380X Livery Converter (MSFS 2020 -> 2024)")
        root.geometry("700x480")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.queue: queue.Queue = queue.Queue()
        self._busy = False
        self._plan = None

        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)
        self._folder_row(frame, 0, "Old livery package or folder:", self.input_var)
        self._folder_row(frame, 1, "Output folder (Community):", self.output_var)

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=3, pady=8, sticky="ew")
        self.analyze_button = ttk.Button(buttons, text="Analyze", command=self.analyze)
        self.analyze_button.pack(side="left")
        self.convert_button = ttk.Button(buttons, text="Convert", command=self.convert,
                                         state="disabled")
        self.convert_button.pack(side="left", padx=6)
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel,
                                        state="disabled")
        self.cancel_button.pack(side="left")

        self.progressbar = ttk.Progressbar(frame, maximum=100)
        self.progressbar.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.log = scrolledtext.ScrolledText(frame, height=16, state="disabled")
        self.log.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

    def _folder_row(self, parent, row, label, var):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=4)
        ttk.Button(parent, text="Browse...",
                   command=lambda: var.set(filedialog.askdirectory() or var.get())
                   ).grid(row=row, column=2)

    def analyze(self):
        input_dir, output_dir = self.input_var.get().strip(), self.output_var.get().strip()
        if not input_dir or not output_dir:
            self._append_log("Please select both folders.")
            return
        self._busy = True
        self._set_buttons(analyze=False, convert=False, cancel=False)
        self._append_log("Analyzing...")
        threading.Thread(target=self._do_analyze,
                         args=(Path(input_dir), Path(output_dir)), daemon=True).start()
        self.root.after(100, self._poll)

    def _do_analyze(self, input_dir, output_dir):
        try:
            self.queue.put(("plan", plan_conversion(input_dir, output_dir)))
        except Exception as exc:
            self.queue.put(("error", exc))

    def convert(self):
        if self._plan is None:
            return
        self._busy = True
        self._set_buttons(analyze=False, convert=False, cancel=False)
        self.progressbar.config(value=0)
        threading.Thread(target=self._do_convert, args=(self._plan,), daemon=True).start()
        self.root.after(100, self._poll)

    def _do_convert(self, plan):
        try:
            result = execute_plan(
                plan, progress=lambda d, t, m: self.queue.put(("progress", d, t, m)))
            self.queue.put(("done", result))
        except Exception as exc:
            self.queue.put(("error", exc))

    def cancel(self):
        self._plan = None
        self._append_log("Cancelled.")
        self._reset()

    def _poll(self):
        while not self.queue.empty():
            item = self.queue.get_nowait()
            kind = item[0]
            if kind == "plan":
                self._plan = item[1]
                self._show_plan(self._plan)
            elif kind == "progress":
                _, done, total, message = item
                self.progressbar.config(maximum=total, value=done)
                self._append_log(f"[{done}/{total}] {message}")
            elif kind == "done":
                self._show_result(item[1])
                self._plan = None
                self._reset()
            elif kind == "error":
                self._append_log(f"ERROR: {item[1]}")
                self._plan = None
                self._reset()
        if self._busy:
            self.root.after(100, self._poll)

    def _show_plan(self, plan):
        self._busy = False
        self._append_log(f"Found {plan.package_count} package(s), {plan.livery_count} "
                         f"liveries, {plan.texture_count} textures:")
        for pkg in plan.packages:
            self._append_log(f"  - {pkg.output_name}: {len(pkg.livery_names)} liveries, "
                             f"{pkg.texture_count} textures")
            for warning in pkg.warnings:
                self._append_log(f"      WARNING: {warning}")
        for path, reason in plan.skipped:
            self._append_log(f"  - skipped {Path(path).name}: {reason}")
        if plan.packages:
            self._append_log("Review above, then Convert or Cancel.")
            self._set_buttons(analyze=True, convert=True, cancel=True)
        else:
            self._append_log("Nothing to convert.")
            self._set_buttons(analyze=True, convert=False, cancel=False)

    def _show_result(self, result):
        self._append_log("")
        self._append_log(f"Done: {result.converted} textures converted, "
                         f"{result.skipped_textures} skipped.")
        for warning in result.warnings:
            self._append_log(f"WARNING: {warning}")
        for res in result.results:
            self._append_log(f"Output: {res.output_root}")

    def _reset(self):
        self._busy = False
        self._set_buttons(analyze=True, convert=False, cancel=False)

    def _set_buttons(self, analyze, convert, cancel):
        self.analyze_button.config(state="normal" if analyze else "disabled")
        self.convert_button.config(state="normal" if convert else "disabled")
        self.cancel_button.config(state="normal" if cancel else "disabled")

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

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_gui.py -v`
Then the whole suite: `uv run pytest -q`
Expected: PASS (GUI tests pass or skip without a display; full suite green). Manual check: `uv run python -m a380x_livery_converter` opens the window with Analyze/Convert/Cancel; close it.

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/gui.py tests/test_gui.py
git commit -m "Add analyze-preview-confirm flow and English strings to the GUI"
```

---

### Task 8: Cleanup, docs & integration verification

**Files:**
- Modify: `src/a380x_livery_converter/converter.py` (remove `dry_run`)
- Modify: `tests/test_converter.py` (drop the obsolete dry-run test)
- Modify: `README.md`

**Interfaces:**
- Produces: `Converter.__init__` without the `dry_run` parameter; `run()` always executes.

- [ ] **Step 1: Remove the obsolete dry-run test**

In `tests/test_converter.py`, delete the `test_dry_run_writes_nothing` test function entirely (its behaviour is now covered by `test_plan_lists_liveries_and_writes_nothing`). If the shared `_convert` helper passes `dry_run` through `**kwargs`, leave it — no test passes `dry_run` anymore.

- [ ] **Step 2: Remove `dry_run` from the Converter**

In `src/a380x_livery_converter/converter.py`, change `__init__` to drop `dry_run`:

```python
    def __init__(self, input_dir: Path, output_dir: Path,
                 progress: ProgressCallback | None = None,
                 max_workers: int | None = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.progress: ProgressCallback = progress or (lambda done, total, msg: None)
        self.max_workers = max_workers or min(8, os.cpu_count() or 4)
```

And remove the dry-run branch from `run` (delete these three lines):

```python
        if self.dry_run:
            warnings.append(f"[dry-run] would convert {len(jobs)} textures into {out_root}")
            return ConversionResult(out_root, 0, 0, warnings)
```

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest -q`
Expected: PASS (all). If any test still references `dry_run=`, fix that call to drop the argument.

- [ ] **Step 4: Update the README**

In `README.md`, update the CLI section and known limitations to reflect the new behaviour. Replace the "Usage (command line)" section body with:

```markdown
    A380XLiveryConverter.exe convert "C:\path\to\input" -o "C:\path\to\Community" [--yes] [--dry-run] [--verbose]

The tool first shows a plan of what it found (packages, liveries, anything
skipped) and asks for confirmation. Pass `--yes` to skip the prompt (for
scripts), or `--dry-run` to show the plan and exit without converting.

`input` may be a single extracted livery package **or** a folder containing
several packages — the tool detects which and converts them all, writing one
installable package each plus a `batch_report.txt` summary.

Exit codes: 0 = success (or cancelled), 1 = finished with warnings, 2 = error.
```

And add these bullets to "Known limitations":

```markdown
- Non-A380 input (e.g. an A320 livery) is rejected with a message naming the
  detected aircraft. Foreign variants inside an otherwise-valid package are
  skipped and reported.
- The generated `livery.cfg` leaves `atc_id` empty (native style); the visible
  tail number comes from each livery's own registration texture.
```

- [ ] **Step 5: Integration verification**

Run the real single-package conversion (only if `data/` is present):

```bash
uv run python -m a380x_livery_converter convert "data/oldLivery/HUES - QatarAirways Fleet  A380 FBW" -o "dist/e2e2-out" --yes --verbose
```
Expected: exit code 1 (MODEL/unknown-name warnings), 8 liveries converted, no traceback. Verify a generated `livery.cfg` contains `atc_id=""`:

```bash
uv run python -c "import glob; print([p for p in glob.glob('dist/e2e2-out/**/livery.cfg', recursive=True)][:1])"
```

Then clean up: `rm -rf dist/e2e2-out`.

- [ ] **Step 6: Commit**

```bash
git add src/a380x_livery_converter/converter.py tests/test_converter.py README.md
git commit -m "Remove dry_run flag and document batch, preview and registration"
```

---

## Execution notes

- Tasks are ordered 1 → 8; each keeps the full suite green. Tasks 1–3 are independent; 4 depends on 2; 5 depends on 3+4; 6 and 7 depend on 5; 8 depends on 6+7.
- After each task run `uv run pytest -q` and commit.
- The exe is rebuilt separately (the GitHub Actions release workflow, or `scripts/build_exe.ps1`) — not part of these tasks.
