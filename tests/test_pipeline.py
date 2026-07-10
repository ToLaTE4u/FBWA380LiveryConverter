import struct

import texture2ddecoder

from a380x_livery_converter.texture.dds import read_dds
from a380x_livery_converter.texture.pipeline import convert_texture, has_transparency
from tests.helpers import make_bc3_dds


def _largest_level(ktx2_bytes):
    levels = struct.unpack_from("<I", ktx2_bytes, 40)[0]
    off, length, _ = struct.unpack_from("<3Q", ktx2_bytes, 80)
    w, h = struct.unpack_from("<2I", ktx2_bytes, 20)
    assert levels >= 1
    return ktx2_bytes[off:off + length], w, h


def test_convert_opaque_texture(tmp_path):
    src = tmp_path / "A380X_TEST.PNG.DDS"
    src.write_bytes(make_bc3_dds(8, 8))
    dest = tmp_path / "out" / "A380X_TEST.PNG.KTX2"
    convert_texture(src, dest, tmp_path / "work")
    blob = dest.read_bytes()
    assert blob[:4] == b"\xabKTX"
    assert struct.unpack_from("<I", blob, 12)[0] == 145
    assert b"ASOBO_transp\x00\x00" in blob
    assert (dest.parent / "A380X_TEST.PNG.KTX2.json").is_file()


def test_convert_transparent_texture_sets_transp_flag(tmp_path):
    src = tmp_path / "T.PNG.DDS"
    src.write_bytes(make_bc3_dds(8, 8, alpha=40))
    dest = tmp_path / "out" / "T.PNG.KTX2"
    convert_texture(src, dest, tmp_path / "work")
    assert b"ASOBO_transp\x00\x01" in dest.read_bytes()


def test_roundtrip_color_survives(tmp_path):
    src = tmp_path / "C.PNG.DDS"
    src.write_bytes(make_bc3_dds(16, 16))
    dest = tmp_path / "out" / "C.PNG.KTX2"
    convert_texture(src, dest, tmp_path / "work")
    data, w, h = _largest_level(dest.read_bytes())
    decoded = texture2ddecoder.decode_bc7(data, w, h)  # BGRA
    pixels = [(decoded[i + 2], decoded[i + 1], decoded[i]) for i in range(0, len(decoded), 4)]
    avg = [sum(c) / len(c) for c in zip(*pixels)]
    assert abs(avg[0] - 200) < 25 and abs(avg[1] - 30) < 25 and abs(avg[2] - 30) < 25


def test_has_transparency(tmp_path):
    opaque = tmp_path / "o.dds"
    opaque.write_bytes(make_bc3_dds(8, 8, alpha=255))
    transparent = tmp_path / "t.dds"
    transparent.write_bytes(make_bc3_dds(8, 8, alpha=0))
    assert has_transparency(read_dds(opaque)) is False
    assert has_transparency(read_dds(transparent)) is True
