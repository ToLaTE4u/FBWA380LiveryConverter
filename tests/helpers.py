import json
import struct
from pathlib import Path

from PIL import Image

OLD_MANIFEST = {
    "dependencies": [],
    "content_type": "AIRCRAFT",
    "title": "Test Fleet Pack",
    "manufacturer": "Airbus",
    "creator": "TestCreator",
    "package_version": "2.0",
    "minimum_game_version": "1.26.5.0",
}

AIRCRAFT_CFG_TEMPLATE = """[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "..\\FlyByWire_A380_842"

[FLTSIM.0]
title = "TEST {suffix} A380" ; Variation name
ui_variation = "TEST {suffix} A380"
texture = "{suffix}" ; texture folder
model = "{model}" ; model folder
atc_id = "A380X" ; tail number
atc_airline = "Test Airways" ; airline name
icao_airline = "TST"
isUserSelectable = {selectable}
"""

OLD_TEXTURE_CFG = """[fltsim]
fallback.1=..\\..\\Common Textures
fallback.2=..\\..\\FlyByWire_A380_842\\texture
fallback.3=..\\..\\..\\..\\texture
"""

# Without a Common Textures folder the package must not claim to fall back to
# one - that would be a genuinely broken source package, not a neutral fixture.
OLD_TEXTURE_CFG_NO_COMMON = """[fltsim]
fallback.1=..\\..\\FlyByWire_A380_842\\texture
fallback.2=..\\..\\..\\..\\texture
"""


def make_old_package(root, suffixes=("A7APC", "A7APD"), dds_bytes=b"",
                     with_common=True, with_model=True, name="Old Test Livery",
                     depot_suffixes=(), texture_cfg=None):
    """Build an MSFS 2020 style package.

    depot_suffixes get isUserSelectable = 0, i.e. they are shared texture
    depots that other liveries fall back to rather than selectable liveries.
    """
    pkg = Path(root) / name
    airplanes = pkg / "SimObjects" / "AirPlanes"
    for suffix in tuple(suffixes) + tuple(depot_suffixes):
        variant = airplanes / f"A388_TST_{suffix}"
        tex = variant / f"TEXTURE.{suffix}"
        tex.mkdir(parents=True)
        model_value = "TST" if with_model else ""
        (variant / "aircraft.cfg").write_text(AIRCRAFT_CFG_TEMPLATE.format(
            suffix=suffix, model=model_value,
            selectable=0 if suffix in depot_suffixes else 1))
        if with_model:
            (variant / "MODEL.TST").mkdir()
            (variant / "MODEL.TST" / "A380.xml").write_text("<Model/>")
        default_cfg = OLD_TEXTURE_CFG if with_common else OLD_TEXTURE_CFG_NO_COMMON
        (tex / "texture.CFG").write_text(
            default_cfg if texture_cfg is None else texture_cfg)
        (tex / "A380X_FUSE1_ALBEDO.PNG.DDS").write_bytes(dds_bytes)
        (tex / "A380X_FUSE1_ALBEDO.PNG.DDS.json").write_text(
            '{"Version":2,"SourceFileDate":1,"Flags":["FL_BITMAP_COMPRESSION","FL_BITMAP_MIPMAP"]}')
        (tex / "CUSTOM_DECAL.PNG.DDS").write_bytes(dds_bytes)
        Image.new("RGB", (412, 170), "blue").save(tex / "thumbnail.JPG")
    if with_common:
        common = airplanes / "Common Textures"
        common.mkdir(parents=True)
        (common / "A380X_FUSE2_ALBEDO.PNG.DDS").write_bytes(dds_bytes)
    (pkg / "manifest.json").write_text(json.dumps(OLD_MANIFEST))
    (pkg / "layout.json").write_text('{"content": []}')
    return pkg


def _bc3_block(r=200, g=30, b=30, alpha=255):
    c565 = ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)
    return struct.pack("<BB6x", alpha, alpha) + struct.pack("<HH4x", c565, c565)


def make_bc3_dds(width, height, alpha=255):
    blocks_x = max(1, (width + 3) // 4)
    blocks_y = max(1, (height + 3) // 4)
    payload = _bc3_block(alpha=alpha) * (blocks_x * blocks_y)
    ddsd_flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000  # CAPS|HEIGHT|WIDTH|PIXELFORMAT|LINEARSIZE
    header = struct.pack("<7I44x", 124, ddsd_flags, height, width, len(payload), 0, 1)
    pixelformat = struct.pack("<II4s20x", 32, 0x4, b"DXT5")  # DDPF_FOURCC
    caps = struct.pack("<I16x", 0x1000)  # DDSCAPS_TEXTURE
    return b"DDS " + header + pixelformat + caps + payload


def make_uncompressed_dds(width, height, alpha=255, r=200, g=30, b=30):
    """A valid uncompressed B8G8R8A8 DDS (fourCC = 0).

    read_dds rejects this (it only parses BC1/BC3/BC7), but texconv reads it
    fine - it mirrors the real-world liveries that ship uncompressed textures.
    """
    payload = bytes([b, g, r, alpha]) * (width * height)
    ddsd_flags = 0x1 | 0x2 | 0x4 | 0x1000 | 0x8  # CAPS|HEIGHT|WIDTH|PIXELFORMAT|PITCH
    header = struct.pack("<7I44x", 124, ddsd_flags, height, width, width * 4, 0, 1)
    pixelformat = struct.pack("<8I", 32, 0x41, 0, 32,  # DDPF_RGB|DDPF_ALPHAPIXELS
                              0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000)  # BGRA masks
    caps = struct.pack("<I16x", 0x1000)  # DDSCAPS_TEXTURE
    return b"DDS " + header + pixelformat + caps + payload
