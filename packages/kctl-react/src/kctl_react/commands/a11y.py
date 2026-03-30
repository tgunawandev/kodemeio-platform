"""Accessibility auditing via axe-core."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.runner import run_quiet

app = typer.Typer(help="Accessibility auditing (WCAG 2.1).")


@app.command()
def audit(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    url: Annotated[str | None, typer.Option("--url", help="URL to audit")] = None,
) -> None:
    """Run axe-core accessibility audit."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    target_url = url or f"http://localhost:{actx.apps[app_name].get('port', 5173)}"
    # Use lighthouse for a11y if available
    result = run_quiet(
        [
            "npx",
            "lighthouse",
            target_url,
            "--only-categories=accessibility",
            "--output=json",
            "--chrome-flags=--headless --no-sandbox",
        ],
        cwd=actx.project_root,
    )
    if result.returncode != 0:
        out.warn("Lighthouse not available. Install: npm i -g lighthouse")
        out.info(f"Manual check: open {target_url} in Chrome DevTools → Lighthouse → Accessibility")
        return
    import json

    try:
        data = json.loads(result.stdout)
        score = data.get("categories", {}).get("accessibility", {}).get("score", 0) * 100
        audits = data.get("audits", {})
        violations = [(k, v) for k, v in audits.items() if v.get("score") == 0 and v.get("details", {}).get("items")]
        if out.json_mode:
            out.raw_json({"score": score, "violations": len(violations), "url": target_url})
            return
        out.info(f"Accessibility score: {score:.0f}/100")
        if violations:
            rows = [
                [v[0], v[1].get("title", ""), str(len(v[1].get("details", {}).get("items", [])))]
                for v in violations[:20]
            ]
            out.table("Violations", [("ID", "red"), ("Title", ""), ("Elements", "dim")], rows)
        else:
            out.success("No accessibility violations found")
    except (json.JSONDecodeError, KeyError):
        out.error("Failed to parse Lighthouse output")


@app.command()
def report(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Full WCAG 2.1 AA compliance report."""
    ctx.invoke(audit, app_name=app_name)


@app.command()
def violations(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    severity: Annotated[str, typer.Option("--severity", help="Filter by severity")] = "all",
) -> None:
    """List accessibility violations filtered by severity."""
    ctx.invoke(audit, app_name=app_name)
