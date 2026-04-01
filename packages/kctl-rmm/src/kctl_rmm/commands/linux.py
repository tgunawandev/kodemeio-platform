"""Linux agent install/update/uninstall commands using LinuxRMM-Script."""

from __future__ import annotations

import subprocess
from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext
from kctl_rmm.core.config import resolve_connection, resolve_mesh_url

SCRIPT_URL = "https://raw.githubusercontent.com/netvolt/LinuxRMM-Script/main/rmmagent-linux.sh"

app = typer.Typer(help="Linux agent management (install/update/uninstall via LinuxRMM-Script).")


def _pick_site(c: AppContext, client_name: str | None, site_name: str | None) -> tuple[int, int, str, str]:
    """Resolve client_id and site_id from names, prompting if needed."""
    data = c.client.get("/clients/")
    clients = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    if not clients:
        c.output.error("No clients found in Tactical RMM.")
        raise typer.Exit(1)

    # Filter or prompt for client
    if client_name:
        matches = [cl for cl in clients if client_name.lower() in cl.get("name", "").lower()]
        if not matches:
            c.output.error(f"No client matching '{client_name}'.")
            raise typer.Exit(1)
        chosen_client = matches[0]
    else:
        c.output.info("Available clients:")
        for i, cl in enumerate(clients, 1):
            c.output.text(f"  {i}. {cl.get('name', '')} (id={cl.get('id', '')})")
        idx = typer.prompt("Select client number", type=int)
        if idx < 1 or idx > len(clients):
            c.output.error("Invalid selection.")
            raise typer.Exit(1)
        chosen_client = clients[idx - 1]

    client_id = chosen_client.get("id")
    client_display = chosen_client.get("name", "")
    sites = chosen_client.get("sites", [])

    if not sites:
        c.output.error(f"Client '{client_display}' has no sites.")
        raise typer.Exit(1)

    # Filter or prompt for site
    if site_name:
        site_matches = [s for s in sites if site_name.lower() in s.get("name", "").lower()]
        if not site_matches:
            c.output.error(f"No site matching '{site_name}' in client '{client_display}'.")
            raise typer.Exit(1)
        chosen_site = site_matches[0]
    elif len(sites) == 1:
        chosen_site = sites[0]
    else:
        c.output.info(f"Sites for '{client_display}':")
        for i, s in enumerate(sites, 1):
            c.output.text(f"  {i}. {s.get('name', '')} (id={s.get('id', '')})")
        idx = typer.prompt("Select site number", type=int)
        if idx < 1 or idx > len(sites):
            c.output.error("Invalid selection.")
            raise typer.Exit(1)
        chosen_site = sites[idx - 1]

    site_id = chosen_site.get("id")
    site_display = chosen_site.get("name", "")
    return client_id, site_id, client_display, site_display


