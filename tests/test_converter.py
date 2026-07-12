import json

from a380x_livery_converter.converter import Converter
from tests.helpers import make_bc3_dds, make_old_package

LIVERIES = "SimObjects/AirPlanes/FlyByWire_A380X/liveries"


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
    assert (root / "conversion_report.txt").is_file()
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


def test_dry_run_writes_nothing(tmp_path):
    result, out, _ = _convert(tmp_path, dry_run=True)
    assert not out.exists()
    assert result.converted == 0
    assert any("dry-run" in w for w in result.warnings)


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
