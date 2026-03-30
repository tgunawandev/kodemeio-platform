"""Global settings management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_dokploy.core.callbacks import AppContext

app = typer.Typer(help="Manage Dokploy global settings.")


@app.command()
def show(ctx: typer.Context) -> None:
    """Show current global settings."""
    c: AppContext = ctx.obj
    data = c.client.get("/settings.one")
    if not isinstance(data, dict):
        data = {}
    # Extract key settings
    letsencrypt_email = data.get("letsEncryptEmail", data.get("certificateEmail", "-"))
    cleanup_enabled = str(data.get("cleanupCacheEnabled", data.get("enableDockerCleanup", "-")))
    traefik_enabled = str(data.get("isTraefikEnabled", data.get("traefikEnabled", "-")))
    server_ip = data.get("serverIp", data.get("ipAddress", "-"))
    sections = [
        (
            "Server",
            [
                ("Server IP", str(server_ip)),
                ("Let's Encrypt Email", str(letsencrypt_email)),
                ("Traefik Enabled", traefik_enabled),
                ("Docker Cleanup", cleanup_enabled),
            ],
        ),
    ]
    # Add docker/system info if available
    docker_version = data.get("dockerVersion")
    os_info = data.get("os")
    if docker_version or os_info:
        sys_items = []
        if docker_version:
            sys_items.append(("Docker Version", str(docker_version)))
        if os_info:
            sys_items.append(("OS", str(os_info)))
        sections.append(("System", sys_items))
    c.output.detail("Global Settings", sections, data_for_json=data)


@app.command()
def update(
    ctx: typer.Context,
    letsencrypt_email: Annotated[str | None, typer.Option("--letsencrypt-email", help="Let's Encrypt email")] = None,
    cleanup_enabled: Annotated[
        bool | None, typer.Option("--docker-cleanup/--no-docker-cleanup", help="Enable Docker cleanup")
    ] = None,
) -> None:
    """Update global settings."""
    c: AppContext = ctx.obj
    payload: dict = {}
    if letsencrypt_email is not None:
        payload["letsEncryptEmail"] = letsencrypt_email
    if cleanup_enabled is not None:
        payload["cleanupCacheEnabled"] = cleanup_enabled
    if not payload:
        c.output.warn("No settings to update. Use --help to see available options.")
        raise typer.Exit(1)
    result = c.client.post("/settings.update", json=payload)
    c.output.success("Global settings updated")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("ssh-keys")
def ssh_keys(ctx: typer.Context) -> None:
    """List SSH keys configured in Dokploy."""
    c: AppContext = ctx.obj
    keys = c.client.get("/sshKey.all")
    if not isinstance(keys, list):
        keys = []
    rows = []
    for k in keys:
        kid = k.get("sshKeyId", "")[:12]
        name = k.get("name", "")
        fingerprint = k.get("fingerprint", k.get("publicKey", ""))
        if len(str(fingerprint)) > 40:
            fingerprint = str(fingerprint)[:40] + "..."
        created = k.get("createdAt", "-")
        rows.append([kid, name, str(fingerprint), str(created)])
    c.output.table(
        "SSH Keys",
        [("ID", "dim"), ("Name", "cyan"), ("Fingerprint", "dim"), ("Created", "dim")],
        rows,
        data_for_json=keys,
    )


@app.command("create-ssh-key")
def ssh_key_create(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", "-n", help="SSH key name")],
    public_key: Annotated[str | None, typer.Option("--public-key", help="Public key content")] = None,
    public_key_path: Annotated[str | None, typer.Option("--public-key-file", help="Path to public key file")] = None,
    private_key_path: Annotated[str | None, typer.Option("--private-key-file", help="Path to private key file")] = None,
) -> None:
    """Create/add an SSH key."""
    c: AppContext = ctx.obj
    payload: dict = {"name": name}
    if public_key:
        payload["publicKey"] = public_key
    elif public_key_path:
        try:
            with open(public_key_path) as f:
                payload["publicKey"] = f.read().strip()
        except FileNotFoundError as e:
            c.output.error(f"File not found: {e}")
            raise typer.Exit(1) from e
    if private_key_path:
        if not c.client.root_url.startswith("https://"):
            c.output.error("Refusing to transmit private key over non-HTTPS connection")
            raise typer.Exit(1)
        try:
            with open(private_key_path) as f:
                payload["privateKey"] = f.read()
        except FileNotFoundError as e:
            c.output.error(f"File not found: {e}")
            raise typer.Exit(1) from e
    result = c.client.post("/sshKey.create", json=payload)
    kid = result.get("sshKeyId", "") if isinstance(result, dict) else ""
    c.output.success(f"SSH key '{name}' created: {kid}")
    if c.json_mode:
        c.output.raw_json(result)


@app.command("remove-ssh-key")
def ssh_key_remove(
    ctx: typer.Context,
    ssh_key_id: Annotated[str, typer.Argument(help="SSH key ID to remove")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
) -> None:
    """Remove an SSH key (destructive)."""
    c: AppContext = ctx.obj
    if not force:
        typer.confirm(f"Remove SSH key '{ssh_key_id}'?", abort=True)
    result = c.client.post("/sshKey.remove", json={"sshKeyId": ssh_key_id})
    c.output.success(f"SSH key '{ssh_key_id}' removed")
    if c.json_mode:
        c.output.raw_json(result)
