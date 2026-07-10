from typer.testing import CliRunner

from a380x_livery_converter.cli import app
from tests.helpers import make_bc3_dds, make_old_package

runner = CliRunner()


def test_convert_success_without_warnings_exits_0(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    (pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "TEXTURE.X" / "CUSTOM_DECAL.PNG.DDS").unlink()
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out")])
    assert result.exit_code == 0, result.output
    assert "Converted textures: 1" in result.output


def test_convert_with_warnings_exits_1(tmp_path):
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out")])
    assert result.exit_code == 1
    assert "WARNING" in result.output


def test_invalid_package_exits_2(tmp_path):
    (tmp_path / "empty").mkdir()
    result = runner.invoke(app, [str(tmp_path / "empty"), "-o", str(tmp_path / "out")])
    assert result.exit_code == 2


def test_dry_run_writes_nothing(tmp_path):
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--dry-run"])
    assert result.exit_code == 1  # dry-run-Hinweis ist eine Warnung
    assert not (tmp_path / "out").exists()


def test_verbose_shows_progress(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--verbose"])
    assert "[1/" in result.output
