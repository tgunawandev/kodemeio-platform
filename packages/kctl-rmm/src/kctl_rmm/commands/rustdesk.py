"""RustDesk remote access integration.

Provides CLI commands to connect to agents via RustDesk, deploy the RustDesk
client to agents, and manage the TRMM custom fields/scripts needed for
the integration.
"""

from __future__ import annotations

import webbrowser
from typing import Annotated

import typer

from kctl_rmm.core.callbacks import AppContext

app = typer.Typer(help="RustDesk remote access (connect, deploy, manage).")

# Custom field names in TRMM
CF_RUSTDESK_ID = "rustdeskid"
CF_RUSTDESK_PWD = "rustdeskpwd"


def _resolve_agent(ctx: AppContext, identifier: str) -> dict:
    """Resolve agent by ID or hostname (with full detail for custom fields)."""
    # Try exact agent_id
    try:
        agent = ctx.client.get(f"/agents/{identifier}/")
        if isinstance(agent, dict) and agent.get("agent_id"):
            return agent
    except Exception:
        pass

    # Search by hostname
    data = ctx.client.get("/agents/", params={"detail": "false"})
    agents = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
    for a in agents:
        if identifier.lower() in a.get("hostname", "").lower():
            try:
                return ctx.client.get(f"/agents/{a['agent_id']}/")
            except Exception:
                return a
    return {}


def _get_custom_field(agent: dict, field_name: str) -> str:
    """Extract a custom field value from agent data."""
    for cf in agent.get("custom_fields", []):
        if cf.get("field") == field_name or cf.get("name") == field_name:
            return str(cf.get("value", "")).strip()
    return ""


@app.command()
def connect(
    ctx: typer.Context,
    agent: Annotated[str, typer.Argument(help="Agent ID or hostname")],
) -> None:
    """Open RustDesk remote session to agent."""
    c: AppContext = ctx.obj
    a = _resolve_agent(c, agent)

    if not a:
        c.output.error(f"Agent not found: {agent}")
        raise typer.Exit(1)

    hostname = a.get("hostname", agent)
    rd_id = _get_custom_field(a, CF_RUSTDESK_ID)
    rd_pwd = _get_custom_field(a, CF_RUSTDESK_PWD)

    if not rd_id or rd_id in ("NOT_INSTALLED", "ERROR_NO_ID"):
        c.output.error(
            f"RustDesk not configured on {hostname}. Run: kctl-rmm rustdesk deploy {a.get('agent_id', agent)}"
        )
        raise typer.Exit(1)

    url = f"rustdesk://connection/new/{rd_id}"
    if rd_pwd and rd_pwd not in ("NO_CONFIG", "NO_PASSWORD"):
        url += f"?password={rd_pwd}"

    c.output.info(f"Connecting to {hostname} (RustDesk ID: {rd_id})")
    c.output.success(f"Opening {url}")
    webbrowser.open(url)


@app.command()
def transfer(
    ctx: typer.Context,
    agent: Annotated[str, typer.Argument(help="Agent ID or hostname")],
) -> None:
    """Open RustDesk file transfer session to agent."""
    c: AppContext = ctx.obj
    a = _resolve_agent(c, agent)

    if not a:
        c.output.error(f"Agent not found: {agent}")
        raise typer.Exit(1)

    hostname = a.get("hostname", agent)
    rd_id = _get_custom_field(a, CF_RUSTDESK_ID)
    rd_pwd = _get_custom_field(a, CF_RUSTDESK_PWD)

    if not rd_id or rd_id in ("NOT_INSTALLED", "ERROR_NO_ID"):
        c.output.error(f"RustDesk not configured on {hostname}.")
        raise typer.Exit(1)

    url = f"rustdesk://file-transfer/{rd_id}"
    if rd_pwd and rd_pwd not in ("NO_CONFIG", "NO_PASSWORD"):
        url += f"?password={rd_pwd}"

    c.output.info(f"File transfer to {hostname} (RustDesk ID: {rd_id})")
    c.output.success(f"Opening {url}")
    webbrowser.open(url)


