"""Health check command."""

from __future__ import annotations

import typer

from kctl_mailcow.core.callbacks import AppContext
from kctl_mailcow.core.exceptions import KctlError

app = typer.Typer(help="Health checks.")


@app.callback(invoke_without_command=True)
def health(ctx: typer.Context) -> None:
    """Check Mailcow API health."""
    actx: AppContext = ctx.obj
    out = actx.output

    results: dict = {
        "api": False,
        "containers": None,
        "score": 0,
    }

    # API connectivity
    try:
        ok, info = actx.client.check_health()
        results["api"] = ok
    except KctlError:
        results["api"] = False

    # Container status
    try:
        data = actx.client.mc_get("status/containers")
        if isinstance(data, dict):
            results["containers"] = data
    except Exception:
        pass

    # Score
    score = 0
    if results["api"]:
        score += 50
    if results["containers"]:
        running = sum(
            1
            for v in results["containers"].values()
            if (isinstance(v, dict) and v.get("state") == "running") or v == "running"
        )
        total = len(results["containers"])
        if total > 0:
            score += int(50 * running / total)
    results["score"] = score

    # Display
    def icon(ok: bool) -> str:
        return "[green]OK[/green]" if ok else "[red]FAIL[/red]"

    score_color = "green" if score >= 80 else ("yellow" if score >= 50 else "red")

    sections: list[tuple[str, list[tuple[str, str]]]] = [
        ("API", [("Connectivity", icon(results["api"]))]),
    ]

    if results["containers"]:
        container_kvs = []
        for name, info in results["containers"].items():
            if isinstance(info, dict):
                state = info.get("state", "unknown")
            else:
                state = str(info)
            container_kvs.append((name, icon(state == "running")))
        sections.append(("Containers", container_kvs))

    sections.append(
        (
            "Health Score",
            [
                ("Score", f"[{score_color}]{score}/100[/{score_color}]"),
            ],
        )
    )

    out.detail("Health Check", sections, data_for_json=results)

    if score < 50:
        raise typer.Exit(code=1)
