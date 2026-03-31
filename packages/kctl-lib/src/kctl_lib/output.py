"""Centralized output handler with multi-format support.

Supports output formats: pretty (Rich tables), json, csv, yaml.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from io import StringIO
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

_RICH_TAG_RE = re.compile(r"\[/?[a-z_ ]+\]")


class Output:
    """Output handler that switches between Rich (pretty), JSON, CSV, and YAML modes."""

    def __init__(
        self,
        json_mode: bool = False,
        quiet: bool = False,
        format: str = "pretty",
        no_header: bool = False,
    ):
        self.json_mode = json_mode or format == "json"
        self.quiet = quiet
        self.format = format if not json_mode else "json"
        self.no_header = no_header
        use_stderr = self.format != "pretty"
        self.console = Console(stderr=True) if use_stderr else Console()
        self._stdout = Console(file=sys.stdout)

    @staticmethod
    def _strip_markup(text: str) -> str:
        """Remove Rich markup tags from a string."""
        return _RICH_TAG_RE.sub("", str(text))

    def _build_json_data(
        self,
        columns: list[tuple[str, str]],
        rows: list[list[str]],
        data_for_json: list[dict] | None,  # type: ignore[type-arg]
    ) -> list[dict]:  # type: ignore[type-arg]
        """Build list-of-dicts from table data."""
        return data_for_json or [
            {col[0].lower().replace(" ", "_"): val for col, val in zip(columns, row, strict=False)} for row in rows
        ]

    def table(
        self,
        title: str,
        columns: list[tuple[str, str]],
        rows: list[list[str]],
        data_for_json: list[dict] | None = None,  # type: ignore[type-arg]
    ) -> None:
        """Print a table in the configured format."""
        fmt = self.format

        if fmt == "json" or self.json_mode:
            json_data = self._build_json_data(columns, rows, data_for_json)
            print(json.dumps(json_data, indent=2, default=str))
            return

        if fmt == "csv":
            buf = StringIO()
            writer = csv.writer(buf)
            if not self.no_header:
                writer.writerow([col[0] for col in columns])
            stripped = [[self._strip_markup(val) for val in row] for row in rows]
            writer.writerows(stripped)
            sys.stdout.write(buf.getvalue())
            return

        if fmt == "yaml":
            yaml_data = self._build_json_data(columns, rows, data_for_json)
            print(yaml.dump(yaml_data, default_flow_style=False, allow_unicode=True).rstrip())
            return

        t = Table(title=title, show_header=True, header_style="bold cyan")
        for col_name, col_style in columns:
            t.add_column(col_name, style=col_style)
        for row in rows:
            t.add_row(*row)
        self.console.print(t)

    def detail(
        self,
        title: str,
        sections: list[tuple[str, list[tuple[str, str]]]],
        data_for_json: dict[str, Any] | None = None,
    ) -> None:
        """Print a detail panel in the configured format."""
        fmt = self.format

        if fmt == "json" or self.json_mode:
            if data_for_json is not None:
                print(json.dumps(data_for_json, indent=2, default=str))
            return

        if fmt == "yaml":
            if data_for_json is not None:
                print(yaml.dump(data_for_json, default_flow_style=False, allow_unicode=True).rstrip())
            else:
                result: dict[str, dict[str, str]] = {}
                for section_title, kvs in sections:
                    result[section_title] = {k: v for k, v in kvs}
                print(yaml.dump(result, default_flow_style=False, allow_unicode=True).rstrip())
            return

        if fmt == "csv":
            buf = StringIO()
            writer = csv.writer(buf)
            if not self.no_header:
                writer.writerow(["section", "key", "value"])
            for section_title, kvs in sections:
                for key, value in kvs:
                    writer.writerow(
                        [
                            self._strip_markup(section_title),
                            self._strip_markup(key),
                            self._strip_markup(value),
                        ]
                    )
            sys.stdout.write(buf.getvalue())
            return

        lines: list[str] = []
        for section_title, kvs in sections:
            lines.append(f"[bold cyan]{section_title}[/bold cyan]")
            for key, value in kvs:
                lines.append(f"  [dim]{key}:[/dim] {value}")
            lines.append("")

        content = "\n".join(lines).rstrip()
        self.console.print(Panel(content, title=f"[bold]{title}[/bold]", border_style="blue", expand=False))

    def tree(self, title: str, nodes: list[dict[str, Any]], data_for_json: list[dict[str, Any]] | None = None) -> None:
        """Print Rich tree. Each node: {name, children: [...], info: str}."""
        if self.json_mode:
            print(json.dumps(data_for_json or nodes, indent=2, default=str))
            return

        t = Tree(f"[bold]{title}[/bold]")
        self._build_tree(t, nodes)
        self.console.print(t)

    def _build_tree(self, parent: Tree, nodes: list[dict[str, Any]]) -> None:
        for node in nodes:
            label = node.get("name", "")
            info = node.get("info", "")
            if info:
                label = f"{label} [dim]({info})[/dim]"
            branch = parent.add(label)
            children = node.get("children", [])
            if children:
                self._build_tree(branch, children)

    def success(self, message: str) -> None:
        if not self.quiet:
            self.console.print(f"[green]OK[/green] {message}")

    def error(self, message: str) -> None:
        self.console.print(f"[red]ERROR[/red] {message}", highlight=False)

    def warn(self, message: str) -> None:
        if not self.quiet:
            self.console.print(f"[yellow]WARN[/yellow] {message}")

    def info(self, message: str) -> None:
        if not self.quiet:
            self.console.print(f"[blue]INFO[/blue] {message}")

    def raw_json(self, data: Any) -> None:
        """Output raw JSON to stdout (for piping)."""
        print(json.dumps(data, indent=2, default=str))

    def kv(self, key: str, value: str) -> None:
        """Print a single key-value pair."""
        if self.json_mode:
            return
        self.console.print(f"  [dim]{key}:[/dim] {value}")

    def header(self, title: str) -> None:
        if self.quiet or self.json_mode:
            return
        self.console.print()
        self.console.rule(f"[bold]{title}[/bold]", style="blue")

    def text(self, msg: str) -> None:
        if not self.quiet:
            self.console.print(msg)
