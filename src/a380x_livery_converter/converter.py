"""Top-level conversion orchestration."""

import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from a380x_livery_converter.core.rename_map import load_rename_map, map_texture_filename
from a380x_livery_converter.core.scanner import (
    NotAnA380XPackageError, Variant, find_packages, scan_package,
)
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
class PackagePlan:
    source: Path
    output_name: str
    livery_names: list[str]
    texture_count: int
    warnings: list[str]
    exists: bool = False


@dataclass
class _Prepared:
    old: object
    jobs: list["_TextureJob"]
    warnings: list[str]
    out_root: Path
    flybywire_root: Path
    folder_names: dict[int, str]


@dataclass
class _TextureJob:
    src: Path
    dest: Path
    label: str
    digest: str
    # Set only for jobs whose dest was chosen by the "identical file shared
    # by multiple variants" dedup step: the (variant, src) pairs that all
    # produced this exact content, needed to relocate per-variant on collision.
    group: list[tuple[Variant, Path]] | None = None


def _dds_files(folder: Path) -> list[Path]:
    return sorted(p for p in Path(folder).iterdir()
                  if p.is_file() and p.name.upper().endswith(".DDS"))


def _assign_folder_names(variants: list[Variant]) -> dict[int, str]:
    """Map id(variant) -> livery folder name, disambiguating collisions.

    package_gen.livery_folder_name() can return the same name for two
    different variants (e.g. two [FLTSIM] sections sharing a texture
    suffix). The first variant to produce a given base name keeps it
    unchanged; later collisions get a "_1", "_2", ... suffix.
    """
    seen: dict[str, int] = {}
    names: dict[int, str] = {}
    for variant in variants:
        base = package_gen.livery_folder_name(variant)
        count = seen.get(base, 0)
        names[id(variant)] = base if count == 0 else f"{base}_{count}"
        seen[base] = count + 1
    return names


class Converter:
    def __init__(self, input_dir: Path, output_dir: Path,
                 progress: ProgressCallback | None = None,
                 max_workers: int | None = None,
                 output_name: str | None = None):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.progress: ProgressCallback = progress or (lambda done, total, msg: None)
        self.max_workers = max_workers or min(8, os.cpu_count() or 4)
        self.output_name = output_name

    def _prepare(self) -> _Prepared:
        old = scan_package(self.input_dir)
        rename_map = load_rename_map()
        warnings: list[str] = []
        for label in old.skipped_foreign:
            warnings.append(f"Skipped foreign variant: {label}")

        out_root = self.output_dir / (self.output_name
                                      or package_gen.package_folder_name(old))
        flybywire_root = out_root / package_gen.LIVERIES_SUBPATH / "flybywire"
        common_texture = out_root / package_gen.LIVERIES_SUBPATH / "common" / "texture"
        folder_names = _assign_folder_names(old.variants)

        jobs: list[_TextureJob] = []
        if old.common_texture_dir is not None:
            for src in _dds_files(old.common_texture_dir):
                name = self._mapped(src.name, rename_map, warnings)
                digest = hashlib.sha1(src.read_bytes()).hexdigest()
                jobs.append(_TextureJob(src, common_texture / name, f"common/{src.name}", digest))

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
        for (name, digest), sources in grouped.items():
            variants_involved = {id(v) for v, _ in sources}
            if len(variants_involved) > 1:
                jobs.append(_TextureJob(sources[0][1], common_texture / name,
                                        f"common/{name}", digest, group=sources))
            else:
                variant, src = sources[0]
                dest = (flybywire_root / folder_names[id(variant)] / "texture" / name)
                jobs.append(_TextureJob(src, dest, f"{variant.texture_suffix}/{src.name}", digest))

        jobs = self._resolve_collisions(jobs, warnings, flybywire_root, folder_names)
        return _Prepared(old, jobs, warnings, out_root, flybywire_root, folder_names)

    def plan(self) -> PackagePlan:
        p = self._prepare()
        livery_names = [p.folder_names[id(v)] for v in p.old.variants]
        return PackagePlan(
            source=self.input_dir,
            output_name=self.output_name or package_gen.package_folder_name(p.old),
            livery_names=livery_names,
            texture_count=len(p.jobs),
            warnings=list(p.warnings),
        )

    def run(self) -> ConversionResult:
        p = self._prepare()
        old, jobs, warnings = p.old, p.jobs, p.warnings
        out_root, flybywire_root, folder_names = p.out_root, p.flybywire_root, p.folder_names

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
            livery_dir = flybywire_root / folder_names[id(variant)]
            livery_gen.write_texture_cfg(livery_dir / "texture")
            livery_dir.mkdir(parents=True, exist_ok=True)
            (livery_dir / "livery.cfg").write_text(livery_gen.livery_cfg_text(variant),
                                                   encoding="utf-8")
            thumb = livery_gen.find_old_thumbnail(variant.texture_dir)
            for w in livery_gen.write_thumbnails(thumb, livery_dir / "thumbnail"):
                warnings.append(f"{variant.title}: {w}")
            done += 1
            self.progress(done, total, f"Config for {variant.title}")

        mappings = [f"{job.src.name} -> {job.dest.relative_to(out_root).as_posix()}"
                   for job in jobs]
        package_gen.write_report(out_root, warnings, converted=converted,
                                 skipped=skipped, source=old, mappings=mappings)
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

    @staticmethod
    def _resolve_collisions(jobs: list[_TextureJob], warnings: list[str],
                            flybywire_root: Path,
                            folder_names: dict[int, str]) -> list[_TextureJob]:
        """Resolve destination collisions between jobs.

        Same dest + same digest -> true duplicate, drop the later one silently.
        Same dest + different digest -> keep the first job's content at dest and
        relocate the colliding job instead of dropping it: per-variant if it
        carries a source group (the multi-variant dedup case), otherwise next to
        its original dest under a content-disambiguated name.
        """
        resolved: dict[Path, _TextureJob] = {}
        queue: list[_TextureJob] = list(jobs)
        while queue:
            job = queue.pop(0)
            existing = resolved.get(job.dest)
            if existing is None:
                resolved[job.dest] = job
                continue
            if existing.digest == job.digest:
                continue  # identical content already present at dest - true duplicate

            warnings.append(
                f"Texture name collision at {job.dest.name}: keeping content from "
                f"'{existing.label}', relocating '{job.label}' to per-variant folders")

            name = job.dest.name
            for variant, src in (job.group or [(None, job.src)]):
                if variant is not None:
                    dest = flybywire_root / folder_names[id(variant)] / "texture" / name
                    label = f"{variant.texture_suffix}/{src.name}"
                else:
                    dest = job.dest.parent / f"{job.digest[:8]}_{name}"
                    label = job.label
                queue.append(_TextureJob(src, dest, label, job.digest))
        return list(resolved.values())


