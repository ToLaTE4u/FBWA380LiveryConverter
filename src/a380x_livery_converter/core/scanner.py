"""Inventory of an old-format (MSFS 2020) livery package."""

import json
from dataclasses import dataclass, field
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
    is_user_selectable: bool = True
    # texture.cfg fallbacks naming an aircraft container that exists neither in
    # this package nor anywhere else in the batch - textures this livery asks
    # for and nothing on hand can supply.
    missing_fallbacks: list[str] = field(default_factory=list)


@dataclass
class OldPackage:
    root: Path
    title: str
    creator: str
    package_version: str
    variants: list[Variant]
    common_texture_dir: Path | None
    skipped_foreign: list[str] = field(default_factory=list)
    # Variants with isUserSelectable = 0: shared texture depots that sibling
    # liveries fall back to, not liveries in their own right.
    depots: list[Variant] = field(default_factory=list)


def _find_child(parent: Path, name: str) -> Path | None:
    if parent is None or not parent.is_dir():
        return None
    for child in parent.iterdir():
        if child.name.upper() == name.upper():
            return child
    return None


def _fallback_paths(texture_dir: Path | None) -> list[str]:
    """The fallback.N entries of a texture.cfg, in their configured order."""
    if texture_dir is None:
        return []
    cfg = _find_child(texture_dir, "texture.cfg")
    if cfg is None or not cfg.is_file():
        return []
    try:
        body = parse_cfg(cfg.read_text(encoding="utf-8", errors="replace")).get("FLTSIM", {})
    except OSError:
        return []
    numbered = []
    for key, value in body.items():
        _, _, suffix = key.partition("fallback.")
        if key.startswith("fallback.") and suffix.isdigit() and value.strip():
            numbered.append((int(suffix), value.strip()))
    return [value for _, value in sorted(numbered)]


def container_names(roots) -> set[str]:
    """Upper-cased aircraft container names across a batch of packages.

    MSFS merges every Community package into one virtual file system, so a
    texture.cfg fallback may legitimately point into a container shipped by a
    *different* package - the Emirates fleet does exactly that with its shared
    texture depots. Only against the whole batch can a fallback be called
    missing.
    """
    names: set[str] = set()
    for root in roots:
        simobjects = _find_child(Path(root), "SimObjects")
        airplanes = _find_child(simobjects, "AirPlanes") if simobjects else None
        if airplanes is None:
            continue
        names.update(child.name.upper() for child in airplanes.iterdir() if child.is_dir())
    return names


def _missing_fallbacks(texture_dir: Path | None, folder: Path, airplanes: Path,
                       base_name: str, known_containers: set[str]) -> list[str]:
    """Fallbacks pointing at a container nothing on hand can supply.

    Four kinds of entry are absent by design and mean nothing is missing:
    paths resolving outside SimObjects/AirPlanes (sim level), the base
    container (ships with the A380X itself), paths staying inside the variant's
    own container (boilerplate such as fallback=..\\texture), and containers
    another package in the batch provides.
    """
    if texture_dir is None:
        return []
    airplanes_root = airplanes.resolve()
    benign = {base_name.upper(), folder.name.upper()}
    benign.update(name.upper() for name in known_containers)
    missing = []
    for raw in _fallback_paths(texture_dir):
        target = (texture_dir / raw.replace("\\", "/")).resolve()
        if target.exists():
            continue
        try:
            relative = target.relative_to(airplanes_root)
        except ValueError:
            continue
        if not relative.parts or relative.parts[0].upper() in benign:
            continue
        missing.append(raw)
    return missing


def _is_2024_format(airplanes: Path) -> bool:
    """True for packages that already use the MSFS 2024 layout.

    2024 packages carry their liveries in SimObjects/Airplanes/<aircraft>/liveries
    and have no per-livery aircraft.cfg at all, so they reach the same "no
    variants" dead end as a genuinely foreign package.
    """
    for child in airplanes.iterdir():
        if child.is_dir() and _find_child(child, "liveries") is not None:
            return True
    return False


def _rejection_reason(root: Path, airplanes: Path, skipped_foreign: list[str]) -> str:
    if _is_2024_format(airplanes):
        return (f"{root.name} is already in MSFS 2024 livery format "
                f"- nothing to convert")
    if skipped_foreign:
        detected = ", ".join(sorted(set(skipped_foreign)))
        return (f"{root.name} contains no FBW A380X livery "
                f"- detected other aircraft: {detected}")
    return (f"{root.name} contains no aircraft.cfg with an FBW A380X "
            f"base_container - not an MSFS 2020 A380X livery")


def scan_package(root: Path, known_containers: set[str] | None = None) -> OldPackage:
    root = Path(root)
    known_containers = known_containers or set()
    simobjects = _find_child(root, "SimObjects")
    airplanes = _find_child(simobjects, "AirPlanes") if simobjects else None
    if airplanes is None:
        raise NotAnA380XPackageError(f"No SimObjects/AirPlanes folder found in {root}")

    variants: list[Variant] = []
    depots: list[Variant] = []
    common_dir: Path | None = None
    skipped_foreign: list[str] = []
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
        base_name = base.replace("\\", "/").rsplit("/", 1)[-1]
        if "FLYBYWIRE_A380" not in base_name.upper():
            skipped_foreign.append(base_name or folder.name)
            continue
        for index, body in fltsim_sections(sections):
            suffix = body.get("texture", "")
            texture_dir = _find_child(folder, f"TEXTURE.{suffix}" if suffix else "TEXTURE")
            model = body.get("model", "")
            model_dir = _find_child(folder, f"MODEL.{model}" if model else "MODEL")
            selectable = body.get("isuserselectable", "1").strip() != "0"
            variant = Variant(
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
                is_user_selectable=selectable,
                missing_fallbacks=(
                    _missing_fallbacks(texture_dir, folder, airplanes, base_name,
                                       known_containers)
                    if selectable else []),
            )
            (variants if selectable else depots).append(variant)
    # A depot-only package carries no livery of its own, but it is exactly what
    # the sibling packages fall back to, so it still has textures to convert.
    if not variants and not depots:
        raise NotAnA380XPackageError(_rejection_reason(root, airplanes, skipped_foreign))

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
                      variants=variants, common_texture_dir=common_dir,
                      skipped_foreign=skipped_foreign, depots=depots)


def _is_package(path: Path) -> bool:
    simobjects = _find_child(path, "SimObjects")
    return simobjects is not None and _find_child(simobjects, "AirPlanes") is not None


def find_packages(root: Path) -> tuple[list[Path], list[tuple[Path, str]]]:
    root = Path(root)
    if _is_package(root):
        return [root], []
    packages: list[Path] = []
    skipped: list[tuple[Path, str]] = []
    if root.is_dir():
        for child in sorted(root.iterdir()):
            if not child.is_dir():
                continue
            if _is_package(child):
                packages.append(child)
            else:
                skipped.append((child, "not a livery package"))
    if not packages:
        return [], [(root, "no livery package found")]
    return packages, skipped
