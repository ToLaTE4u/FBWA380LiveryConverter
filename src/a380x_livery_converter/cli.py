"""Command line front end."""

from pathlib import Path

import typer

from a380x_livery_converter.converter import Converter
from a380x_livery_converter.core.scanner import NotAnA380XPackageError

app = typer.Typer(add_completion=False,
                  help="Convert FBW A380X MSFS 2020 liveries to native MSFS 2024 packages.")


@app.command()
def convert(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False,
                                     help="Old livery package folder (extracted)"),
    output: Path = typer.Option(..., "--output", "-o", file_okay=False,
                                help="Destination folder, e.g. the Community folder"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Scan and plan only, write nothing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-file progress"),
) -> None:
    def progress(done: int, total: int, message: str) -> None:
        if verbose:
            typer.echo(f"[{done}/{total}] {message}")

    try:
        result = Converter(input_dir, output, progress=progress, dry_run=dry_run).run()
    except NotAnA380XPackageError as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    except Exception as exc:
        typer.secho(f"Unexpected error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    typer.echo(f"Output: {result.output_root}")
    typer.echo(f"Converted textures: {result.converted}, skipped: {result.skipped}")
    for warning in result.warnings:
        typer.secho(f"WARNING: {warning}", fg=typer.colors.YELLOW)
    if result.warnings or result.skipped:
        raise typer.Exit(1)
