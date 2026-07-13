"""Command line front end."""

from pathlib import Path

import typer

from a380x_livery_converter.converter import (
    ConversionPlan, execute_plan, plan_conversion,
)

app = typer.Typer(add_completion=False,
                  help="Convert FBW A380X MSFS 2020 liveries to native MSFS 2024 packages.")


def _print_plan(plan: ConversionPlan) -> None:
    typer.echo(f"Found {plan.package_count} package(s), {plan.livery_count} liveries, "
               f"{plan.texture_count} textures:")
    for pkg in plan.packages:
        typer.echo(f"  - {pkg.output_name}: {len(pkg.livery_names)} liveries, "
                   f"{pkg.texture_count} textures")
        for warning in pkg.warnings:
            typer.secho(f"      WARNING: {warning}", fg=typer.colors.YELLOW)
    for path, reason in plan.skipped:
        typer.secho(f"  - skipped {Path(path).name}: {reason}", fg=typer.colors.YELLOW)


@app.command()
def convert(
    input_dir: Path = typer.Argument(..., exists=True, file_okay=False,
                                     help="Old livery package or a folder of packages"),
    output: Path = typer.Option(..., "--output", "-o", file_okay=False,
                                help="Destination folder, e.g. the Community folder"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show the plan and exit"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show per-file progress"),
) -> None:
    try:
        plan = plan_conversion(input_dir, output)
    except Exception as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)

    _print_plan(plan)
    if not plan.packages:
        typer.secho("No convertible A380X liveries found.", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    if dry_run:
        raise typer.Exit(0)
    if not yes and not typer.confirm(
            f"Convert {plan.livery_count} liveries in {plan.package_count} package(s)?"):
        typer.echo("Cancelled.")
        raise typer.Exit(0)

    def progress(done: int, total: int, message: str) -> None:
        if verbose:
            typer.echo(f"[{done}/{total}] {message}")

    try:
        result = execute_plan(plan, progress=progress)
    except Exception as exc:
        typer.secho(f"Unexpected error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    for res in result.results:
        typer.echo(f"Output: {res.output_root}")
    typer.echo(f"Converted textures: {result.converted}, skipped: {result.skipped_textures}")
    for warning in result.warnings:
        typer.secho(f"WARNING: {warning}", fg=typer.colors.YELLOW)
    for path, reason in result.skipped:
        typer.secho(f"SKIPPED {Path(path).name}: {reason}", fg=typer.colors.YELLOW)
    if not result.results:
        typer.secho("No packages were converted.", fg=typer.colors.RED, err=True)
        raise typer.Exit(2)
    if result.warnings or result.skipped_textures or result.skipped:
        raise typer.Exit(1)
