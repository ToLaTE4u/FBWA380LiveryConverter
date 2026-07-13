from pathlib import Path

from typer.testing import CliRunner

from a380x_livery_converter.cli import app
from a380x_livery_converter.converter import BatchResult, ConversionResult
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


def test_unexpected_execution_error_exits_2(tmp_path, monkeypatch):
    """Fix 2: an unexpected error during execution must exit 2 with a short
    message instead of surfacing a raw traceback with exit code 1."""
    pkg = _single(tmp_path)

    def boom(plan, progress=None):
        raise PermissionError("boom")

    monkeypatch.setattr("a380x_livery_converter.cli.execute_plan", boom)
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--yes"])
    assert result.exit_code == 2, result.output
    assert "boom" in result.output


def test_all_packages_failing_at_runtime_exits_2(tmp_path, monkeypatch):
    """A batch where every package fails DURING conversion (not planning) must
    be reported as a failure: exit 2, "No packages were converted", and the
    failure reason - not a silent "Converted textures: 0, skipped: 0" success."""
    pkg = _single(tmp_path)

    def fake_execute_plan(plan, progress=None):
        return BatchResult(results=[], skipped=[(Path("pkgX"), "conversion failed: boom")])

    monkeypatch.setattr("a380x_livery_converter.cli.execute_plan", fake_execute_plan)
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--yes"])
    assert result.exit_code == 2, result.output
    assert "No packages were converted" in result.output
    assert "boom" in result.output


def test_partial_runtime_failure_exits_1_and_reports_skipped(tmp_path, monkeypatch):
    """When some packages convert but one fails at runtime, the CLI must exit 1
    (not 0) and print the failed package, not just the plan-time skips."""
    pkg = _single(tmp_path)
    ok_result = ConversionResult(output_root=tmp_path / "out" / "pkgY_ok",
                                 converted=1, skipped=0, warnings=[])

    def fake_execute_plan(plan, progress=None):
        return BatchResult(results=[ok_result],
                           skipped=[(Path("pkgY"), "conversion failed: boom")])

    monkeypatch.setattr("a380x_livery_converter.cli.execute_plan", fake_execute_plan)
    result = runner.invoke(app, [str(pkg), "-o", str(tmp_path / "out"), "--yes"])
    assert result.exit_code == 1, result.output
    assert "pkgY" in result.output
    assert "boom" in result.output


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
