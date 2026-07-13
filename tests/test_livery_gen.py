from pathlib import Path

from PIL import Image

from a380x_livery_converter.core.scanner import Variant
from a380x_livery_converter.output.livery_gen import (
    TEXTURE_CFG,
    find_old_thumbnail,
    livery_cfg_text,
    write_texture_cfg,
    write_thumbnails,
)


def _variant(**overrides):
    defaults = dict(folder=Path("x"), index=0, title="T", ui_variation="HUES QATAR A7-APC",
                    atc_id="A7-APC", atc_airline="Qatar Airways", icao_airline="QTR",
                    texture_suffix="A7APC", texture_dir=None, has_custom_model=False)
    defaults.update(overrides)
    return Variant(**defaults)


def test_livery_cfg_content():
    text = livery_cfg_text(_variant())
    assert '[GENERAL]' in text and '[version]' in text
    assert 'Name = "HUES QATAR A7-APC"' in text
    assert 'atc_airline="Qatar Airways"' in text
    assert 'atc_id=""' in text
    assert 'icao_airline="QTR"' in text
    assert 'atc_parking_codes="QTR"' in text
    assert "ui_createdby" not in text


def test_livery_cfg_falls_back_to_title():
    text = livery_cfg_text(_variant(ui_variation=""))
    assert 'Name = "T"' in text


def test_texture_cfg_written(tmp_path):
    write_texture_cfg(tmp_path)
    content = (tmp_path / "texture.CFG").read_text()
    assert content == TEXTURE_CFG
    assert "fallback.1=..\\..\\..\\common\\texture" in content
    assert "fallback.2=..\\..\\FlyByWire_A380_842\\texture" in content


def test_find_old_thumbnail_case_insensitive(tmp_path):
    Image.new("RGB", (100, 50), "blue").save(tmp_path / "THUMBNAIL.JPG")
    found = find_old_thumbnail(tmp_path)
    assert found is not None and found.name == "THUMBNAIL.JPG"
    assert find_old_thumbnail(None) is None


def test_find_old_thumbnail_ignores_directory(tmp_path):
    (tmp_path / "THUMBNAIL.JPG").mkdir()
    assert find_old_thumbnail(tmp_path) is None


def test_find_old_thumbnail_skips_directory_finds_real_file(tmp_path):
    (tmp_path / "THUMBNAIL.JPG").mkdir()
    Image.new("RGB", (100, 50), "blue").save(tmp_path / "THUMBNAIL.PNG")
    found = find_old_thumbnail(tmp_path)
    assert found is not None and found.name == "THUMBNAIL.PNG"


def test_write_thumbnails_from_source(tmp_path):
    src = tmp_path / "thumbnail.JPG"
    Image.new("RGB", (412, 170), "blue").save(src)
    warnings = write_thumbnails(src, tmp_path / "thumb")
    assert warnings == []
    assert Image.open(tmp_path / "thumb" / "thumbnail.png").size == (720, 344)
    assert Image.open(tmp_path / "thumb" / "thumbnail_button.png").size == (830, 260)
    assert Image.open(tmp_path / "thumb" / "thumbnail_side.png").size == (930, 340)


def test_write_thumbnails_placeholder_when_missing(tmp_path):
    warnings = write_thumbnails(None, tmp_path / "thumb")
    assert len(warnings) == 1
    assert (tmp_path / "thumb" / "thumbnail.png").is_file()
    assert (tmp_path / "thumb" / "thumbnail_side.png").is_file()
