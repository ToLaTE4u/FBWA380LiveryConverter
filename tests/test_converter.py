import json
import shutil
import threading
from pathlib import Path

import pytest

from a380x_livery_converter.converter import ConversionCancelled, Converter, PackagePlan
from tests.helpers import make_bc3_dds, make_old_package

LIVERIES = "SimObjects/AirPlanes/FlyByWire_A380X/liveries"


def test_plan_lists_liveries_and_writes_nothing(tmp_path):
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    out = tmp_path / "out"
    plan = Converter(pkg, out).plan()
    assert isinstance(plan, PackagePlan)
    assert len(plan.livery_names) == 2
    assert plan.texture_count >= 1
    assert not out.exists()


def _convert(tmp_path, **kwargs):
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    out = tmp_path / "out"
    progress_calls = []
    conv = Converter(pkg, out, progress=lambda d, t, m: progress_calls.append((d, t)), **kwargs)
    return conv.run(), out, progress_calls


def test_full_conversion_structure(tmp_path):
    result, out, progress_calls = _convert(tmp_path)
    root = result.output_root
    assert root.parent == out
    for suffix in ("A7APC", "A7APD"):
        livery = root / LIVERIES / "flybywire" / f"FlyByWire_A380_842_{suffix}"
        assert (livery / "livery.cfg").is_file()
        assert (livery / "texture" / "texture.CFG").is_file()
        assert (livery / "thumbnail" / "thumbnail.png").is_file()
    # identische Dateien beider Varianten + Common Textures liegen dedupliziert in common
    common = root / LIVERIES / "common" / "texture"
    assert (common / "A380X_FUSE1_ALBD.PNG.KTX2").is_file()      # dedupliziert
    assert (common / "A380X_FUSE2_ALBD.PNG.KTX2").is_file()      # aus Common Textures
    assert (common / "CUSTOM_DECAL.PNG.KTX2").is_file()          # unbekannt, dedupliziert
    assert (common / "A380X_FUSE1_ALBD.PNG.KTX2.json").is_file()
    assert result.converted == 3
    assert result.skipped == 0
    assert (root / "manifest.json").is_file()
    assert (root / "layout.json").is_file()
    report_path = root / "conversion_report.txt"
    assert report_path.is_file()
    assert "->" in report_path.read_text()
    assert progress_calls, "progress callback was never invoked"


def test_warnings_for_model_and_unmapped(tmp_path):
    result, _, _ = _convert(tmp_path)
    joined = "\n".join(result.warnings)
    assert "MODEL" in joined
    assert "CUSTOM_DECAL" in joined


def test_layout_covers_generated_files(tmp_path):
    result, _, _ = _convert(tmp_path)
    layout = json.loads((result.output_root / "layout.json").read_text())
    paths = {e["path"] for e in layout["content"]}
    assert any(p.endswith("livery.cfg") for p in paths)
    assert any(p.endswith(".KTX2") for p in paths)
    assert not any(p.endswith("conversion_report.txt") for p in paths)


def test_corrupt_dds_is_skipped_with_warning(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False)
    bad = pkg / "SimObjects" / "AirPlanes" / "A388_TST_X" / "TEXTURE.X" / "BROKEN.PNG.DDS"
    bad.write_bytes(b"garbage")
    result = Converter(pkg, tmp_path / "out").run()
    assert result.skipped == 1
    assert any("BROKEN" in w for w in result.warnings)


