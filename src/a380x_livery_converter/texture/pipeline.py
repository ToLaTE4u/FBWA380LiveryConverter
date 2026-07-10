"""Full conversion of one legacy DDS texture into a 2024 KTX2 texture."""

from pathlib import Path

import texture2ddecoder

from a380x_livery_converter.texture.dds import DdsFile, read_dds
from a380x_livery_converter.texture.ktx2 import (
    filetime_from_unix,
    write_flags_json,
    write_ktx2,
)
from a380x_livery_converter.texture.texconv import dds_to_bc7_dds

_ALPHA_THRESHOLD = 250


def has_transparency(dds: DdsFile) -> bool:
    if dds.format not in ("BC1", "BC3"):
        return False
    level = dds.mip_levels[0]
    for candidate in reversed(dds.mip_levels):
        if candidate.width >= 4 and candidate.height >= 4:
            level = candidate
            break
    if dds.format == "BC1":
        decoded = texture2ddecoder.decode_bc1(level.data, level.width, level.height)
    else:
        decoded = texture2ddecoder.decode_bc3(level.data, level.width, level.height)
    return any(a < _ALPHA_THRESHOLD for a in decoded[3::4])


def convert_texture(src: Path, dest_ktx2: Path, work_dir: Path) -> None:
    src = Path(src)
    dest_ktx2 = Path(dest_ktx2)
    source = read_dds(src)  # validates the input file
    transparent = has_transparency(source)
    bc7_dds_path = dds_to_bc7_dds(src, Path(work_dir))
    try:
        bc7 = read_dds(bc7_dds_path)
        dest_ktx2.parent.mkdir(parents=True, exist_ok=True)
        write_ktx2(dest_ktx2, bc7, transparent)
        write_flags_json(dest_ktx2, filetime_from_unix(src.stat().st_mtime))
    finally:
        bc7_dds_path.unlink(missing_ok=True)
