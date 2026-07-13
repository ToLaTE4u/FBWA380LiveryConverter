# Spec: Validation, Batch Conversion, Preview/Confirm & Registration

**Date:** 2026-07-13
**Status:** Draft (brainstorming complete, pending user review)
**Builds on:** `docs/superpowers/specs/2026-07-10-a380x-livery-converter-design.md`

## 1. Context & goals

Four related improvements to the shipped converter:

1. **Robust A380 validation** — reliably reject non-A380 input (e.g. an A320 livery) and skip foreign variants instead of aborting or mis-converting.
2. **Batch conversion** — point the tool at a folder containing several livery packages and convert them all in one run.
3. **Registration** — stop writing the stale placeholder `atc_id` into the generated `livery.cfg`.
4. **Preview & confirm** — always show the user what will be converted *before* any work happens; the user explicitly confirms or cancels. This puts the user in control.

Plus a cross-cutting requirement: **the tool is English-only** (international audience).

### Success criteria

- Handing the tool an A320 (or any non-FBW-A380) livery produces a clear, non-technical rejection message naming the detected aircraft — never a partial or wrong conversion.
- A folder with several A380 livery packages converts to one installable 2024 package each, in a single run; foreign/invalid subfolders are skipped and reported, never aborting the batch.
- Every conversion is preceded by a preview the user confirms (GUI: Convert/Cancel; CLI: `[y/N]` prompt with a `--yes` escape for automation).
- Generated `livery.cfg` files carry `atc_id=""` (native-style); the visible tail number continues to come from the per-variant `REGISTRATION` texture, which is already preserved.
- All user-facing text is English.

## 2. Decisions (from brainstorming)

1. **Registration:** `atc_id` is always written empty, matching the native FBW reference livery. The visible registration is unaffected (per-variant `REGISTRATION_ALBEDO` texture is already preserved — verified: the Qatar variants each have a distinct registration texture).
2. **Batch trigger:** auto-detected. No new flag/mode — the tool inspects the given folder and decides whether it is one package or a folder of packages.
3. **Validation strictness:** skip-and-report. Foreign variants inside a package are skipped with a warning; a package is only rejected if *no* valid A380 variant remains. In batch, foreign/non-livery subfolders are skipped, the rest continues. Never a full abort because of one bad item.
4. **Preview/confirm:** mandatory. A cheap plan phase (scan only, no texture work) produces the preview; the user confirms before the expensive conversion runs.
5. **CLI confirmation:** default shows the plan and prompts `[y/N]`; `--yes`/`-y` skips the prompt for scripts/CI; `--dry-run` shows the plan and exits without converting.
6. **Language:** English throughout.

## 3. Feature 1 — Robust A380 validation (`scanner.py`)

Current behaviour: `scan_package` sets one package-wide `is_a380` flag (OR across all variants) and raises `NotAnA380XPackageError` only if it is never set. A package mixing A380 and foreign variants would convert everything.

New behaviour:

- Validation is decided **per variant folder** by its `aircraft.cfg` `base_container`. A variant whose `base_container` last path segment does not contain `FLYBYWIRE_A380` (case-insensitive) is **skipped** — not added to `OldPackage.variants` — and recorded.
- `scan_package` raises `NotAnA380XPackageError` only when **zero** valid A380 variants remain. The message names the detected non-A380 aircraft, e.g. `No FBW A380X livery found (detected: FlyByWire_A32NX)`.
- Skipped foreign variants are surfaced as warnings in the conversion report. `OldPackage` gains a field to carry them (e.g. `skipped_foreign: list[str]` — the foreign aircraft/variant labels), so the converter and preview can report them.

The existing `SimObjects/AirPlanes` structural check and its clear error stay.

## 4. Feature 2 — Batch conversion (auto-detect)

### Package discovery

New helper `find_packages(root: Path) -> tuple[list[Path], list[tuple[Path, str]]]` returning `(package_roots, skipped_non_packages)`:

