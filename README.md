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
