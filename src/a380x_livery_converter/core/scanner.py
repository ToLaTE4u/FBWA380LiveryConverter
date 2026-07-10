"""Inventory of an old-format (MSFS 2020) livery package."""

import json
from dataclasses import dataclass
from pathlib import Path

from a380x_livery_converter.core.aircraft_cfg import fltsim_sections, parse_cfg


class NotAnA380XPackageError(Exception):
    """Input folder is not an FBW A380X livery package."""


@dataclass
class Variant:
    folder: Path
    index: int
    title: str
    ui_variation: str
    atc_id: str
    atc_airline: str
    icao_airline: str
    texture_suffix: str
    texture_dir: Path | None
    has_custom_model: bool


@dataclass
class OldPackage:
    root: Path
    title: str
    creator: str
    package_version: str
    variants: list[Variant]
    common_texture_dir: Path | None


def _find_child(parent: Path, name: str) -> Path | None:
    if parent is None or not parent.is_dir():
        return None
    for child in parent.iterdir():
        if child.name.upper() == name.upper():
            return child
    return None


def scan_package(root: Path) -> OldPackage:
    root = Path(root)
    simobjects = _find_child(root, "SimObjects")
    airplanes = _find_child(simobjects, "AirPlanes") if simobjects else None
    if airplanes is None:
        raise NotAnA380XPackageError(f"No SimObjects/AirPlanes folder found in {root}")

    variants: list[Variant] = []
    common_dir: Path | None = None
    is_a380 = False
    for folder in sorted(airplanes.iterdir()):
        if not folder.is_dir():
            continue
        cfg_path = _find_child(folder, "aircraft.cfg")
        if cfg_path is None:
            if "COMMON" in folder.name.upper():
                common_dir = folder
            continue
        sections = parse_cfg(cfg_path.read_text(encoding="utf-8", errors="replace"))
        base = sections.get("VARIATION", {}).get("base_container", "")
        if "FLYBYWIRE_A380" in base.replace("\\", "/").rsplit("/", 1)[-1].upper():
            is_a380 = True
        for index, body in fltsim_sections(sections):
            suffix = body.get("texture", "")
            texture_dir = _find_child(folder, f"TEXTURE.{suffix}" if suffix else "TEXTURE")
            model = body.get("model", "")
            model_dir = _find_child(folder, f"MODEL.{model}" if model else "MODEL")
            variants.append(Variant(
                folder=folder,
                index=index,
                title=body.get("title", folder.name),
                ui_variation=body.get("ui_variation", body.get("title", folder.name)),
                atc_id=body.get("atc_id", ""),
                atc_airline=body.get("atc_airline", ""),
                icao_airline=body.get("icao_airline", ""),
                texture_suffix=suffix,
                texture_dir=texture_dir,
                has_custom_model=model_dir is not None,
            ))
    if not is_a380 or not variants:
        raise NotAnA380XPackageError(
            f"{root} does not contain FBW A380X variants (base_container check failed)")

    title, creator, version = root.name, "unknown", "1.0"
    manifest_path = _find_child(root, "manifest.json")
    if manifest_path is not None:
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig", errors="replace"))
            title = manifest.get("title", title)
            creator = manifest.get("creator", creator)
            version = manifest.get("package_version", version)
        except (json.JSONDecodeError, OSError):
            pass
    return OldPackage(root=root, title=title, creator=creator, package_version=version,
                      variants=variants, common_texture_dir=common_dir)