@app.command()
def install(
    ctx: typer.Context,
    mesh_agent_url: Annotated[
        str, typer.Option("--mesh-url", help="MeshCentral agent download URL (from MeshCentral > Add Agent > Linux)")
    ] = "",
    auth_key: Annotated[
        str, typer.Option("--auth-key", help="TRMM install auth key (from Agents > Install Agent)")
    ] = "",
    client_name: Annotated[str | None, typer.Option("--client", help="Client name (partial match)")] = None,
    site_name: Annotated[str | None, typer.Option("--site", help="Site name (partial match)")] = None,
    client_id: Annotated[int | None, typer.Option("--client-id", help="Client ID (skip lookup)")] = None,
    site_id: Annotated[int | None, typer.Option("--site-id", help="Site ID (skip lookup)")] = None,
    agent_type: Annotated[str, typer.Option("--type", help="Agent type: server or workstation")] = "server",
    ssh_host: Annotated[str | None, typer.Option("--ssh", help="Deploy via SSH to this host (user@host)")] = None,
    ssh_port: Annotated[int, typer.Option("--ssh-port", help="SSH port")] = 22,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print command without executing")] = False,
) -> None:
    """Install Tactical RMM agent on a Linux machine.

    Generates or executes the LinuxRMM-Script install command.

    Required info (prompted if not provided):
      - MeshCentral agent URL: MeshCentral > Add Agent > Linux > copy URL
      - Auth key: TRMM dashboard > Agents > Install Agent > show auth key
      - Client/Site: selected from API or passed as --client/--site
    """
    c: AppContext = ctx.obj

    if agent_type not in ("server", "workstation"):
        c.output.error("Agent type must be 'server' or 'workstation'.")
        raise typer.Exit(1)

    # Resolve client/site IDs
    if client_id is None or site_id is None:
        cid, sid, cname, sname = _pick_site(c, client_name, site_name)
        client_id = client_id or cid
        site_id = site_id or sid
        c.output.info(f"Target: {cname} / {sname} (client_id={client_id}, site_id={site_id})")

    # Get API URL from config
    api_url, _ = resolve_connection(
        profile_name=c.profile,
        url_override=c.url_override,
        api_key_override=c.api_key_override,
    )

    if not api_url:
        c.output.error("No API URL configured. Run: kctl-rmm config init")
        raise typer.Exit(1)

    # Prompt for required values if not provided
    if not mesh_agent_url:
        c.output.warn("MeshCentral agent URL required.")
        c.output.text("  Get it from: MeshCentral dashboard > Add Agent > Linux > copy download URL")
        mesh_url_base = resolve_mesh_url(c.profile)
        if mesh_url_base:
            c.output.text(f"  MeshCentral dashboard: {mesh_url_base}")
        mesh_agent_url = typer.prompt("Mesh agent download URL")

    if not auth_key:
        c.output.warn("TRMM auth key required.")
        c.output.text("  Get it from: TRMM dashboard > Agents > Install Agent > show auth key value")
        auth_key = typer.prompt("Auth key")

    # Build the install command
    install_cmd = (
        f"wget -q -O /tmp/rmmagent-linux.sh '{SCRIPT_URL}' && "
        f"chmod +x /tmp/rmmagent-linux.sh && "
        f"sudo /tmp/rmmagent-linux.sh install "
        f"'{mesh_agent_url}' "
        f"'{api_url}' "
        f"{client_id} "
        f"{site_id} "
        f"'{auth_key}' "
        f"{agent_type}"
    )

    if dry_run or ssh_host is None:
        c.output.header("Linux Agent Install Command")
        c.output.text("")
        c.output.text(f"[bold]{install_cmd}[/bold]")
        c.output.text("")
        if ssh_host is None and not dry_run:
            c.output.info("Tip: use --ssh user@host to deploy directly via SSH")
        return

    # Deploy via SSH
    if ssh_host and not dry_run:
        c.output.info(f"Deploying to {ssh_host}:{ssh_port} ...")
        if not typer.confirm(f"Run install on {ssh_host}?"):
            raise typer.Exit(0)

        ssh_cmd = ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=accept-new", ssh_host, install_cmd]
        result = subprocess.run(ssh_cmd, text=True)
        if result.returncode == 0:
            c.output.success(f"Agent installed on {ssh_host}")
        else:
            c.output.error(f"Install failed on {ssh_host} (exit code {result.returncode})")
            raise typer.Exit(1)


@app.command()
def update(
    ctx: typer.Context,
    ssh_host: Annotated[str | None, typer.Option("--ssh", help="Run via SSH on this host (user@host)")] = None,
    ssh_port: Annotated[int, typer.Option("--ssh-port", help="SSH port")] = 22,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print command without executing")] = False,
) -> None:
    """Update the Tactical RMM agent on a Linux machine.

    Recompiles and reinstalls the latest agent from source.
    """
    c: AppContext = ctx.obj

    update_cmd = (
        f"wget -q -O /tmp/rmmagent-linux.sh '{SCRIPT_URL}' && "
        f"chmod +x /tmp/rmmagent-linux.sh && "
        f"sudo /tmp/rmmagent-linux.sh update"
    )

    if dry_run or ssh_host is None:
        c.output.header("Linux Agent Update Command")
        c.output.text("")
        c.output.text(f"[bold]{update_cmd}[/bold]")
        c.output.text("")
        if ssh_host is None and not dry_run:
            c.output.info("Tip: use --ssh user@host to update directly via SSH")
        return

    if ssh_host and not dry_run:
        c.output.info(f"Updating agent on {ssh_host}:{ssh_port} ...")
        if not typer.confirm(f"Run update on {ssh_host}?"):
            raise typer.Exit(0)

        ssh_cmd = ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=accept-new", ssh_host, update_cmd]
        result = subprocess.run(ssh_cmd, text=True)
        if result.returncode == 0:
            c.output.success(f"Agent updated on {ssh_host}")
        else:
            c.output.error(f"Update failed on {ssh_host} (exit code {result.returncode})")
            raise typer.Exit(1)


