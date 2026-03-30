"""Odoo error traceback parsing and analysis commands."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

app = typer.Typer(help="Parse, analyze, and suggest fixes for Odoo tracebacks.")
console = Console()

# ---------------------------------------------------------------------------
# Error pattern database
# ---------------------------------------------------------------------------

_PATTERNS = [
    (
        r"AccessError",
        "Access denied to model/record",
        [
            "Check ir.model.access.csv — model may be missing access for user's group",
            "Check ir.rule record rules — domain may exclude this record for the user",
            "Verify user is in the correct security group",
        ],
    ),
    (
        r"ValidationError",
        "Python or SQL constraint violation",
        [
            "Check @api.constrains methods in the model",
            "Check SQL constraints (_sql_constraints) on the model",
            "Validate required field values before saving",
        ],
    ),
    (
        r"MissingError|Record does not exist",
        "Record deleted or ID is wrong",
        [
            "The record may have been deleted — refresh the view",
            "Check if 'active' field is set to False (archived)",
            "Verify the ID is correct before calling browse()",
        ],
    ),
    (
        r"External ID not found|ir\.model\.data.*not found",
        "XML external ID reference broken",
        [
            "Check data XML files for the referenced external ID",
            "Verify the module providing the external ID is installed",
            "Run: kctl-odoo modules upgrade <module> to reload data",
        ],
    ),
    (
        r"psycopg2\.IntegrityError|UniqueViolation|ForeignKeyViolation",
        "Database constraint violation",
        [
            "UniqueViolation: record with same unique key already exists",
            "ForeignKeyViolation: referenced record does not exist or is being deleted",
            "Check _sql_constraints on the model for the constraint name",
        ],
    ),
    (
        r"ParseError|lxml\.etree\.XMLSyntaxError",
        "XML syntax error in view definition",
        [
            "Run: kctl-odoo views validate to find the broken XML file",
            "Check for unclosed tags, invalid characters, or bad attribute syntax",
            "Use: kctl-odoo views parse <file> to inspect the XML structure",
        ],
    ),
    (
        r"UserError",
        "Business logic error raised intentionally",
        [
            "This is an intentional error raised by the module's business logic",
            "Read the error message carefully — it describes the constraint",
            "Check the model method that raised raise UserError(...)",
        ],
    ),
    (
        r"KeyError.*ir\.actions",
        "Action not found or not loaded",
        [
            "The action XML ID may be missing from data files",
            "Check if the module was upgraded after adding the action",
            "Run: kctl-odoo modules upgrade <module>",
        ],
    ),
    (
        r"AttributeError.*recordset",
        "Attribute access on wrong recordset type",
        [
            "Check if the field exists on the model",
            "Verify you are not accessing a Many2many/One2many as a scalar",
            "Use .mapped() instead of direct attribute access on multi-record sets",
        ],
    ),
]

# ---------------------------------------------------------------------------
# Parser helpers
# ---------------------------------------------------------------------------


def _extract_tracebacks(text: str) -> list[dict]:
    """Extract structured traceback info from Odoo log text."""
    results = []
    # Match Python tracebacks
    tb_pattern = re.compile(r"Traceback \(most recent call last\):(.*?)(?=\n\S|\Z)", re.DOTALL)

    for match in tb_pattern.finditer(text):
        tb_text = match.group(0)

        # Extract error type and message
        error_match = re.search(r"(\w+(?:\.\w+)*Error[^\n]*|(?:odoo\.exceptions\.\w+)[^\n]*)", tb_text)
        error_type = error_match.group(1) if error_match else "Unknown"

        # Extract module mentions from file paths
        module_matches = re.findall(r"addons/(\w+)/", tb_text)
        modules = list(dict.fromkeys(module_matches))  # deduplicate, preserve order

        # Extract model from error context
        model_match = re.search(r'"([a-z][a-z0-9.]+\.[a-z][a-z0-9._]+)"', tb_text)
        model = model_match.group(1) if model_match else ""

        # Extract method from last File line
        method_match = re.search(r"in (\w+)\s*\n", tb_text)
        method = method_match.group(1) if method_match else ""

        results.append(
            {
                "error_type": error_type,
                "modules": modules,
                "model": model,
                "method": method,
                "text": tb_text[:1000],
            }
        )

    return results


def _suggest_fixes(error_text: str) -> list[tuple[str, str, list[str]]]:
    """Return matching patterns for the given error text."""
    matches = []
    for pattern, description, suggestions in _PATTERNS:
        if re.search(pattern, error_text):
            matches.append((pattern, description, suggestions))
    return matches


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command("parse")
def parse_traceback(
    logfile: Annotated[str, typer.Argument(help="Log file path or - for stdin")],
) -> None:
    """Extract module, model, method, error type from Odoo tracebacks."""
    if logfile == "-":
        text = sys.stdin.read()
    else:
        path = Path(logfile)
        if not path.exists():
            console.print(f"[red]ERROR[/red] File not found: {logfile}")
            raise typer.Exit(1)
        text = path.read_text(encoding="utf-8", errors="replace")

    tracebacks = _extract_tracebacks(text)

    if not tracebacks:
        console.print("[green]No Python tracebacks found in input.[/green]")
        return

    console.print(f"\n[bold]Found {len(tracebacks)} traceback(s):[/bold]\n")
    for i, tb in enumerate(tracebacks, 1):
        console.print(f"[bold cyan]--- Traceback {i} ---[/bold cyan]")
        console.print(f"  Error:   [red]{tb['error_type']}[/red]")
        if tb["modules"]:
            console.print(f"  Modules: [cyan]{', '.join(tb['modules'])}[/cyan]")
        if tb["model"]:
            console.print(f"  Model:   [cyan]{tb['model']}[/cyan]")
        if tb["method"]:
            console.print(f"  Method:  [cyan]{tb['method']}[/cyan]")
        console.print()


@app.command("analyze")
def analyze_traceback(
    logfile: Annotated[str, typer.Argument(help="Log file path to analyze")],
) -> None:
    """Pattern-match common errors in a log file and suggest fixes."""
    path = Path(logfile)
    if not path.exists():
        console.print(f"[red]ERROR[/red] File not found: {logfile}")
        raise typer.Exit(1)

    text = path.read_text(encoding="utf-8", errors="replace")
    tracebacks = _extract_tracebacks(text)

    if not tracebacks:
        console.print("[green]No tracebacks found.[/green]")
        return

    console.print(f"\n[bold]Analyzing {len(tracebacks)} traceback(s)...[/bold]\n")

    for i, tb in enumerate(tracebacks, 1):
        matches = _suggest_fixes(tb["text"])
        console.print(f"[bold cyan]--- Traceback {i} ---[/bold cyan]")
        console.print(f"  [red]{tb['error_type']}[/red]")

        if matches:
            for _pattern, description, suggestions in matches:
                console.print(f"\n  [yellow]Diagnosis:[/yellow] {description}")
                console.print("  [bold]Suggestions:[/bold]")
                for suggestion in suggestions:
                    console.print(f"    • {suggestion}")
        else:
            console.print("  [dim]No matching pattern — see traceback for details[/dim]")
        console.print()


@app.command("suggest")
def suggest_fix(
    error_text: Annotated[str, typer.Argument(help="Error message or exception type to analyze")],
) -> None:
    """Given an error message, suggest cause and fix."""
    matches = _suggest_fixes(error_text)

    if not matches:
        console.print(f"[yellow]No specific pattern matched for:[/yellow] {error_text}")
        console.print("\nGeneral suggestions:")
        console.print("  • Check Odoo server logs for full traceback")
        console.print("  • Run: kctl-odoo traceback recent")
        console.print("  • Verify module is upgraded: kctl-odoo modules upgrade <module>")
        return

    console.print(f"\n[bold]Analysis for:[/bold] {error_text}\n")
    for _pattern, description, suggestions in matches:
        console.print(f"[yellow]Diagnosis:[/yellow] {description}")
        console.print("[bold]Suggested fixes:[/bold]")
        for suggestion in suggestions:
            console.print(f"  • {suggestion}")
        console.print()


@app.command("recent")
def recent_tracebacks(
    count: Annotated[int, typer.Option("--count", help="Number of recent tracebacks to show")] = 10,
    service: Annotated[str, typer.Option("--service", help="Docker service name")] = "odoo",
) -> None:
    """Show last N tracebacks from Docker logs."""
    try:
        result = subprocess.run(
            ["docker", "compose", "logs", "--no-color", "--tail", "2000", service],
            capture_output=True,
            text=True,
            timeout=15,
        )
        log_text = result.stdout + result.stderr
    except FileNotFoundError:
        console.print("[red]ERROR[/red] docker not found. Check your Docker installation.")
        raise typer.Exit(1) from None
    except subprocess.TimeoutExpired:
        console.print("[red]ERROR[/red] docker logs timed out.")
        raise typer.Exit(1) from None

    if not log_text.strip():
        console.print("[yellow]No logs found. Is the service running?[/yellow]")
        console.print(f"  docker compose logs {service}")
        return

    tracebacks = _extract_tracebacks(log_text)

    if not tracebacks:
        console.print(f"[green]No tracebacks found in recent {service} logs.[/green]")
        return

    recent = tracebacks[-count:]
    console.print(f"\n[bold]Last {len(recent)} traceback(s) from {service}:[/bold]\n")

    for i, tb in enumerate(recent, 1):
        console.print(f"[bold cyan]--- {i} ---[/bold cyan]")
        console.print(f"  Error:   [red]{tb['error_type']}[/red]")
        if tb["modules"]:
            console.print(f"  Modules: [cyan]{', '.join(tb['modules'])}[/cyan]")
        if tb["model"]:
            console.print(f"  Model:   [cyan]{tb['model']}[/cyan]")
        matches = _suggest_fixes(tb["text"])
        if matches:
            console.print(f"  Hint:    [yellow]{matches[0][1]}[/yellow]")
        console.print()
