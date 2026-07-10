"""Texture filename mapping old (2020) -> new (2024) based on the FBW paintkit CSV."""

import csv

from a380x_livery_converter import resource_path


def load_rename_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    with resource_path("rename_list.csv").open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            old = row["current_name"].strip()
            new = row["new_name"].strip()
            if old and new:
                mapping[old.upper()] = new
    return mapping


def map_texture_filename(filename: str, rename_map: dict[str, str]) -> tuple[str, bool]:
    base = filename
    if base.upper().endswith(".DDS"):
        base = base[: -len(".DDS")]
    new_base = rename_map.get(base.upper())
    if new_base is None:
        return f"{base}.KTX2", False
    return f"{new_base}.KTX2", True
