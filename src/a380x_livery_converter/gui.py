"""Tkinter GUI front end."""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from a380x_livery_converter.converter import execute_plan, plan_conversion


class ConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("FBW A380X Livery Converter (MSFS 2020 -> 2024)")
        root.geometry("700x480")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.queue: queue.Queue = queue.Queue()
        self._busy = False
        self._plan = None

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

        self.progressbar = ttk.Progressbar(frame, maximum=100)
        self.progressbar.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.log = scrolledtext.ScrolledText(frame, height=16, state="disabled")
        self.log.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
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
        self._set_buttons(analyze=False, convert=False, cancel=False)
        self._append_log("Analyzing...")
        threading.Thread(target=self._do_analyze,
                         args=(Path(input_dir), Path(output_dir)), daemon=True).start()
        self.root.after(100, self._poll)

    def _do_analyze(self, input_dir, output_dir):
        try:
            self.queue.put(("plan", plan_conversion(input_dir, output_dir)))
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
        self._set_buttons(analyze=False, convert=False, cancel=False)
        self.progressbar.config(value=0)
        threading.Thread(target=self._do_convert, args=(self._plan,), daemon=True).start()
        self.root.after(100, self._poll)

    def _do_convert(self, plan):
        try:
            result = execute_plan(
                plan, progress=lambda d, t, m: self.queue.put(("progress", d, t, m)))
            self.queue.put(("done", result))
        except Exception as exc:
            self.queue.put(("error", exc))

    def cancel(self):
        self._plan = None
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
            elif kind == "error":
                self._append_log(f"ERROR: {item[1]}")
                self._plan = None
                self._reset()
        if self._busy:
            self.root.after(100, self._poll)

    def _show_plan(self, plan):
        self._busy = False
        self._append_log(f"Found {plan.package_count} package(s), {plan.livery_count} "
                         f"liveries, {plan.texture_count} textures:")
        for pkg in plan.packages:
            marker = " (already exists — will be overwritten)" if pkg.exists else ""
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
        self._append_log("")
        self._append_log(f"Done: {result.converted} textures converted, "
                         f"{result.skipped_textures} skipped.")
        for warning in result.warnings:
            self._append_log(f"WARNING: {warning}")
        for res in result.results:
            self._append_log(f"Output: {res.output_root}")
        for path, reason in result.skipped:
            self._append_log(f"SKIPPED {Path(path).name}: {reason}")

    def _reset(self):
        self._busy = False
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
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()
