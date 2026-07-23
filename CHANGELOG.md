# Changelog

## v0.3.2

- Analyze is much faster on large folders. It used to read every texture in full
  to fingerprint it; it now only reads the ones that can actually be duplicates
  of each other. A 132-package, 37 GB fleet folder went from 58 s to 2.3 s.
- Analyze now reports progress per package instead of leaving the window silent
  for minutes on large batch folders.
- Analyze and Convert can be cancelled while they run. Cancel used to be greyed
  out for the whole run, which made the tool look frozen.
- Reduce texture conversion to 2 parallel jobs. `texconv.exe` is already
  multithreaded, so 8 jobs gave no extra throughput but tripled peak memory and
  left no CPU for the rest of the machine.
- Convert reuses the work done during Analyze instead of reading and hashing
  every texture a second time.
- Clearer skip reasons: packages that are already in MSFS 2024 format now say so
  instead of reporting "no FBW A380X livery found (detected: unknown)".
- Liveries marked `isUserSelectable = 0` are shared texture depots, not
  liveries. They no longer show up as selectable entries in the MSFS livery
  picker. A package that contains nothing but depots - such as the Emirates
  "commons" package - is now converted into a shared-texture package instead of
  being skipped, so the tail numbers that fall back to it keep their fuselage
  and cabin.
- Warn when a livery falls back to textures no package in the folder provides.
  Fleet packs such as the Emirates collection keep their shared textures in a
  separate "commons" package, which the sim merges in at runtime - those
  fallbacks are fine and are no longer reported. Only fallbacks that nothing in
  the selected folder can serve are flagged now.

## v0.3.1

- Add a "Check for Updates" button that opens the tool's GitHub releases page in
  your browser, so you can grab the latest version.

## v0.3.0

- Distribute as a standalone folder inside a ZIP instead of a single
  self-extracting executable — this avoids the antivirus false positives that
  blocked the upload on flightsim.to. Download the ZIP, extract the whole folder,
  and run `A380XLiveryConverter.exe` from inside it.
- `texconv.exe` now ships as a normal file next to the application instead of
  being embedded and unpacked to a temp folder at runtime.

## v0.2.0

- Add application icon to the GUI window and exe
- Show version number in the window title bar
- Check for texconv.exe at startup with a clear error message
- Add "Open Output Folder" button after successful conversion
- Fix progressbar not reaching 100% when textures are skipped
- Make log text selectable and copyable
- Set Windows file properties (version, copyright, product name) on the exe
- Add manually curated changelog for GitHub releases

## v0.1.2

- Append `-2024` suffix to output package folder names
- Add missing `ENGINE_BLUR5` texture mapping

## v0.1.1

- Fix GUI subprocess handle error (`WinError 6`) when running as windowed exe
- Support DDS formats that the built-in reader cannot parse (texconv fallback)

## v0.1.0

- Initial release
- CLI and GUI for converting FBW A380X liveries from MSFS 2020 to 2024
- Batch conversion with progress reporting
- Overwrite warning for existing output packages
