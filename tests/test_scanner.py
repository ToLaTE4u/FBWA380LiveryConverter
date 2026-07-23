from pathlib import Path

import pytest

from a380x_livery_converter.core.scanner import (
    NotAnA380XPackageError,
    container_names,
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


def test_depot_variant_is_not_offered_as_a_livery(tmp_path):
    """isUserSelectable = 0 marks a shared texture depot, not a livery - it must
    not show up in the MSFS livery picker."""
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), depot_suffixes=("CMN",))
    result = scan_package(pkg)
    assert [v.texture_suffix for v in result.variants] == ["A7APC"]
    assert [d.texture_suffix for d in result.depots] == ["CMN"]


def test_depot_only_package_is_scanned_instead_of_rejected(tmp_path):
    """The Emirates fleet ships its shared textures as a package of their own.
    Rejecting it would strip exactly the textures every sibling falls back to."""
    pkg = make_old_package(tmp_path, suffixes=(), depot_suffixes=("EKNA6CMN", "EKOA6CMN"))
    result = scan_package(pkg)
    assert result.variants == []
    assert [d.texture_suffix for d in result.depots] == ["EKNA6CMN", "EKOA6CMN"]


def test_package_without_variants_or_depots_is_still_rejected(tmp_path):
    pkg = tmp_path / "junk"
    (pkg / "SimObjects" / "AirPlanes" / "SomeFolder").mkdir(parents=True)
    with pytest.raises(NotAnA380XPackageError):
        scan_package(pkg)


def test_fallback_into_another_package_is_recorded(tmp_path):
    """The Emirates fleet keeps its shared textures in a separate package; those
    fallbacks cannot resolve inside this package and must be reported."""
    cfg = ("[fltsim]\n"
           "fallback.1=..\\..\\FBW A380 EKNA6CMN\\texture.EKNA6CMN\n"
           "fallback.2=..\\..\\FlyByWire_A380_842\\texture\n"
           "fallback.3=..\\..\\..\\..\\texture\\Glass\n")
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), with_common=False,
                           texture_cfg=cfg)
    result = scan_package(pkg)
    assert result.variants[0].missing_fallbacks == [
        "..\\..\\FBW A380 EKNA6CMN\\texture.EKNA6CMN"]


def test_fallback_into_a_container_present_elsewhere_in_the_batch_is_not_reported(tmp_path):
    """MSFS merges every Community package into one virtual file system, so a
    fallback into a sibling *package* resolves at runtime and is not missing."""
    cfg = ("[fltsim]\n"
           "fallback.1=..\\..\\FBW A380 EKNA6CMN\\texture.EKNA6CMN\n")
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), with_common=False,
                           texture_cfg=cfg)
    result = scan_package(pkg, known_containers={"FBW A380 EKNA6CMN"})
    assert result.variants[0].missing_fallbacks == []


def test_container_names_indexes_every_package_in_the_batch(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), name="tail")
    make_old_package(parent, suffixes=(), depot_suffixes=("CMN",), name="commons")
    names = container_names([parent / "tail", parent / "commons"])
    assert {"A388_TST_A7APC", "A388_TST_CMN"} <= names


def test_fallback_inside_the_own_container_is_not_reported(tmp_path):
    """`fallback=..\\texture` is boilerplate pointing back into the variant's own
    container - absent by design and not a cross-package reference."""
    cfg = "[fltsim]\nfallback.1=..\\texture\n"
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), with_common=False,
                           texture_cfg=cfg)
    assert scan_package(pkg).variants[0].missing_fallbacks == []


def test_resolvable_and_sim_level_fallbacks_are_not_reported(tmp_path):
    """Common Textures exists in the package, FlyByWire_A380_842 ships with the
    A380X itself and ..\\..\\..\\..\\texture is sim level - none are a problem."""
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), with_common=True)
    result = scan_package(pkg)
    assert result.variants[0].missing_fallbacks == []


def test_rejection_message_for_already_converted_package(tmp_path):
    """A package that is already in MSFS 2024 format must say so rather than
    claiming no A380X livery was detected."""
    pkg = tmp_path / "FlyByWire_A380X-British_Airways_G-XLEF-2024"
    livery = (pkg / "SimObjects" / "Airplanes" / "FlyByWire_A380X" / "liveries"
              / "flybywire" / "FlyByWire_A380_842_BAW")
    (livery / "texture").mkdir(parents=True)
    (livery / "livery.cfg").write_text("[GENERAL]\nName = \"BA\"\n")
    with pytest.raises(NotAnA380XPackageError, match="already in MSFS 2024"):
        scan_package(pkg)


def test_rejection_message_for_package_without_any_aircraft_cfg(tmp_path):
    pkg = tmp_path / "junk"
    (pkg / "SimObjects" / "AirPlanes" / "SomeFolder").mkdir(parents=True)
    with pytest.raises(NotAnA380XPackageError, match="no aircraft.cfg"):
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
