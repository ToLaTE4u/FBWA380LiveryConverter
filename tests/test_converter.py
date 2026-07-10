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
