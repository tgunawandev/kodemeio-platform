"""Centralized output handler with multi-format support.

Supports: pretty (Rich), JSON, CSV, YAML.
"""

from __future__ import annotations

import csv
import io
import json
import re
import sys
from typing import Any

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree


def _strip_markup(text: str) -> str:
    """Remove Rich markup tags from text."""
    return re.sub(r"\[/?[^\]]*\]", "", text)


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

    def _is_data_mode(self) -> bool:
        return self.format in ("json", "csv", "yaml")

    def table(
        self,
        title: str,
        columns: list[tuple[str, str]],
        rows: list[list[str]],
        data_for_json: list[dict] | None = None,
    ) -> None:
        """Print a Rich table, JSON array, CSV, or YAML list."""
        if self.format == "json":
            json_data = data_for_json or [
                {col[0].lower().replace(" ", "_"): val for col, val in zip(columns, row, strict=False)} for row in rows
            ]
            print(json.dumps(json_data, indent=2, default=str))
            return

        if self.format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            if not self.no_header:
                writer.writerow([col[0] for col in columns])
            for row in rows:
                writer.writerow([_strip_markup(cell) for cell in row])
            sys.stdout.write(buf.getvalue())
            return

        if self.format == "yaml":
            json_data = data_for_json or [
                {col[0].lower().replace(" ", "_"): _strip_markup(val) for col, val in zip(columns, row, strict=False)}
                for row in rows
            ]
            yaml.dump(json_data, sys.stdout, default_flow_style=False, sort_keys=False)
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
        """Print a Rich panel with key-value sections."""
        if self.format == "json":
            if data_for_json is not None:
                print(json.dumps(data_for_json, indent=2, default=str))
            else:
                fallback = {}
                for _section_title, kvs in sections:
                    for k, v in kvs:
                        fallback[_strip_markup(k).lower().replace(" ", "_")] = _strip_markup(v)
                print(json.dumps(fallback, indent=2, default=str))
            return

        if self.format == "yaml":
            if data_for_json is not None:
                yaml.dump(data_for_json, sys.stdout, default_flow_style=False, sort_keys=False)
            else:
                data: dict[str, Any] = {}
                for section_title, kvs in sections:
                    data[_strip_markup(section_title)] = {_strip_markup(k): _strip_markup(v) for k, v in kvs}
                yaml.dump(data, sys.stdout, default_flow_style=False, sort_keys=False)
            return

        if self.format == "csv":
            buf = io.StringIO()
            writer = csv.writer(buf)
            if not self.no_header:
                writer.writerow(["section", "key", "value"])
            for section_title, kvs in sections:
                for k, v in kvs:
                    writer.writerow([_strip_markup(section_title), _strip_markup(k), _strip_markup(v)])
            sys.stdout.write(buf.getvalue())
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
        """Print Rich tree."""
        if self._is_data_mode():
            data = data_for_json or nodes
            if self.format == "json":
                print(json.dumps(data, indent=2, default=str))
            elif self.format == "yaml":
                yaml.dump(data, sys.stdout, default_flow_style=False, sort_keys=False)
            elif self.format == "csv":
                print(json.dumps(data, indent=2, default=str))
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
        """Output raw JSON to stdout."""
        print(json.dumps(data, indent=2, default=str))

    def kv(self, key: str, value: str) -> None:
        """Print a single key-value pair."""
        if self._is_data_mode():
            return
        self.console.print(f"  [dim]{key}:[/dim] {value}")

    def header(self, title: str) -> None:
        if self.quiet or self._is_data_mode():
            return
        self.console.print()
        self.console.rule(f"[bold]{title}[/bold]", style="blue")

    def text(self, msg: str) -> None:
        if not self.quiet:
            self.console.print(msg)
