"""CI/CD pipeline commands."""

from __future__ import annotations

import time
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.exceptions import CommandError
from kctl_react.core.runner import run

app = typer.Typer(help="CI/CD pipeline gates, affected builds, and releases.")


def _run_step(
    name: str,
    cmd: list[str],
    cwd: object,
    timeout: int = 300,
) -> dict:
    """Run a pipeline step and return result dict."""
    start = time.monotonic()
    try:
        run(cmd, cwd=cwd, capture=True, timeout=timeout)
        elapsed = round(time.monotonic() - start, 1)
        return {"step": name, "status": "pass", "duration": elapsed, "exit_code": 0, "stderr": ""}
    except CommandError as e:
        elapsed = round(time.monotonic() - start, 1)
        stderr = (e.stderr or "")[-2000:]
        return {"step": name, "status": "fail", "duration": elapsed, "exit_code": e.returncode, "stderr": stderr}
    except Exception as e:
        elapsed = round(time.monotonic() - start, 1)
        return {"step": name, "status": "fail", "duration": elapsed, "exit_code": -1, "stderr": str(e)[-2000:]}


def _run_gate(
    root: object,
    app_name: str | None,
    strict: bool,
    skip_build: bool,
) -> list[dict]:
    """Execute gate pipeline steps and return results."""
    from pathlib import Path

    root_path = Path(str(root))
    filter_args = ["--filter", f"@kodemeio/{app_name}"] if app_name else []

    steps: list[tuple[str, list[str], int]] = [
        ("lint", ["pnpm", "turbo", "run", "lint", *filter_args], 300),
        ("type-check", ["pnpm", "turbo", "run", "type-check", *filter_args], 300),
        ("test:ci", ["pnpm", "turbo", "run", "test:ci", *filter_args], 300),
        ("audit", ["pnpm", "audit"], 120),
    ]

    if not skip_build:
        steps.append(("build", ["pnpm", "turbo", "run", "build", *filter_args], 600))

    if strict:
        # Also run secrets scan (reuse security helpers)
        steps.append(("secrets", ["echo", "secrets-check"], 10))  # placeholder, handled below

    results: list[dict] = []
    for step_name, cmd, timeout in steps:
        if step_name == "secrets":
            # Run secrets check via internal helper
            from kctl_react.commands.security import _collect_secrets

            findings = _collect_secrets(root_path, app_name, [], root_path / "packages")
            # If app_name not specified, scan all apps
            if not app_name:
                from kctl_react.core.discovery import discover_apps

                all_apps = list(discover_apps(root_path).keys())
                findings = _collect_secrets(root_path, None, all_apps, root_path / "packages")
            result = {
                "step": "secrets",
                "status": "pass" if len(findings) == 0 else "fail",
                "duration": 0.0,
                "exit_code": 0 if len(findings) == 0 else 1,
                "stderr": f"{len(findings)} secret(s) found" if findings else "",
            }
            results.append(result)
        else:
            results.append(_run_step(step_name, cmd, root_path, timeout))

    return results