@app.command("list")
def list_(
    ctx: typer.Context,
    client_filter: Annotated[str | None, typer.Option("--client", "-c", help="Filter by client name")] = None,
    installed_only: Annotated[bool, typer.Option("--installed", help="Show only agents with RustDesk")] = False,
) -> None:
    """List agents with their RustDesk IDs."""
    c: AppContext = ctx.obj
    data = c.client.get("/agents/", params={"detail": "true"})
    agents = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []

    if client_filter:
        agents = [a for a in agents if client_filter.lower() in a.get("client_name", "").lower()]

    rows: list[list[str]] = []
    json_data: list[dict] = []
    for a in agents:
        rd_id = _get_custom_field(a, CF_RUSTDESK_ID)
        rd_pwd = _get_custom_field(a, CF_RUSTDESK_PWD)

        if installed_only and (not rd_id or rd_id in ("NOT_INSTALLED", "ERROR_NO_ID", "")):
            continue

        status = a.get("status", "unknown")
        status_str = "[green]online[/green]" if status == "online" else "[red]offline[/red]"

        if not rd_id or rd_id == "":
            rd_status = "[dim]no data[/dim]"
        elif rd_id == "NOT_INSTALLED":
            rd_status = "[yellow]not installed[/yellow]"
        elif rd_id == "ERROR_NO_ID":
            rd_status = "[red]error[/red]"
        else:
            rd_status = f"[green]{rd_id}[/green]"

        pwd_status = (
            "[green]yes[/green]" if rd_pwd and rd_pwd not in ("NO_CONFIG", "NO_PASSWORD", "") else "[dim]no[/dim]"
        )

        rows.append(
            [
                a.get("hostname", ""),
                a.get("client_name", ""),
                status_str,
                rd_status,
                pwd_status,
            ]
        )
        json_data.append(
            {
                "hostname": a.get("hostname", ""),
                "agent_id": a.get("agent_id", ""),
                "client_name": a.get("client_name", ""),
                "status": a.get("status", ""),
                "rustdesk_id": rd_id,
                "rustdesk_pwd": "***" if rd_pwd else "",
            }
        )

    c.output.table(
        f"RustDesk Agents ({len(rows)})",
        [("Hostname", ""), ("Client", "dim"), ("Agent", ""), ("RustDesk ID", ""), ("Password", "")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def deploy(
    ctx: typer.Context,
    agent_id: Annotated[str | None, typer.Argument(help="Agent ID (omit for --all)")] = None,
    all_agents: Annotated[bool, typer.Option("--all", help="Deploy to all online agents")] = False,
    client_filter: Annotated[str | None, typer.Option("--client", "-c", help="Deploy to all agents in client")] = None,
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="Script timeout in seconds")] = 600,
) -> None:
    """Deploy RustDesk client to agent(s) via TRMM script.

    Requires the install script to be uploaded first (kctl-rmm rustdesk setup).
    """
    c: AppContext = ctx.obj

    if not agent_id and not all_agents and not client_filter:
        c.output.error("Specify agent ID, --all, or --client")
        raise typer.Exit(1)

    # Find the install script by name
    scripts_data = c.client.get("/scripts/")
    scripts_list = (
        scripts_data
        if isinstance(scripts_data, list)
        else scripts_data.get("results", [])
        if isinstance(scripts_data, dict)
        else []
    )
    install_script = next(
        (s for s in scripts_list if "rustdesk" in s.get("name", "").lower() and "install" in s.get("name", "").lower()),
        None,
    )

    if not install_script:
        c.output.error("Install script not found in TRMM. Run: kctl-rmm rustdesk setup")
        raise typer.Exit(1)

    script_id = install_script["id"]

    # Resolve target agents
    target_ids: list[str] = []
    if agent_id:
        target_ids = [agent_id]
    else:
        data = c.client.get("/agents/", params={"detail": "false"})
        agents = data if isinstance(data, list) else data.get("results", []) if isinstance(data, dict) else []
        if client_filter:
            agents = [a for a in agents if client_filter.lower() in a.get("client_name", "").lower()]
        target_ids = [a["agent_id"] for a in agents if a.get("status") == "online"]

    if not target_ids:
        c.output.warn("No target agents found")
        return

    c.output.info(f"Deploying RustDesk (script {script_id}) to {len(target_ids)} agent(s)")

    success, failed = 0, 0
    for aid in target_ids:
        try:
            c.client.post(
                f"/agents/{aid}/runscript/",
                data={
                    "script": script_id,
                    "output": "forget",
                    "timeout": timeout,
                },
            )
            success += 1
        except Exception as e:
            c.output.warn(f"Failed on {aid}: {e}")
            failed += 1

    c.output.success(f"Deploy dispatched: {success} ok, {failed} failed")
    c.output.info("Check progress: kctl-rmm scripts history")


