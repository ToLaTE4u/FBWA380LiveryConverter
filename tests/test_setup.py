from a380x_livery_converter import resource_path


def test_bundled_resources_exist():
    assert resource_path("rename_list.csv").is_file()
    assert resource_path("texconv.exe").is_file()
    for name in ("thumbnail.png", "thumbnail_button.png", "thumbnail_side.png"):
        assert resource_path(f"thumbnails/{name}").is_file()