def test_destination_collision_relocates_differing_content(tmp_path):
    """Finding 1: a Common Textures file whose mapped name collides with a
    multi-variant dedup group of different content must not silently drop
    either file - the loser is relocated to per-variant folders."""
    pkg = make_old_package(tmp_path, dds_bytes=make_bc3_dds(8, 8))
    common = pkg / "SimObjects" / "AirPlanes" / "Common Textures"
    # Same original filename as the variants' shared texture, but different
    # content -> maps to the same new name (A380X_FUSE1_ALBD.PNG.KTX2) as the
    # common-dedup job built from both variants' identical FUSE1 texture.
    (common / "A380X_FUSE1_ALBEDO.PNG.DDS").write_bytes(make_bc3_dds(16, 16))

    out = tmp_path / "out"
    result = Converter(pkg, out).run()
    root = result.output_root

    common_texture = root / LIVERIES / "common" / "texture"
    assert (common_texture / "A380X_FUSE1_ALBD.PNG.KTX2").is_file()

    for suffix in ("A7APC", "A7APD"):
        relocated = (root / LIVERIES / "flybywire" / f"FlyByWire_A380_842_{suffix}"
                    / "texture" / "A380X_FUSE1_ALBD.PNG.KTX2")
        assert relocated.is_file(), f"expected relocated texture for {suffix}"

    assert any("A380X_FUSE1_ALBD" in w and "collision" in w.lower()
               for w in result.warnings), result.warnings


def test_livery_folder_collision_gets_disambiguated(tmp_path):
    """Finding 2: two FLTSIM sections sharing the same texture suffix (hence
    the same livery_folder_name) must not overwrite each other's livery.cfg."""
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8))
    variant_dir = pkg / "SimObjects" / "AirPlanes" / "A388_TST_X"
    cfg_text = """[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "..\\FlyByWire_A380_842"

[FLTSIM.0]
title = "TEST X A380 First"
ui_variation = "TEST X A380 First"
texture = "X"
model = "TST"
atc_id = "FIRST01"
atc_airline = "Test Airways"
icao_airline = "TST"

[FLTSIM.1]
title = "TEST X A380 Second"
ui_variation = "TEST X A380 Second"
texture = "X"
model = "TST"
atc_id = "SECOND02"
atc_airline = "Test Airways Two"
icao_airline = "TS2"
"""
    (variant_dir / "aircraft.cfg").write_text(cfg_text)

    out = tmp_path / "out"
    result = Converter(pkg, out).run()
    root = result.output_root

    flybywire = root / LIVERIES / "flybywire"
    folders = {p.name: p for p in flybywire.iterdir() if p.is_dir()}
    assert folders.keys() == {"FlyByWire_A380_842_X", "FlyByWire_A380_842_X_1"}

    cfg_texts = []
    for folder in folders.values():
        livery_cfg = folder / "livery.cfg"
        assert livery_cfg.is_file()
        cfg_texts.append(livery_cfg.read_text())
    assert cfg_texts[0] != cfg_texts[1]


