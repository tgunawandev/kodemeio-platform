"""Server configuration management commands.

Includes:
- Outgoing/incoming mail server management
- Default value management
- System parameter (ir.config_parameter) management
"""

from __future__ import annotations

from typing import Annotated, Optional

import typer

from kctl_odoo.core.callbacks import AppContext
from kctl_odoo.core.exceptions import RPCError

app = typer.Typer(help="Manage Odoo server configuration (mail servers, defaults, system parameters).")


@app.command("mail-outgoing")
def mail_outgoing(ctx: typer.Context) -> None:
    """List outgoing SMTP mail servers."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    servers = c.search_read(
        "ir.mail_server",
        domain=[],
        fields=["id", "name", "smtp_host", "smtp_port", "smtp_encryption", "smtp_user", "active", "sequence"],
        order="sequence, id",
    )

    if not servers:
        out.info("No outgoing mail servers configured.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for s in servers:
        status = "[green]active[/green]" if s.get("active") else "[dim]inactive[/dim]"
        rows.append(
            [
                str(s["id"]),
                s.get("name", ""),
                s.get("smtp_host", ""),
                str(s.get("smtp_port", "")),
                s.get("smtp_encryption", "") or "none",
                s.get("smtp_user", "") or "-",
                status,
            ]
        )
        json_data.append(
            {
                "id": s["id"],
                "name": s.get("name"),
                "smtp_host": s.get("smtp_host"),
                "smtp_port": s.get("smtp_port"),
                "smtp_encryption": s.get("smtp_encryption"),
                "smtp_user": s.get("smtp_user"),
                "active": s.get("active"),
                "sequence": s.get("sequence"),
            }
        )

    out.table(
        f"Outgoing Mail Servers ({len(servers)})",
        [("ID", "cyan"), ("Name", ""), ("Host", ""), ("Port", ""), ("Encryption", ""), ("User", "dim"), ("Status", "")],
        rows,
        data_for_json=json_data,
    )


@app.command("add-mail-outgoing")
def mail_outgoing_add(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Server display name")],
    host: Annotated[str, typer.Option("--host", help="SMTP server hostname")],
    port: Annotated[int, typer.Option("--port", help="SMTP server port")],
    user: Annotated[str | None, typer.Option("--user", help="SMTP username")] = None,
    password: Annotated[str | None, typer.Option("--password", help="SMTP password")] = None,
    encryption: Annotated[str, typer.Option("--encryption", help="Encryption: none, starttls, or ssl")] = "none",
) -> None:
    """Add a new outgoing SMTP mail server."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if encryption not in ("none", "starttls", "ssl"):
        out.error("Encryption must be 'none', 'starttls', or 'ssl'.")
        raise typer.Exit(1)

    vals: dict = {
        "name": name,
        "smtp_host": host,
        "smtp_port": port,
        "smtp_encryption": encryption,
    }
    if user:
        vals["smtp_user"] = user
    if password:
        vals["smtp_pass"] = password

    try:
        server_id = c.create("ir.mail_server", vals)
    except RPCError as e:
        out.error(f"Failed to create SMTP server: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Created outgoing mail server '{name}' (ID: {server_id})")
    if actx.json_mode:
        out.raw_json({"id": server_id, "name": name, "host": host, "port": port})


