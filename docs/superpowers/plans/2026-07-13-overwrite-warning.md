# Overwrite Warning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Warn and require explicit confirmation before overwriting an output package folder that already exists — in both CLI and GUI.

**Architecture:** The plan phase records, per package, whether its output folder already exists. The CLI adds a `--force` flag and an explicit overwrite prompt before the convert confirmation; the GUI shows a modal when Convert is clicked and a package exists. Both front ends mark existing packages in the preview.

**Tech Stack:** Python 3.12, uv, typer, Tkinter, pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-13-overwrite-warning-design.md` — governs on conflict.
- All commands via `uv run …`.
- All user-facing strings English.
- The tool does NOT wipe the existing folder; overwrite replaces files in place (unchanged behaviour). This feature only adds the warning/confirmation.
- CLI: `--yes` skips both the overwrite prompt and the convert prompt; `--force`/`--overwrite` skips only the overwrite prompt. `--dry-run` shows the plan (with markers) and exits, no prompts.
- Git: imperative commit messages, no AI attribution. Branch `feature/overwrite-warning` (already created).
- Tests run the real texconv.exe on small 8x8 textures (works).

---

### Task 1: PackagePlan.exists set during planning

**Files:**
- Modify: `src/a380x_livery_converter/converter.py`
- Test: `tests/test_converter.py`

**Interfaces:**
- Produces: `PackagePlan` gains `exists: bool = False`. `plan_conversion` sets each package's `exists` to whether `output_dir / output_name` exists on disk, AFTER `_dedupe_output_names`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_converter.py`:

```python
def test_plan_marks_existing_output_package(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False, name="src")
    out = tmp_path / "out"
    plan1 = plan_conversion(pkg, out)
    assert plan1.packages[0].exists is False
    (out / plan1.packages[0].output_name).mkdir(parents=True)
    plan2 = plan_conversion(pkg, out)
    assert plan2.packages[0].exists is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_converter.py::test_plan_marks_existing_output_package -v`
Expected: FAIL (`PackagePlan` has no `exists` attribute).

- [ ] **Step 3: Implement**

In `src/a380x_livery_converter/converter.py`, add the field to `PackagePlan`:

```python
@dataclass
class PackagePlan:
    source: Path
    output_name: str
    livery_names: list[str]
    texture_count: int
    warnings: list[str]
    exists: bool = False
```

And in `plan_conversion`, set it after the dedup call:

```python
    _dedupe_output_names(packages)
    for pkg in packages:
        pkg.exists = (output_dir / pkg.output_name).exists()
    return ConversionPlan(packages, skipped, output_dir)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_converter.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/converter.py tests/test_converter.py
git commit -m "Record whether each output package already exists in the plan"
```

---

### Task 2: CLI overwrite prompt and --force flag

**Files:**
- Modify: `src/a380x_livery_converter/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `PackagePlan.exists` (Task 1), `plan_conversion` (for test setup).
- Produces: `convert` gains `--force`/`--overwrite`; `_print_plan` marks existing packages; an overwrite prompt runs before the convert confirmation when any package exists and neither `--yes` nor `--force` is set.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py` (add `plan_conversion` to the converter import at the top: `from a380x_livery_converter.converter import BatchResult, ConversionResult, plan_conversion` — keep any names already imported):

```python
def _existing_single(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    (pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "TEXTURE.X"
     / "CUSTOM_DECAL.PNG.DDS").unlink()
    out = tmp_path / "out"
    name = plan_conversion(pkg, out).packages[0].output_name
    (out / name).mkdir(parents=True)
    return pkg, out, name


def test_existing_package_marked_in_plan(tmp_path):
    pkg, out, name = _existing_single(tmp_path)
    result = runner.invoke(app, [str(pkg), "-o", str(out), "--dry-run"])
    assert "already exists" in result.output


def test_decline_overwrite_cancels(tmp_path):
    pkg, out, name = _existing_single(tmp_path)
    result = runner.invoke(app, [str(pkg), "-o", str(out)], input="n\n")
    assert result.exit_code == 0
    assert "Cancelled." in result.output
    assert not (out / name / "manifest.json").exists()


def test_overwrite_then_convert(tmp_path):
    pkg, out, name = _existing_single(tmp_path)
    result = runner.invoke(app, [str(pkg), "-o", str(out)], input="y\ny\n")
    assert result.exit_code == 0, result.output
    assert (out / name / "manifest.json").exists()


def test_force_skips_overwrite_prompt(tmp_path):
    pkg, out, name = _existing_single(tmp_path)
    result = runner.invoke(app, [str(pkg), "-o", str(out), "--force"], input="y\n")
    assert result.exit_code == 0, result.output
    assert (out / name / "manifest.json").exists()


def test_yes_skips_both_prompts(tmp_path):
    pkg, out, name = _existing_single(tmp_path)
    result = runner.invoke(app, [str(pkg), "-o", str(out), "--yes"])
    assert result.exit_code == 0, result.output
    assert (out / name / "manifest.json").exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_cli.py -k "overwrite or existing or force or skips_both" -v`
