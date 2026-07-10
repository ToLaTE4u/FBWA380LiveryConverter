from pathlib import Path

import pytest

from a380x_livery_converter.texture.dds import DdsError, read_dds
from tests.helpers import make_bc3_dds

QATAR_DDS = Path("data/oldLivery/HUES - QatarAirways Fleet  A380 FBW/SimObjects/"
                 "AirPlanes/A388_QTR_A7-APC/TEXTURE.A7APC/A380X_FUSE1_ALBEDO.PNG.DDS")


def test_read_synthetic_bc3(tmp_path):
    p = tmp_path / "t.dds"
    p.write_bytes(make_bc3_dds(8, 8))
    dds = read_dds(p)
    assert (dds.width, dds.height, dds.format) == (8, 8, "BC3")
    assert len(dds.mip_levels) == 1
    assert len(dds.mip_levels[0].data) == 4 * 16  # 2x2 blocks * 16 bytes


def test_rejects_non_dds(tmp_path):
    p = tmp_path / "x.dds"
    p.write_bytes(b"not a dds file at all, definitely not")
    with pytest.raises(DdsError):
        read_dds(p)


def test_rejects_truncated_payload(tmp_path):
    p = tmp_path / "t.dds"
    p.write_bytes(make_bc3_dds(16, 16)[:-8])
    with pytest.raises(DdsError):
        read_dds(p)


@pytest.mark.skipif(not QATAR_DDS.exists(), reason="real sample data not present")
def test_read_real_bc3_texture():
    dds = read_dds(QATAR_DDS)
    assert (dds.width, dds.height, dds.format) == (4096, 4096, "BC3")
    assert len(dds.mip_levels) >= 1
    assert len(dds.mip_levels[0].data) == 1024 * 1024 * 16
