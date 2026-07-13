# Third-Party Notices

The FBW A380X Livery Converter is distributed under the terms in [LICENSE](LICENSE).
It bundles and/or builds upon the third-party components below, each of which remains
under its own license. These notices are provided for attribution and to satisfy those
licenses; the restrictions in LICENSE do **not** apply to these components.

---

## DirectXTex `texconv.exe`

Bundled as `src/a380x_livery_converter/resources/texconv.exe` and used to compress
textures to BC7. Part of Microsoft's DirectXTex project.

<https://github.com/microsoft/DirectXTex> — MIT License.

```
Copyright (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## FlyByWire Simulations — A380X livery paintkit

The texture rename table `src/a380x_livery_converter/resources/rename_list.csv`
(the old-name → 2024-name mapping) originates from FlyByWire's official A380X livery
paintkit, which FlyByWire provides to assist livery authors in porting their work.
The placeholder thumbnails in `src/a380x_livery_converter/resources/thumbnails/` also
originate from that paintkit's sample livery.

Credit: FlyByWire Simulations — <https://flybywiresim.com/>

This project is an independent tool and is not affiliated with or endorsed by
FlyByWire Simulations.

## Python libraries (bundled into the compiled executable)

The compiled `A380XLiveryConverter.exe` includes the following open-source Python
packages, each under its own permissive license:

- **Pillow** — HPND (PIL Software License / MIT-CMU style). <https://python-pillow.org/>
- **texture2ddecoder** — MIT License. <https://github.com/K0lb3/texture2ddecoder>
- **Typer** — MIT License. <https://typer.tiangolo.com/>
- **CPython** and its standard library (including Tkinter) — Python Software
  Foundation License. <https://www.python.org/>

The build tooling (Nuitka) is not distributed with the executable.