@app.command()
def uninstall(
    ctx: typer.Context,
    mesh_fqdn: Annotated[str, typer.Option("--mesh-fqdn", help="MeshCentral FQDN (e.g. mesh.kodeme.io)")] = "",
    mesh_id: Annotated[str, typer.Option("--mesh-id", help="MeshCentral device group mesh ID")] = "",
    ssh_host: Annotated[str | None, typer.Option("--ssh", help="Run via SSH on this host (user@host)")] = None,
    ssh_port: Annotated[int, typer.Option("--ssh-port", help="SSH port")] = 22,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Print command without executing")] = False,
) -> None:
    """Uninstall the Tactical RMM agent from a Linux machine.

    Note: This removes local files only. The agent must be manually deleted
    from the TRMM and MeshCentral dashboards.
    """
    c: AppContext = ctx.obj

    # Try to resolve mesh FQDN from config
    if not mesh_fqdn:
        mesh_url_base = resolve_mesh_url(c.profile)
        if mesh_url_base:
            # Extract FQDN from URL like https://mesh.kodeme.io
            mesh_fqdn = mesh_url_base.replace("https://", "").replace("http://", "").rstrip("/")

    if not mesh_fqdn:
        c.output.warn("MeshCentral FQDN required for uninstall.")
        mesh_fqdn = typer.prompt("MeshCentral FQDN (e.g. mesh.kodeme.io)")

    if not mesh_id:
        c.output.warn("MeshCentral mesh ID required for uninstall.")
        c.output.text("  Get it from: MeshCentral > Device Group > Info > Identifier")
        mesh_id = typer.prompt("Mesh ID")

    uninstall_cmd = (
        f"wget -q -O /tmp/rmmagent-linux.sh '{SCRIPT_URL}' && "
        f"chmod +x /tmp/rmmagent-linux.sh && "
        f"sudo /tmp/rmmagent-linux.sh uninstall '{mesh_fqdn}' '{mesh_id}'"
    )

    if dry_run or ssh_host is None:
        c.output.header("Linux Agent Uninstall Command")
        c.output.text("")
        c.output.text(f"[bold]{uninstall_cmd}[/bold]")
        c.output.text("")
        c.output.warn("This removes local files only. Delete the agent from TRMM/MeshCentral dashboards manually.")
        if ssh_host is None and not dry_run:
            c.output.info("Tip: use --ssh user@host to uninstall directly via SSH")
        return

    if ssh_host and not dry_run:
        c.output.info(f"Uninstalling agent on {ssh_host}:{ssh_port} ...")
        if not typer.confirm(f"Uninstall agent on {ssh_host}? This cannot be undone."):
            raise typer.Exit(0)

        ssh_cmd = ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=accept-new", ssh_host, uninstall_cmd]
        result = subprocess.run(ssh_cmd, text=True)
        if result.returncode == 0:
            c.output.success(f"Agent uninstalled from {ssh_host}")
            c.output.warn("Remember to delete the agent from TRMM and MeshCentral dashboards.")
        else:
            c.output.error(f"Uninstall failed on {ssh_host} (exit code {result.returncode})")
            raise typer.Exit(1)


@app.command()
def status(
    ctx: typer.Context,
    ssh_host: Annotated[str, typer.Option("--ssh", help="Check via SSH on this host (user@host)")],
    ssh_port: Annotated[int, typer.Option("--ssh-port", help="SSH port")] = 22,
) -> None:
    """Check Linux agent status on a remote host via SSH."""
    c: AppContext = ctx.obj

    check_cmd = (
        "echo '=== tacticalagent service ===' && "
        "systemctl is-active tacticalagent 2>/dev/null || echo 'not installed' && "
        "echo '=== rmmagent binary ===' && "
        "ls -la /usr/local/bin/rmmagent 2>/dev/null || echo 'not found' && "
        "echo '=== meshagent ===' && "
        "ls -la /opt/tacticalmesh/meshagent 2>/dev/null || echo 'not found' && "
        "echo '=== service details ===' && "
        "systemctl status tacticalagent --no-pager 2>/dev/null || true"
    )

    ssh_cmd = ["ssh", "-p", str(ssh_port), "-o", "StrictHostKeyChecking=accept-new", ssh_host, check_cmd]
    c.output.info(f"Checking agent status on {ssh_host}:{ssh_port} ...")
    result = subprocess.run(ssh_cmd, text=True, capture_output=True)

    if result.returncode == 255:
        c.output.error(f"SSH connection failed to {ssh_host}:{ssh_port}")
        raise typer.Exit(1)

    c.output.header(f"Agent Status: {ssh_host}")
    c.output.text(result.stdout)
    if result.stderr.strip():
        c.output.warn(result.stderr.strip())