@app.command()
def status(
    ctx: typer.Context,
    agent_id: Annotated[str, typer.Argument(help="Agent ID or hostname")],
    timeout: Annotated[int, typer.Option("--timeout", "-t", help="Script timeout")] = 60,
) -> None:
    """Check RustDesk status on an agent (runs check script)."""
    c: AppContext = ctx.obj
    a = _resolve_agent(c, agent_id)

    if not a:
        c.output.error(f"Agent not found: {agent_id}")
        raise typer.Exit(1)

    resolved_id = a.get("agent_id", agent_id)
    hostname = a.get("hostname", agent_id)

    # Find the check script
    scripts_data = c.client.get("/scripts/")
    scripts_list = (
        scripts_data
        if isinstance(scripts_data, list)
        else scripts_data.get("results", [])
        if isinstance(scripts_data, dict)
        else []
    )
    check_script = next(
        (s for s in scripts_list if "rustdesk" in s.get("name", "").lower() and "status" in s.get("name", "").lower()),
        None,
    )

    if not check_script:
        # Fallback: show custom field data
        rd_id = _get_custom_field(a, CF_RUSTDESK_ID)
        rd_pwd = _get_custom_field(a, CF_RUSTDESK_PWD)
        sections: list[tuple[str, list[tuple[str, str]]]] = [
            (
                "RustDesk on " + hostname,
                [
                    ("RustDesk ID", rd_id or "N/A"),
                    ("Password Set", "Yes" if rd_pwd and rd_pwd not in ("NO_CONFIG", "NO_PASSWORD", "") else "No"),
                    ("Note", "Check script not found. Run: kctl-rmm rustdesk setup"),
                ],
            ),
        ]
        c.output.detail(
            f"RustDesk Status: {hostname}",
            sections,
            data_for_json={
                "hostname": hostname,
                "agent_id": resolved_id,
                "rustdesk_id": rd_id,
                "has_password": bool(rd_pwd and rd_pwd not in ("NO_CONFIG", "NO_PASSWORD", "")),
            },
        )
        return

    c.output.info(f"Running RustDesk status check on {hostname}...")
    c.client.post(
        f"/agents/{resolved_id}/runscript/",
        data={
            "script": check_script["id"],
            "output": "forget",
            "timeout": timeout,
        },
    )
    c.output.success(f"Status check dispatched to {hostname} (fire-and-forget)")
    c.output.info(f"Check results: kctl-rmm scripts history --agent {resolved_id}")


# ---------------------------------------------------------------------------
# Script bodies embedded for the setup command
# ---------------------------------------------------------------------------
_SCRIPT_COLLECT_ID = r"""$ErrorActionPreference = 'SilentlyContinue'
$rdPath = "$env:ProgramFiles\RustDesk\RustDesk.exe"
if (-not (Test-Path $rdPath)) { Write-Output "NOT_INSTALLED"; exit 0 }
$id = & $rdPath --get-id 2>$null
if ($id) { Write-Output $id.Trim() } else { Write-Output "ERROR_NO_ID" }
"""

_SCRIPT_COLLECT_PWD = r"""$ErrorActionPreference = 'SilentlyContinue'
$configPath = "$env:ProgramFiles\RustDesk\RustDesk.toml"
if (-not (Test-Path $configPath)) { $configPath = "$env:APPDATA\RustDesk\config\RustDesk.toml" }
if (-not (Test-Path $configPath)) { Write-Output "NO_CONFIG"; exit 0 }
$content = Get-Content $configPath -Raw
if ($content -match "password\s*=\s*'([^']+)'") { Write-Output $Matches[1] }
elseif ($content -match 'password\s*=\s*"([^"]+)"') { Write-Output $Matches[1] }
else { Write-Output "NO_PASSWORD" }
"""

_SCRIPT_CHECK_STATUS = r"""$ErrorActionPreference = 'SilentlyContinue'
$rdExe = "$env:ProgramFiles\RustDesk\RustDesk.exe"
if (-not (Test-Path $rdExe)) { Write-Output "Status: NOT_INSTALLED"; exit 0 }
$svc = Get-Service -Name "RustDesk"
$svcStatus = if ($svc) { $svc.Status } else { "No Service" }
$id = & $rdExe --get-id 2>$null
$idStr = if ($id) { $id.Trim() } else { "N/A" }
$version = (Get-Item $rdExe).VersionInfo.ProductVersion
Write-Output "Status: INSTALLED"
Write-Output "Version: $version"
Write-Output "Service: $svcStatus"
Write-Output "RustDesk ID: $idStr"
"""

