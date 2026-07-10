"""Tolerant parser for MSFS aircraft.cfg / livery.cfg style files."""


def parse_cfg(text: str) -> dict[str, dict[str, str]]:
    sections: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith((";", "#", "//")):
            continue
        if line.startswith("[") and "]" in line:
            name = line[1 : line.index("]")].strip().upper()
            current = sections.setdefault(name, {})
            continue
        if "=" not in line or current is None:
            continue
        key, _, value = line.partition("=")
        value = _strip_inline_comment(value).strip()
        if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
            value = value[1:-1]
        current[key.strip().lower()] = value
    return sections


def _strip_inline_comment(value: str) -> str:
    in_quotes = False
    for i, ch in enumerate(value):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == ";" and not in_quotes:
            return value[:i]
    return value


def fltsim_sections(sections: dict[str, dict[str, str]]) -> list[tuple[int, dict[str, str]]]:
    result = []
    for name, body in sections.items():
        if name.startswith("FLTSIM."):
            suffix = name.split(".", 1)[1]
            if suffix.isdigit():
                result.append((int(suffix), body))
    return sorted(result, key=lambda pair: pair[0])
