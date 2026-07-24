"""Tkinter GUI front end."""

import importlib.metadata
import os
import queue
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from a380x_livery_converter.converter import (
    DEFAULT_MAX_WORKERS, ConversionCancelled, execute_plan, plan_conversion,
)

RELEASES_URL = "https://github.com/ToLaTE4u/FBWA380LiveryConverter/releases/latest"


def open_releases_page() -> None:
    """Open the tool's GitHub releases page in the default browser."""
    webbrowser.open(RELEASES_URL)


class ConverterApp:
    def __init__(self, root: tk.Tk, version: str = "dev"):
        self.root = root
        root.title(f"FBW A380X Livery Converter v{version} (MSFS 2020 -> 2024)")
        root.geometry("700x480")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.queue: queue.Queue = queue.Queue()
        self._busy = False
        self._plan = None
        self._output_dir: Path | None = None
        self._cancel = threading.Event()

        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)
        self._folder_row(frame, 0, "Old livery package or folder:", self.input_var)
        self._folder_row(frame, 1, "Output folder (Community):", self.output_var)

        buttons = ttk.Frame(frame)
        buttons.grid(row=2, column=0, columnspan=3, pady=8, sticky="ew")
        self.analyze_button = ttk.Button(buttons, text="Analyze", command=self.analyze)
        self.analyze_button.pack(side="left")
        self.convert_button = ttk.Button(buttons, text="Convert", command=self.convert,
                                         state="disabled")
        self.convert_button.pack(side="left", padx=6)
        self.cancel_button = ttk.Button(buttons, text="Cancel", command=self.cancel,
                                        state="disabled")
        self.cancel_button.pack(side="left")
        self.open_folder_button = ttk.Button(buttons, text="Open Output Folder",
                                             command=self._open_folder, state="disabled")
        self.open_folder_button.pack(side="left", padx=6)
        self.updates_button = ttk.Button(buttons, text="Check for Updates",
                                         command=open_releases_page)
        self.updates_button.pack(side="right")
        self.workers_var = tk.IntVar(value=DEFAULT_MAX_WORKERS)
        self.workers_spin = ttk.Spinbox(buttons, from_=1, to=64,
                                        textvariable=self.workers_var, width=4)
        self.workers_spin.pack(side="right")
        ttk.Label(buttons, text="Workers:").pack(side="right", padx=(12, 0))

        self.progressbar = ttk.Progressbar(frame, maximum=100)
        self.progressbar.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.log = scrolledtext.ScrolledText(frame, height=16, state="disabled")
        self.log.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        self.log.bind("<1>", lambda e: self.log.focus_set())
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

    def _folder_row(self, parent, row, label, var):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=4)
        ttk.Button(parent, text="Browse...",
                   command=lambda: var.set(filedialog.askdirectory() or var.get())
                   ).grid(row=row, column=2)

    def analyze(self):
        input_dir, output_dir = self.input_var.get().strip(), self.output_var.get().strip()
        if not input_dir or not output_dir:
            self._append_log("Please select both folders.")
            return
        self._busy = True
        self._cancel.clear()
        self.progressbar.config(value=0)
        self._set_buttons(analyze=False, convert=False, cancel=True)
        workers = self.workers_var.get()
        self._append_log(f"Analyzing with {workers} worker(s)...")
        threading.Thread(target=self._do_analyze,
                         args=(Path(input_dir), Path(output_dir), workers),
                         daemon=True).start()
        self.root.after(100, self._poll)

    def _do_analyze(self, input_dir, output_dir, max_workers):
        try:
            plan = plan_conversion(
                input_dir, output_dir,
                progress=lambda d, t, m: self.queue.put(("progress", d, t, m)),
                cancel=self._cancel, max_workers=max_workers)
            self.queue.put(("plan", plan))
        except ConversionCancelled:
            self.queue.put(("cancelled",))
        except Exception as exc:
            self.queue.put(("error", exc))

    def convert(self):
        if self._plan is None:
            return
        existing = [pkg.output_name for pkg in self._plan.packages if pkg.exists]
        if existing and not messagebox.askyesno(
                "Overwrite?",
                f"{len(existing)} package(s) already exist and will be overwritten:\n"
                + "\n".join(existing) + "\n\nOverwrite?"):
            return
        self._busy = True
        self._cancel.clear()
        self._set_buttons(analyze=False, convert=False, cancel=True)
        self.progressbar.config(value=0)
        workers = self.workers_var.get()
        threading.Thread(target=self._do_convert, args=(self._plan, workers),
                         daemon=True).start()
        self.root.after(100, self._poll)

    def _do_convert(self, plan, max_workers):
        try:
            result = execute_plan(
                plan, progress=lambda d, t, m: self.queue.put(("progress", d, t, m)),
                cancel=self._cancel, max_workers=max_workers)
            self.queue.put(("done", result))
        except ConversionCancelled:
            self.queue.put(("cancelled",))
        except Exception as exc:
            self.queue.put(("error", exc))

    def cancel(self):
        if self._busy:
            # A worker thread is running: ask it to stop and let _poll report
            # back. It finishes the texture currently in texconv first.
            self._cancel.set()
            self.cancel_button.config(state="disabled")
            self._append_log("Cancelling, waiting for the running texture...")
            return
        self._plan = None
        self._output_dir = None
        self.open_folder_button.config(state="disabled")
        self._append_log("Cancelled.")
        self._reset()

    def _poll(self):
        while not self.queue.empty():
            item = self.queue.get_nowait()
            kind = item[0]
            if kind == "plan":
                self._plan = item[1]
                self._show_plan(self._plan)
            elif kind == "progress":
                _, done, total, message = item
                self.progressbar.config(maximum=total, value=done)
                self._append_log(f"[{done}/{total}] {message}")
            elif kind == "done":
                self._show_result(item[1])
                self._plan = None
                self._reset()
            elif kind == "cancelled":
                self._append_log("Cancelled.")
                self._plan = None
                self._reset()
            elif kind == "error":
                self._append_log(f"ERROR: {item[1]}")
                self._plan = None
                self._output_dir = None
                self.open_folder_button.config(state="disabled")
                self._reset()
        if self._busy:
            self.root.after(100, self._poll)

    def _show_plan(self, plan):
        self._busy = False
        self._append_log(f"Found {plan.package_count} package(s), {plan.livery_count} "
                         f"liveries, {plan.texture_count} textures:")
        for pkg in plan.packages:
            marker = " (already exists - will be overwritten)" if pkg.exists else ""
            self._append_log(f"  - {pkg.output_name}: {len(pkg.livery_names)} liveries, "
                             f"{pkg.texture_count} textures{marker}")
            for warning in pkg.warnings:
                self._append_log(f"      WARNING: {warning}")
        for path, reason in plan.skipped:
            self._append_log(f"  - skipped {Path(path).name}: {reason}")
        if plan.packages:
            self._append_log("Review above, then Convert or Cancel.")
            self._set_buttons(analyze=True, convert=True, cancel=True)
        else:
            self._append_log("Nothing to convert.")
            self._set_buttons(analyze=True, convert=False, cancel=False)

    def _show_result(self, result):
        self.progressbar.config(value=self.progressbar["maximum"])
        if result.results:
            self._output_dir = result.results[0].output_root.parent
            self.open_folder_button.config(state="normal")
        self._append_log("")
        self._append_log(f"Done: {result.converted} textures converted, "
                         f"{result.skipped_textures} skipped.")
        for warning in result.warnings:
            self._append_log(f"WARNING: {warning}")
        for res in result.results:
            self._append_log(f"Output: {res.output_root}")
        for path, reason in result.skipped:
            self._append_log(f"SKIPPED {Path(path).name}: {reason}")

    def _open_folder(self):
        if self._output_dir is not None:
            os.startfile(str(self._output_dir))

    def _reset(self):
        self._busy = False
        if self._output_dir is None:
            self.open_folder_button.config(state="disabled")
        self._set_buttons(analyze=True, convert=False, cancel=False)

    def _set_buttons(self, analyze, convert, cancel):
        self.analyze_button.config(state="normal" if analyze else "disabled")
        self.convert_button.config(state="normal" if convert else "disabled")
        self.cancel_button.config(state="normal" if cancel else "disabled")

    def _append_log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main() -> None:
    try:
        version = importlib.metadata.version("a380x-livery-converter")
    except importlib.metadata.PackageNotFoundError:
        version = "dev"
    root = tk.Tk()
    texconv_path = Path(__file__).parent / "resources" / "texconv.exe"
    if not texconv_path.exists():
        messagebox.showerror("Missing dependency", "texconv.exe not found in resources. The application cannot convert textures without it.")
        return
    icon_path = Path(__file__).parent / "resources" / "app.ico"
    if icon_path.exists():
        root.iconbitmap(str(icon_path))
    ConverterApp(root, version=version)
    root.mainloop()
