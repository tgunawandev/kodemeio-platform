"""Self-test diagnostic command."""

from __future__ import annotations

import typer

from kctl_grafana.core.callbacks import AppContext

app = typer.Typer(help="Self-test diagnostics.")


@app.command("run")
def run_selftest(ctx: typer.Context) -> None:
    """Run diagnostic checks for kctl-grafana."""
    c: AppContext = ctx.obj
    out = c.output
    client = c.client

    checks_passed = 0
    checks_failed = 0

    # Check 1: API connectivity
    out.header("Self-Test")

    out.info("Checking API connectivity...")
    health = client.check_health()
    if health.get("database") == "ok":
        out.success(f"API reachable \u2014 v{health.get('version', 'unknown')}")
        checks_passed += 1
    else:
        out.error(f"API unreachable: {health}")
        checks_failed += 1

    # Check 2: Organization info
    out.info("Checking organization...")
    try:
        org = client.get_org()
        out.success(f"Organization: {org.get('name', 'unknown')} (id: {org.get('id', 'unknown')})")
        checks_passed += 1
    except Exception as e:
        out.error(f"Cannot read organization: {e}")
        checks_failed += 1

    # Check 3: Datasource connectivity
    out.info("Checking datasources...")
    try:
        datasources = client.get("/datasources")
        ds_ok = 0
        ds_fail = 0
        for ds in datasources:
            ds_uid = ds.get("uid", "")
            try:
                result = client.post(f"/datasources/uid/{ds_uid}/health", json_body={})
                if result.get("status") == "OK":
                    ds_ok += 1
                else:
                    ds_fail += 1
            except Exception:
                ds_fail += 1

        if ds_fail == 0:
            out.success(f"All {ds_ok} datasources healthy")
            checks_passed += 1
        else:
            out.warn(f"{ds_ok}/{ds_ok + ds_fail} datasources healthy, {ds_fail} failing")
            checks_failed += 1
    except Exception as e:
        out.error(f"Cannot list datasources: {e}")
        checks_failed += 1

    # Check 4: Folders accessible
    out.info("Checking folders...")
    try:
        folders = client.get("/folders")
        out.success(f"{len(folders)} folders accessible")
        checks_passed += 1
    except Exception as e:
        out.error(f"Cannot list folders: {e}")
        checks_failed += 1

    # Check 5: Dashboards accessible
    out.info("Checking dashboards...")
    try:
        client.get("/search", params={"type": "dash-db", "limit": 1})
        out.success("Dashboard search working")
        checks_passed += 1
    except Exception as e:
        out.error(f"Cannot search dashboards: {e}")
        checks_failed += 1

    # Summary
    out.header("Summary")
    total = checks_passed + checks_failed
    if checks_failed == 0:
        out.success(f"All {total} checks passed")
    else:
        out.error(f"{checks_failed}/{total} checks failed")
        raise typer.Exit(1)
