import pytest
from PIL import Image

from a380x_livery_converter.texture.dds import read_dds
from a380x_livery_converter.texture.texconv import TexconvError, dds_to_bc7_dds
from tests.helpers import make_bc3_dds


def test_png_to_bc7_with_full_mip_chain(tmp_path):
    src = tmp_path / "test.png"
    Image.new("RGBA", (16, 16), (200, 30, 30, 255)).save(src)
    out = dds_to_bc7_dds(src, tmp_path / "out")
    dds = read_dds(out)
    assert dds.format == "BC7"
    assert (dds.width, dds.height) == (16, 16)
    assert len(dds.mip_levels) == 5  # 16,8,4,2,1


def test_bc3_dds_to_bc7(tmp_path):
    src = tmp_path / "A380X_TEST.PNG.DDS"
    src.write_bytes(make_bc3_dds(8, 8))
    out = dds_to_bc7_dds(src, tmp_path / "out")
    dds = read_dds(out)
    assert dds.format == "BC7"
    assert len(dds.mip_levels) == 4  # 8,4,2,1


def test_invalid_input_raises(tmp_path):
    src = tmp_path / "broken.dds"
    src.write_bytes(b"garbage")
    with pytest.raises(TexconvError):
        dds_to_bc7_dds(src, tmp_path / "out")


def test_subprocess_uses_devnull_stdin(monkeypatch, tmp_path):
    """A windowed (no-console) exe has no valid stdin handle; texconv must be
    launched with stdin=DEVNULL or it fails with WinError 6 in the GUI."""
    import subprocess

    from a380x_livery_converter.texture import texconv as texconv_mod
    captured = {}
    real_run = subprocess.run

    def fake_run(cmd, **kwargs):
        captured.update(kwargs)
        return real_run(cmd, **kwargs)

    monkeypatch.setattr(texconv_mod.subprocess, "run", fake_run)
    src = tmp_path / "T.PNG.DDS"
    src.write_bytes(make_bc3_dds(8, 8))
    dds_to_bc7_dds(src, tmp_path / "out")
    assert captured.get("stdin") is subprocess.DEVNULL
