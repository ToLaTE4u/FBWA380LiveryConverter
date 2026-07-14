import json
from pathlib import Path

from a380x_livery_converter.core.scanner import OldPackage, Variant
from a380x_livery_converter.output.package_gen import (
    livery_folder_name,
    package_folder_name,
    write_layout,
    write_manifest,
    write_report,
)


def _old_package(title="Fleet Pack: SD & HD!", creator="HUES | Valexyo"):
    return OldPackage(root=Path("x"), title=title, creator=creator,
                      package_version="2.0", variants=[], common_texture_dir=None)


def _variant(suffix="A7APC"):
    return Variant(folder=Path("x"), index=0, title="t", ui_variation="u", atc_id="A380X",
                   atc_airline="a", icao_airline="", texture_suffix=suffix,
                   texture_dir=None, has_custom_model=False)


def test_package_folder_name_sanitized_with_2024_suffix():
    name = package_folder_name(_old_package())
    assert name == "hues-valexyo-livery-fbw-a380x-fleet-pack-sd-hd-2024"
    assert name.endswith("-2024")
    assert " " not in name and ":" not in name


def test_livery_folder_name():
    assert livery_folder_name(_variant()) == "FlyByWire_A380_842_A7APC"
    assert livery_folder_name(_variant(suffix="")) == "FlyByWire_A380_842_A380X"


def test_layout_excludes_meta_files(tmp_path):
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.KTX2").write_bytes(b"12345")
    (tmp_path / "conversion_report.txt").write_text("report")
    write_layout(tmp_path)
    layout = json.loads((tmp_path / "layout.json").read_text())
    paths = [e["path"] for e in layout["content"]]
    assert paths == ["sub/a.KTX2"]
    entry = layout["content"][0]
    assert entry["size"] == 5
    assert entry["date"] > 116444736000000000  # FILETIME after 1970


def test_manifest_content(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 100)
    write_layout(tmp_path)
    write_manifest(tmp_path, "My Livery", "Creator", "2.0")
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["content_type"] == "LIVERY"
    assert manifest["minimum_game_version"] == "1.26.5"
    assert manifest["title"] == "My Livery (MSFS2024)"
    assert {d["name"] for d in manifest["dependencies"]} == {
        "asobo-vcockpits-instruments-airliners", "fs-base-aircraft-common"}
    total = manifest["total_package_size"]
    assert len(total) == 20 and total.isdigit()
    assert int(total) >= 100  # a.bin + layout.json


def test_report_lists_warnings(tmp_path):
    path = write_report(tmp_path, ["warn one", "warn two"], converted=5, skipped=1,
                        source=_old_package())
    text = path.read_text()
    assert "warn one" in text and "warn two" in text
    assert "5" in text and "Fleet Pack" in text


def test_report_lists_mappings(tmp_path):
    path = write_report(tmp_path, [], converted=1, skipped=0, source=_old_package(),
                        mappings=["A.PNG.DDS -> flybywire/x/texture/A.PNG.KTX2"])
    text = path.read_text()
    assert "Mappings:" in text
    assert "A.PNG.DDS -> flybywire/x/texture/A.PNG.KTX2" in text


def test_report_omits_mappings_section_when_absent_or_empty(tmp_path):
    path = write_report(tmp_path, [], converted=1, skipped=0, source=_old_package())
    text = path.read_text()
    assert "Mappings:" not in text

    path = write_report(tmp_path, [], converted=1, skipped=0, source=_old_package(),
                        mappings=[])
    text = path.read_text()
    assert "Mappings:" not in text


def test_batch_report_lists_packages_and_skips(tmp_path):
    from a380x_livery_converter.converter import ConversionResult
    from a380x_livery_converter.output.package_gen import write_batch_report
    results = [ConversionResult(tmp_path / "pkgA", 5, 0, []),
               ConversionResult(tmp_path / "pkgB", 3, 1, ["w"])]
    path = write_batch_report(tmp_path, results, [(tmp_path / "junk", "not a livery package")])
    text = path.read_text()
    assert "pkgA" in text and "pkgB" in text
    assert "junk" in text and "not a livery package" in text
