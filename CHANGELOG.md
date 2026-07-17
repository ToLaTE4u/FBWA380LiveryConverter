# Changelog

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
