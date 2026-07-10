"""Package level generation: folder names, manifest.json, layout.json, report."""

import json
import re
from pathlib import Path

from a380x_livery_converter.core.scanner import OldPackage, Variant
from a380x_livery_converter.texture.ktx2 import filetime_from_unix

LIVERIES_SUBPATH = Path("SimObjects") / "AirPlanes" / "FlyByWire_A380X" / "liveries"

MANIFEST_DEPENDENCIES = [
    {"package_version": "0.1.129", "name": "asobo-vcockpits-instruments-airliners"},
    {"package_version": "0.1.125", "name": "fs-base-aircraft-common"},
]

_EXCLUDED_FROM_LAYOUT = {"layout.json", "manifest.json", "conversion_report.txt"}


def _sanitize(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", text).strip("-")
    cleaned = re.sub(r"-{2,}", "-", cleaned)
    return cleaned or "unnamed"


def package_folder_name(old: OldPackage) -> str:
    return _sanitize(f"{old.creator}-livery-fbw-a380x-{old.title}").lower()


def livery_folder_name(variant: Variant) -> str:
    tag = variant.texture_suffix or variant.atc_id or f"VAR{variant.index}"
    return f"FlyByWire_A380_842_{_sanitize(tag)}"


def write_layout(root: Path) -> None:
    root = Path(root)
    entries = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name in _EXCLUDED_FROM_LAYOUT:
            continue
        stat = path.stat()
        entries.append({
            "path": path.relative_to(root).as_posix(),
            "size": stat.st_size,
            "date": filetime_from_unix(stat.st_mtime),
        })
    (root / "layout.json").write_text(json.dumps({"content": entries}, indent=2))


def write_manifest(root: Path, title: str, creator: str, version: str) -> None:
    root = Path(root)
    total = sum(p.stat().st_size for p in root.rglob("*")
                if p.is_file() and p.name != "manifest.json")
    manifest = {
        "dependencies": MANIFEST_DEPENDENCIES,
        "content_type": "LIVERY",
        "title": f"{title} (MSFS2024)",
        "manufacturer": "Airbus",
        "creator": creator,
        "package_version": version or "1.0.0",
        "minimum_game_version": "1.26.5",
        "total_package_size": f"{total:020d}",
    }
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2))


def write_report(root: Path, warnings: list[str], converted: int, skipped: int,
                 source: OldPackage) -> Path:
    lines = [
        "A380X Livery Converter - conversion report",
        "=" * 44,
        "",
        f"Source package  : {source.title} (by {source.creator})",
        f"Variants        : {len(source.variants)}",
        f"Textures OK     : {converted}",
        f"Textures skipped: {skipped}",
        "",
    ]
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {w}" for w in warnings)
    else:
        lines.append("No warnings.")
    lines += ["", "Note: interior/cabin textures are converted as-is; whether the native",
              "2024 model actually uses them is outside this tool's control."]
    path = Path(root) / "conversion_report.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
