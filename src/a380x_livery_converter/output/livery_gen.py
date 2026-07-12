"""Generation of livery.cfg, texture.CFG and thumbnails for one converted livery."""

from pathlib import Path

from PIL import Image

from a380x_livery_converter import resource_path
from a380x_livery_converter.core.scanner import Variant

TEXTURE_CFG = (
    "[fltsim]\n"
    "fallback.1=..\\..\\..\\common\\texture\n"
    "fallback.2=..\\..\\FlyByWire_A380_842\\texture\n"
    "fallback.3=..\\..\\..\\..\\texture\\DetailMap\n"
    "fallback.4=..\\..\\..\\..\\texture\\Glass\n"
    "fallback.5=..\\..\\..\\..\\texture\\Interiors\n"
    "fallback.6=..\\..\\..\\..\\texture\n"
)

THUMBNAIL_SIZES = {
    "thumbnail.png": (720, 344),
    "thumbnail_button.png": (830, 260),
    "thumbnail_side.png": (930, 340),
}

_THUMBNAIL_NAMES = {"THUMBNAIL.JPG", "THUMBNAIL.PNG", "THUMBNAIL.JPEG"}


def livery_cfg_text(variant: Variant) -> str:
    name = variant.ui_variation or variant.title
    return (
        "[version]\n"
        "major = 1\n"
        "minor = 0\n"
        "\n"
        "[GENERAL]\n"
        f'Name = "{name}"\n'
        f'atc_id="{variant.atc_id}"\n'
        f'atc_parking_codes="{variant.icao_airline}"\n'
        f'icao_airline="{variant.icao_airline}"\n'
        f'atc_airline="{variant.atc_airline}"\n'
    )


def write_texture_cfg(texture_dir: Path) -> None:
    Path(texture_dir).mkdir(parents=True, exist_ok=True)
    (Path(texture_dir) / "texture.CFG").write_text(TEXTURE_CFG, encoding="utf-8")


def find_old_thumbnail(texture_dir: Path | None) -> Path | None:
    if texture_dir is None or not Path(texture_dir).is_dir():
        return None
    for child in Path(texture_dir).iterdir():
        if child.name.upper() in _THUMBNAIL_NAMES and child.is_file():
            return child
    return None


def write_thumbnails(src_image: Path | None, thumb_dir: Path) -> list[str]:
    thumb_dir = Path(thumb_dir)
    thumb_dir.mkdir(parents=True, exist_ok=True)
    warnings: list[str] = []
    if src_image is None:
        warnings.append("No source thumbnail found - using paintkit placeholders")
    for name, size in THUMBNAIL_SIZES.items():
        if src_image is not None:
            img = Image.open(src_image).convert("RGB")
            out = _cover_resize(img, size)
        else:
            out = Image.open(resource_path(f"thumbnails/{name}"))
        out.save(thumb_dir / name)
    return warnings


def _cover_resize(img: Image.Image, size: tuple[int, int]) -> Image.Image:
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - target_h) // 2
    return resized.crop((left, top, left + target_w, top + target_h))