_SCRIPT_UNINSTALL = r"""$ErrorActionPreference = 'SilentlyContinue'
$rdExe = "$env:ProgramFiles\RustDesk\RustDesk.exe"
if (-not (Test-Path $rdExe)) { Write-Output "RustDesk not installed."; exit 0 }
Write-Output "Uninstalling RustDesk..."
& $rdExe --uninstall 2>$null
Start-Sleep -Seconds 5
if (-not (Test-Path $rdExe)) { Write-Output "RustDesk uninstalled successfully." }
else { Write-Output "WARNING: RustDesk.exe still exists after uninstall." }
"""

_SETUP_SCRIPTS = [
    {
        "name": "RustDesk - Collect ID",
        "shell": "powershell",
        "body": _SCRIPT_COLLECT_ID,
        "description": "Collector: harvests RustDesk ID for custom field rustdeskid",
        "timeout": 60,
    },
    {
        "name": "RustDesk - Collect Password",
        "shell": "powershell",
        "body": _SCRIPT_COLLECT_PWD,
        "description": "Collector: harvests RustDesk password for custom field rustdeskpwd",
        "timeout": 60,
    },
    {
        "name": "RustDesk - Check Status",
        "shell": "powershell",
        "body": _SCRIPT_CHECK_STATUS,
        "description": "Check if RustDesk is installed and running",
        "timeout": 60,
    },
    {
        "name": "RustDesk - Uninstall",
        "shell": "powershell",
        "body": _SCRIPT_UNINSTALL,
        "description": "Silently uninstall RustDesk client",
        "timeout": 120,
    },
]

_CUSTOM_FIELDS = [
    {"model": "agent", "name": CF_RUSTDESK_ID, "type": "text"},
    {"model": "agent", "name": CF_RUSTDESK_PWD, "type": "text"},
]


@app.command()
def setup(ctx: typer.Context) -> None:
    """One-time setup: create TRMM custom fields and upload RustDesk scripts.

    Creates custom fields (rustdeskid, rustdeskpwd) and uploads collector/
    management scripts to the TRMM instance. Safe to run multiple times
    (skips existing items).
    """
    c: AppContext = ctx.obj

    c.output.header("RustDesk Integration Setup")

    # Step 1: Create custom fields
    c.output.info("Creating custom fields...")
    for cf in _CUSTOM_FIELDS:
        try:
            c.client.post("/core/customfields/", data=cf)
            c.output.success(f"  Created custom field: {cf['name']}")
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str or "unique" in err_str or "duplicate" in err_str:
                c.output.info(f"  Custom field already exists: {cf['name']}")
            else:
                c.output.warn(f"  Failed to create {cf['name']}: {e}")

    # Step 2: Upload scripts
    c.output.info("Uploading scripts...")
    for script in _SETUP_SCRIPTS:
        try:
            c.client.post(
                "/scripts/",
                data={
                    "name": script["name"],
                    "shell": script["shell"],
                    "script_body": script["body"],
                    "description": script["description"],
                    "default_timeout": script["timeout"],
                },
            )
            c.output.success(f"  Uploaded: {script['name']}")
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str or "unique" in err_str or "duplicate" in err_str:
                c.output.info(f"  Script already exists: {script['name']}")
            else:
                c.output.warn(f"  Failed to upload {script['name']}: {e}")

    c.output.header("Next Steps")
    c.output.text("1. In TRMM dashboard: Automation Manager → Create Collector Tasks")
    c.output.text("   - 'RustDesk - Collect ID' → custom field: rustdeskid")
    c.output.text("   - 'RustDesk - Collect Password' → custom field: rustdeskpwd")
    c.output.text("2. In TRMM dashboard: Global Settings → URL Actions, add:")
    c.output.text("   - Name: RustDesk Remote")
    c.output.text("   - URL: rustdesk://connection/new/{{agent.rustdeskid}}?password={{agent.rustdeskpwd}}")
    c.output.text("   - Name: RustDesk File Transfer")
    c.output.text("   - URL: rustdesk://file-transfer/{{agent.rustdeskid}}?password={{agent.rustdeskpwd}}")
    c.output.text("3. Deploy RustDesk client: kctl-rmm rustdesk deploy --all")
    c.output.text("4. Verify: kctl-rmm rustdesk list --installed")