@dataclass
class ConversionPlan:
    packages: list[PackagePlan]
    skipped: list[tuple[Path, str]]
    output_dir: Path

    @property
    def package_count(self) -> int:
        return len(self.packages)

    @property
    def livery_count(self) -> int:
        return sum(len(p.livery_names) for p in self.packages)

    @property
    def texture_count(self) -> int:
        return sum(p.texture_count for p in self.packages)


@dataclass
class BatchResult:
    results: list[ConversionResult]
    skipped: list[tuple[Path, str]]

    @property
    def converted(self) -> int:
        return sum(r.converted for r in self.results)

    @property
    def skipped_textures(self) -> int:
        return sum(r.skipped for r in self.results)

    @property
    def warnings(self) -> list[str]:
        out: list[str] = []
        for r in self.results:
            out.extend(r.warnings)
        return out


def plan_conversion(input_dir: Path, output_dir: Path) -> ConversionPlan:
    input_dir, output_dir = Path(input_dir), Path(output_dir)
    roots, skipped = find_packages(input_dir)
    skipped = list(skipped)
    packages: list[PackagePlan] = []
    for root in roots:
        try:
            packages.append(Converter(root, output_dir).plan())
        except NotAnA380XPackageError as exc:
            skipped.append((root, str(exc)))
        except Exception as exc:
            skipped.append((root, f"planning failed: {exc}"))
    _dedupe_output_names(packages)
    for pkg in packages:
        pkg.exists = (output_dir / pkg.output_name).exists()
    return ConversionPlan(packages, skipped, output_dir)


def _dedupe_output_names(packages: list[PackagePlan]) -> None:
    """Disambiguate colliding output package names across a batch.

    Two packages whose manifest title+creator sanitise to the same
    package_folder_name would otherwise write into the same output folder,
    the second overwriting the first. Mirrors _assign_folder_names: the
    first package keeps the base name, later collisions get "_1", "_2", ...
    """
    seen: dict[str, int] = {}
    for pkg in packages:
        base = pkg.output_name
        count = seen.get(base, 0)
        pkg.output_name = base if count == 0 else f"{base}_{count}"
        seen[base] = count + 1


def execute_plan(plan: ConversionPlan,
                 progress: ProgressCallback | None = None) -> BatchResult:
    report = progress or (lambda done, total, msg: None)
    total = sum(p.texture_count + len(p.livery_names) + 2 for p in plan.packages) or 1
    base = 0
    results: list[ConversionResult] = []
    skipped = list(plan.skipped)
    for pkg in plan.packages:
        def shim(done, _total, msg, _base=base, _name=pkg.output_name):
            report(_base + done, total, f"[{_name}] {msg}")
        try:
            results.append(Converter(pkg.source, plan.output_dir, progress=shim,
                                     output_name=pkg.output_name).run())
        except Exception as exc:
            skipped.append((pkg.source, f"conversion failed: {exc}"))
        base += pkg.texture_count + len(pkg.livery_names) + 2
    if len(results) > 1 or skipped:
        package_gen.write_batch_report(plan.output_dir, results, skipped)
    return BatchResult(results, skipped)
