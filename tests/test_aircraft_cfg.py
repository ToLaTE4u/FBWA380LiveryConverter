from a380x_livery_converter.core.aircraft_cfg import parse_cfg, fltsim_sections

REAL_SNIPPET = """
[VERSION]
major = 1
minor = 0

[VARIATION]
base_container = "..\\FlyByWire_A380_842"

;===================== FLTSIM =====================

[FLTSIM.0]
title = "HUES QATAR AIRWAYS A7-APC 2025 A380" ; Variation name
ui_variation = "HUES QATAR AIRWAYS A7-APC 2025 A380"
texture = "A7APC" ; texture folder
model = "QTR" ; model folder
atc_id = "A380X" ; tail number
atc_airline = "Qatar Airways" ; airline name
"""


def test_parses_sections_and_strips_quotes_and_comments():
    cfg = parse_cfg(REAL_SNIPPET)
    assert cfg["VARIATION"]["base_container"] == "..\\FlyByWire_A380_842"
    assert cfg["FLTSIM.0"]["title"] == "HUES QATAR AIRWAYS A7-APC 2025 A380"
    assert cfg["FLTSIM.0"]["texture"] == "A7APC"
    assert cfg["FLTSIM.0"]["atc_airline"] == "Qatar Airways"


def test_section_names_case_insensitive_keys_lowercased():
    cfg = parse_cfg("[fltsim.0]\nTITLE = x\n")
    assert cfg["FLTSIM.0"]["title"] == "x"


def test_semicolon_inside_quotes_is_kept():
    cfg = parse_cfg('[A]\nk = "a;b" ; comment\n')
    assert cfg["A"]["k"] == "a;b"


def test_fltsim_sections_sorted():
    cfg = parse_cfg("[FLTSIM.2]\na=2\n[FLTSIM.0]\na=0\n[FLTSIM.10]\na=10\n[GENERAL]\nx=y\n")
    result = fltsim_sections(cfg)
    assert [n for n, _ in result] == [0, 2, 10]
    assert result[2][1]["a"] == "10"


def test_blank_lines_and_garbage_ignored():
    cfg = parse_cfg("\n\n;only comment\nnokey_novalue\n[S]\nk=v\n")
    assert cfg == {"S": {"k": "v"}}
