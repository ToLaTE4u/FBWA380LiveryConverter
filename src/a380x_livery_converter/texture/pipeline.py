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


_DECODERS = {
    "BC1": texture2ddecoder.decode_bc1,
    "BC3": texture2ddecoder.decode_bc3,
    "BC7": texture2ddecoder.decode_bc7,
}


def has_transparency(dds: DdsFile) -> bool:
    decode = _DECODERS.get(dds.format)
    if decode is None:
        return False
    level = dds.mip_levels[0]
    for candidate in reversed(dds.mip_levels):
        if candidate.width >= 4 and candidate.height >= 4:
            level = candidate
            break
    decoded = decode(level.data, level.width, level.height)
    return any(a < _ALPHA_THRESHOLD for a in decoded[3::4])


def convert_texture(src: Path, dest_ktx2: Path, work_dir: Path) -> None:
    src = Path(src)
    dest_ktx2 = Path(dest_ktx2)
    # texconv reads any supported DDS format (including uncompressed ones our
    # own read_dds cannot parse), so it is the source gatekeeper. Transparency
    # is detected from the resulting BC7, which works regardless of source format.
    bc7_dds_path = dds_to_bc7_dds(src, Path(work_dir))
    try:
        bc7 = read_dds(bc7_dds_path)
        transparent = has_transparency(bc7)
        dest_ktx2.parent.mkdir(parents=True, exist_ok=True)
        write_ktx2(dest_ktx2, bc7, transparent)
        write_flags_json(dest_ktx2, filetime_from_unix(src.stat().st_mtime))
    finally:
        bc7_dds_path.unlink(missing_ok=True)
