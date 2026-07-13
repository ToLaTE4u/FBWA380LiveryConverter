from pathlib import Path

import pytest

from a380x_livery_converter.core.scanner import (
    NotAnA380XPackageError,
    find_packages,
    scan_package,
)
from tests.helpers import make_old_package

QATAR = Path("data/oldLivery/HUES - QatarAirways Fleet  A380 FBW")


def test_scan_synthetic_package(tmp_path):
    pkg = make_old_package(tmp_path)
    result = scan_package(pkg)
    assert result.title == "Test Fleet Pack"
    assert result.creator == "TestCreator"
    assert len(result.variants) == 2
    v = result.variants[0]
    assert v.texture_suffix == "A7APC"
    assert v.texture_dir is not None and v.texture_dir.name == "TEXTURE.A7APC"
    assert v.atc_airline == "Test Airways"
    assert v.icao_airline == "TST"
    assert v.has_custom_model is True
    assert result.common_texture_dir is not None


def test_scan_without_common_and_model(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), with_common=False, with_model=False)
    result = scan_package(pkg)
    assert result.common_texture_dir is None
    assert result.variants[0].has_custom_model is False


def test_scan_rejects_non_a380_package(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",))
    cfg = pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "aircraft.cfg"
    cfg.write_text(cfg.read_text().replace("FlyByWire_A380_842", "Asobo_B747"))
    with pytest.raises(NotAnA380XPackageError):
        scan_package(pkg)


def test_scan_rejects_folder_without_simobjects(tmp_path):
    with pytest.raises(NotAnA380XPackageError):
        scan_package(tmp_path)


def test_foreign_variant_skipped_not_rejected(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("A7APC", "FOREIGN"))
    cfg = pkg / "SimObjects" / "AirPlanes" / "A388_TST_FOREIGN" / "aircraft.cfg"
    cfg.write_text(cfg.read_text().replace("FlyByWire_A380_842", "FlyByWire_A32NX"))
    result = scan_package(pkg)
    assert {v.texture_suffix for v in result.variants} == {"A7APC"}
    assert any("A32NX" in label for label in result.skipped_foreign)


def test_rejection_message_names_detected_aircraft(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",))
    cfg = pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "aircraft.cfg"
    cfg.write_text(cfg.read_text().replace("FlyByWire_A380_842", "FlyByWire_A32NX"))
    with pytest.raises(NotAnA380XPackageError, match="A32NX"):
        scan_package(pkg)


@pytest.mark.skipif(not QATAR.exists(), reason="real sample data not present")
def test_scan_real_qatar_pack():
    result = scan_package(QATAR)
    assert len(result.variants) == 8
    assert all(v.has_custom_model for v in result.variants)
    assert result.common_texture_dir is not None
    suffixes = {v.texture_suffix for v in result.variants}
    assert "A7APC" in suffixes


def test_find_packages_single(tmp_path):
    pkg = make_old_package(tmp_path)
    roots, skipped = find_packages(pkg)
    assert roots == [pkg]
    assert skipped == []


def test_find_packages_parent_of_multiple(tmp_path):
    parent = tmp_path / "batch"
    parent.mkdir()
    a = make_old_package(parent, suffixes=("A7APC",), name="pkgA")
    b = make_old_package(parent, suffixes=("A7APD",), name="pkgB")
    junk = parent / "notapackage"
    junk.mkdir()
    (junk / "readme.txt").write_text("hi")
    roots, skipped = find_packages(parent)
    assert set(roots) == {a, b}
    assert any("notapackage" in str(p) for p, _ in skipped)


def test_find_packages_none(tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    roots, skipped = find_packages(empty)
    assert roots == []
    assert skipped == [(empty, "no livery package found")]