@app.command("test-mail-outgoing")
def mail_outgoing_test(
    ctx: typer.Context,
    server_id: Annotated[int, typer.Argument(help="SMTP server ID to test")],
) -> None:
    """Test an outgoing SMTP server connection."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify server exists
    servers = c.search_read(
        "ir.mail_server",
        domain=[("id", "=", server_id)],
        fields=["id", "name", "smtp_host", "smtp_port"],
    )
    if not servers:
        out.error(f"SMTP server ID {server_id} not found.")
        raise typer.Exit(1)

    server_info = servers[0]
    out.info(f"Testing SMTP server: {server_info['name']} ({server_info['smtp_host']}:{server_info['smtp_port']})")

    try:
        c.execute_kw("ir.mail_server", "test_smtp_connection", [[server_id]])
        out.success(f"SMTP connection test passed for server '{server_info['name']}'")
        if actx.json_mode:
            out.raw_json({"server_id": server_id, "status": "ok", "name": server_info["name"]})
    except RPCError as e:
        out.error(f"SMTP test failed: {e.detail}")
        if actx.json_mode:
            out.raw_json({"server_id": server_id, "status": "error", "error": e.detail})
        raise typer.Exit(1) from e


@app.command("mail-incoming")
def mail_incoming(ctx: typer.Context) -> None:
    """List incoming mail servers (IMAP/POP3)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    try:
        servers = c.search_read(
            "fetchmail.server",
            domain=[],
            fields=["id", "name", "server", "port", "server_type", "user", "is_ssl", "state", "active"],
            order="name",
        )
    except RPCError as e:
        if "fetchmail.server" in str(e) or "does not exist" in str(e).lower() or "not found" in str(e).lower():
            out.warn("The 'fetchmail' module is not installed. Install it to manage incoming mail servers.")
            if actx.json_mode:
                out.raw_json([])
            return
        raise

    if not servers:
        out.info("No incoming mail servers configured.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for s in servers:
        status = "[green]active[/green]" if s.get("active") else "[dim]inactive[/dim]"
        ssl_display = "[green]yes[/green]" if s.get("is_ssl") else "no"
        state = s.get("state", "")
        state_display = "[green]done[/green]" if state == "done" else state
        rows.append(
            [
                str(s["id"]),
                s.get("name", ""),
                s.get("server", ""),
                str(s.get("port", "")),
                s.get("server_type", "").upper(),
                s.get("user", "") or "-",
                ssl_display,
                state_display,
                status,
            ]
        )
        json_data.append(
            {
                "id": s["id"],
                "name": s.get("name"),
                "server": s.get("server"),
                "port": s.get("port"),
                "server_type": s.get("server_type"),
                "user": s.get("user"),
                "is_ssl": s.get("is_ssl"),
                "state": state,
                "active": s.get("active"),
            }
        )

    out.table(
        f"Incoming Mail Servers ({len(servers)})",
        [
            ("ID", "cyan"),
            ("Name", ""),
            ("Host", ""),
            ("Port", ""),
            ("Type", ""),
            ("User", "dim"),
            ("SSL", ""),
            ("State", ""),
            ("Status", ""),
        ],
        rows,
        data_for_json=json_data,
    )


@app.command("add-mail-incoming")
def mail_incoming_add(
    ctx: typer.Context,
    name: Annotated[str, typer.Option("--name", help="Server display name")],
    host: Annotated[str, typer.Option("--host", help="Mail server hostname")],
    port: Annotated[int, typer.Option("--port", help="Mail server port")],
    server_type: Annotated[str, typer.Option("--type", help="Server type: imap or pop")],
    user: Annotated[str | None, typer.Option("--user", help="Login username")] = None,
    password: Annotated[str | None, typer.Option("--password", help="Login password")] = None,
    ssl: Annotated[bool, typer.Option("--ssl", help="Use SSL connection")] = False,
) -> None:
    """Add a new incoming mail server (IMAP/POP3)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    if server_type not in ("imap", "pop"):
        out.error("Server type must be 'imap' or 'pop'.")
        raise typer.Exit(1)

    vals: dict = {
        "name": name,
        "server": host,
        "port": port,
        "server_type": server_type,
        "is_ssl": ssl,
    }
    if user:
        vals["user"] = user
    if password:
        vals["password"] = password

    try:
        server_id = c.create("fetchmail.server", vals)
    except RPCError as e:
        if "fetchmail.server" in str(e) or "does not exist" in str(e).lower() or "not found" in str(e).lower():
            out.error("The 'fetchmail' module is not installed. Install it first: kctl-odoo modules install fetchmail")
            raise typer.Exit(1) from e
        out.error(f"Failed to create incoming mail server: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Created incoming mail server '{name}' (ID: {server_id})")
    if actx.json_mode:
        out.raw_json({"id": server_id, "name": name, "host": host, "port": port, "type": server_type})


@app.command("defaults")
def defaults_list(
    ctx: typer.Context,
    model: Annotated[str | None, typer.Option("--model", "-m", help="Filter by model name")] = None,
) -> None:
    """List default values configured in the system."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if model:
        # ir.default stores field_id (Many2one to ir.model.fields), so we need to search by the field's model
        field_ids = c.search("ir.model.fields", [("model", "=", model)])
        if not field_ids:
            out.info(f"No fields found for model '{model}'.")
            if actx.json_mode:
                out.raw_json([])
            return
        domain.append(("field_id", "in", field_ids))

    defaults = c.search_read(
        "ir.default",
        domain=domain,
        fields=["id", "field_id", "json_value", "company_id", "user_id"],
        order="field_id",
    )

    if not defaults:
        out.info("No defaults configured.")
        if actx.json_mode:
            out.raw_json([])
        return

    rows = []
    json_data = []
    for d in defaults:
        field_info = d.get("field_id")
        field_display = field_info[1] if isinstance(field_info, list) else str(field_info or "-")
        company = d.get("company_id")
        company_display = company[1] if isinstance(company, list) else str(company or "all")
        user = d.get("user_id")
        user_display = user[1] if isinstance(user, list) else str(user or "all")
        value = str(d.get("json_value", ""))[:50]

        rows.append(
            [
                str(d["id"]),
                field_display,
                value,
                company_display,
                user_display,
            ]
        )
        json_data.append(
            {
                "id": d["id"],
                "field": field_display,
                "json_value": d.get("json_value"),
                "company_id": company[0] if isinstance(company, list) else company,
                "company_name": company[1] if isinstance(company, list) else None,
                "user_id": user[0] if isinstance(user, list) else user,
                "user_name": user[1] if isinstance(user, list) else None,
            }
        )

    out.table(
        f"Default Values ({len(defaults)})",
        [("ID", "cyan"), ("Field", ""), ("Value", ""), ("Company", "dim"), ("User", "dim")],
        rows,
        data_for_json=json_data,
    )


@app.command("set-default")
def defaults_set(
    ctx: typer.Context,
    model: Annotated[str, typer.Argument(help="Model name (e.g. res.partner)")],
    field: Annotated[str, typer.Argument(help="Field name")],
    value: Annotated[str, typer.Argument(help="Default value (as JSON string)")],
    company_id: Annotated[int | None, typer.Option("--company", help="Company ID (omit for global)")] = None,
) -> None:
    """Set a default value for a model field."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Find the field ID
    field_records = c.search_read(
        "ir.model.fields",
        domain=[("model", "=", model), ("name", "=", field)],
        fields=["id", "name", "model"],
    )
    if not field_records:
        out.error(f"Field '{field}' not found on model '{model}'.")
        raise typer.Exit(1)

    field_id = field_records[0]["id"]

    vals: dict = {
        "field_id": field_id,
        "json_value": value,
    }
    if company_id is not None:
        vals["company_id"] = company_id

    try:
        default_id = c.create("ir.default", vals)
    except RPCError as e:
        out.error(f"Failed to set default: {e.detail}")
        raise typer.Exit(1) from e

    out.success(f"Set default for {model}.{field} = {value} (ID: {default_id})")
    if actx.json_mode:
        out.raw_json(
            {
                "id": default_id,
                "model": model,
                "field": field,
                "value": value,
                "company_id": company_id,
            }
        )


@app.command("delete-default")
def defaults_delete(
    ctx: typer.Context,
    default_id: Annotated[int, typer.Argument(help="Default record ID to delete")],
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Delete a default value record."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Verify it exists
    defaults = c.search_read(
        "ir.default",
        domain=[("id", "=", default_id)],
        fields=["id", "field_id", "json_value"],
    )
    if not defaults:
        out.error(f"Default record ID {default_id} not found.")
        raise typer.Exit(1)

    d = defaults[0]
    field_info = d.get("field_id")
    field_display = field_info[1] if isinstance(field_info, list) else str(field_info)

    if not force and not typer.confirm(f"Delete default for {field_display} (value: {d.get('json_value')})?"):
        raise typer.Exit(0)

    c.unlink("ir.default", [default_id])
    out.success(f"Deleted default record ID {default_id} ({field_display})")
    if actx.json_mode:
        out.raw_json({"id": default_id, "deleted": True})


# ---------------------------------------------------------------------------
# System Parameters (ir.config_parameter) — merged from params.py
# ---------------------------------------------------------------------------


@app.command("params")
def params_list(
    ctx: typer.Context,
    search: Annotated[str | None, typer.Option("--search", "-s", help="Filter by key pattern")] = None,
    limit: Annotated[int, typer.Option("--limit", "-l")] = 100,
) -> None:
    """List system parameters."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if search:
        domain.append(("key", "ilike", search))

    params = c.search_read(
        "ir.config_parameter",
        domain=domain,
        fields=["id", "key", "value"],
        limit=limit,
        order="key",
    )

    rows = []
    for p in params:
        value = str(p.get("value", ""))
        if len(value) > 60:
            value = value[:57] + "..."
        rows.append([str(p["id"]), p["key"], value])

    out.table(
        f"System Parameters ({len(params)})",
        [("ID", "cyan"), ("Key", ""), ("Value", "")],
        rows,
        data_for_json=params,
    )


@app.command("get-param")
def params_get(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Parameter key")],
) -> None:
    """Get a system parameter value."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    params = c.search_read(
        "ir.config_parameter",
        domain=[("key", "=", key)],
        fields=["id", "key", "value"],
    )

    if not params:
        out.error(f"Parameter not found: {key}")
        raise typer.Exit(1)

    p = params[0]
    out.detail(
        f"Parameter: {key}",
        [
            (
                "Details",
                [
                    ("ID", str(p["id"])),
                    ("Key", p["key"]),
                    ("Value", str(p.get("value", ""))),
                ],
            ),
        ],
        data_for_json=p,
    )


@app.command("set-param")
def params_set(
    ctx: typer.Context,
    key: Annotated[str, typer.Argument(help="Parameter key")],
    value: Annotated[str, typer.Argument(help="Parameter value")],
) -> None:
    """Set a system parameter value (creates if not exists)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    c.execute_kw("ir.config_parameter", "set_param", [key, value])
    out.success(f"{key} = {value}")


@app.command("sync-base-url")
def sync_base_url(
    ctx: typer.Context,
    all_dbs: Annotated[bool, typer.Option("--all-dbs", help="Sync across all databases")] = False,
) -> None:
    """Update web.base.url to match the CLI profile URL.

    Prevents stale URLs in emails and reports after port changes.

    Examples:
        kctl-odoo server sync-base-url
        kctl-odoo server sync-base-url --all-dbs
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    profile_url = c._base_url

    if all_dbs:
        try:
            db_list = c.db_list()
        except Exception:
            out.error("Could not list databases. Check admin password.")
            raise typer.Exit(1) from None

        for db_name in db_list:
            try:
                db_client = c.with_database(db_name)
                current = db_client.search_read(
                    "ir.config_parameter",
                    domain=[("key", "=", "web.base.url")],
                    fields=["value"],
                )
                current_url = current[0]["value"] if current else ""
                if current_url == profile_url:
                    out.info(f"  {db_name}: already correct ({profile_url})")
                else:
                    db_client.execute_kw("ir.config_parameter", "set_param", ["web.base.url", profile_url])
                    out.success(f"  {db_name}: {current_url} -> {profile_url}")
            except Exception as e:
                out.warn(f"  {db_name}: skipped ({e})")
    else:
        current = c.search_read(
            "ir.config_parameter",
            domain=[("key", "=", "web.base.url")],
            fields=["value"],
        )
        current_url = current[0]["value"] if current else ""
        if current_url == profile_url:
            out.info(f"web.base.url already correct: {profile_url}")
        else:
            c.execute_kw("ir.config_parameter", "set_param", ["web.base.url", profile_url])
            out.success(f"web.base.url: {current_url} -> {profile_url}")


@app.command("params-export")
def params_export(
    ctx: typer.Context,
    output: Annotated[str, typer.Option("--output", "-o", help="Output file (YAML or JSON)")] = "params.yaml",
    search: Annotated[Optional[str], typer.Option("--search", "-s", help="Filter by key pattern")] = None,
) -> None:
    """Export system parameters to YAML or JSON file.

    Examples:
        kctl-odoo server params-export -o params.yaml
        kctl-odoo server params-export -s web. -o web_params.json
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    domain: list = []
    if search:
        domain.append(("key", "ilike", search))

    params = c.search_read(
        "ir.config_parameter",
        domain=domain,
        fields=["key", "value"],
        limit=1000,
        order="key",
    )

    data = {p["key"]: p["value"] for p in params}

    from pathlib import Path

    output_path = Path(output)

    if output_path.suffix in (".yaml", ".yml"):
        lines = []
        for key, value in sorted(data.items()):
            val_str = str(value).replace("\n", "\\n") if value else ""
            lines.append(f"{key}: {val_str}")
        output_path.write_text("\n".join(lines) + "\n")
    else:
        import json

        output_path.write_text(json.dumps(data, indent=2, sort_keys=True))

    out.success(f"Exported {len(data)} parameters to {output}")


@app.command("params-import")
def params_import(
    ctx: typer.Context,
    file_path: Annotated[str, typer.Argument(help="YAML or JSON file with key-value pairs")],
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show what would be changed")] = False,
    force: Annotated[bool, typer.Option("--force", help="Skip confirmation")] = False,
) -> None:
    """Import system parameters from YAML or JSON file.

    File format (YAML): key: value (one per line)
    File format (JSON): {"key": "value", ...}

    Examples:
        kctl-odoo server params-import params.yaml --dry-run
        kctl-odoo server params-import params.json --force
    """
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    from pathlib import Path

    input_path = Path(file_path)

    if not input_path.exists():
        out.error(f"File not found: {file_path}")
        raise typer.Exit(1)

    content = input_path.read_text()

    if input_path.suffix in (".json",):
        import json

        data = json.loads(content)
    else:
        data = {}
        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ": " in line:
                key, value = line.split(": ", 1)
                data[key.strip()] = value.strip()

    if not data:
        out.info("No parameters found in file.")
        return

    current = c.search_read(
        "ir.config_parameter",
        domain=[("key", "in", list(data.keys()))],
        fields=["key", "value"],
        limit=1000,
    )
    current_map = {p["key"]: p["value"] for p in current}

    changes = []
    new_keys = []
    for key, value in sorted(data.items()):
        if key in current_map:
            if str(current_map[key]) != str(value):
                changes.append((key, current_map[key], value))
        else:
            new_keys.append((key, value))

    if not changes and not new_keys:
        out.success("All parameters already match. No changes needed.")
        return

    if changes:
        out.info(f"Parameters to UPDATE ({len(changes)}):")
        for key, old, new in changes:
            old_short = str(old)[:50]
            new_short = str(new)[:50]
            out.info(f"  {key}: {old_short} -> {new_short}")

    if new_keys:
        out.info(f"Parameters to CREATE ({len(new_keys)}):")
        for key, value in new_keys:
            out.info(f"  {key}: {str(value)[:50]}")

    if dry_run:
        out.info("DRY RUN — no changes applied.")
        return

    if not force:
        if not typer.confirm(f"Apply {len(changes) + len(new_keys)} changes?"):
            out.info("Cancelled.")
            return

    applied = 0
    for key, value in data.items():
        if key in current_map and str(current_map[key]) == str(value):
            continue
        try:
            c.execute_kw("ir.config_parameter", "set_param", [key, str(value)])
            applied += 1
        except Exception as e:
            out.warn(f"  Failed: {key} — {e}")

    out.success(f"Applied {applied} parameter change(s).")
