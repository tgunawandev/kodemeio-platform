"""Claude Code skill integration commands for kctl-supa."""

from __future__ import annotations

import typer

app = typer.Typer(help="Claude Code skill integration.", hidden=True)


_CAPABILITIES = """
kctl-supa — Kodemeio Supabase CLI capabilities:

CONFIG & ADMIN
  config init/show/add/set/use/remove/list  — manage profiles and connection settings
  doctor check                               — run full diagnostics (DNS, HTTP, DB, disk)

HEALTH & STATUS
  health check / db / ping                   — HTTP health checks and DB health
  status containers / ps / services          — container and service status
  dashboard url / open / status              — Supabase Studio dashboard

SERVICES
  realtime status / channels / connections   — Realtime service management
  monitor overview / connections / disk / slow-queries  — Performance monitoring

DATABASE
  db size / tables / extensions / schemas / connections / query  — DB introspection
  migrate run / status / create / diff       — Migration management
  backup create / list / restore / verify    — Backup operations
  maintenance vacuum / reindex / analyze / pool-stats / connections / kill-idle  — Maintenance

AUTH & USERS
  auth list / get / create / delete / update / generate-link / invite  — User management

STORAGE & FILES
  storage buckets / create-bucket / delete-bucket / ls / info  — Bucket and object management

REALTIME & FUNCTIONS
  functions list / deploy / logs / invoke    — Edge function management

OPERATIONS
  logs tail / search / follow                — Log management
  deploy up / down / restart / pull / redeploy  — Stack deployment

SECURITY
  security rls-policies / jwt-inspect / api-keys / audit  — Security checks

OTHER
  self-update                                — Upgrade kctl-supa
  completions                                — Shell completion setup
"""


@app.command()
def describe(ctx: typer.Context) -> None:
    """Output kctl-supa capabilities for Claude Code."""
    typer.echo(_CAPABILITIES)
