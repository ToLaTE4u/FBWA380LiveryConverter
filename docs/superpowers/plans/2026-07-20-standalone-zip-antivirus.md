# Standalone-ZIP Antivirus-Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Den Windows-Build von Nuitka `--onefile` auf `--standalone` umstellen und als ZIP-Ordner ausliefern, um die generischen Antivirus-False-Positives (Bkav, Elastic, Malwarebytes) zu beseitigen, die durch das Onefile-Selbstentpacken und die eingebettete `texconv.exe` ausgelöst werden.

**Architecture:** Reine Build- und Verpackungsänderung. Nuitka erzeugt statt einer selbstentpackenden Einzel-EXE einen Ordner (Launcher-EXE + `python3*.dll` + Extension-Module + `resources/` inkl. `texconv.exe` als reguläre Datei). Der Ordner wird zu einem ZIP gepackt und als Release-Asset ausgeliefert. Kein Python-Quellcode ändert sich — `resource_path()` und die texconv-Suche in `gui.py` lösen im Standalone-Modus über `Path(__file__).parent / "resources"` unverändert korrekt auf.

**Tech Stack:** Nuitka (standalone), PowerShell (`Compress-Archive`), GitHub Actions (`windows-latest`), uv, Python 3.12.

## Global Constraints

- Build läuft **nur unter Windows** (Nuitka kann nicht cross-compilen); Python 3.12 via uv.
- **Keine Python-Quellcode-Änderungen** — die bestehende Test-Suite bleibt unverändert grün (`uv run pytest -q`).
- Kein Code-Signing, kein texconv-Download, kein Ersatz der BC7-Encodierung (bewusst außerhalb des Scopes).
- Fixe Namen: Company `ToLaTE4u`, Product `FBW A380X Livery Converter`, EXE-Dateiname `A380XLiveryConverter.exe`.
- Ordnername im ZIP: `A380XLiveryConverter/`. ZIP-Dateiname: `A380XLiveryConverter-v{semver}.zip` (z. B. `A380XLiveryConverter-v0.2.0.zip`).
- Alle bestehenden Nuitka-Metadaten-Flags (Version, Company, Product, Icon, Copyright, File-Description, `--windows-console-mode=attach`) bleiben erhalten.

---

### Task 1: Build-Script auf Standalone + ZIP umstellen

**Files:**
- Modify: `scripts/build_exe.ps1` (komplett ersetzen, siehe Step 1)

**Interfaces:**
- Consumes: nichts aus früheren Tasks.
- Produces: nach dem Lauf existiert `dist/A380XLiveryConverter/A380XLiveryConverter.exe` (Standalone-Ordner) **und** `dist/A380XLiveryConverter-v{semver}.zip` mit `A380XLiveryConverter/` als Top-Level-Ordner. Diese Pfade nutzt Task 2.

- [ ] **Step 1: Build-Script ersetzen**

Ersetze den **gesamten** Inhalt von `scripts/build_exe.ps1` durch:

```powershell
# Build the standalone Windows application folder and package it as a ZIP.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

# Derive version from git tag (v0.2.0 -> semver 0.2.0, Windows version 0.2.0.0)
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
Rename-Item "dist/__main__.dist" $distDir

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
```

- [ ] **Step 2: Build ausführen**

Run: `powershell -ExecutionPolicy Bypass -File scripts/build_exe.ps1`
Expected: Nuitka läuft durch (mehrere Minuten), am Ende zwei Zeilen: `Built dist/A380XLiveryConverter/A380XLiveryConverter.exe` und `Packaged dist/A380XLiveryConverter-v<semver>.zip`. Kein Fehler.

- [ ] **Step 3: Standalone-Ausgabe verifizieren**

Run (PowerShell):
```powershell
Test-Path dist/A380XLiveryConverter/A380XLiveryConverter.exe
Test-Path dist/A380XLiveryConverter/a380x_livery_converter/resources/texconv.exe
```
Expected: beide `True`. Damit ist bestätigt, dass die Launcher-EXE existiert und `texconv.exe` als reguläre Sibling-Datei im Ordner liegt (nicht mehr eingebettet).

- [ ] **Step 4: ZIP-Struktur verifizieren (Top-Level-Ordner)**

Run (PowerShell):
```powershell
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead((Resolve-Path dist/A380XLiveryConverter-v*.zip))
$zip.Entries[0].FullName
$zip.Dispose()
```
Expected: Der Pfad beginnt mit `A380XLiveryConverter/`. Falls stattdessen direkt Dateinamen erscheinen (Ordner fehlt), stimmt die `Compress-Archive`-Annahme nicht — dann in Step 1 den Aufruf ändern zu: erst in `dist` wechseln und `Compress-Archive -Path A380XLiveryConverter -DestinationPath "A380XLiveryConverter-v$semver.zip"`.

- [ ] **Step 5: Smoke-Test der Standalone-EXE**

Run: `./dist/A380XLiveryConverter/A380XLiveryConverter.exe convert --help`
Expected: Die CLI-Hilfe für `convert` wird ausgegeben, Exit-Code 0. Das bestätigt, dass die EXE ohne Onefile-Entpacken startet und ihre Ressourcen findet.

