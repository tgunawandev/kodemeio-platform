"""inspect — URL Inspection API (2000/day quota)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Annotated

import typer
from rich.progress import Progress

app = typer.Typer(help="URL inspection + request-index.")


def _sleep(seconds: float) -> None:  # indirection for tests
    time.sleep(seconds)


def _inspect_one(client, property_uri: str, url: str) -> dict:
    body = {"inspectionUrl": url, "siteUrl": property_uri}
    resp = client.url_inspection().inspect(body=body).execute() or {}
    r = resp.get("inspectionResult", {})
    idx = r.get("indexStatusResult", {})
    mob = r.get("mobileUsabilityResult", {})
    return {
        "url": url,
        "indexed": idx.get("verdict", "") == "PASS",
        "verdict": idx.get("verdict", ""),
        "canonical": idx.get("googleCanonical", ""),
        "last_crawl": idx.get("lastCrawlTime", ""),
        "mobile": mob.get("verdict", ""),
    }


@app.command()
def url(ctx: typer.Context, url: str) -> None:
    """Inspect one URL."""
    actx = ctx.obj
    row = _inspect_one(actx.client, actx.property, url)
    sections = [
        (
            "Inspection",
            [
                ("url", str(row["url"])),
                ("indexed", str(row["indexed"])),
                ("verdict", str(row["verdict"])),
                ("canonical", str(row["canonical"])),
                ("last_crawl", str(row["last_crawl"])),
                ("mobile", str(row["mobile"])),
            ],
        )
    ]
    actx.output.detail(f"URL: {url}", sections, data_for_json=row)


@app.command()
def bulk(
    ctx: typer.Context,
    urls_file: Path,
    rps: Annotated[float, typer.Option("--rps", help="Max requests/sec")] = 1.0,
) -> None:
    """Inspect every URL in a newline-separated file (respects quota)."""
    actx = ctx.obj
    out = actx.output
    delay = 1.0 / max(rps, 0.1)
    lines = [ln.strip() for ln in urls_file.read_text().splitlines() if ln.strip()]
    results: list[dict] = []
    with Progress(disable=actx.quiet) as prog:
        task = prog.add_task("inspecting", total=len(lines))
        for i, line in enumerate(lines):
            results.append(_inspect_one(actx.client, actx.property, line))
            prog.update(task, advance=1)
            if i < len(lines) - 1:
                _sleep(delay)
    rows = [
        [
            str(d["url"]),
            str(d["indexed"]),
            str(d["canonical"]),
            str(d["last_crawl"]),
            str(d["mobile"]),
        ]
        for d in results
    ]
    out.table(
        "Inspection results",
        [("url", "cyan"), ("indexed", ""), ("canonical", ""), ("last_crawl", ""), ("mobile", "")],
        rows,
        data_for_json=results,
    )


@app.command("request-index")
def request_index(ctx: typer.Context, url: str) -> None:
    """Inspecting implicitly reports a URL; GSC does not have an explicit re-index API v1 endpoint."""
    actx = ctx.obj
    row = _inspect_one(actx.client, actx.property, url)
    actx.output.info(
        f"Inspection submitted for {url} — verdict={row['verdict']}. "
        "Google treats inspection as a signal; re-crawl latency is not guaranteed."
    )