@app.command()
def gate(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for all)")] = None,
    strict: Annotated[bool, typer.Option("--strict", help="Also run secrets + headers checks")] = False,
    skip_build: Annotated[bool, typer.Option("--skip-build", help="Skip the build step")] = False,
) -> None:
    """Run full CI gate: lint → type-check → test → audit → build."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    if app_name:
        actx.validate_app(app_name)

    target = app_name or "all apps"
    out.info(f"Running pipeline gate for {target}...")

    results = _run_gate(root, app_name, strict, skip_build)

    # Display results
    rows: list[list[str]] = []
    for r in results:
        status = "[green]PASS[/green]" if r["status"] == "pass" else "[red]FAIL[/red]"
        rows.append([r["step"], status, f"{r['duration']}s", str(r["exit_code"])])

    out.table(
        f"Pipeline Gate — {target}",
        [("Step", "cyan"), ("Status", ""), ("Duration", "green"), ("Exit", "dim")],
        rows,
        data_for_json=results,
    )

    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")

    if failed == 0:
        out.success(f"All {passed} steps passed")
    else:
        out.error(f"{failed}/{len(results)} step(s) failed")
        # Show stderr for failed steps
        for r in results:
            if r["status"] == "fail" and r["stderr"]:
                out.text(f"\n[red]{r['step']}[/red] stderr:\n{r['stderr'][:500]}")
        raise typer.Exit(1) from None


@app.command("affected-gate")
def affected_gate(
    ctx: typer.Context,
    base: Annotated[str, typer.Option("--base", help="Git base ref for diff")] = "main",
    strict: Annotated[bool, typer.Option("--strict", help="Also run secrets checks")] = False,
) -> None:
    """Run gate only for apps affected by git changes."""
    from kctl_react.core.git import get_affected_apps

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    out.info(f"Detecting affected apps (vs {base})...")
    affected = get_affected_apps(root, base)

    if not affected:
        out.success("No apps affected — nothing to check")
        if out.json_mode:
            out.raw_json({"affected": [], "results": {}})
        return

    out.info(f"Affected apps: {', '.join(affected)}")

    all_results: dict[str, list[dict]] = {}
    any_failed = False

    for app_name in affected:
        out.header(app_name)
        results = _run_gate(root, app_name, strict, skip_build=False)
        all_results[app_name] = results

        for r in results:
            if r["status"] == "fail":
                any_failed = True

    # Summary
    rows: list[list[str]] = []
    json_data: list[dict] = []

    for app_name, results in all_results.items():
        passed = sum(1 for r in results if r["status"] == "pass")
        total = len(results)
        status = "[green]PASS[/green]" if passed == total else "[red]FAIL[/red]"
        duration = sum(r["duration"] for r in results)
        rows.append([app_name, f"{passed}/{total}", f"{duration:.1f}s", status])
        json_data.append({"app": app_name, "passed": passed, "total": total, "duration": duration, "steps": results})

    out.table(
        f"Affected Gate Summary (vs {base})",
        [("App", "cyan"), ("Steps", "green"), ("Duration", ""), ("Status", "")],
        rows,
        data_for_json=json_data,
    )

    if any_failed:
        out.error("Some apps have failing steps")
        raise typer.Exit(1)
    else:
        out.success(f"All {len(affected)} affected app(s) passed")


@app.command()
def release(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    tag: Annotated[str | None, typer.Option("--tag", "-t", help="Image tag (default: git short SHA)")] = None,
    push: Annotated[bool, typer.Option("--push", help="Push image to GHCR")] = False,
) -> None:
    """Build Docker image for an app and optionally push to GHCR."""
    from kctl_react.core.git import get_last_commit_hash

    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)

    # Determine tag
    image_tag = tag or get_last_commit_hash(root) or "latest"
    image_name = f"ghcr.io/kodemeio/kodemeio-react/{app_name}:{image_tag}"

    out.info(f"Building Docker image: {image_name}")

    # Build
    try:
        run(
            [
                "docker",
                "build",
                "--build-arg",
                f"APP_NAME={app_name}",
                "-t",
                image_name,
                ".",
            ],
            cwd=root,
            capture=True,
            timeout=600,
        )
    except CommandError as e:
        out.error(f"Docker build failed: {e.stderr[:500] if e.stderr else e}")
        raise typer.Exit(1) from None

    # Get image size
    image_size = "unknown"
    try:
        inspect = run(
            ["docker", "image", "inspect", image_name, "--format", "{{.Size}}"],
            cwd=root,
            capture=True,
            timeout=10,
        )
        size_bytes = int(inspect.stdout.strip())
        from kctl_react.commands.build import _format_size

        image_size = _format_size(size_bytes)
    except Exception:
        pass

    release_info = {
        "app": app_name,
        "image": image_name,
        "tag": image_tag,
        "size": image_size,
        "pushed": False,
    }

    # Push if requested
    if push:
        out.info(f"Pushing {image_name}...")
        try:
            run(["docker", "push", image_name], cwd=root, capture=True, timeout=300)
            release_info["pushed"] = True
            out.success(f"Pushed {image_name}")
        except CommandError as e:
            out.error(f"Push failed: {e.stderr[:300] if e.stderr else e}")
            raise typer.Exit(1) from None

    out.table(
        f"Release — {app_name}",
        [("Field", "cyan"), ("Value", "")],
        [
            ["Image", image_name],
            ["Tag", image_tag],
            ["Size", image_size],
            ["Pushed", "yes" if release_info["pushed"] else "no"],
        ],
        data_for_json=[release_info],
    )

    out.success(f"Release complete: {image_name}")
