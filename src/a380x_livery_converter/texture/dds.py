"""Minimal DDS reader for BC1/BC3 (legacy fourCC) and BC7 (DX10 header) files."""

import struct
from dataclasses import dataclass
from pathlib import Path

FOURCC_TO_FORMAT = {b"DXT1": "BC1", b"DXT5": "BC3"}
BLOCK_BYTES = {"BC1": 8, "BC3": 16, "BC7": 16}
DXGI_BC7 = {98, 99}  # BC7_UNORM, BC7_UNORM_SRGB


class DdsError(Exception):
    pass


@dataclass
class MipLevel:
    width: int
    height: int
    data: bytes


@dataclass
class DdsFile:
    width: int
    height: int
    format: str
    mip_levels: list[MipLevel]


def read_dds(path: Path) -> DdsFile:
    data = Path(path).read_bytes()
    if len(data) < 128 or data[:4] != b"DDS ":
        raise DdsError(f"{path}: not a DDS file")
    height = struct.unpack_from("<I", data, 12)[0]
    width = struct.unpack_from("<I", data, 16)[0]
    mip_count = max(1, struct.unpack_from("<I", data, 28)[0])
    fourcc = data[84:88]
    offset = 128
    if fourcc == b"DX10":
        if len(data) < 148:
            raise DdsError(f"{path}: truncated DX10 header")
        dxgi = struct.unpack_from("<I", data, 128)[0]
        if dxgi not in DXGI_BC7:
            raise DdsError(f"{path}: unsupported DXGI format {dxgi}")
        fmt = "BC7"
        offset = 148
    else:
        fmt = FOURCC_TO_FORMAT.get(fourcc)
        if fmt is None:
            raise DdsError(f"{path}: unsupported fourCC {fourcc!r}")

    levels: list[MipLevel] = []
    w, h = width, height
    for _ in range(mip_count):
        size = max(1, (w + 3) // 4) * max(1, (h + 3) // 4) * BLOCK_BYTES[fmt]
        chunk = data[offset : offset + size]
        if len(chunk) != size:
            raise DdsError(f"{path}: truncated mip data at level {len(levels)}")
        levels.append(MipLevel(w, h, chunk))
        offset += size
        w, h = max(1, w // 2), max(1, h // 2)
    return DdsFile(width=width, height=height, format=fmt, mip_levels=levels)
