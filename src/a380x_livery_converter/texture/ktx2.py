"""KTX2 writer, calibrated byte-for-byte against the FBW 2024 reference livery."""

import json
import struct
from pathlib import Path

from a380x_livery_converter.texture.dds import DdsFile

KTX2_IDENTIFIER = bytes.fromhex("ab4b5458203230bb0d0a1a0a")
VK_FORMAT_BC7_UNORM_BLOCK = 145
LEVEL_ALIGNMENT = 16  # BC7 block byte size
DFD_BC7 = bytes.fromhex(
    "2c000000000000000200280086010100"
    "03030000100000000000000000007f00"
    "0000000000000000ffffffff"
)
_ASOBO_FLAGS = (b"BILINEAR\x00COMPRESSION\x00MIPMAP\x00REDUCE_LESS\x00"
                b"PLATFORM_FORMAT\x00QUALITY_HIGH\x00")
SIDECAR_FLAGS = ["FL_BITMAP_COMPRESSION", "FL_BITMAP_MIPMAP", "FL_BITMAP_QUALITY_HIGH"]

_EPOCH_DIFF = 11644473600  # seconds between 1601-01-01 and 1970-01-01


def filetime_from_unix(ts: float) -> int:
    return int((ts + _EPOCH_DIFF) * 10_000_000)


def build_kvd(transparent: bool) -> bytes:
    entries = [
        (b"ASOBO_flags", _ASOBO_FLAGS),
        (b"ASOBO_opacities", b""),
        (b"ASOBO_transp", b"\x01" if transparent else b"\x00"),
        (b"ASOBOtexversion", struct.pack("<I", 1)),
        (b"KTXwriter", b"ASOBO_FlightSim\x00"),
    ]
    out = bytearray()
    for key, value in entries:
        kv = key + b"\x00" + value
        out += struct.pack("<I", len(kv)) + kv
        out += b"\x00" * (-len(kv) % 4)
    return bytes(out)


def write_ktx2(path: Path, dds: DdsFile, transparent: bool) -> None:
    if dds.format != "BC7":
        raise ValueError(f"KTX2 writer requires BC7 input, got {dds.format}")
    kvd = build_kvd(transparent)
    level_count = len(dds.mip_levels)
    dfd_off = 80 + level_count * 24
    kvd_off = dfd_off + len(DFD_BC7)
    data_start = kvd_off + len(kvd)

    # Daten im File: kleinste Mip-Ebene zuerst (wie Referenz), 16-Byte-aligned
    offsets: dict[int, int] = {}
    pos = data_start
    for i in reversed(range(level_count)):
        pos = -(-pos // LEVEL_ALIGNMENT) * LEVEL_ALIGNMENT
        offsets[i] = pos
        pos += len(dds.mip_levels[i].data)

    header = KTX2_IDENTIFIER + struct.pack(
        "<9I", VK_FORMAT_BC7_UNORM_BLOCK, 1, dds.width, dds.height,
        0, 0, 1, level_count, 0)
    index = struct.pack("<4I2Q", dfd_off, len(DFD_BC7), kvd_off, len(kvd), 0, 0)
    level_index = b"".join(
        struct.pack("<3Q", offsets[i], len(lvl.data), len(lvl.data))
        for i, lvl in enumerate(dds.mip_levels))

    blob = bytearray(header + index + level_index + DFD_BC7 + kvd)
    # Padding + Daten sequenziell schreiben (kleinste Ebene zuerst)
    for i in reversed(range(level_count)):
        blob += b"\x00" * (offsets[i] - len(blob))
        blob += dds.mip_levels[i].data
    Path(path).write_bytes(bytes(blob))


def write_flags_json(ktx2_path: Path, source_file_date: int) -> Path:
    sidecar = Path(str(ktx2_path) + ".json")
    sidecar.write_text(json.dumps(
        {"Version": 2, "SourceFileDate": source_file_date, "Flags": SIDECAR_FLAGS},
        separators=(",", ":")))
    return sidecar
