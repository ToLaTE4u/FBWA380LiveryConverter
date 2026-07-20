# Changelog

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