def test_unexpected_texture_error_is_caught_and_warned(tmp_path, monkeypatch):
    """Regression test: converter should catch Exception (not just specific types) in texture jobs."""
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False)

    # Monkeypatch convert_texture to raise RuntimeError
    def failing_convert_texture(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("a380x_livery_converter.converter.convert_texture",
                        failing_convert_texture)

    result = Converter(pkg, tmp_path / "out").run()
    assert result.skipped >= 1
    assert any("boom" in w for w in result.warnings)


from a380x_livery_converter.converter import plan_conversion, execute_plan

BATCH_LIVERIES = "SimObjects/AirPlanes/FlyByWire_A380X/liveries"


def test_plan_marks_existing_output_package(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False, name="src")
    out = tmp_path / "out"
    plan1 = plan_conversion(pkg, out)
    assert plan1.packages[0].exists is False
    (out / plan1.packages[0].output_name).mkdir(parents=True)
    plan2 = plan_conversion(pkg, out)
    assert plan2.packages[0].exists is True


def test_plan_conversion_batch_folder(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgA")
    make_old_package(parent, suffixes=("A7APD",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgB")
    plan = plan_conversion(parent, tmp_path / "out")
    assert plan.package_count == 2
    assert plan.livery_count == 2
    assert not (tmp_path / "out").exists()


def test_plan_conversion_marks_foreign_package_skipped(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="good")
    bad = make_old_package(parent, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False, name="bad")
    cfg = bad / "SimObjects" / "AirPlanes" / "A388_TST_X" / "aircraft.cfg"
    cfg.write_text(cfg.read_text().replace("FlyByWire_A380_842", "FlyByWire_A32NX"))
    plan = plan_conversion(parent, tmp_path / "out")
    assert plan.package_count == 1
    assert any("bad" in str(p) for p, _ in plan.skipped)


def test_single_package_writes_no_batch_report(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("X",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    out = tmp_path / "out"
    result = execute_plan(plan_conversion(pkg, out))
    assert len(result.results) == 1
    assert not (out / "batch_report.txt").exists()


def test_plan_conversion_skips_package_that_fails_to_plan(tmp_path):
    """Fix 1: an unexpected error while planning one package (here: an
    unreadable aircraft.cfg) must not abort planning the whole batch."""
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="good")
    bad = parent / "bad"
    variant = bad / "SimObjects" / "AirPlanes" / "A388_BAD"
    variant.mkdir(parents=True)
    # a directory named aircraft.cfg makes read_text() raise (not a
    # NotAnA380XPackageError), which previously aborted the whole plan
    (variant / "aircraft.cfg").mkdir()
    plan = plan_conversion(parent, tmp_path / "out")
    assert plan.package_count == 1
    assert any("bad" in str(p) for p, _ in plan.skipped)


def test_execute_plan_continues_after_package_failure(tmp_path):
    """Fix 1: a package that fails during execution must not abort the batch
    or discard the results of the packages already converted."""
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgA")
    pkg_b = make_old_package(parent, suffixes=("A7APD",), dds_bytes=make_bc3_dds(8, 8),
                             with_common=False, with_model=False, name="pkgB")
    out = tmp_path / "out"
    plan = plan_conversion(parent, out)
    shutil.rmtree(pkg_b / "SimObjects")  # pkgB breaks between plan and execute
    result = execute_plan(plan)
    assert len(result.results) == 1
    assert any("pkgB" in str(p) for p, _ in result.skipped)
    assert (out / "batch_report.txt").is_file()


def test_execute_plan_batch_writes_two_packages_and_report(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgA")
    make_old_package(parent, suffixes=("A7APD",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="pkgB")
    out = tmp_path / "out"
    plan = plan_conversion(parent, out)
    result = execute_plan(plan)
    assert len(result.results) == 2
    assert result.converted >= 2
    assert (out / "batch_report.txt").is_file()
    # Fix 3: both helper packages share manifest title/creator, so their
    # output names collide - each must still get its own package folder.
    assert len({r.output_root for r in result.results}) == 2
    for r in result.results:
        assert r.output_root.is_dir()
        assert (r.output_root / "manifest.json").is_file()


def test_only_comparable_textures_are_read_for_hashing(tmp_path, monkeypatch):
    """Analyze used to read all 37 GB of a fleet folder just to hash it. A
    content digest is only needed where two files could actually meet: a mapped
    name occurring once in the package has nothing to be compared against."""
    pkg = make_old_package(tmp_path, suffixes=("A7APC", "A7APD"),
                           dds_bytes=make_bc3_dds(8, 8), with_common=False,
                           with_model=False)
    unique = (pkg / "SimObjects" / "AirPlanes" / "A388_TST_A7APC" / "TEXTURE.A7APC"
              / "A380X_FUSE3_ALBEDO.PNG.DDS")
    unique.write_bytes(make_bc3_dds(16, 16))

    read = []
    original = Path.read_bytes
    monkeypatch.setattr(Path, "read_bytes",
                        lambda self: (read.append(self), original(self))[1])
    Converter(pkg, tmp_path / "out").plan()

    assert unique not in read, "texture with a package-unique name was read"
    # both variants carry A380X_FUSE1_ALBEDO, so those do need comparing
    shared = [p for p in read if p.name == "A380X_FUSE1_ALBEDO.PNG.DDS"]
    assert len(shared) == 2


def test_unique_texture_still_reaches_its_livery_folder(tmp_path):
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False)
    (pkg / "SimObjects" / "AirPlanes" / "A388_TST_A7APC" / "TEXTURE.A7APC"
     / "A380X_FUSE3_ALBEDO.PNG.DDS").write_bytes(make_bc3_dds(16, 16))
    result = Converter(pkg, tmp_path / "out").run()
    assert (result.output_root / LIVERIES / "flybywire" / "FlyByWire_A380_842_A7APC"
            / "texture" / "A380X_FUSE3_ALBD.PNG.KTX2").is_file()


def test_fallback_served_by_another_package_in_the_batch_is_not_warned_about(tmp_path):
    """The Emirates fleet splits liveries and shared textures across packages on
    purpose. Warning on every one of them buried the real problems."""
    parent = tmp_path / "in"
    parent.mkdir()
    cfg = "[fltsim]\nfallback.1=..\\..\\A388_TST_CMN\\texture.CMN\n"
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="tail",
                     texture_cfg=cfg)
    make_old_package(parent, suffixes=(), depot_suffixes=("CMN",),
                     dds_bytes=make_bc3_dds(8, 8), with_common=False,
                     with_model=False, name="commons")
    plan = plan_conversion(parent, tmp_path / "out")
    tail = next(p for p in plan.packages if p.source.name == "tail")
    assert not [w for w in tail.warnings if "A388_TST_CMN" in w], tail.warnings


def test_fallback_missing_from_the_whole_batch_is_still_warned_about(tmp_path):
    parent = tmp_path / "in"
    parent.mkdir()
    cfg = "[fltsim]\nfallback.1=..\\..\\A388_TST_NOWHERE\\texture.NOWHERE\n"
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="tail",
                     texture_cfg=cfg)
    plan = plan_conversion(parent, tmp_path / "out")
    joined = "\n".join(plan.packages[0].warnings)
    assert "A388_TST_NOWHERE" in joined


def test_external_fallback_warns_that_livery_will_be_incomplete(tmp_path):
    cfg = ("[fltsim]\n"
           "fallback.1=..\\..\\FBW A380 EKNA6CMN\\texture.EKNA6CMN\n"
           "fallback.2=..\\..\\FlyByWire_A380_842\\texture\n")
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                           with_common=False, with_model=False, texture_cfg=cfg)
    plan = Converter(pkg, tmp_path / "out").plan()
    joined = "\n".join(plan.warnings)
    assert "EKNA6CMN" in joined
    assert "incomplete" in joined.lower()
    # the harmless base-aircraft fallback must not be reported
    assert "FlyByWire_A380_842" not in joined


def test_depot_textures_still_land_in_common(tmp_path):
    """A depot inside the package is what its sibling liveries fall back to, so
    dropping it as a livery must not drop its textures."""
    pkg = make_old_package(tmp_path, suffixes=("A7APC",), depot_suffixes=("CMN",),
                           dds_bytes=make_bc3_dds(8, 8), with_common=False,
                           with_model=False)
    depot_dds = (pkg / "SimObjects" / "AirPlanes" / "A388_TST_CMN" / "TEXTURE.CMN"
                 / "A380X_FUSE2_ALBEDO.PNG.DDS")
    depot_dds.write_bytes(make_bc3_dds(16, 16))
    result = Converter(pkg, tmp_path / "out").run()
    root = result.output_root
    flybywire = root / LIVERIES / "flybywire"
    assert [p.name for p in flybywire.iterdir()] == ["FlyByWire_A380_842_A7APC"]
    assert (root / LIVERIES / "common" / "texture"
            / "A380X_FUSE2_ALBD.PNG.KTX2").is_file()
    assert any("depot" in w.lower() for w in result.warnings), result.warnings


def test_depot_only_package_converts_into_a_shared_texture_package(tmp_path):
    """It carries no livery of its own, but its textures are what the sibling
    packages fall back to - they have to reach the shared common folder."""
    parent = tmp_path / "in"
    parent.mkdir()
    make_old_package(parent, suffixes=("A7APC",), dds_bytes=make_bc3_dds(8, 8),
                     with_common=False, with_model=False, name="tail")
    make_old_package(parent, suffixes=(), depot_suffixes=("CMN",),
                     dds_bytes=make_bc3_dds(8, 8), with_common=False,
                     with_model=False, name="commons")
    plan = plan_conversion(parent, tmp_path / "out")
    assert plan.package_count == 2
    assert not plan.skipped, plan.skipped

    result = execute_plan(plan)
    commons = next(r for r in result.results if not any(
        (r.output_root / LIVERIES / "flybywire").glob("*")))
    assert (commons.output_root / LIVERIES / "common" / "texture"
            / "A380X_FUSE1_ALBD.PNG.KTX2").is_file()


def _batch(tmp_path, names=("pkgA", "pkgB")):
    parent = tmp_path / "in"
    parent.mkdir()
    for i, name in enumerate(names):
        make_old_package(parent, suffixes=(f"S{i}",), dds_bytes=make_bc3_dds(8, 8),
                         with_common=False, with_model=False, name=name)
    return parent


def test_default_max_workers_is_two(tmp_path):
    """texconv is internally multithreaded: throughput saturates at 2 workers
    while more triple the peak RAM and starve the rest of the machine."""
    assert Converter(tmp_path, tmp_path).max_workers == 2


def test_plan_conversion_reports_progress_per_package(tmp_path):
    parent = _batch(tmp_path)
    calls = []
    plan_conversion(parent, tmp_path / "out",
                    progress=lambda d, t, m: calls.append((d, t, m)))
    assert [d for d, _, _ in calls] == [1, 2]
    assert all(t == 2 for _, t, _ in calls)
    assert any("pkgA" in m for _, _, m in calls)


def test_plan_conversion_aborts_when_cancelled(tmp_path):
    parent = _batch(tmp_path)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ConversionCancelled):
        plan_conversion(parent, tmp_path / "out", cancel=cancel)


def test_plan_conversion_cancel_stops_between_packages(tmp_path):
    parent = _batch(tmp_path)
    cancel = threading.Event()
    seen = []

    def progress(done, total, message):
        seen.append(message)
        cancel.set()  # abort right after the first package

    with pytest.raises(ConversionCancelled):
        plan_conversion(parent, tmp_path / "out", progress=progress, cancel=cancel)
    assert len(seen) == 1


def test_execute_plan_aborts_when_cancelled(tmp_path):
    parent = _batch(tmp_path)
    out = tmp_path / "out"
    plan = plan_conversion(parent, out)
    cancel = threading.Event()
    cancel.set()
    with pytest.raises(ConversionCancelled):
        execute_plan(plan, cancel=cancel)


def test_prepare_runs_once_per_package_across_plan_and_execute(tmp_path, monkeypatch):
    """Fix 3: planning already hashes every DDS of a package - executing it
    must reuse that work instead of reading all textures a second time."""
    parent = _batch(tmp_path, names=("pkgA", "pkgB", "pkgC"))
    calls = []
    original = Converter._prepare

    def counting(self):
        calls.append(self.input_dir)
        return original(self)

    monkeypatch.setattr(Converter, "_prepare", counting)
    plan = plan_conversion(parent, tmp_path / "out")
    # all three share manifest title/creator, so two get renamed on dedupe -
    # a rename must not force a re-prepare
    assert len({p.output_name for p in plan.packages}) == 3
    execute_plan(plan)
    assert len(calls) == 3


def test_renamed_output_package_writes_into_its_own_folder(tmp_path):
    parent = _batch(tmp_path)  # both helper packages share manifest title/creator
    out = tmp_path / "out"
    result = execute_plan(plan_conversion(parent, out))
    assert len({r.output_root for r in result.results}) == 2
    for r in result.results:
        textures = list(r.output_root.rglob("*.KTX2"))
        assert textures
        for texture in textures:
            assert texture.is_relative_to(r.output_root)
