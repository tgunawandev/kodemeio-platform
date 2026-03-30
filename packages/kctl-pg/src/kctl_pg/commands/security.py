"""Security management commands."""

from __future__ import annotations

from typing import Annotated

import typer

from kctl_pg.core.callbacks import AppContext
from kctl_pg.core.exceptions import DatabaseError

app = typer.Typer(help="Security management (SSL, HBA, privileges, RLS, auditing).")


@app.command("ssl")
def ssl_status(ctx: typer.Context) -> None:
    """Show SSL connection status for all active connections."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            a.pid,
            a.usename,
            a.datname,
            a.client_addr::text,
            s.ssl,
            s.version AS ssl_version,
            s.cipher,
            s.bits,
            s.client_dn,
            s.client_serial::text,
            a.backend_start::text
        FROM pg_stat_ssl s
        JOIN pg_stat_activity a ON a.pid = s.pid
        WHERE a.backend_type = 'client backend'
        ORDER BY s.ssl DESC, a.usename
    """)

    if not rows_data:
        out.info("No active client connections")
        return

    ssl_count = sum(1 for r in rows_data if r["ssl"])
    total = len(rows_data)

    rows = [
        [
            str(r["pid"]),
            r["usename"] or "-",
            r["datname"] or "-",
            r["client_addr"] or "local",
            "[green]yes[/green]" if r["ssl"] else "[red]no[/red]",
            r["ssl_version"] or "-",
            r["cipher"] or "-",
            str(r["bits"]) if r["bits"] else "-",
            "[green]yes[/green]" if r["client_dn"] else "[dim]no[/dim]",
        ]
        for r in rows_data
    ]

    out.table(
        f"SSL Status ({ssl_count}/{total} using SSL)",
        [
            ("PID", ""),
            ("User", ""),
            ("Database", "cyan"),
            ("Client", ""),
            ("SSL", ""),
            ("Version", "green"),
            ("Cipher", "dim"),
            ("Bits", "dim"),
            ("Client Cert", ""),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command("hba-rules")
def hba_rules(ctx: typer.Context) -> None:
    """Show pg_hba.conf rules (PostgreSQL 15+)."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    # Check version
    version = c.short_version
    major = int(version.split(".")[0]) if version and version[0].isdigit() else 0

    if major < 15:
        out.error(f"pg_hba_file_rules view requires PostgreSQL 15+ (current: {version})")
        out.info("On older versions, inspect pg_hba.conf directly on the server.")
        raise typer.Exit(1)

    try:
        rows_data = c.fetchall("""
            SELECT
                rule_number,
                type,
                database,
                user_name,
                address,
                netmask,
                auth_method,
                options,
                error
            FROM pg_hba_file_rules
            ORDER BY rule_number
        """)
    except DatabaseError:
        # Fallback for PG15 where column names may differ slightly
        try:
            rows_data = c.fetchall("""
                SELECT
                    line_number AS rule_number,
                    type,
                    database,
                    user_name,
                    address,
                    netmask,
                    auth_method,
                    options,
                    error
                FROM pg_hba_file_rules
                ORDER BY line_number
            """)
        except DatabaseError as e:
            out.error(f"Failed to query pg_hba_file_rules: {e}")
            raise typer.Exit(1) from e

    if not rows_data:
        out.info("No HBA rules found")
        return

    error_count = sum(1 for r in rows_data if r.get("error"))

    rows = [
        [
            str(r["rule_number"]),
            r["type"] or "-",
            ", ".join(r["database"]) if isinstance(r["database"], list) else str(r["database"] or "-"),
            ", ".join(r["user_name"]) if isinstance(r["user_name"], list) else str(r["user_name"] or "-"),
            r["address"] or "*",
            r["auth_method"] or "-",
            str(r["options"] or ""),
            f"[red]{r['error']}[/red]" if r.get("error") else "",
        ]
        for r in rows_data
    ]

    title = f"HBA Rules ({len(rows_data)})"
    if error_count:
        title += f" — [red]{error_count} errors[/red]"

    out.table(
        title,
        [
            ("#", "dim"),
            ("Type", ""),
            ("Database", "cyan"),
            ("User", ""),
            ("Address", ""),
            ("Auth Method", "green"),
            ("Options", "dim"),
            ("Error", "red"),
        ],
        rows,
        data_for_json=rows_data,
    )


@app.command()
def privileges(
    ctx: typer.Context,
    role: Annotated[str, typer.Argument(help="Role name to inspect")],
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database name (default: current)")] = None,
) -> None:
    """Show privileges for a specific role (tables, routines, database-level)."""
    actx: AppContext = ctx.obj
    out = actx.output

    if database:
        c = actx.get_client(database)
    else:
        c = actx.client

    try:
        # Check if role exists
        role_exists = c.fetchval("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,))
        if not role_exists:
            out.error(f"Role '{role}' not found")
            if database:
                c.close()
            raise typer.Exit(1)

        # Role attributes
        role_info = c.fetchone(
            """
            SELECT
                rolname,
                rolsuper,
                rolinherit,
                rolcreaterole,
                rolcreatedb,
                rolcanlogin,
                rolreplication,
                rolbypassrls,
                rolconnlimit,
                rolvaliduntil::text
            FROM pg_roles
            WHERE rolname = %s
        """,
            (role,),
        )

        sections = []
        if role_info:
            attrs = []
            if role_info["rolsuper"]:
                attrs.append("SUPERUSER")
            if role_info["rolcreatedb"]:
                attrs.append("CREATEDB")
            if role_info["rolcreaterole"]:
                attrs.append("CREATEROLE")
            if role_info["rolcanlogin"]:
                attrs.append("LOGIN")
            if role_info["rolreplication"]:
                attrs.append("REPLICATION")
            if role_info["rolbypassrls"]:
                attrs.append("BYPASSRLS")

            sections.append(
                (
                    "Role Attributes",
                    [
                        ("Name", role_info["rolname"]),
                        ("Attributes", ", ".join(attrs) if attrs else "none"),
                        ("Connection Limit", str(role_info["rolconnlimit"])),
                        ("Valid Until", role_info["rolvaliduntil"] or "never"),
                    ],
                )
            )

        # Membership
        memberships = c.fetchall(
            """
            SELECT
                r.rolname AS member_of
            FROM pg_auth_members m
            JOIN pg_roles r ON r.oid = m.roleid
            JOIN pg_roles u ON u.oid = m.member
            WHERE u.rolname = %s
            ORDER BY r.rolname
        """,
            (role,),
        )

        if memberships:
            sections.append(
                (
                    "Member Of",
                    [(m["member_of"], "granted") for m in memberships],
                )
            )

        # Table grants
        table_grants = c.fetchall(
            """
            SELECT
                table_schema,
                table_name,
                string_agg(privilege_type, ', ' ORDER BY privilege_type) AS privileges
            FROM information_schema.role_table_grants
            WHERE grantee = %s
            GROUP BY table_schema, table_name
            ORDER BY table_schema, table_name
        """,
            (role,),
        )

        if table_grants:
            sections.append(
                (
                    f"Table Privileges ({len(table_grants)})",
                    [
                        (f"{g['table_schema']}.{g['table_name']}", g["privileges"])
                        for g in table_grants[:20]  # Limit display
                    ],
                )
            )
            if len(table_grants) > 20:
                sections[-1][1].append(("...", f"and {len(table_grants) - 20} more"))

        # Routine grants
        routine_grants = c.fetchall(
            """
            SELECT
                routine_schema,
                routine_name,
                string_agg(privilege_type, ', ' ORDER BY privilege_type) AS privileges
            FROM information_schema.role_routine_grants
            WHERE grantee = %s
            GROUP BY routine_schema, routine_name
            ORDER BY routine_schema, routine_name
        """,
            (role,),
        )

        if routine_grants:
            sections.append(
                (
                    f"Routine Privileges ({len(routine_grants)})",
                    [(f"{g['routine_schema']}.{g['routine_name']}", g["privileges"]) for g in routine_grants[:20]],
                )
            )
            if len(routine_grants) > 20:
                sections[-1][1].append(("...", f"and {len(routine_grants) - 20} more"))

        # Database-level privileges
        db_privs = c.fetchall(
            """
            SELECT
                datname,
                has_database_privilege(%s, datname, 'CONNECT') AS can_connect,
                has_database_privilege(%s, datname, 'CREATE') AS can_create,
                has_database_privilege(%s, datname, 'TEMPORARY') AS can_temp
            FROM pg_database
            WHERE datname NOT LIKE 'template%%'
            ORDER BY datname
        """,
            (role, role, role),
        )

        if db_privs:
            sections.append(
                (
                    "Database Privileges",
                    [
                        (
                            d["datname"],
                            ", ".join(
                                p
                                for p, v in [
                                    ("CONNECT", d["can_connect"]),
                                    ("CREATE", d["can_create"]),
                                    ("TEMPORARY", d["can_temp"]),
                                ]
                                if v
                            )
                            or "none",
                        )
                        for d in db_privs
                    ],
                )
            )

        if not sections:
            out.info(f"No privileges found for role '{role}'")
            if database:
                c.close()
            return

        json_data = {
            "role": role_info,
            "memberships": memberships,
            "table_grants": table_grants,
            "routine_grants": routine_grants,
            "database_privileges": db_privs,
        }

        out.detail(f"Privileges for '{role}'", sections, data_for_json=json_data)
    finally:
        if database:
            c.close()


@app.command("rls")
def rls_status(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database name (default: current)")] = None,
) -> None:
    """Show tables with Row-Level Security (RLS) enabled."""
    actx: AppContext = ctx.obj
    out = actx.output

    if database:
        c = actx.get_client(database)
    else:
        c = actx.client

    try:
        rows_data = c.fetchall("""
            SELECT
                n.nspname AS schema,
                c.relname AS table_name,
                c.relrowsecurity AS rls_enabled,
                c.relforcerowsecurity AS rls_forced,
                pg_catalog.pg_get_userbyid(c.relowner) AS owner,
                (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policy_count
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind = 'r'
              AND c.relrowsecurity = true
              AND n.nspname NOT IN ('pg_catalog', 'information_schema')
            ORDER BY n.nspname, c.relname
        """)

        if not rows_data:
            out.info("No tables have RLS enabled")
            if database:
                c.close()
            return

        rows = [
            [
                f"{r['schema']}.{r['table_name']}",
                r["owner"],
                "[green]yes[/green]",
                "[green]yes[/green]" if r["rls_forced"] else "[dim]no[/dim]",
                str(r["policy_count"]),
            ]
            for r in rows_data
        ]

        out.table(
            f"Tables with RLS ({len(rows_data)})",
            [
                ("Table", "cyan"),
                ("Owner", ""),
                ("RLS Enabled", ""),
                ("RLS Forced", ""),
                ("# Policies", "yellow"),
            ],
            rows,
            data_for_json=rows_data,
        )
    finally:
        if database:
            c.close()


@app.command("rls-policies")
def rls_policies(
    ctx: typer.Context,
    database: Annotated[str | None, typer.Option("--db", "-d", help="Database name (default: current)")] = None,
    table: Annotated[str | None, typer.Option("--table", "-t", help="Filter by table name")] = None,
) -> None:
    """Show RLS policies (name, table, command, roles, expressions)."""
    actx: AppContext = ctx.obj
    out = actx.output

    if database:
        c = actx.get_client(database)
    else:
        c = actx.client

    try:
        sql = """
            SELECT
                p.polname AS policy_name,
                n.nspname AS schema,
                c.relname AS table_name,
                CASE p.polcmd
                    WHEN 'r' THEN 'SELECT'
                    WHEN 'a' THEN 'INSERT'
                    WHEN 'w' THEN 'UPDATE'
                    WHEN 'd' THEN 'DELETE'
                    WHEN '*' THEN 'ALL'
                    ELSE p.polcmd::text
                END AS command,
                CASE
                    WHEN p.polpermissive THEN 'PERMISSIVE'
                    ELSE 'RESTRICTIVE'
                END AS type,
                ARRAY(
                    SELECT rolname FROM pg_roles
                    WHERE oid = ANY(p.polroles)
                )::text[] AS roles,
                pg_get_expr(p.polqual, p.polrelid, true) AS using_expr,
                pg_get_expr(p.polwithcheck, p.polrelid, true) AS with_check_expr
            FROM pg_policy p
            JOIN pg_class c ON c.oid = p.polrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
        """
        params: list = []

        if table:
            sql += " AND c.relname = %s"
            params.append(table)

        sql += " ORDER BY n.nspname, c.relname, p.polname"

        rows_data = c.fetchall(sql, tuple(params) if params else None)

        if not rows_data:
            msg = "No RLS policies found"
            if table:
                msg += f" for table '{table}'"
            out.info(msg)
            if database:
                c.close()
            return

        rows = [
            [
                r["policy_name"],
                f"{r['schema']}.{r['table_name']}",
                r["command"],
                r["type"],
                ", ".join(r["roles"]) if r["roles"] else "(public)",
                (r["using_expr"] or "-")[:50],
                (r["with_check_expr"] or "-")[:50],
            ]
            for r in rows_data
        ]

        out.table(
            f"RLS Policies ({len(rows_data)})",
            [
                ("Policy", "cyan"),
                ("Table", ""),
                ("Command", ""),
                ("Type", "green"),
                ("Roles", ""),
                ("USING", "dim"),
                ("WITH CHECK", "dim"),
            ],
            rows,
            data_for_json=rows_data,
        )
    finally:
        if database:
            c.close()


@app.command("superuser-audit")
def superuser_audit(ctx: typer.Context) -> None:
    """Audit superuser roles and their recent activity."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            r.rolname,
            r.rolcanlogin,
            r.rolcreatedb,
            r.rolcreaterole,
            r.rolreplication,
            r.rolbypassrls,
            r.rolconnlimit,
            r.rolvaliduntil::text,
            (
                SELECT count(*)
                FROM pg_stat_activity a
                WHERE a.usename = r.rolname
                  AND a.backend_type = 'client backend'
            ) AS active_connections,
            (
                SELECT a.state
                FROM pg_stat_activity a
                WHERE a.usename = r.rolname
                  AND a.backend_type = 'client backend'
                ORDER BY a.backend_start DESC
                LIMIT 1
            ) AS latest_state,
            (
                SELECT a.client_addr::text
                FROM pg_stat_activity a
                WHERE a.usename = r.rolname
                  AND a.backend_type = 'client backend'
                ORDER BY a.backend_start DESC
                LIMIT 1
            ) AS latest_client,
            (
                SELECT a.backend_start::text
                FROM pg_stat_activity a
                WHERE a.usename = r.rolname
                  AND a.backend_type = 'client backend'
                ORDER BY a.backend_start DESC
                LIMIT 1
            ) AS latest_backend_start
        FROM pg_roles r
        WHERE r.rolsuper = true
        ORDER BY r.rolname
    """)

    if not rows_data:
        out.success("No superuser roles found (unlikely)")
        return

    rows = [
        [
            r["rolname"],
            "[green]yes[/green]" if r["rolcanlogin"] else "[dim]no[/dim]",
            str(r["active_connections"]),
            r["latest_state"] or "-",
            r["latest_client"] or "-",
            (r["latest_backend_start"] or "-")[:19],
            r["rolvaliduntil"] or "never",
        ]
        for r in rows_data
    ]

    out.table(
        f"Superuser Audit ({len(rows_data)} superusers)",
        [
            ("Role", "cyan"),
            ("Can Login", ""),
            ("Active Conns", "yellow"),
            ("Latest State", ""),
            ("Latest Client", ""),
            ("Last Connected", "dim"),
            ("Valid Until", ""),
        ],
        rows,
        data_for_json=rows_data,
    )

    # Warn about issues
    login_supers = [r for r in rows_data if r["rolcanlogin"]]
    if len(login_supers) > 2:
        out.warn(f"{len(login_supers)} superuser roles can login — consider reducing this number")

    no_expiry = [r for r in rows_data if r["rolcanlogin"] and not r["rolvaliduntil"]]
    if no_expiry:
        out.warn(f"Superusers without password expiry: {', '.join(r['rolname'] for r in no_expiry)}")


@app.command("password-check")
def password_check(ctx: typer.Context) -> None:
    """Check for password security issues: missing passwords, weak hashing, unnecessary passwords."""
    actx: AppContext = ctx.obj
    out = actx.output
    c = actx.client

    rows_data = c.fetchall("""
        SELECT
            rolname,
            rolcanlogin,
            rolsuper,
            rolpassword IS NOT NULL AS has_password,
            CASE
                WHEN rolpassword IS NULL THEN 'no_password'
                WHEN rolpassword LIKE 'md5%%' THEN 'md5'
                WHEN rolpassword LIKE 'SCRAM-SHA-256%%' THEN 'scram-sha-256'
                ELSE 'unknown'
            END AS hash_method,
            rolvaliduntil::text
        FROM pg_authid
        ORDER BY rolname
    """)

    if not rows_data:
        out.info("No roles found")
        return

    issues: list[dict] = []

    for r in rows_data:
        role_issues: list[str] = []

        # Login role with no password
        if r["rolcanlogin"] and not r["has_password"]:
            role_issues.append("LOGIN role without password")

        # Using md5 instead of scram-sha-256
        if r["has_password"] and r["hash_method"] == "md5":
            role_issues.append("Using weak MD5 hash (should be SCRAM-SHA-256)")

        # No login but has password (unnecessary)
        if not r["rolcanlogin"] and r["has_password"]:
            role_issues.append("NOLOGIN role has a password set (unnecessary)")

        # Expired password
        if r["rolvaliduntil"]:
            try:
                # Check using the database
                is_expired = c.fetchval("SELECT %s::timestamptz < now()", (r["rolvaliduntil"],))
                if is_expired:
                    role_issues.append(f"Password expired on {r['rolvaliduntil'][:19]}")
            except DatabaseError:
                pass

        if role_issues:
            issues.append(
                {
                    "role": r["rolname"],
                    "can_login": r["rolcanlogin"],
                    "is_super": r["rolsuper"],
                    "hash_method": r["hash_method"],
                    "issues": role_issues,
                }
            )

    # Summary table of all roles
    rows = [
        [
            r["rolname"],
            "[green]yes[/green]" if r["rolcanlogin"] else "[dim]no[/dim]",
            "[red]SUPER[/red]" if r["rolsuper"] else "",
            "[green]yes[/green]" if r["has_password"] else "[yellow]no[/yellow]",
            _hash_style(r["hash_method"]),
            (r["rolvaliduntil"] or "-")[:19],
        ]
        for r in rows_data
    ]

    out.table(
        f"Password Status ({len(rows_data)} roles)",
        [
            ("Role", "cyan"),
            ("Login", ""),
            ("Super", ""),
            ("Has Password", ""),
            ("Hash Method", ""),
            ("Valid Until", "dim"),
        ],
        rows,
        data_for_json=rows_data,
    )

    # Show issues
    if issues:
        out.warn(f"{len(issues)} role(s) with security issues:")
        issue_rows = []
        for iss in issues:
            for problem in iss["issues"]:
                issue_rows.append(
                    [
                        iss["role"],
                        "[red]SUPER[/red]" if iss["is_super"] else "",
                        f"[yellow]{problem}[/yellow]",
                    ]
                )

        out.table(
            "Security Issues",
            [
                ("Role", "cyan"),
                ("Super", ""),
                ("Issue", ""),
            ],
            issue_rows,
            data_for_json=issues,
        )
    else:
        out.success("No password security issues found")


def _hash_style(method: str) -> str:
    """Style the hash method with appropriate color."""
    if method == "scram-sha-256":
        return "[green]scram-sha-256[/green]"
    if method == "md5":
        return "[red]md5[/red]"
    if method == "no_password":
        return "[yellow]none[/yellow]"
    return method
