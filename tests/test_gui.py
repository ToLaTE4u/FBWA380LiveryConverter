import tkinter as tk

import pytest


def _make_root():
    try:
        return tk.Tk()
    except tk.TclError:
        pytest.skip("no display available")


def test_app_builds_widgets():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        assert str(app.convert_button.cget("state")) != "disabled"
        assert app.progressbar is not None
    finally:
        root.destroy()


def test_start_without_folders_logs_hint_and_stays_enabled():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        app.start()
        assert "Bitte beide Ordner" in app.log.get("1.0", "end")
        assert str(app.convert_button.cget("state")) != "disabled"
    finally:
        root.destroy()
