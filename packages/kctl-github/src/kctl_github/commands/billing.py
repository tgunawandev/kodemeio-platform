"""GitHub billing and usage commands."""

from __future__ import annotations

import typer

from kctl_github.core.callbacks import AppContext

app = typer.Typer(help="GitHub Actions billing and usage.")


@app.command()
def actions(ctx: typer.Context) -> None:
    """Actions minutes used this billing cycle."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    org = client.organization

    # Try org endpoint first, fall back to user
    try:
        data = client.get(f"/orgs/{org}/settings/billing/actions")
    except Exception:  # noqa: BLE001
        try:
            data = client.get(f"/users/{org}/settings/billing/actions")
        except Exception:  # noqa: BLE001
            out.error("Unable to fetch billing data. Token may lack billing scope.")
            raise typer.Exit(1) from None

    if out.json_mode:
        out.raw_json(data)
        return

    total_min = data.get("total_minutes_used", 0)
    included_min = data.get("included_minutes", 0)
    paid_min = data.get("total_paid_minutes_used", 0)

    sections = [
        (
            "Actions Minutes",
            [
                ("Total Used", f"{total_min} min"),
                ("Included", f"{included_min} min"),
                ("Paid Overage", f"{paid_min} min"),
            ],
        ),
    ]

    # Per-OS breakdown if available
    breakdown = data.get("minutes_used_breakdown", {})
    if breakdown:
        os_lines = [(os_name, f"{minutes} min") for os_name, minutes in breakdown.items() if minutes > 0]
        if os_lines:
            sections.append(("By OS", os_lines))

    out.detail("Actions Billing", sections)


@app.command()
def storage(ctx: typer.Context) -> None:
    """Git LFS + Packages storage usage."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    org = client.organization

    try:
        data = client.get(f"/orgs/{org}/settings/billing/shared-storage")
    except Exception:  # noqa: BLE001
        try:
            data = client.get(f"/users/{org}/settings/billing/shared-storage")
        except Exception:  # noqa: BLE001
            out.error("Unable to fetch storage billing data.")
            raise typer.Exit(1) from None

    if out.json_mode:
        out.raw_json(data)
        return

    sections = [
        (
            "Storage",
            [
                ("Days Left in Cycle", str(data.get("days_left_in_billing_cycle", "?"))),
                ("Estimated Paid Storage (GB)", f"{data.get('estimated_paid_storage_for_month', 0):.2f}"),
                ("Estimated Storage (GB)", f"{data.get('estimated_storage_for_month', 0):.2f}"),
            ],
        ),
    ]
    out.detail("Storage Billing", sections)


@app.command()
def packages(ctx: typer.Context) -> None:
    """Packages data transfer."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    org = client.organization

    try:
        data = client.get(f"/orgs/{org}/settings/billing/packages")
    except Exception:  # noqa: BLE001
        try:
            data = client.get(f"/users/{org}/settings/billing/packages")
        except Exception:  # noqa: BLE001
            out.error("Unable to fetch packages billing data.")
            raise typer.Exit(1) from None

    if out.json_mode:
        out.raw_json(data)
        return

    sections = [
        (
            "Packages",
            [
                ("Total Bandwidth (GB)", f"{data.get('total_gigabytes_bandwidth_used', 0):.2f}"),
                ("Included Bandwidth (GB)", f"{data.get('included_gigabytes_bandwidth', 0)}"),
                ("Paid Bandwidth (GB)", f"{data.get('total_paid_gigabytes_bandwidth_used', 0):.2f}"),
            ],
        ),
    ]
    out.detail("Packages Billing", sections)


@app.command()
def overview(ctx: typer.Context) -> None:
    """Combined billing summary."""
    actx: AppContext = ctx.obj
    out = actx.output
    client = actx.client
    org = client.organization

    results: dict[str, dict] = {}

    # Fetch all billing endpoints
    for endpoint_name, path_suffix in [
        ("actions", "actions"),
        ("storage", "shared-storage"),
        ("packages", "packages"),
    ]:
        try:
            data = client.get(f"/orgs/{org}/settings/billing/{path_suffix}")
        except Exception:  # noqa: BLE001
            try:
                data = client.get(f"/users/{org}/settings/billing/{path_suffix}")
            except Exception:  # noqa: BLE001
                data = {}
        results[endpoint_name] = data

    if out.json_mode:
        out.raw_json(results)
        return

    actions_data = results.get("actions", {})
    storage_data = results.get("storage", {})
    packages_data = results.get("packages", {})

    sections = [
        (
            "Actions",
            [
                ("Minutes Used", f"{actions_data.get('total_minutes_used', 0)}"),
                ("Minutes Included", f"{actions_data.get('included_minutes', 0)}"),
            ],
        ),
        (
            "Storage",
            [
                ("Estimated (GB)", f"{storage_data.get('estimated_storage_for_month', 0):.2f}"),
            ],
        ),
        (
            "Packages",
            [
                ("Bandwidth Used (GB)", f"{packages_data.get('total_gigabytes_bandwidth_used', 0):.2f}"),
                ("Bandwidth Included (GB)", f"{packages_data.get('included_gigabytes_bandwidth', 0)}"),
            ],
        ),
    ]
    out.detail("Billing Overview", sections)
