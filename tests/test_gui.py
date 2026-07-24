import threading
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
        assert str(app.analyze_button.cget("state")) != "disabled"
        assert str(app.convert_button.cget("state")) == "disabled"
        assert app.progressbar is not None
    finally:
        root.destroy()


def test_analyze_without_folders_logs_hint():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        app.analyze()
        assert "Please select both folders." in app.log.get("1.0", "end")
        assert str(app.analyze_button.cget("state")) != "disabled"
    finally:
        root.destroy()


def test_releases_url_targets_repo_releases():
    from a380x_livery_converter import gui as gui_mod
    assert gui_mod.RELEASES_URL == (
        "https://github.com/ToLaTE4u/FBWA380LiveryConverter/releases/latest")


def test_open_releases_page_opens_browser(monkeypatch):
    from a380x_livery_converter import gui as gui_mod
    opened = []
    monkeypatch.setattr(gui_mod.webbrowser, "open", lambda url: opened.append(url))
    gui_mod.open_releases_page()
    assert opened == [gui_mod.RELEASES_URL]


def test_updates_button_present_and_enabled():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        assert app.updates_button.cget("text") == "Check for Updates"
        assert str(app.updates_button.cget("state")) != "disabled"
    finally:
        root.destroy()


def test_cancel_button_enabled_while_analyzing(monkeypatch):
    """Fix 2: Analyze used to disable every button, leaving a dead window for
    the minutes it spends hashing textures."""
    from a380x_livery_converter import gui as gui_mod
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        started = threading.Event()
        release = threading.Event()

        def blocking_plan(input_dir, output_dir, progress=None, cancel=None, max_workers=None):
            started.set()
            release.wait(5)
            raise gui_mod.ConversionCancelled("cancelled")

        monkeypatch.setattr(gui_mod, "plan_conversion", blocking_plan)
        app.input_var.set(str(root and "."))
        app.output_var.set(".")
        app.analyze()
        assert started.wait(5)
        assert str(app.cancel_button.cget("state")) == "normal"
        app.cancel()
        assert app._cancel.is_set()
        release.set()
    finally:
        root.destroy()


def test_cancelled_worker_resets_ui():
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        app._busy = True
        app.queue.put(("cancelled",))
        app._poll()
        assert app._busy is False
        assert app._plan is None
        assert "Cancelled." in app.log.get("1.0", "end")
        assert str(app.analyze_button.cget("state")) == "normal"
    finally:
        root.destroy()


def test_convert_declined_overwrite_does_not_start(monkeypatch):
    from types import SimpleNamespace

    from a380x_livery_converter import gui as gui_mod
    from a380x_livery_converter.gui import ConverterApp
    root = _make_root()
    try:
        app = ConverterApp(root)
        app._plan = SimpleNamespace(packages=[
            SimpleNamespace(output_name="foo", exists=True,
                            livery_names=["l"], texture_count=1, warnings=[])])
        monkeypatch.setattr(gui_mod.messagebox, "askyesno", lambda *a, **k: False)
        app.convert()
        assert app._busy is False
    finally:
        root.destroy()
