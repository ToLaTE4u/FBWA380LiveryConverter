# Design: Standalone-ZIP-Build zur Vermeidung von Antivirus-False-Positives

**Datum:** 2026-07-20
**Status:** Genehmigt

## Problem

Der auf flightsim.to hochgeladene Build (`A380XLiveryConverter.exe`, Nuitka
`--onefile`) wurde blockiert, weil VirusTotal drei Treffer meldete:

| Engine | Detection | Typ |
|---|---|---|
| Bkav Pro | `W32.Malware.7ACE613E` | Generische Heuristik |
| Elastic | `Malicious (moderate confidence)` | ML |
| Malwarebytes | `Malware.AI.1324982085` | AI/ML |
| Acronis (Static ML) | Undetected | — |

Alle Treffer sind rein generisch/ML — keine Engine nennt eine echte
Malware-Familie. Microsoft Defender ist **nicht** unter den Treffern
(undetected). Das ist ein klassisches False-Positive-Muster für kompilierte
Python-Tools.

## Ursachenanalyse

Zwei strukturelle Eigenschaften des aktuellen Builds triggern die
Heuristik-/ML-Engines:

1. **Nuitka `--onefile`** — packt beim Start das gesamte Programm nach `%TEMP%`
   aus und führt es dort aus. Dieses „Selbst-Entpacken und Ausführen aus TEMP"
   ist das Kennzeichen von Packer-/Dropper-Malware. Bkav, Elastic und
   Malwarebytes reagieren notorisch genau darauf.
2. **Eingebettete `texconv.exe`** — eine zweite ausführbare Datei wird zur
   Laufzeit nach `%TEMP%` entpackt und gestartet („EXE droppt EXE"), einer der
   stärksten Dropper-Indikatoren.

Beide Trigger verschwinden bei einem **Standalone**-Build.

## Rahmenbedingungen (mit dem Nutzer geklärt)

- Verteilung als **ZIP-Ordner** ist akzeptabel (auf flightsim.to üblich).
- **Kein** Code-Signing-Zertifikat (vorerst kostenlos bleiben).
- texconv bleibt erhalten (macht die BC7-Encodierung; nicht ersatzlos
  streichbar) — wird aber als normale Datei neben der EXE ausgeliefert statt
  eingebettet.

## Lösung

`--onefile` → `--standalone`. Nuitka erzeugt einen Ordner mit Launcher-EXE,
`python3xx.dll`, Extension-Modulen und `resources/` (inkl. `texconv.exe` als
reguläre, Microsoft-signierte Datei). Der Ordner wird als ZIP ausgeliefert.
Zur Laufzeit wird nichts mehr nach `%TEMP%` entpackt.

**Keine Python-Code-Änderung nötig:** `resource_path()`
(`src/a380x_livery_converter/__init__.py`) und die texconv-Suche in `gui.py`
lösen über `Path(__file__).parent / "resources"` im Standalone-Modus korrekt
auf, genau wie im Onefile-Modus.

### Änderungen

**1. `scripts/build_exe.ps1`**
- `--onefile` → `--standalone`.
- Nach dem Build den Nuitka-Ausgabeordner `dist/__main__.dist/` sauber nach
  `dist/A380XLiveryConverter/` umbenennen (vorhandenen Zielordner vorher
  entfernen, damit ein Re-Build idempotent ist).
- Ordner zu `dist/A380XLiveryConverter-v{version}.zip` zippen, mit
  `A380XLiveryConverter/` als Top-Level-Ordner im ZIP (beim Entpacken werden so
  keine Dateien verstreut).
- Alle Metadaten-Flags (Version, Company, Product, Icon, Copyright,
  File-Description) bleiben unverändert.

**2. `.github/workflows/release.yml`**
- Smoke-Test-Pfad ändern:
  `./dist/A380XLiveryConverter/A380XLiveryConverter.exe convert --help`.
- Upload-Artifact und Release-Asset: die **ZIP**
  (`dist/A380XLiveryConverter-v*.zip`) statt der nackten EXE.

**3. `README.md`** (+ ggf. `THIRD-PARTY-NOTICES.md`)
- Download-/Install-Abschnitt: „ZIP herunterladen → **vollständig** entpacken →
  `A380XLiveryConverter.exe` im Ordner starten. Alle Dateien im Ordner
  belassen." Hinweis, dass es kein Einzel-EXE mehr ist, sondern ein Ordner.

## Verifikation

1. Lokaler Build über `scripts/build_exe.ps1` erzeugt
   `dist/A380XLiveryConverter/A380XLiveryConverter.exe` und die ZIP.
2. Smoke-Test: `A380XLiveryConverter.exe convert --help` läuft; GUI startet per
   Doppelklick; eine echte Konvertierung (mit `data/`-Testdaten) erzeugt ein
   valides 2024-Paket → bestätigt, dass texconv als Sibling gefunden wird.
3. Bestehende Test-Suite (`uv run pytest -q`) bleibt grün (keine Code-Änderung).
4. Neue ZIP-EXE auf VirusTotal hochladen, Trefferzahl mit vorher vergleichen.
5. Falls einzelne Engines noch anschlagen: gezielte False-Positive-Meldung an
   den jeweiligen Hersteller.

## Erwartetes Ergebnis / Grenzen

- **Erwartet:** Bkav-, Elastic- und Malwarebytes-Treffer entfallen mit hoher
  Wahrscheinlichkeit, da der Onefile-Selbstentpacker-Trigger und die
  eingebettete zweite EXE wegfallen. Realistisch 0–1 statt 3 Treffer.
- **Grenze:** Ohne Code-Signatur ist garantierte Null nicht sicher. Sollte
  flightsim.to bei jedem einzelnen Treffer blocken, bleibt Code-Signing die
  Restlösung — bewusst auf später verschoben.

## Nicht im Scope

- Code-Signing.
- Ersatz von texconv durch einen Python-BC7-Encoder.
- Download von texconv zur Laufzeit.
