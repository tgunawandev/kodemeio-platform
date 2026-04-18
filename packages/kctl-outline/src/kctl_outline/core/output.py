"""Centralized output handler with JSON/pretty toggle.

# KCTL-COMMON: extractable
"""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree


class Output:
    """Output handler that switches between Rich (pretty) and JSON modes."""

    def __init__(self, json_mode: bool = False, quiet: bool = False):
        self.json_mode = json_mode
        self.quiet = quiet
        self.console = Console(stderr=True) if json_mode else Console()
        self._stdout = Console(file=sys.stdout)

    def table(
        self,
        title: str,
        columns: list[tuple[str, str]],
        rows: list[list[str]],
        data_for_json: list[dict] | None = None,
    ) -> None:
        """Print a Rich table or JSON array."""
        if self.json_mode:
            json_data = data_for_json or [
                {col[0].lower().replace(" ", "_"): val for col, val in zip(columns, row, strict=False)} for row in rows
            ]
            print(json.dumps(json_data, indent=2, default=str))
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
        data_for_json: dict | None = None,
    ) -> None:
        """Print a Rich panel with key-value sections or JSON object."""
        if self.json_mode:
            if data_for_json:
                print(json.dumps(data_for_json, indent=2, default=str))
            return

        lines: list[str] = []
        for section_title, kvs in sections:
            lines.append(f"[bold cyan]{section_title}[/bold cyan]")
            for key, value in kvs:
                lines.append(f"  [dim]{key}:[/dim] {value}")
            lines.append("")

        content = "\n".join(lines).rstrip()
        self.console.print(Panel(content, title=f"[bold]{title}[/bold]", border_style="blue"))

    def tree(self, title: str, nodes: list[dict], data_for_json: list[dict] | None = None) -> None:
        """Print Rich tree. Each node: {name, children: [...], info: str}."""
        if self.json_mode:
            print(json.dumps(data_for_json or nodes, indent=2, default=str))
            return

        tree = Tree(f"[bold]{title}[/bold]")
        self._build_tree(tree, nodes)
        self.console.print(tree)

    def _build_tree(self, parent: Tree, nodes: list[dict]) -> None:
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
        self.console.print(f"[red]ERROR[/red] {message}")

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
