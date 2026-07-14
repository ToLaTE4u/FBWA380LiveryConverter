from a380x_livery_converter.core.rename_map import load_rename_map, map_texture_filename


def test_map_contains_known_entries_uppercase_keyed():
    m = load_rename_map()
    assert m["A380X_FUSE1_ALBEDO.PNG"] == "A380X_FUSE1_ALBD.PNG"
    assert m["A380_EXTERIOR_WING1_ALBEDO.PNG"] == "A380X_EXT_WING1_ALBD.PNG"
    assert len(m) > 300


def test_engine_blur5_mapped():
    # BLUR5 exists in the 2024 model but was missing from FBW's rename table.
    m = load_rename_map()
    assert m["ENGINE_BLUR5_ALBEDO.PNG"] == "A380X_ENGINE_BLUR5_ALBD.PNG"


def test_mapped_filename_any_case():
    m = load_rename_map()
    assert map_texture_filename("A380X_FUSE1_ALBEDO.PNG.DDS", m) == ("A380X_FUSE1_ALBD.PNG.KTX2", True)
    assert map_texture_filename("A380X_FUSE2_ALBEDO.png.dds", m) == ("A380X_FUSE2_ALBD.PNG.KTX2", True)


def test_unmapped_filename_keeps_base_name():
    m = load_rename_map()
    assert map_texture_filename("HUES_A380_DECALS_ALBD.png.dds", m) == ("HUES_A380_DECALS_ALBD.png.KTX2", False)