Expected: FAIL (no marker, no `--force`, overwrite prompt absent).

- [ ] **Step 3: Implement**

In `src/a380x_livery_converter/cli.py`, mark existing packages in `_print_plan`:

```python
    for pkg in plan.packages:
        marker = " (already exists — will be overwritten)" if pkg.exists else ""
        typer.echo(f"  - {pkg.output_name}: {len(pkg.livery_names)} liveries, "
                   f"{pkg.texture_count} textures{marker}")
        for warning in pkg.warnings:
            typer.secho(f"      WARNING: {warning}", fg=typer.colors.YELLOW)
```

Add the `--force` option to `convert`'s signature (after `yes`):

```python
    force: bool = typer.Option(False, "--force", "--overwrite",
                               help="Overwrite existing packages without asking"),
```

And insert the overwrite prompt between the `dry_run` exit and the convert confirmation:

```python
    if dry_run:
        raise typer.Exit(0)
    existing = [pkg.output_name for pkg in plan.packages if pkg.exists]
    if existing and not yes and not force and not typer.confirm(
            f"{len(existing)} package(s) already exist and will be overwritten: "
            f"{', '.join(existing)}. Overwrite?"):
        typer.echo("Cancelled.")
        raise typer.Exit(0)
    if not yes and not typer.confirm(
            f"Convert {plan.livery_count} liveries in {plan.package_count} package(s)?"):
        typer.echo("Cancelled.")
        raise typer.Exit(0)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (all).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/cli.py tests/test_cli.py
git commit -m "Warn and confirm before overwriting existing packages in the CLI"
```

---

### Task 3: GUI overwrite modal and marker

**Files:**
- Modify: `src/a380x_livery_converter/gui.py`
- Test: `tests/test_gui.py`

**Interfaces:**
- Consumes: `PackagePlan.exists` (Task 1).
- Produces: `_show_plan` marks existing packages; `convert()` shows a `messagebox.askyesno` when any package exists and only proceeds on "Yes".

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gui.py`:

```python
def test_convert_declined_overwrite_does_not_start(monkeypatch):
    from types import SimpleNamespace

    from a380x_livery_converter import gui as gui_mod
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        app._plan = SimpleNamespace(packages=[
            SimpleNamespace(output_name="foo", exists=True,
                            livery_names=["l"], texture_count=1, warnings=[])])
        monkeypatch.setattr(gui_mod.messagebox, "askyesno", lambda *a, **k: False)
        app.convert()
        assert app._busy is False
    finally:
        root.destroy()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gui.py::test_convert_declined_overwrite_does_not_start -v`
Expected: FAIL (convert does not consult a modal; `_busy` becomes True) — or SKIP without a display.

- [ ] **Step 3: Implement**

In `src/a380x_livery_converter/gui.py`, add `messagebox` to the tkinter import:

```python
from tkinter import filedialog, messagebox, scrolledtext, ttk
```

Mark existing packages in `_show_plan`:

```python
        for pkg in plan.packages:
            marker = " (already exists — will be overwritten)" if pkg.exists else ""
            self._append_log(f"  - {pkg.output_name}: {len(pkg.livery_names)} liveries, "
                             f"{pkg.texture_count} textures{marker}")
            for warning in pkg.warnings:
                self._append_log(f"      WARNING: {warning}")
```

And guard `convert()` with the overwrite modal:

```python
    def convert(self):
        if self._plan is None:
            return
        existing = [pkg.output_name for pkg in self._plan.packages if pkg.exists]
        if existing and not messagebox.askyesno(
                "Overwrite?",
                f"{len(existing)} package(s) already exist and will be overwritten:\n"
                + "\n".join(existing) + "\n\nOverwrite?"):
            return
        self._busy = True
        self._set_buttons(analyze=False, convert=False, cancel=False)
        self.progressbar.config(value=0)
        threading.Thread(target=self._do_convert, args=(self._plan,), daemon=True).start()
        self.root.after(100, self._poll)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_gui.py -v`
Then the whole suite: `uv run pytest -q`
Expected: PASS (GUI tests run or skip without a display; full suite green).

- [ ] **Step 5: Commit**

```bash
git add src/a380x_livery_converter/gui.py tests/test_gui.py
git commit -m "Warn and confirm before overwriting existing packages in the GUI"
```

---

## Execution notes

- Tasks 1 → 2 → 3 in order; 2 and 3 depend on `PackagePlan.exists` from Task 1.
- After each task run `uv run pytest -q` and commit.
- README already documents the preview/confirm flow; a one-line mention of the overwrite warning can be added but is optional and not required by this plan.
