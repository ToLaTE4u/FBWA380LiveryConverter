import struct
from pathlib import Path

import pytest

from a380x_livery_converter.texture.dds import DdsFile, MipLevel
from a380x_livery_converter.texture.ktx2 import (
    DFD_BC7,
    build_kvd,
    filetime_from_unix,
    write_flags_json,
    write_ktx2,
)

REF_TEX_DIR = Path("data/NewLivery/steffieth-livery-fbw_a380-lufthansa_100Y_2024/SimObjects/"
                   "AirPlanes/FlyByWire_A380X/liveries/flybywire/FlyByWire_A380_842_DLH_100Y/texture")

# 1:1 aus der Referenz-Livery extrahiert (opake Textur, ASOBO_transp = 0x00)
REFERENCE_KVD_OPAQUE = (
    b"Q\x00\x00\x00ASOBO_flags\x00BILINEAR\x00COMPRESSION\x00MIPMAP\x00REDUCE_LESS\x00"
    b"PLATFORM_FORMAT\x00QUALITY_HIGH\x00\x00\x00\x00"
    b"\x10\x00\x00\x00ASOBO_opacities\x00"
    b"\x0e\x00\x00\x00ASOBO_transp\x00\x00\x00\x00"
    b"\x14\x00\x00\x00ASOBOtexversion\x00\x01\x00\x00\x00"
    b"\x1a\x00\x00\x00KTXwriter\x00ASOBO_FlightSim\x00\x00\x00"
)


def _fake_bc7(width, height):
    levels = []
    w, h = width, height
    while True:
        n_blocks = max(1, (w + 3) // 4) * max(1, (h + 3) // 4)
        levels.append(MipLevel(w, h, b"\xAB" * (n_blocks * 16)))
        if w == 1 and h == 1:
            break
        w, h = max(1, w // 2), max(1, h // 2)
    return DdsFile(width=width, height=height, format="BC7", mip_levels=levels)


def test_kvd_matches_reference_bytes():
    assert build_kvd(False) == REFERENCE_KVD_OPAQUE
    assert len(build_kvd(True)) == 184
    assert b"ASOBO_transp\x00\x01" in build_kvd(True)


def test_write_ktx2_header_and_levels(tmp_path):
    out = tmp_path / "t.PNG.KTX2"
    write_ktx2(out, _fake_bc7(16, 16), transparent=False)
    data = out.read_bytes()
    assert data[:12] == bytes.fromhex("ab4b5458203230bb0d0a1a0a")
    vk, ts, w, h, depth, layers, faces, levels = struct.unpack_from("<8I", data, 12)
    assert (vk, ts, w, h, depth, layers, faces, levels) == (145, 1, 16, 16, 0, 0, 1, 5)
    sc, dfd_off, dfd_len, kvd_off, kvd_len = struct.unpack_from("<5I", data, 44)
    assert sc == 0
    assert data[dfd_off:dfd_off + dfd_len] == DFD_BC7
    assert kvd_len == 184
    # Level-Index: Eintrag 0 = größte Ebene, Daten im File kleinste zuerst, 16er-Alignment
    offsets = []
    for i in range(levels):
        off, length, unc = struct.unpack_from("<3Q", data, 80 + i * 24)
        assert length == unc
        assert off % 16 == 0
        offsets.append((off, length))
    assert offsets[0][1] == 16 * 16  # 16x16 -> 16 Blöcke à 16 Byte
    assert offsets[-1][0] < offsets[0][0]  # kleinste Ebene liegt vorne im File
    assert offsets[0][0] + offsets[0][1] == len(data)


def test_write_ktx2_rejects_non_bc7(tmp_path):
    dds = DdsFile(width=4, height=4, format="BC3", mip_levels=[MipLevel(4, 4, b"\0" * 16)])
    with pytest.raises(ValueError):
        write_ktx2(tmp_path / "x.KTX2", dds, transparent=False)


def test_flags_json_sidecar(tmp_path):
    ktx2 = tmp_path / "A.PNG.KTX2"
    ktx2.write_bytes(b"x")
    sidecar = write_flags_json(ktx2, 134271355895062044)
    assert sidecar.name == "A.PNG.KTX2.json"
    text = sidecar.read_text()
    assert '"SourceFileDate":134271355895062044' in text.replace(" ", "")
    assert "FL_BITMAP_QUALITY_HIGH" in text


def test_filetime_epoch():
    assert filetime_from_unix(0) == 116444736000000000


@pytest.mark.skipif(not REF_TEX_DIR.exists(), reason="real sample data not present")
def test_kvd_and_dfd_match_real_reference_files():
    opaque = (REF_TEX_DIR / "A380X_EXT_ENG_LH_ALBD.PNG.KTX2").read_bytes()
    transparent = (REF_TEX_DIR / "A380X_AFT_STAIRS_ALBD.PNG.KTX2").read_bytes()
    for blob, expected_kvd in ((opaque, build_kvd(False)), (transparent, build_kvd(True))):
        dfd_off, dfd_len, kvd_off, kvd_len = struct.unpack_from("<4I", blob, 48)
        assert blob[dfd_off:dfd_off + dfd_len] == DFD_BC7
        assert blob[kvd_off:kvd_off + kvd_len] == expected_kvd
