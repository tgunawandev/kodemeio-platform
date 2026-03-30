"""Performance testing commands for kctl-api.

Benchmarking, profiling, and latency analysis.
"""

from __future__ import annotations

import statistics
import time
from typing import Annotated

import typer

from kctl_api.core.callbacks import AppContext

app = typer.Typer(name="perf", help="Performance — bench, profile, latency, endpoints.", no_args_is_help=True)


# ---------------------------------------------------------------------------
# bench
# ---------------------------------------------------------------------------
@app.command()
def bench(
    ctx: typer.Context,
    endpoint: Annotated[str, typer.Argument(help="Endpoint path to benchmark (e.g. /api/v1/health).")],
    rps: Annotated[int, typer.Option("--rps", help="Target requests per second.")] = 10,
    duration: Annotated[int, typer.Option("--duration", help="Test duration in seconds.")] = 10,
    method: Annotated[str, typer.Option("--method", "-X", help="HTTP method.")] = "GET",
) -> None:
    """Load test an endpoint — target RPS for a duration."""
    actx: AppContext = ctx.obj
    out = actx.output

    total_requests = rps * duration
    interval = 1.0 / rps

    out.info(f"Benchmarking {method} {endpoint} — {rps} RPS for {duration}s ({total_requests} requests) ...")

    latencies: list[float] = []
    errors: list[str] = []
    status_counts: dict[int, int] = {}

    start_time = time.monotonic()
    next_send = start_time

    for i in range(total_requests):
        # Rate control
        now = time.monotonic()
        if now < next_send:
            time.sleep(next_send - now)
        next_send = time.monotonic() + interval

        req_start = time.monotonic()
        try:
            response = actx.client.get_raw(endpoint)

            elapsed_ms = (time.monotonic() - req_start) * 1000
            latencies.append(elapsed_ms)
            status = response.status_code
            status_counts[status] = status_counts.get(status, 0) + 1
        except Exception as e:
            elapsed_ms = (time.monotonic() - req_start) * 1000
            latencies.append(elapsed_ms)
            errors.append(str(e)[:60])

        # Progress every 10%
        if (i + 1) % max(total_requests // 10, 1) == 0:
            pct = round((i + 1) / total_requests * 100)
            out.info(f"  Progress: {pct}% ({i + 1}/{total_requests})")

    total_time = time.monotonic() - start_time
    actual_rps = round(len(latencies) / max(total_time, 0.001))

    if not latencies:
        out.error("No requests completed.")
        raise typer.Exit(1)

    sorted_lat = sorted(latencies)
    p50 = statistics.median(sorted_lat)
    p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
    p99 = sorted_lat[int(len(sorted_lat) * 0.99)]
    avg = statistics.mean(sorted_lat)
    min_lat = min(sorted_lat)
    max_lat = max(sorted_lat)

    out.text("")
    out.header(f"Benchmark Results: {endpoint}")
    out.text(f"  Duration:    {round(total_time, 1)}s")
    out.text(f"  Requests:    {len(latencies)}")
    out.text(f"  Actual RPS:  {actual_rps}")
    out.text(f"  Errors:      [{'red' if errors else 'green'}]{len(errors)}[/{'red' if errors else 'green'}]")
    out.text("")
    out.text("  Latency:")
    out.text(f"    min:  {round(min_lat, 1)}ms")
    out.text(f"    avg:  {round(avg, 1)}ms")
    out.text(f"    p50:  {round(p50, 1)}ms")
    out.text(f"    p95:  {round(p95, 1)}ms")
    out.text(f"    p99:  {round(p99, 1)}ms")
    out.text(f"    max:  {round(max_lat, 1)}ms")
    out.text("")
    if status_counts:
        out.text("  Status codes: " + ", ".join(f"{k}:{v}" for k, v in sorted(status_counts.items())))

    if actx.json_mode:
        out.raw_json(
            {
                "endpoint": endpoint,
                "method": method,
                "duration_s": round(total_time, 2),
                "requests": len(latencies),
                "actual_rps": actual_rps,
                "errors": len(errors),
                "latency_ms": {
                    "min": round(min_lat, 1),
                    "avg": round(avg, 1),
                    "p50": round(p50, 1),
                    "p95": round(p95, 1),
                    "p99": round(p99, 1),
                    "max": round(max_lat, 1),
                },
                "status_counts": status_counts,
            }
        )


# ---------------------------------------------------------------------------
# profile
# ---------------------------------------------------------------------------
@app.command()
def profile(
    ctx: typer.Context,
    endpoint: Annotated[str, typer.Argument(help="Endpoint path to profile.")],
    samples: Annotated[int, typer.Option("--samples", "-n", help="Number of samples.")] = 10,
    method: Annotated[str, typer.Option("--method", "-X", help="HTTP method.")] = "GET",
) -> None:
    """Profile endpoint execution — timing breakdown over N samples."""
    actx: AppContext = ctx.obj
    out = actx.output

    out.info(f"Profiling {method} {endpoint} — {samples} samples ...")

    latencies: list[float] = []
    ttfbs: list[float] = []  # time to first byte (approximated)

    for i in range(samples):
        req_start = time.monotonic()
        try:
            actx.client.get_raw(endpoint)
            elapsed_ms = (time.monotonic() - req_start) * 1000
            latencies.append(elapsed_ms)
            ttfbs.append(elapsed_ms)  # httpx doesn't expose TTFB separately without streaming
        except Exception as e:
            out.warn(f"Sample {i + 1} failed: {e}")

    if not latencies:
        out.error("All samples failed.")
        raise typer.Exit(1)

    rows = [[str(i + 1), f"{round(lat, 1)}ms"] for i, lat in enumerate(latencies)]
    out.table(
        title=f"Profile: {endpoint} ({len(latencies)} samples)",
        columns=[("Sample", ""), ("Latency", "")],
        rows=rows,
        data_for_json=[{"sample": i + 1, "latency_ms": round(lat, 1)} for i, lat in enumerate(latencies)],
    )

    if len(latencies) > 1:
        out.text("")
        out.text(f"  avg: {round(statistics.mean(latencies), 1)}ms  stdev: {round(statistics.stdev(latencies), 1)}ms")


# ---------------------------------------------------------------------------
# latency
# ---------------------------------------------------------------------------
@app.command()
def latency(
    ctx: typer.Context,
    endpoint: Annotated[str | None, typer.Argument(help="Endpoint to check (default: /api/v1/health).")] = None,
    samples: Annotated[int, typer.Option("--samples", "-n", help="Number of samples.")] = 20,
) -> None:
    """Show latency percentiles for an endpoint."""
    actx: AppContext = ctx.obj
    out = actx.output

    target = endpoint or "/api/v1/health"
    out.info(f"Measuring latency: {target} ({samples} samples) ...")

    latencies: list[float] = []
    for _ in range(samples):
        start = time.monotonic()
        try:
            actx.client.get_raw(target)
            latencies.append((time.monotonic() - start) * 1000)
        except Exception:
            latencies.append(-1.0)

    valid = [lat for lat in latencies if lat >= 0]
    if not valid:
        out.error("All requests failed.")
        raise typer.Exit(1)

    sorted_lat = sorted(valid)
    percentiles = [50, 75, 90, 95, 99]

    rows = [
        [f"p{p}", f"{round(sorted_lat[min(int(len(sorted_lat) * p / 100), len(sorted_lat) - 1)], 1)}ms"]
        for p in percentiles
    ]
    rows.insert(0, ["min", f"{round(min(sorted_lat), 1)}ms"])
    rows.insert(1, ["avg", f"{round(statistics.mean(sorted_lat), 1)}ms"])
    rows.append(["max", f"{round(max(sorted_lat), 1)}ms"])

    failed = len(latencies) - len(valid)
    out.table(
        title=f"Latency Percentiles: {target} ({len(valid)} samples, {failed} failed)",
        columns=[("Percentile", "bold"), ("Latency", "")],
        rows=rows,
        data_for_json={
            "endpoint": target,
            "samples": len(valid),
            "failed": failed,
            "percentiles": {
                f"p{p}": round(sorted_lat[min(int(len(sorted_lat) * p / 100), len(sorted_lat) - 1)], 1)
                for p in percentiles
            },
            "min": round(min(sorted_lat), 1),
            "avg": round(statistics.mean(sorted_lat), 1),
            "max": round(max(sorted_lat), 1),
        },
    )


# ---------------------------------------------------------------------------
# endpoints
# ---------------------------------------------------------------------------
@app.command()
def endpoints(
    ctx: typer.Context,
    samples: Annotated[int, typer.Option("--samples", "-n", help="Samples per endpoint.")] = 3,
    tag: Annotated[str | None, typer.Option("--tag", help="Filter by OpenAPI tag.")] = None,
) -> None:
    """Measure response times for all GET endpoints from the OpenAPI spec."""
    actx: AppContext = ctx.obj
    out = actx.output

    # Fetch spec
    try:
        spec_data = actx.client.get("/openapi.json")
        if not spec_data:
            raise RuntimeError("Empty spec")
    except Exception as e:
        out.error(f"Failed to fetch spec: {e}")
        raise typer.Exit(1) from None

    # Collect GET endpoints
    get_endpoints: list[str] = []
    for path, path_item in spec_data.get("paths", {}).items():
        if "get" not in path_item:
            continue
        operation = path_item["get"]
        # Skip paths with parameters (can't call them without values)
        if "{" in path:
            continue
        if tag and tag not in operation.get("tags", []):
            continue
        get_endpoints.append(path)

    if not get_endpoints:
        out.warn("No GET endpoints without path parameters found.")
        raise typer.Exit(0)

    out.info(f"Testing {len(get_endpoints)} GET endpoints ({samples} samples each) ...")

    results: list[dict] = []
    for ep in get_endpoints:
        ep_latencies: list[float] = []
        last_status = 0
        for _ in range(samples):
            start = time.monotonic()
            try:
                resp = actx.client.get_raw(ep)
                last_status = resp.status_code
                ep_latencies.append((time.monotonic() - start) * 1000)
            except Exception:
                ep_latencies.append(-1.0)

        valid = [lat for lat in ep_latencies if lat >= 0]
        avg = round(statistics.mean(valid), 1) if valid else -1

        results.append(
            {
                "endpoint": ep,
                "status": last_status,
                "avg_ms": avg,
                "samples": len(valid),
            }
        )

    results.sort(key=lambda x: -x["avg_ms"])

    rows = [[r["endpoint"], str(r["status"]), f"{r['avg_ms']}ms", str(r["samples"])] for r in results]
    out.table(
        title="Endpoint Response Times (slowest first)",
        columns=[("Endpoint", ""), ("Status", ""), ("Avg Latency", "bold"), ("Samples", "")],
        rows=rows,
        data_for_json=results,
    )
