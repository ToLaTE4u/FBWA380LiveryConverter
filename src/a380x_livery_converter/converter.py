"""Top-level conversion orchestration."""

import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from a380x_livery_converter.core.rename_map import load_rename_map, map_texture_filename
from a380x_livery_converter.core.scanner import Variant, scan_package
from a380x_livery_converter.output import livery_gen, package_gen
from a380x_livery_converter.texture.pipeline import convert_texture

ProgressCallback = Callable[[int, int, str], None]


@dataclass
class ConversionResult:
    output_root: Path
    converted: int
    skipped: int
    warnings: list[str]


@dataclass
class _TextureJob:
    src: Path
    dest: Path
    label: str


def _dds_files(folder: Path) -> list[Path]:
    return sorted(p for p in Path(folder).iterdir()
                  if p.is_file() and p.name.upper().endswith(".DDS"))


class Converter:
    def __init__(self, input_dir: Path, output_dir: Path,
                 progress: ProgressCallback | None = None,
                 dry_run: bool = False, max_workers: int | None = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.progress: ProgressCallback = progress or (lambda done, total, msg: None)
        self.dry_run = dry_run
        self.max_workers = max_workers or min(8, os.cpu_count() or 4)

    def run(self) -> ConversionResult:
        old = scan_package(self.input_dir)
        rename_map = load_rename_map()
        warnings: list[str] = []

        out_root = self.output_dir / package_gen.package_folder_name(old)
        flybywire_root = out_root / package_gen.LIVERIES_SUBPATH / "flybywire"
        common_texture = out_root / package_gen.LIVERIES_SUBPATH / "common" / "texture"

        jobs: list[_TextureJob] = []
        if old.common_texture_dir is not None:
            for src in _dds_files(old.common_texture_dir):
                name = self._mapped(src.name, rename_map, warnings)
                jobs.append(_TextureJob(src, common_texture / name, f"common/{src.name}"))

        # Variantentexturen sammeln, identische Dateien über Varianten deduplizieren
        grouped: dict[tuple[str, str], list[tuple[Variant, Path]]] = {}
        for variant in old.variants:
            if variant.has_custom_model:
                warnings.append(f"{variant.title}: custom MODEL folder cannot be converted "
                                f"- decals/3D additions are lost")
            if variant.texture_dir is None:
                warnings.append(f"{variant.title}: no texture folder found - variant has no own textures")
                continue
            for src in _dds_files(variant.texture_dir):
                name = self._mapped(src.name, rename_map, warnings)
                digest = hashlib.sha1(src.read_bytes()).hexdigest()
                grouped.setdefault((name, digest), []).append((variant, src))
        for (name, _digest), sources in grouped.items():
            variants_involved = {id(v) for v, _ in sources}
            if len(variants_involved) > 1:
                jobs.append(_TextureJob(sources[0][1], common_texture / name, f"common/{name}"))
            else:
                variant, src = sources[0]
                dest = (flybywire_root / package_gen.livery_folder_name(variant)
                        / "texture" / name)
                jobs.append(_TextureJob(src, dest, f"{variant.texture_suffix}/{src.name}"))

        # Ziel-Kollisionen (z. B. Dedup-Name schon aus Common Textures belegt): erster gewinnt
        unique: dict[Path, _TextureJob] = {}
        for job in jobs:
            unique.setdefault(job.dest, job)
        jobs = list(unique.values())

        if self.dry_run:
            warnings.append(f"[dry-run] would convert {len(jobs)} textures into {out_root}")
            return ConversionResult(out_root, 0, 0, warnings)

        total = len(jobs) + len(old.variants) + 2
        done = 0
        converted = skipped = 0
        with tempfile.TemporaryDirectory(prefix="a380xconv_") as tmp, \
                ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            futures = {}
            for i, job in enumerate(jobs):
                futures[pool.submit(convert_texture, job.src, job.dest,
                                    Path(tmp) / f"job{i}")] = job
            for future in as_completed(futures):
                job = futures[future]
                try:
                    future.result()
                    converted += 1
                except Exception as exc:
                    skipped += 1
                    warnings.append(f"Texture skipped ({job.label}): {exc}")
                done += 1
                self.progress(done, total, f"Texture {job.label}")

        for variant in old.variants:
            livery_dir = flybywire_root / package_gen.livery_folder_name(variant)
            livery_gen.write_texture_cfg(livery_dir / "texture")
            livery_dir.mkdir(parents=True, exist_ok=True)
            (livery_dir / "livery.cfg").write_text(livery_gen.livery_cfg_text(variant),
                                                   encoding="utf-8")
            thumb = livery_gen.find_old_thumbnail(variant.texture_dir)
            for w in livery_gen.write_thumbnails(thumb, livery_dir / "thumbnail"):
                warnings.append(f"{variant.title}: {w}")
            done += 1
            self.progress(done, total, f"Config for {variant.title}")

        package_gen.write_report(out_root, warnings, converted=converted,
                                 skipped=skipped, source=old)
        package_gen.write_layout(out_root)
        done += 1
        self.progress(done, total, "layout.json")
        package_gen.write_manifest(out_root, old.title, old.creator, old.package_version)
        done += 1
        self.progress(done, total, "manifest.json")
        return ConversionResult(out_root, converted, skipped, warnings)

    @staticmethod
    def _mapped(filename: str, rename_map: dict[str, str], warnings: list[str]) -> str:
        name, was_mapped = map_texture_filename(filename, rename_map)
        if not was_mapped:
            warnings.append(f"Unknown texture name kept as-is: {filename}")
        return name
