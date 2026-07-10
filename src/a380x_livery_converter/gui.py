"""Tkinter GUI front end."""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, scrolledtext, ttk

from a380x_livery_converter.converter import Converter


class ConverterApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("FBW A380X Livery Converter (MSFS 2020 -> 2024)")
        root.geometry("680x440")
        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.queue: queue.Queue = queue.Queue()
        self._running = False

        frame = ttk.Frame(root, padding=10)
        frame.pack(fill="both", expand=True)
        self._folder_row(frame, 0, "Altes Livery-Paket:", self.input_var)
        self._folder_row(frame, 1, "Ausgabeordner (Community):", self.output_var)
        self.convert_button = ttk.Button(frame, text="Konvertieren", command=self.start)
        self.convert_button.grid(row=2, column=0, columnspan=3, pady=8, sticky="ew")
        self.progressbar = ttk.Progressbar(frame, maximum=100)
        self.progressbar.grid(row=3, column=0, columnspan=3, sticky="ew")
        self.log = scrolledtext.ScrolledText(frame, height=14, state="disabled")
        self.log.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(8, 0))
        frame.columnconfigure(1, weight=1)
        frame.rowconfigure(4, weight=1)

    def _folder_row(self, parent, row, label, var):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", padx=4)
        ttk.Button(parent, text="...", width=4,
                   command=lambda: var.set(filedialog.askdirectory() or var.get())
                   ).grid(row=row, column=2)

    def start(self):
        input_dir, output_dir = self.input_var.get().strip(), self.output_var.get().strip()
        if not input_dir or not output_dir:
            self._append_log("Bitte beide Ordner auswählen.")
            return
        self._running = True
        self.convert_button.config(state="disabled")
        self.progressbar.config(value=0)
        threading.Thread(target=self._work, args=(Path(input_dir), Path(output_dir)),
                         daemon=True).start()
        self.root.after(100, self._poll)

    def _work(self, input_dir: Path, output_dir: Path):
        try:
            result = Converter(
                input_dir, output_dir,
                progress=lambda d, t, m: self.queue.put(("progress", d, t, m)),
            ).run()
            self.queue.put(("done", result))
        except Exception as exc:  # GUI boundary: show any failure instead of crashing
            self.queue.put(("error", exc))

    def _poll(self):
        while not self.queue.empty():
            item = self.queue.get_nowait()
            if item[0] == "progress":
                _, done, total, message = item
                self.progressbar.config(maximum=total, value=done)
                self._append_log(f"[{done}/{total}] {message}")
            elif item[0] == "done":
                result = item[1]
                self._append_log("")
                self._append_log(f"Fertig: {result.converted} Texturen konvertiert, "
                                 f"{result.skipped} übersprungen.")
                for warning in result.warnings:
                    self._append_log(f"WARNUNG: {warning}")
                self._append_log(f"Ausgabe: {result.output_root}")
                self._append_log("Details: conversion_report.txt im Ausgabepaket.")
                self._finish()
            elif item[0] == "error":
                self._append_log(f"FEHLER: {item[1]}")
                self._finish()
        if self._running:
            self.root.after(100, self._poll)

    def _finish(self):
        self._running = False
        self.convert_button.config(state="normal")

    def _append_log(self, text: str):
        self.log.config(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.config(state="disabled")


def main() -> None:
    root = tk.Tk()
    ConverterApp(root)
    root.mainloop()