- A folder is a **package** if it contains a `SimObjects/AirPlanes` subtree (case-insensitive).
- If `root` itself is a package → `([root], [])` (today's single-package case).
- Otherwise → every **direct child** that is a package becomes a package root; direct children that are not packages are recorded as skipped with reason `not a livery package`.
- If neither `root` nor any child is a package → `([], [(root, "no livery package found")])`.

Scan depth is intentionally shallow (the given folder, else its direct children) — no deep recursion.

### Orchestration

- The existing `Converter` remains the **single-package engine** — its responsibility (convert one package) is unchanged; it is only refactored internally to expose a cheap plan phase (see §6).
- A thin batch layer runs each discovered package through its own `Converter` and aggregates the results. Each package still produces its own output package folder under the chosen output directory (e.g. 5 liveries → 5 installable packages side by side) and its own `conversion_report.txt`.
- A batch also writes a top-level `batch_report.txt` in the output directory summarising: packages converted, packages/subfolders skipped (with reasons), and totals.

## 5. Feature 3 — Registration (`livery_gen.py`)

Single change in `livery_cfg_text`: always emit `atc_id=""` instead of the source value. The `Variant.atc_id` field may remain (harmless) but is no longer written into the cfg. `atc_airline`, `icao_airline`, `atc_parking_codes` are unchanged.

## 6. Preview & confirm flow

### Plan phase

The converter is refactored to separate **planning** (cheap) from **execution** (expensive):

- Planning scans the input, resolves texture jobs (name mapping, dedup, folder-name assignment) and collects warnings — **without** invoking texconv and **without writing any files**. This is the same logic the current dry-run path already exercises, promoted to a reusable building block.
- A new `plan_conversion(input_dir, output_dir) -> ConversionPlan` ties discovery + per-package planning together and returns a structured preview.

### Preview data

`ConversionPlan` (top level):
- `packages: list[PackagePlan]`
- `skipped: list[tuple[Path, str]]` — skipped folders/subfolders with reasons (foreign aircraft, not a package)
- `output_dir: Path`
- convenience totals (package count, livery count, texture count)

`PackagePlan` (per package):
- `source: Path`, `output_name: str`
- `livery_names: list[str]` — the liveries that will be created
- `texture_count: int` — number of textures that will be converted
- `warnings: list[str]` — custom MODEL loss, unknown texture names, skipped foreign variants

### GUI flow (`gui.py`)

1. Select **old livery package or folder** and **output folder**.
2. Click **Analyze** → the plan is built and shown (packages, liveries, skipped items, warnings). This is fast (no conversion).
3. **Convert** starts the actual work with the progress bar; **Cancel** discards the plan and returns to step 1.
4. On completion the log shows the aggregate result and points to the report(s).

### CLI flow (`cli.py`)

`convert <input> -o <output> [--yes/-y] [--dry-run] [--verbose]`

1. Build and print the plan (packages, liveries, skipped items, warnings).
2. If `--dry-run`: exit after printing (no conversion).
3. Else if not `--yes`: prompt `Convert <N> liveries in <M> package(s)? [y/N]`. On no/empty → print `Cancelled.` and exit 0. On yes → proceed.
4. With `--yes`: proceed without prompting.
5. Execute, print the aggregate result and per-package/batch report locations.

## 7. English-only

All user-facing strings are English. In practice this means translating the GUI (`gui.py`) strings and buttons — the conversion reports and internal warnings are already English. No i18n framework is introduced (YAGNI); strings are simply English literals.

## 8. Architecture & modules touched

| Module | Change |
|---|---|
| `core/scanner.py` | Per-variant A380 validation; skip + record foreign variants; `find_packages`; `OldPackage.skipped_foreign` |
| `converter.py` | Split plan vs execute; `PackagePlan`; batch orchestration; `plan_conversion`; `ConversionPlan`; `BatchResult` |
| `output/livery_gen.py` | `atc_id=""` |
| `output/package_gen.py` | `batch_report.txt` writer |
| `cli.py` | Plan → print → confirm (`--yes`, `--dry-run`); aggregate output |
| `gui.py` | Analyze → preview → Convert/Cancel; English strings |

The single-package output format is unchanged apart from the empty `atc_id`.

## 9. Error handling & exit codes (CLI)

- `0` = success (or user cancelled at the prompt — an intentional no-op, not an error).
- `1` = finished with warnings or skipped items.
- `2` = nothing convertible / invalid input (no package found, or every package rejected as non-A380).

Individual package failures inside a batch never abort the batch; they are reported and reflected in the exit code (`1` if others succeeded, `2` if none did). Per-texture failures keep their existing skip-and-warn behaviour.

## 10. Testing

- **Validation:** foreign variant skipped + warned; pure A320 package rejected with a message naming the type; mixed package converts only the A380 variants.
- **Discovery:** `find_packages` on a single-package folder, on a parent with 2 packages + 1 non-package child, and on a folder with no packages.
- **Batch:** parent with 2 valid + 1 foreign subfolder → 2 output packages + `batch_report.txt`; foreign one listed as skipped; totals correct.
- **Registration:** generated `livery.cfg` contains `atc_id=""` (update existing `livery_gen` test).
- **Preview:** `plan_conversion` returns correct package/livery/texture counts and writes **no** files; CLI `--dry-run` exits without writing; CLI without `--yes` and simulated `n` cancels without writing; `--yes` converts.
- **English:** GUI/CLI user-facing strings assert English (light checks).
- **Integration:** the real Qatar fleet pack still converts (single-package path); a synthetic 2-package folder exercises the batch path.

## 11. Backward compatibility & non-goals

- Single-package usage (`convert <pkg> -o <out>`, GUI single folder) still works — `find_packages` returns `[pkg]`. Output is identical to before **except** `atc_id` is now empty.
- **Behaviour change:** the CLI now prints a plan and prompts by default; scripts must add `--yes`. The GUI is now two-step (Analyze → Convert). Both are intended.
- **Non-goals (v1):** no zip input; no deep/recursive package discovery (direct children only); no per-livery selection in the preview (confirm is all-or-nothing for the whole run); no i18n framework / non-English languages.
