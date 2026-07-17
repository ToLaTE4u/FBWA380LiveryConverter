# Build the single-file Windows executable.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Derive version from git tag (v0.1.3 -> 0.1.3.0), fallback to 0.0.0.0
$rawTag = git describe --tags --abbrev=0 2>$null
if ($rawTag -match '^v?(\d+\.\d+\.\d+)') {
    $version = "$($Matches[1]).0"
} else {
    $version = "0.0.0.0"
}
Write-Host "Building version $version"

uv run python -m nuitka `
    --onefile `
    --assume-yes-for-downloads `
    --enable-plugin=tk-inter `
    --include-package=a380x_livery_converter `
    --include-data-dir=src/a380x_livery_converter/resources=a380x_livery_converter/resources `
    --include-data-files=src/a380x_livery_converter/resources/texconv.exe=a380x_livery_converter/resources/texconv.exe `
    --windows-console-mode=attach `
    --windows-icon-from-ico=src/a380x_livery_converter/resources/app.ico `
    --windows-file-version=$version `
    --windows-product-version=$version `
    --windows-company-name=ToLaTE4u `
    --windows-product-name="FBW A380X Livery Converter" `
    --windows-file-description="Convert FBW A380X MSFS 2020 liveries to MSFS 2024" `
    --copyright="Copyright (c) ToLaTE4u" `
    --output-filename=A380XLiveryConverter.exe `
    --output-dir=dist `
    src/a380x_livery_converter/__main__.py

if ($LASTEXITCODE -ne 0) {
    Write-Error "Nuitka build failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "Built dist/A380XLiveryConverter.exe"
