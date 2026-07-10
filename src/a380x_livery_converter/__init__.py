from pathlib import Path

def resource_path(name: str) -> Path:
    """Path to a bundled resource file (works from source and Nuitka onefile)."""
    return Path(__file__).parent / "resources" / name
