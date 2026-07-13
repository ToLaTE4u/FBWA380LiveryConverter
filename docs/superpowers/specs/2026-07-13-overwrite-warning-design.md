# Spec: Overwrite warning when an output package already exists

**Date:** 2026-07-13
**Status:** Draft (design approved)
**Builds on:** the batch/preview features in `2026-07-13-validation-batch-preview-design.md`

## Goal

Before converting, warn the user when an output package folder already exists in the
chosen output directory, and require an explicit overwrite confirmation. Today the
converter silently writes into an existing folder (files are replaced in place). This
adds a clear "already exists — overwrite?" gate in both GUI and CLI.

## Decisions (from brainstorming)

- **Explicit overwrite prompt**, separate from (and in addition to) the existing
  convert confirmation, plus a CLI `--force` flag.
- Detection happens in the cheap plan phase; the preview marks existing packages.
- The tool does NOT wipe an existing folder first — overwrite replaces files in place,
  exactly as today; this feature only adds the warning/confirmation. A "clean
  overwrite" is explicitly out of scope (YAGNI).

## Behaviour

### Detection

- `PackagePlan` gains a boolean field `exists`.
- In `plan_conversion`, after output-name deduplication, set each plan's `exists` to
  whether `output_dir / output_name` already exists on disk.

### Preview (both front ends)

- Existing packages are marked in the plan listing, e.g.
  `- <name>: 8 liveries, 88 textures (already exists — will be overwritten)`.

### CLI (`cli.py`)

- New flag `--force` (alias `--overwrite`): skip the overwrite prompt only.
- Flow after printing the plan:
  1. `--dry-run` → print plan (with exists markers) and exit; no prompts.
  2. If any package `exists` and not `--yes` and not `--force`: prompt
     `N package(s) already exist and will be overwritten: <names>. Overwrite?` `[y/N]`.
     Decline → print `Cancelled.` and exit 0.
  3. Existing convert confirmation `[y/N]` (unless `--yes`).
  4. Execute.
- `--yes` skips both prompts; `--force` skips only the overwrite prompt.

### GUI (`gui.py`)

- When **Convert** is clicked and at least one package `exists`, show a modal
  `messagebox.askyesno` titled "Overwrite?" listing the existing package names and
  asking to overwrite. "No" returns to the preview without writing; "Yes" proceeds to
  the conversion. When nothing exists, Convert proceeds as today.

## Affected modules

| Module | Change |
|---|---|
| `converter.py` | `PackagePlan.exists`; set it in `plan_conversion` after dedup |
| `cli.py` | `--force` flag, exists markers in `_print_plan`, overwrite prompt |
| `gui.py` | exists markers in `_show_plan`, overwrite modal in `convert()` |

## Testing

- Plan: a package whose output folder already exists → `PackagePlan.exists is True`;
  a fresh one → `False`.
- CLI: existing package + declined overwrite (`input="n\n"`) → `Cancelled.`, exit 0,
  nothing written; existing + `y` to overwrite + `y` to convert → runs; `--force`
  skips the overwrite prompt (still asks to convert unless `--yes`); `--yes` skips
  both prompts and overwrites.
- CLI `_print_plan` shows the "already exists" marker for existing packages.
- GUI: `_show_plan` marks existing packages; `convert()` with an existing package
  calls `messagebox.askyesno` and only proceeds on "Yes" (verified by monkeypatching
  `askyesno`).

## Non-goals

- No clean/wipe of the existing folder before writing.
- No per-package overwrite choice (the prompt is one combined confirmation for all
  existing packages).
