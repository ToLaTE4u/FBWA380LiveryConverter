"""Wrapper around the bundled DirectXTex texconv.exe."""

import subprocess
from pathlib import Path

from a380x_livery_converter import resource_path


class TexconvError(Exception):
    pass


def dds_to_bc7_dds(src: Path, out_dir: Path) -> Path:
    src = Path(src)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = [
        str(resource_path("texconv.exe")),
        "-f", "BC7_UNORM",
        "-m", "0",          # full mip chain
        "-y",               # overwrite
        "-nologo",
        "-o", str(out_dir),
        str(src),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    result = _find_ci(out_dir, src.stem + ".dds")
    if proc.returncode != 0 or result is None:
        raise TexconvError(
            f"texconv failed for {src.name} (exit {proc.returncode}):\n"
            f"{proc.stdout}\n{proc.stderr}")
    return result


def _find_ci(folder: Path, name: str) -> Path | None:
    if not folder.is_dir():
        return None
    for child in folder.iterdir():
        if child.name.upper() == name.upper():
            return child
    return None
