"""doctor — diagnostic checks for kctl-gsc.

Five checks:
  1. Service-account credentials file exists and is parseable JSON.
  2. Auth works (sites.list returns without error).
  3. Configured property is in the visible list.
  4. URL Inspection quota note (Google's static 2000/day/property).
  5. Sitemaps recency — warn if any registered sitemap is stale (>7d).
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import typer

from kctl_gsc.core.config import resolve_connection

app = typer.Typer(help="Diagnostic checks.", invoke_without_command=True)


@app.callback(invoke_without_command=True)
def run(ctx: typer.Context) -> None:
    """Run all doctor checks for the active profile."""
    if ctx.invoked_subcommand is not None:
        return
    actx = ctx.obj
    out = actx.output

    passed = 0
    failed = 0

    # 1 — credentials file
    creds_path, prop = resolve_connection(
        profile_name=actx.profile,
        property_override=actx.property_override,
        credentials_file_override=actx.credentials_file_override,
    )
    creds_path_p = Path(creds_path).expanduser() if creds_path else Path()
    if creds_path_p.is_file():
        try:
            data = json.loads(creds_path_p.read_text())
            sa_email = data.get("client_email", "?")
            out.success(f"credentials file ok -> {sa_email}")
            passed += 1
        except Exception as e:
            out.error(f"credentials file not JSON: {e}")
            failed += 1
            raise typer.Exit(code=1) from e
    else:
        out.error(f"credentials file missing: {creds_path_p}")
        failed += 1
        raise typer.Exit(code=1)

    # 2 — auth check (sites.list)
    try:
        client = actx.client
        entries = client.sites().list().execute() or {}
        out.success(f"auth ok - {len(entries.get('siteEntry', []))} properties visible")
        passed += 1
    except Exception as e:
        out.error(f"auth failed: {e}")
        failed += 1
        raise typer.Exit(code=1) from e

    # 3 — configured property accessible
    if prop:
        found = any(s.get("siteUrl") == prop for s in entries.get("siteEntry", []))
        if found:
            out.success(f"property accessible: {prop}")
            passed += 1
        else:
            out.error(
                f"property {prop} NOT in visible list - add {client.service_account_email} as a user in Search Console"
            )
            failed += 1

    # 4 — quota note (GSC API does not expose remaining quota; surface the static limit)
    out.info("URL Inspection quota: 2000/day per property (Google static limit)")
    passed += 1

    # 5 — sitemaps recency
    if prop:
        sm = client.sitemaps().list(siteUrl=prop).execute() or {}
        entries_sm = sm.get("sitemap", [])
        if not entries_sm:
            out.warn(f"sitemaps: none submitted for {prop}")
        else:
            now = datetime.now(UTC)
            stale: list[str] = []
            for s in entries_sm:
                last = s.get("lastSubmitted") or s.get("lastDownloaded") or ""
                if last:
                    try:
                        ts = datetime.fromisoformat(last.replace("Z", "+00:00"))
                        if now - ts > timedelta(days=7):
                            stale.append(s.get("path", ""))
                    except ValueError:
                        pass
            if stale:
                out.warn(f"sitemaps stale (>7d): {', '.join(stale)}")
            else:
                out.success("sitemaps recent")
        passed += 1

    out.info(f"\ndoctor: {passed} ok / {failed} failed")
    if failed:
        raise typer.Exit(code=1)
