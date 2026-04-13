"""Diagnostic checks."""

from __future__ import annotations

import typer

from kctl_mm.core.callbacks import AppContext

app = typer.Typer(help="Diagnose kctl-mm configuration and connectivity.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def run(ctx: typer.Context) -> None:
    c: AppContext = ctx.ensure_object(AppContext)
    results: list[tuple[str, bool, str]] = []

    try:
        r = c.client.ping()
        ok = r.get("status") == "OK"
        results.append(("REST ping", ok, f"status={r.get('status')}"))
    except Exception as exc:
        results.append(("REST ping", False, str(exc)))

    try:
        me = c.client.get_me()
        results.append(("REST auth", True, f"authenticated as {me.get('username')}"))
    except Exception as exc:
        results.append(("REST auth", False, str(exc)))

    try:
        r = c.mm_exec.mmctl(["version"])
        if r.returncode == 0:
            detail = r.stdout.strip().splitlines()[0] if r.stdout.strip() else "ok"
            results.append(("SSH + mmctl", True, detail))
        else:
            results.append(("SSH + mmctl", False, f"rc={r.returncode}: {r.stderr.strip()}"))
    except Exception as exc:
        results.append(("SSH + mmctl", False, str(exc)))

    for name, ok, detail in results:
        marker = "OK" if ok else "FAIL"
        typer.echo(f"[{marker}] {name}: {detail}")

    if not all(ok for _, ok, _ in results):
        raise typer.Exit(1)
