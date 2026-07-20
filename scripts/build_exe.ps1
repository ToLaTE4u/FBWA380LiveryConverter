# Build the standalone Windows application folder and package it as a ZIP.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Derive version from git tag (v0.3.0 -> semver 0.3.0, Windows version 0.3.0.0)
$rawTag = git describe --tags --abbrev=0 2>$null
if ($rawTag -match '^v?(\d+\.\d+\.\d+)') {
    $semver = $Matches[1]
} else {
    $semver = "0.0.0"
}
$version = "$semver.0"
Write-Host "Building version $version"

uv run python -m nuitka `
    --standalone `
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

# Nuitka names the standalone folder after the entry module: dist/__main__.dist.
# Rename it to a clean, user-facing folder name (idempotent across re-builds).
$distDir = "dist/A380XLiveryConverter"
if (Test-Path $distDir) {
    Remove-Item $distDir -Recurse -Force
}
Rename-Item "dist/__main__.dist" "A380XLiveryConverter"

# Package the folder as a ZIP. Passing the directory path WITHOUT a wildcard makes
# Compress-Archive include the folder itself as the archive root, so extracting the
# ZIP keeps every file together inside one A380XLiveryConverter/ folder.
$zipPath = "dist/A380XLiveryConverter-v$semver.zip"
if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}
Compress-Archive -Path $distDir -DestinationPath $zipPath

Write-Host "Built $distDir/A380XLiveryConverter.exe"
Write-Host "Packaged $zipPath"
