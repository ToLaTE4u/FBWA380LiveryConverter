import json
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
"""

OLD_TEXTURE_CFG = """[fltsim]
fallback.1=..\\..\\Common Textures
fallback.2=..\\..\\FlyByWire_A380_842\\texture
fallback.3=..\\..\\..\\..\\texture
"""


def make_old_package(root, suffixes=("A7APC", "A7APD"), dds_bytes=b"",
                     with_common=True, with_model=True):
    pkg = Path(root) / "Old Test Livery"
    airplanes = pkg / "SimObjects" / "AirPlanes"
    for suffix in suffixes:
        variant = airplanes / f"A388_TST_{suffix}"
        tex = variant / f"TEXTURE.{suffix}"
        tex.mkdir(parents=True)
        model_value = "TST" if with_model else ""
        (variant / "aircraft.cfg").write_text(
            AIRCRAFT_CFG_TEMPLATE.format(suffix=suffix, model=model_value))
        if with_model:
            (variant / "MODEL.TST").mkdir()
            (variant / "MODEL.TST" / "A380.xml").write_text("<Model/>")
        (tex / "texture.CFG").write_text(OLD_TEXTURE_CFG)
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
