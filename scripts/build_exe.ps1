# Build the single-file Windows executable.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

uv run python -m nuitka `
    --onefile `
    --assume-yes-for-downloads `
    --enable-plugin=tk-inter `
    --include-package=a380x_livery_converter `
    --include-data-dir=src/a380x_livery_converter/resources=a380x_livery_converter/resources `
    --include-data-files=src/a380x_livery_converter/resources/texconv.exe=a380x_livery_converter/resources/texconv.exe `
    --windows-console-mode=attach `
    --output-filename=A380XLiveryConverter.exe `
    --output-dir=dist `
    src/a380x_livery_converter/__main__.py

Write-Host "Built dist/A380XLiveryConverter.exe"
