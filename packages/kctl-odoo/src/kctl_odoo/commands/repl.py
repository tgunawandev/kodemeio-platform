"""Interactive ORM REPL for Odoo exploration."""

from __future__ import annotations

import cmd
import fnmatch
import json
import shlex
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.client import OdooClient

app = typer.Typer(help="Interactive ORM exploration.")

_console = Console()


class OdooREPL(cmd.Cmd):
    """Interactive REPL for Odoo ORM exploration via JSON-RPC."""

    prompt = "odoo> "
    intro = (
        "Odoo ORM REPL - Type 'help' for available commands, 'quit' to exit.\n"
        "Tip: Use Tab for model name completion after loading models with 'models'."
    )

    def __init__(self, client: OdooClient) -> None:
        super().__init__()
        self._client = client
        self._model_names: list[str] = []

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _load_models(self) -> list[str]:
        """Fetch and cache model names from ir.model."""
        if not self._model_names:
            _console.print("[dim]Loading model list...[/dim]")
            records = self._client.search_read(
                "ir.model",
                fields=["model"],
                limit=0,
                order="model",
            )
            self._model_names = sorted(r["model"] for r in records)
            _console.print(f"[dim]Cached {len(self._model_names)} models.[/dim]")
        return self._model_names

    def _complete_model(self, text: str) -> list[str]:
        models = self._model_names or []
        return [m for m in models if m.startswith(text)]

    def _parse_domain(self, raw: str) -> list:
        """Parse a JSON domain string, default to empty domain."""
        raw = raw.strip()
        if not raw:
            return []
        return json.loads(raw)

    def _print_records_table(self, records: list[dict], title: str = "") -> None:
        if not records:
            _console.print("[dim]No records found.[/dim]")
            return
        keys = list(records[0].keys())
        table = Table(title=title or f"{len(records)} record(s)", show_header=True, header_style="bold cyan")
        for k in keys:
            table.add_column(k, overflow="fold")
        for rec in records:
            table.add_row(*(str(rec.get(k, "")) for k in keys))
        _console.print(table)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def do_search(self, line: str) -> None:
        """search <model> [domain_json] [--limit N]
        Search records. Example: search res.partner [["is_company","=",true]] --limit 5"""
        try:
            parts = shlex.split(line)
        except ValueError as e:
            _console.print(f"[red]Parse error:[/red] {e}")
            return

        if not parts:
            _console.print("[red]Usage:[/red] search <model> [domain] [--limit N]")
            return

        model = parts[0]
        limit = 10
        domain_str = ""

        i = 1
        while i < len(parts):
            if parts[i] == "--limit" and i + 1 < len(parts):
                limit = int(parts[i + 1])
                i += 2
            else:
                domain_str = parts[i]
                i += 1

        try:
            domain = self._parse_domain(domain_str)
            records = self._client.search_read(model, domain=domain, limit=limit)
            self._print_records_table(records, f"{model} (limit={limit})")
        except Exception as e:
            _console.print(f"[red]Error:[/red] {e}")

    def complete_search(self, text: str, _line: str, _begidx: int, _endidx: int) -> list[str]:
        return self._complete_model(text)

    def do_read(self, line: str) -> None:
        """read <model> <id> [field1,field2,...]
        Read a single record by ID. Example: read res.partner 1 name,email"""
        parts = line.split()
        if len(parts) < 2:
            _console.print("[red]Usage:[/red] read <model> <id> [field1,field2,...]")
            return

        model = parts[0]
        try:
            rec_id = int(parts[1])
        except ValueError:
            _console.print("[red]ID must be an integer.[/red]")
            return

        fields = parts[2].split(",") if len(parts) > 2 else None

        try:
            records = self._client.read(model, [rec_id], fields=fields)
            if not records:
                _console.print(f"[yellow]Record {model}#{rec_id} not found.[/yellow]")
                return
            self._print_records_table(records, f"{model}#{rec_id}")
        except Exception as e:
            _console.print(f"[red]Error:[/red] {e}")

    def complete_read(self, text: str, _line: str, _begidx: int, _endidx: int) -> list[str]:
        return self._complete_model(text)

    def do_count(self, line: str) -> None:
        """count <model> [domain_json]
        Count records. Example: count res.partner [["is_company","=",true]]"""
        parts = line.split(None, 1)
        if not parts:
            _console.print("[red]Usage:[/red] count <model> [domain]")
            return

        model = parts[0]
        domain_str = parts[1] if len(parts) > 1 else ""

        try:
            domain = self._parse_domain(domain_str)
            count = self._client.search_count(model, domain=domain)
            _console.print(f"[bold]{model}[/bold]: [cyan]{count}[/cyan] record(s)")
        except Exception as e:
            _console.print(f"[red]Error:[/red] {e}")

    def complete_count(self, text: str, _line: str, _begidx: int, _endidx: int) -> list[str]:
        return self._complete_model(text)

    def do_fields(self, line: str) -> None:
        """fields <model>
        Show field definitions for a model."""
        model = line.strip()
        if not model:
            _console.print("[red]Usage:[/red] fields <model>")
            return

        try:
            fields_data = self._client.fields_get(model, attributes=["string", "type", "required", "readonly"])
            table = Table(title=f"{model} fields ({len(fields_data)})", show_header=True, header_style="bold cyan")
            table.add_column("Field", style="bold")
            table.add_column("Type")
            table.add_column("Label")
            table.add_column("Required")
            table.add_column("Readonly")

            for name in sorted(fields_data):
                info = fields_data[name]
                table.add_row(
                    name,
                    info.get("type", ""),
                    info.get("string", ""),
                    str(info.get("required", False)),
                    str(info.get("readonly", False)),
                )
            _console.print(table)
        except Exception as e:
            _console.print(f"[red]Error:[/red] {e}")

    def complete_fields(self, text: str, _line: str, _begidx: int, _endidx: int) -> list[str]:
        return self._complete_model(text)

    def do_create(self, line: str) -> None:
        """create <model> <json_vals>
        Create a record. Example: create res.partner {"name":"Test"}"""
        parts = line.split(None, 1)
        if len(parts) < 2:
            _console.print("[red]Usage:[/red] create <model> <json_vals>")
            return

        model = parts[0]
        try:
            vals = json.loads(parts[1])
        except json.JSONDecodeError as e:
            _console.print(f"[red]Invalid JSON:[/red] {e}")
            return

        try:
            new_id = self._client.create(model, vals)
            _console.print(f"[green]Created[/green] {model}#{new_id}")
        except Exception as e:
            _console.print(f"[red]Error:[/red] {e}")

    def complete_create(self, text: str, _line: str, _begidx: int, _endidx: int) -> list[str]:
        return self._complete_model(text)

    def do_write(self, line: str) -> None:
        """write <model> <id> <json_vals>
        Update a record. Example: write res.partner 1 {"name":"Updated"}"""
        parts = line.split(None, 2)
        if len(parts) < 3:
            _console.print("[red]Usage:[/red] write <model> <id> <json_vals>")
            return

        model = parts[0]
        try:
            rec_id = int(parts[1])
        except ValueError:
            _console.print("[red]ID must be an integer.[/red]")
            return

        try:
            vals = json.loads(parts[2])
        except json.JSONDecodeError as e:
            _console.print(f"[red]Invalid JSON:[/red] {e}")
            return

        try:
            self._client.write(model, [rec_id], vals)
            _console.print(f"[green]Updated[/green] {model}#{rec_id}")
        except Exception as e:
            _console.print(f"[red]Error:[/red] {e}")

    def complete_write(self, text: str, _line: str, _begidx: int, _endidx: int) -> list[str]:
        return self._complete_model(text)

    def do_call(self, line: str) -> None:
        """call <model> <method> [args_json]
        Execute an arbitrary ORM method. Example: call res.partner check_access_rights '["read"]'"""
        parts = line.split(None, 2)
        if len(parts) < 2:
            _console.print("[red]Usage:[/red] call <model> <method> [args_json]")
            return

        model = parts[0]
        method = parts[1]
        args: list = []
        if len(parts) > 2:
            try:
                args = json.loads(parts[2])
            except json.JSONDecodeError as e:
                _console.print(f"[red]Invalid JSON for args:[/red] {e}")
                return

        try:
            result = self._client.execute_kw(model, method, args)
            _console.print_json(json.dumps(result, indent=2, default=str))
        except Exception as e:
            _console.print(f"[red]Error:[/red] {e}")

    def complete_call(self, text: str, _line: str, _begidx: int, _endidx: int) -> list[str]:
        return self._complete_model(text)

    def do_models(self, line: str) -> None:
        """models [pattern]
        List available models. Optionally filter by glob pattern.
        Example: models sale.* or models *partner*"""
        models = self._load_models()
        pattern = line.strip()
        if pattern:
            models = [m for m in models if fnmatch.fnmatch(m, pattern)]

        if not models:
            _console.print("[dim]No models match the pattern.[/dim]")
            return

        table = Table(title=f"Models ({len(models)})", show_header=True, header_style="bold cyan")
        table.add_column("#", style="dim")
        table.add_column("Model")
        for i, m in enumerate(models, 1):
            table.add_row(str(i), m)
        _console.print(table)

    def do_quit(self, _line: str) -> bool:
        """Exit the REPL."""
        _console.print("[dim]Bye.[/dim]")
        return True

    def do_exit(self, _line: str) -> bool:
        """Exit the REPL."""
        return self.do_quit(_line)

    def do_EOF(self, _line: str) -> bool:  # noqa: N802
        """Handle Ctrl+D."""
        _console.print()
        return self.do_quit(_line)

    def emptyline(self) -> None:
        """Do nothing on empty input."""

    def default(self, line: str) -> None:
        _console.print(f"[red]Unknown command:[/red] {line.split()[0]}. Type 'help' for available commands.")


@app.command("repl")
def repl_command(
    ctx: typer.Context,
    load_models: Annotated[bool, typer.Option("--load-models", help="Pre-load model names for tab completion")] = False,
) -> None:
    """Start an interactive ORM REPL session.

    Connects to the configured Odoo instance and provides a command-line
    interface for exploring models, searching records, and executing ORM calls.

    Examples:
      kctl-odoo repl
      kctl-odoo repl --load-models
    """
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client

    # Verify connection before entering REPL
    ok, version = client.check_health()
    if not ok:
        out.error(f"Cannot connect to Odoo: {version}")
        raise typer.Exit(1)

    out.info(f"Connected to {client.database} (Odoo {version})")

    repl = OdooREPL(client)
    if load_models:
        repl._load_models()

    try:
        repl.cmdloop()
    except KeyboardInterrupt:
        _console.print("\n[dim]Interrupted. Bye.[/dim]")
