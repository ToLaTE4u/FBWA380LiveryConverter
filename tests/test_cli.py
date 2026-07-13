from typer.testing import CliRunner

from a380x_livery_converter.cli import app
from tests.helpers import make_bc3_dds, make_old_package

runner = CliRunner()


def _single(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    (pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "TEXTURE.X"
     / "CUSTOM_DECAL.PNG.DDS").unlink()
    return pkg


def test_convert_with_yes_exits_0(tmp_path):
    pkg = _single(tmp_path)
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--yes"])
    assert result.exit_code == 0, result.output
    assert "Converted textures: 1" in result.output


def test_prompt_cancel_writes_nothing(tmp_path):
    pkg = _single(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(app, [str(pkg), "-o", str(out)], input="n\n")
    assert result.exit_code == 0
    assert "Cancelled." in result.output
    assert not out.exists()


def test_prompt_yes_converts(tmp_path):
    pkg = _single(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(app, [str(pkg), "-o", str(out)], input="y\n")
    assert result.exit_code == 0, result.output
    assert out.exists()


def test_dry_run_shows_plan_no_write(tmp_path):
    pkg = _single(tmp_path)
    out = tmp_path / "out"
    result = runner.invoke(app, [str(pkg), "-o", str(out), "--dry-run"])
    assert result.exit_code == 0
    assert "Found 1 package" in result.output
    assert not out.exists()


def test_invalid_input_exits_2(tmp_path):
    (tmp_path / "empty").mkdir()
    result = runner.invoke(app, [str(tmp_path / "empty"), "-o", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_batch_folder_converts_all(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgA")
    make_old_package(parent, suffixes=("A7APD",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgB")
    result = runner.invoke(app, [str(parent), "-o", str(tmp_path / "out"), "--yes"])
    assert result.exit_code in (0, 1), result.output
    assert "2 package(s)" in result.output
