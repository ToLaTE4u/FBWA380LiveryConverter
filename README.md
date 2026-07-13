# FBW A380X Livery Converter

**Convert legacy FlyByWire A380X liveries (MSFS 2020) into ready-to-install native MSFS 2024 packages — automatically.**

When FlyByWire rebuilt the A380X natively for Microsoft Flight Simulator 2024, the
texture format, folder layout, file names and configuration files all changed, so
old community liveries no longer load. This tool takes an old livery package and
produces a finished 2024 package you can drop straight into your Community folder —
no SDK, no developer mode, no manual steps.

---

## Download & install

1. Download `A380XLiveryConverter.exe` from the [Releases](../../releases) page.
2. That's it — it's a single self-contained file. No installer, no Python required.

## How to use it (graphical)

1. Double-click `A380XLiveryConverter.exe`.
2. **Old livery package:** select the extracted folder of the old livery — the one
   that contains `manifest.json` and a `SimObjects` folder.
3. **Output folder:** select your MSFS 2024 **Community** folder (or any folder you
   like, then copy the result over later).
4. Click **Konvertieren** and watch the progress bar. When it finishes, read the log
   and the `conversion_report.txt` inside the new package for any warnings.

The old livery must be **extracted** first — point the tool at the folder, not a
`.zip` archive.

## How to use it (command line)

```
A380XLiveryConverter.exe "C:\path\to\input" -o "C:\path\to\Community" [--yes] [--dry-run] [--verbose]
```

The tool first shows a plan of what it found (packages, liveries, anything
skipped) and asks for confirmation. Pass `--yes` to skip the prompt (for
scripts), or `--dry-run` to show the plan and exit without converting.

`input` may be a single extracted livery package **or** a folder containing
several packages — the tool detects which and converts them all, writing one
installable package each plus a `batch_report.txt` summary.

Exit codes: 0 = success (or cancelled), 1 = finished with warnings, 2 = error.

## What it does

- Converts every texture from the old DDS format to the 2024 KTX2 format (BC7),
  regenerating full mipmaps for good in-sim performance.
- Renames textures to the 2024 naming scheme using FlyByWire's official mapping.
- Rebuilds `livery.cfg`, `texture.CFG`, thumbnails, `manifest.json` and `layout.json`.
- **Fleet packs** (one old package containing several registrations) are converted
  into a single 2024 package — each registration becomes its own livery, and shared
  textures are deduplicated into a common folder to save space.

## Known limitations

- **Custom 3D model changes cannot be carried over.** Some old packs ship their own
  `MODEL.*` folder (for example to add decal geometry). The 2024 livery format does
  not support this, so those changes are dropped. The tool warns you in the report;
  the livery itself still converts.
- Interior/cabin textures are converted as-is; whether the 2024 model actually uses
  them is outside the tool's control.
- The input must be an extracted folder — no `.zip` support.
- On a machine without a suitable GPU, texture compression falls back to a CPU
  encoder, which is much slower (minutes instead of seconds per 4K texture).
- Non-A380 input (e.g. an A320 livery) is rejected with a message naming the
  detected aircraft. Foreign variants inside an otherwise-valid package are
  skipped and reported.
- The generated `livery.cfg` leaves `atc_id` empty (native style); the visible
  tail number comes from each livery's own registration texture.

Every conversion writes a `conversion_report.txt` into the output package listing
all warnings, texture mappings and anything that was skipped.

## License

This tool is **free to use and share, but not to modify.** See [LICENSE](LICENSE)
for the full terms. It bundles third-party components under their own licenses —
see [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md).

Converted liveries you create are yours to share. Remember that a converted livery
may still contain artwork owned by its original author — respect their terms when
redistributing.

## Credits

*Not affiliated with or endorsed by FlyByWire Simulations, Airbus, or Microsoft.*
FlyByWire, A380X and Microsoft Flight Simulator are trademarks of their respective
owners.

---

## For developers

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12 on Windows.

```
uv sync
uv run pytest
powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1
```

Texture compression uses the bundled DirectXTex `texconv.exe` (BC7 + mipmaps); the
KTX2 container writer is calibrated byte-for-byte against the official FlyByWire 2024
paintkit reference livery. The rename mapping comes from FlyByWire's paintkit
`rename_list.csv`.