- [ ] **Step 6: Commit**

```bash
git add scripts/build_exe.ps1
git commit -m "Build standalone folder + ZIP instead of onefile to avoid AV false positives"
```

---

### Task 2: Release-Workflow auf Ordner/ZIP anpassen

**Files:**
- Modify: `.github/workflows/release.yml` (Steps „Smoke-test the executable", „Upload build artifact", „Publish GitHub Release")

**Interfaces:**
- Consumes: aus Task 1 die Pfade `dist/A380XLiveryConverter/A380XLiveryConverter.exe` (Smoke-Test) und `dist/A380XLiveryConverter-v*.zip` (Artifact/Release-Asset).
- Produces: keine späteren Consumer.

- [ ] **Step 1: Smoke-Test-Pfad anpassen**

Ersetze in `.github/workflows/release.yml`:
```yaml
      - name: Smoke-test the executable
        run: ./dist/A380XLiveryConverter.exe convert --help
```
durch:
```yaml
      - name: Smoke-test the executable
        run: ./dist/A380XLiveryConverter/A380XLiveryConverter.exe convert --help
```

- [ ] **Step 2: Upload-Artifact auf ZIP umstellen**

Ersetze:
```yaml
      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: A380XLiveryConverter
          path: dist/A380XLiveryConverter.exe
          if-no-files-found: error
```
durch:
```yaml
      - name: Upload build artifact
        uses: actions/upload-artifact@v4
        with:
          name: A380XLiveryConverter
          path: dist/A380XLiveryConverter-v*.zip
          if-no-files-found: error
```

- [ ] **Step 3: Release-Asset auf ZIP umstellen**

Ersetze im Step „Publish GitHub Release":
```yaml
        with:
          files: dist/A380XLiveryConverter.exe
          body: ${{ steps.changelog.outputs.body }}
          fail_on_unmatched_files: true
```
durch:
```yaml
        with:
          files: dist/A380XLiveryConverter-v*.zip
          body: ${{ steps.changelog.outputs.body }}
          fail_on_unmatched_files: true
```

- [ ] **Step 4: YAML-Syntax prüfen**

Run (PowerShell):
```powershell
python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/release.yml',encoding='utf-8')); print('ok')"
```
Expected: `ok` (keine YAML-Fehler). Falls `yaml` fehlt: `uv run python -c \"import yaml; ...\"` — pyyaml ist als transitive Dev-Abhängigkeit i. d. R. vorhanden; alternativ die drei geänderten Stellen visuell gegen die obigen Blöcke prüfen.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "Release standalone ZIP asset instead of single exe"
```

---

### Task 3: README-Installationsanweisung auf ZIP-Ordner aktualisieren

**Files:**
- Modify: `README.md` (Abschnitt „Download & install" und erster Schritt unter „How to use it (graphical)")

**Interfaces:**
- Consumes: nichts.
- Produces: keine späteren Consumer.

- [ ] **Step 1: „Download & install"-Abschnitt ersetzen**

Ersetze in `README.md`:
```markdown
## Download & install

1. Download `A380XLiveryConverter.exe` **only from an official source** — the
   [GitHub Releases](../../releases) page or flightsim.to.
2. That's it — it's a single self-contained file. No installer, no Python required.
```
durch:
```markdown
## Download & install

1. Download the `A380XLiveryConverter-v*.zip` **only from an official source** —
   the [GitHub Releases](../../releases) page or flightsim.to.
2. **Extract the whole ZIP** to a folder of your choice (right-click → Extract All).
   Keep every file together in that folder — the program needs the files next to it.
3. No installer and no Python required.
```

- [ ] **Step 2: Ersten GUI-Schritt anpassen**

Ersetze:
```markdown
1. Double-click `A380XLiveryConverter.exe`.
```
durch:
```markdown
1. Open the extracted folder and double-click `A380XLiveryConverter.exe`.
```

- [ ] **Step 3: Verifizieren**

Run: `grep -n "Extract the whole ZIP" README.md`
Expected: eine Trefferzeile. Zusätzlich sicherstellen, dass „single self-contained file" nicht mehr vorkommt: `grep -n "single self-contained file" README.md` → keine Treffer.

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "Document ZIP download + extract-to-folder install"
```

---

## Nach Abschluss (operativ, kein Task)

- Die frisch gebaute `dist/A380XLiveryConverter/A380XLiveryConverter.exe` erneut auf VirusTotal hochladen und die Trefferzahl mit dem Ausgangsbefund (Bkav, Elastic, Malwarebytes) vergleichen.
- Falls einzelne Engines noch anschlagen: gezielte False-Positive-Meldung an den jeweiligen Hersteller.
- Neue ZIP erneut auf flightsim.to hochladen.
- CHANGELOG.md-Eintrag für die nächste Version (z. B. „Distribute as a standalone ZIP to avoid antivirus false positives") beim nächsten Release-Tag ergänzen.
