"""Capacitor native app commands."""

from __future__ import annotations

import contextlib
import json
import os
import re
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.callbacks import AppContext
from kctl_react.core.exceptions import CommandError
from kctl_react.core.runner import run, run_pnpm, run_turbo

app = typer.Typer(help="Capacitor native app management (Android/iOS).")

_DEFAULT_APP_ID_PREFIX = "io.kodeme"

# Minimum versions for a successful build
_MIN_JAVA_MAJOR = 21
_MIN_GRADLE_VERSION = "8.11"
_MIN_ANDROID_SDK = 23
_COMPILE_SDK = 35
_REQUIRED_CAP_PACKAGES = [
    "@capacitor/core",
    "@capacitor/cli",
    "@capacitor/app",
]
_ANDROID_CAP_PACKAGE = "@capacitor/android"
_IOS_CAP_PACKAGE = "@capacitor/ios"


# ── Helpers ────────────────────────────────────────────────────────


def _has_capacitor(app_dir: Path) -> bool:
    """Check if an app has Capacitor configured."""
    return (app_dir / "capacitor.config.ts").exists() or (app_dir / "capacitor.config.json").exists()


def _has_platform(app_dir: Path, platform: str) -> bool:
    """Check if a native platform directory exists."""
    return (app_dir / platform).is_dir()


def _run_cap(args: list[str], app_dir: Path, timeout: int = 120) -> None:
    """Run a Capacitor CLI command in an app directory."""
    run(["npx", "cap", *args], cwd=app_dir, capture=False, timeout=timeout)


def _get_java_major_version() -> int | None:
    """Get the major Java version (e.g. 21 for openjdk 21.0.6)."""
    try:
        result = run(["java", "--version"], cwd=Path.cwd(), capture=True, timeout=5)
        for line in (result.stdout + result.stderr).splitlines():
            match = re.search(r"(\d+)\.(\d+)", line)
            if match:
                return int(match.group(1))
    except Exception:
        pass
    return None


def _get_gradle_version(android_dir: Path) -> str | None:
    """Read Gradle version from wrapper properties."""
    props = android_dir / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if not props.exists():
        return None
    try:
        text = props.read_text()
        match = re.search(r"gradle-(\d+\.\d+(?:\.\d+)?)", text)
        return match.group(1) if match else None
    except Exception:
        return None


def _get_android_min_sdk(android_dir: Path) -> int | None:
    """Read minSdkVersion from variables.gradle."""
    variables = android_dir / "variables.gradle"
    if not variables.exists():
        return None
    try:
        text = variables.read_text()
        match = re.search(r"minSdkVersion\s*=\s*(\d+)", text)
        return int(match.group(1)) if match else None
    except Exception:
        return None


def _get_pkg_deps(app_dir: Path) -> dict[str, str]:
    """Get all deps + devDeps from package.json."""
    pkg_file = app_dir / "package.json"
    if not pkg_file.exists():
        return {}
    try:
        pkg = json.loads(pkg_file.read_text())
        return {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    except Exception:
        return {}


def _check_cap_version_match(deps: dict[str, str]) -> tuple[bool, str]:
    """Check that @capacitor/core and @capacitor/android|ios are on the same major version."""
    core_ver = deps.get("@capacitor/core", "")
    android_ver = deps.get("@capacitor/android", "")
    ios_ver = deps.get("@capacitor/ios", "")

    def _major(ver: str) -> int | None:
        match = re.search(r"(\d+)", ver)
        return int(match.group(1)) if match else None

    core_major = _major(core_ver)
    issues: list[str] = []

    if core_major and android_ver:
        android_major = _major(android_ver)
        if android_major and core_major != android_major:
            issues.append(f"@capacitor/core@{core_ver} vs @capacitor/android@{android_ver}")
    if core_major and ios_ver:
        ios_major = _major(ios_ver)
        if ios_major and core_major != ios_major:
            issues.append(f"@capacitor/core@{core_ver} vs @capacitor/ios@{ios_ver}")

    if issues:
        return False, "; ".join(issues)
    return True, ""


# ── Validation engine ──────────────────────────────────────────────


def _validate_environment(
    root: Path,
    app_dir: Path | None,
    platform: str | None,
    *,
    check_deps: bool = True,
    check_build_tools: bool = True,
) -> list[dict]:
    """Run all validation checks and return results list.

    Each result: {"check": str, "status": "pass"|"fail"|"warn", "detail": str, "fix": str}
    """
    checks: list[dict] = []

    # 1. Node.js
    try:
        result = run(["node", "--version"], cwd=root, capture=True, timeout=5)
        checks.append({"check": "node", "status": "pass", "detail": result.stdout.strip(), "fix": ""})
    except Exception:
        checks.append(
            {
                "check": "node",
                "status": "fail",
                "detail": "not found",
                "fix": "Install Node.js 20+",
            }
        )

    # 2. pnpm
    try:
        result = run(["pnpm", "--version"], cwd=root, capture=True, timeout=5)
        checks.append({"check": "pnpm", "status": "pass", "detail": f"v{result.stdout.strip()}", "fix": ""})
    except Exception:
        checks.append(
            {
                "check": "pnpm",
                "status": "fail",
                "detail": "not found",
                "fix": "Install pnpm: npm i -g pnpm",
            }
        )

    # 3. Java (≥21 for Capacitor Android 8.x)
    if not platform or platform == "android":
        java_major = _get_java_major_version()
        if java_major is None:
            checks.append(
                {
                    "check": "java",
                    "status": "fail",
                    "detail": "not found",
                    "fix": "Install Java 21+: sdk install java 21.0.6-tem (via SDKMAN)",
                }
            )
        elif java_major < _MIN_JAVA_MAJOR:
            checks.append(
                {
                    "check": "java",
                    "status": "fail",
                    "detail": f"Java {java_major} (need ≥{_MIN_JAVA_MAJOR})",
                    "fix": f"Upgrade to Java {_MIN_JAVA_MAJOR}+: sdk install java 21.0.6-tem",
                }
            )
        else:
            checks.append({"check": "java", "status": "pass", "detail": f"Java {java_major}", "fix": ""})

    # 4. ANDROID_HOME
    if not platform or platform == "android":
        android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT", "")
        if android_home and Path(android_home).is_dir():
            checks.append({"check": "ANDROID_HOME", "status": "pass", "detail": android_home, "fix": ""})

            # 4b. Check for platform-tools and build-tools
            if check_build_tools:
                pt = Path(android_home) / "platform-tools"
                bt = Path(android_home) / "build-tools"
                if not pt.is_dir():
                    checks.append(
                        {
                            "check": "platform-tools",
                            "status": "fail",
                            "detail": "not installed",
                            "fix": "sdkmanager 'platform-tools'",
                        }
                    )
                if bt.is_dir():
                    versions = sorted(bt.iterdir())
                    if versions:
                        checks.append(
                            {
                                "check": "build-tools",
                                "status": "pass",
                                "detail": versions[-1].name,
                                "fix": "",
                            }
                        )
                    else:
                        checks.append(
                            {
                                "check": "build-tools",
                                "status": "fail",
                                "detail": "no versions installed",
                                "fix": "sdkmanager 'build-tools;35.0.0'",
                            }
                        )
                else:
                    checks.append(
                        {
                            "check": "build-tools",
                            "status": "fail",
                            "detail": "not installed",
                            "fix": "sdkmanager 'build-tools;35.0.0'",
                        }
                    )
        else:
            checks.append(
                {
                    "check": "ANDROID_HOME",
                    "status": "fail",
                    "detail": "not set",
                    "fix": "export ANDROID_HOME=~/Android/Sdk (add to ~/.zshrc)",
                }
            )

    # 5. Xcode + CocoaPods (macOS only)
    import platform as plat

    if plat.system() == "Darwin" and (not platform or platform == "ios"):
        try:
            result = run(["xcodebuild", "-version"], cwd=root, capture=True, timeout=5)
            version = result.stdout.strip().splitlines()[0] if result.stdout else ""
            checks.append({"check": "xcode", "status": "pass", "detail": version, "fix": ""})
        except Exception:
            checks.append(
                {
                    "check": "xcode",
                    "status": "fail",
                    "detail": "not found",
                    "fix": "Install Xcode from App Store",
                }
            )

        try:
            result = run(["pod", "--version"], cwd=root, capture=True, timeout=5)
            checks.append({"check": "cocoapods", "status": "pass", "detail": result.stdout.strip(), "fix": ""})
        except Exception:
            checks.append(
                {
                    "check": "cocoapods",
                    "status": "fail",
                    "detail": "not found",
                    "fix": "sudo gem install cocoapods",
                }
            )

    # 6-10: App-specific checks
    if app_dir and check_deps:
        deps = _get_pkg_deps(app_dir)

        # 6. Capacitor config file
        if _has_capacitor(app_dir):
            checks.append({"check": "capacitor.config", "status": "pass", "detail": "found", "fix": ""})
        else:
            checks.append(
                {
                    "check": "capacitor.config",
                    "status": "fail",
                    "detail": "missing",
                    "fix": f"kctl-react cap init {app_dir.name}",
                }
            )

        # 7. Required Capacitor packages
        for pkg in _REQUIRED_CAP_PACKAGES:
            if pkg in deps:
                checks.append({"check": pkg, "status": "pass", "detail": deps[pkg], "fix": ""})
            else:
                checks.append(
                    {
                        "check": pkg,
                        "status": "fail",
                        "detail": "not installed",
                        "fix": f"pnpm add {pkg} --filter=@kodemeio/{app_dir.name}",
                    }
                )

        # 8. Platform-specific package
        if platform == "android":
            if _ANDROID_CAP_PACKAGE in deps:
                checks.append(
                    {
                        "check": _ANDROID_CAP_PACKAGE,
                        "status": "pass",
                        "detail": deps[_ANDROID_CAP_PACKAGE],
                        "fix": "",
                    }
                )
            else:
                checks.append(
                    {
                        "check": _ANDROID_CAP_PACKAGE,
                        "status": "fail",
                        "detail": "not installed",
                        "fix": f"pnpm add {_ANDROID_CAP_PACKAGE} --filter=@kodemeio/{app_dir.name}",
                    }
                )
        elif platform == "ios":
            if _IOS_CAP_PACKAGE in deps:
                checks.append(
                    {
                        "check": _IOS_CAP_PACKAGE,
                        "status": "pass",
                        "detail": deps[_IOS_CAP_PACKAGE],
                        "fix": "",
                    }
                )
            else:
                checks.append(
                    {
                        "check": _IOS_CAP_PACKAGE,
                        "status": "fail",
                        "detail": "not installed",
                        "fix": f"pnpm add {_IOS_CAP_PACKAGE} --filter=@kodemeio/{app_dir.name}",
                    }
                )

        # 9. Version mismatch
        match_ok, mismatch_detail = _check_cap_version_match(deps)
        if not match_ok:
            checks.append(
                {
                    "check": "cap-version-match",
                    "status": "fail",
                    "detail": mismatch_detail,
                    "fix": "Align all @capacitor/* packages to the same major version",
                }
            )
        elif any(p in deps for p in (_ANDROID_CAP_PACKAGE, _IOS_CAP_PACKAGE)):
            checks.append({"check": "cap-version-match", "status": "pass", "detail": "versions aligned", "fix": ""})

        # 10. workbox-window (required for vite-plugin-pwa build)
        if "vite-plugin-pwa" in deps and "workbox-window" not in deps:
            checks.append(
                {
                    "check": "workbox-window",
                    "status": "fail",
                    "detail": "missing (required by vite-plugin-pwa)",
                    "fix": f"pnpm add -D workbox-window --filter=@kodemeio/{app_dir.name}",
                }
            )

        # 11. dist/ exists (needed for cap sync/add)
        dist = app_dir / "dist"
        if dist.is_dir() and (dist / "index.html").exists():
            checks.append({"check": "dist/", "status": "pass", "detail": "built", "fix": ""})
        else:
            checks.append(
                {
                    "check": "dist/",
                    "status": "warn",
                    "detail": "not built (will build automatically)",
                    "fix": f"pnpm turbo run build --filter=@kodemeio/{app_dir.name}",
                }
            )

    # 12-14: Android project checks (if android/ exists)
    if app_dir and platform == "android" and _has_platform(app_dir, "android"):
        android_dir = app_dir / "android"

        # 12. Gradle version
        gradle_ver = _get_gradle_version(android_dir)
        if gradle_ver:
            # Compare semver-ish
            gradle_parts = [int(x) for x in gradle_ver.split(".")[:2]]
            min_parts = [int(x) for x in _MIN_GRADLE_VERSION.split(".")[:2]]
            if gradle_parts >= min_parts:
                checks.append({"check": "gradle", "status": "pass", "detail": gradle_ver, "fix": ""})
            else:
                checks.append(
                    {
                        "check": "gradle",
                        "status": "fail",
                        "detail": f"{gradle_ver} (need ≥{_MIN_GRADLE_VERSION})",
                        "fix": (
                            "Update distributionUrl in android/gradle/wrapper/"
                            "gradle-wrapper.properties to gradle-8.11.1-all.zip"
                        ),
                    }
                )
        else:
            checks.append(
                {
                    "check": "gradle",
                    "status": "warn",
                    "detail": "cannot read version",
                    "fix": "",
                }
            )

        # 13. minSdkVersion
        min_sdk = _get_android_min_sdk(android_dir)
        if min_sdk is not None:
            if min_sdk >= _MIN_ANDROID_SDK:
                checks.append({"check": "minSdkVersion", "status": "pass", "detail": str(min_sdk), "fix": ""})
            else:
                checks.append(
                    {
                        "check": "minSdkVersion",
                        "status": "fail",
                        "detail": f"{min_sdk} (need ≥{_MIN_ANDROID_SDK})",
                        "fix": f"Set minSdkVersion = {_MIN_ANDROID_SDK} in android/variables.gradle",
                    }
                )

        # 14. gradlew executable
        gradlew = android_dir / "gradlew"
        if gradlew.exists():
            if os.access(gradlew, os.X_OK):
                checks.append({"check": "gradlew", "status": "pass", "detail": "executable", "fix": ""})
            else:
                checks.append(
                    {
                        "check": "gradlew",
                        "status": "fail",
                        "detail": "not executable",
                        "fix": "chmod +x apps/<app>/android/gradlew",
                    }
                )

    return checks


def _show_checks(out: object, title: str, checks: list[dict]) -> int:
    """Display validation checks and return failure count."""
    rows: list[list[str]] = []
    for c in checks:
        status_map = {
            "pass": "[green]PASS[/green]",
            "fail": "[red]FAIL[/red]",
            "warn": "[yellow]WARN[/yellow]",
        }
        fix_text = c["fix"] if c["fix"] else ""
        rows.append([c["check"], status_map.get(c["status"], c["status"]), c["detail"], fix_text])

    out.table(
        title,
        [("Check", "cyan"), ("Status", ""), ("Detail", "dim"), ("Fix", "")],
        rows,
        data_for_json=checks,
    )

    failures = sum(1 for c in checks if c["status"] == "fail")
    warnings = sum(1 for c in checks if c["status"] == "warn")
    passed = sum(1 for c in checks if c["status"] == "pass")

    if failures:
        out.error(f"{passed} passed, {failures} failed, {warnings} warnings — fix FAIL items before building")
    elif warnings:
        out.warn(f"{passed} passed, {warnings} warnings — ready to build (warnings are non-blocking)")
    else:
        out.success(f"All {passed} checks passed — ready to build")

    return failures


def _preflight(
    out: object,
    root: Path,
    app_dir: Path,
    platform: str,
) -> None:
    """Run preflight validation and abort on failures."""
    checks = _validate_environment(root, app_dir, platform)
    failures = _show_checks(out, f"Preflight — {app_dir.name} ({platform})", checks)
    if failures:
        raise typer.Exit(1) from None


# ── Commands ───────────────────────────────────────────────────────


@app.command()
def status(ctx: typer.Context) -> None:
    """Show Capacitor status for all apps."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    rows: list[list[str]] = []
    json_data: list[dict] = []

    for name in actx.app_names:
        app_dir = root / "apps" / name
        has_cap = _has_capacitor(app_dir)
        has_android = _has_platform(app_dir, "android")
        has_ios = _has_platform(app_dir, "ios")

        cap_status = "[green]yes[/green]" if has_cap else "[dim]no[/dim]"
        android_status = "[green]yes[/green]" if has_android else "[dim]no[/dim]"
        ios_status = "[green]yes[/green]" if has_ios else "[dim]no[/dim]"

        rows.append([name, cap_status, android_status, ios_status])
        json_data.append(
            {
                "app": name,
                "capacitor": has_cap,
                "android": has_android,
                "ios": has_ios,
            }
        )

    out.table(
        "Capacitor Status",
        [("App", "cyan"), ("Capacitor", ""), ("Android", ""), ("iOS", "")],
        rows,
        data_for_json=json_data,
    )

    cap_count = sum(1 for d in json_data if d["capacitor"])
    out.info(f"{cap_count}/{len(json_data)} app(s) have Capacitor configured")


@app.command()
def doctor(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name (omit for general check)")] = None,
    platform: Annotated[str | None, typer.Option("--platform", "-p", help="Platform to check")] = None,
) -> None:
    """Comprehensive Capacitor build environment validation.

    Checks: Node, pnpm, Java ≥21, ANDROID_HOME, build-tools, platform-tools,
    Capacitor deps, version alignment, Gradle version, minSdkVersion, workbox-window,
    dist/ output, gradlew permissions. On macOS also checks Xcode and CocoaPods.
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    app_dir = None
    if app_name:
        actx.validate_app(app_name)
        app_dir = root / "apps" / app_name

    checks = _validate_environment(root, app_dir, platform)
    _show_checks(out, "Capacitor Doctor" + (f" — {app_name}" if app_name else ""), checks)


@app.command()
def init(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    app_id: Annotated[str | None, typer.Option("--app-id", help="Bundle ID (default: io.kodeme.<app>)")] = None,
) -> None:
    """Initialize Capacitor for an app (creates capacitor.config.ts)."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    if _has_capacitor(app_dir):
        out.warn(f"{app_name}: Capacitor already configured")
        return

    bundle_id = app_id or f"{_DEFAULT_APP_ID_PREFIX}.{app_name}"
    app_info = actx.apps[app_name]
    display_name = app_info.get("name", app_name)
    theme_color = "#14b8a6"

    config_content = f'''import type {{ CapacitorConfig }} from "@capacitor/cli";

const config: CapacitorConfig = {{
  appId: "{bundle_id}",
  appName: "{display_name}",
  webDir: "dist",
  server: {{
    androidScheme: "https",
  }},
  plugins: {{
    SplashScreen: {{
      launchAutoHide: true,
      showSpinner: false,
      backgroundColor: "{theme_color}",
    }},
    Keyboard: {{
      resize: "body",
      resizeOnFullScreen: true,
    }},
  }},
  android: {{
    allowMixedContent: false,
  }},
  ios: {{
    contentInset: "automatic",
  }},
}};

export default config;
'''

    (app_dir / "capacitor.config.ts").write_text(config_content)
    out.success(f"Created capacitor.config.ts for {app_name} (appId: {bundle_id})")

    # Check required deps
    deps = _get_pkg_deps(app_dir)
    missing = [pkg for pkg in _REQUIRED_CAP_PACKAGES if pkg not in deps]
    if missing:
        out.info("Install required packages:")
        out.info(f"  pnpm add {' '.join(missing)} --filter=@kodemeio/{app_name}")


@app.command()
def add(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    platform: Annotated[str, typer.Argument(help="Platform: android or ios")],
) -> None:
    """Add a native platform (android/ios) to an app. Validates everything first."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    if platform not in ("android", "ios"):
        out.error("Platform must be 'android' or 'ios'")
        raise typer.Exit(1)

    if not _has_capacitor(app_dir):
        out.error(f"{app_name}: No capacitor.config.ts — run `kctl-react cap init {app_name}` first")
        raise typer.Exit(1)

    if _has_platform(app_dir, platform):
        out.warn(f"{app_name}: {platform}/ already exists")
        return

    # Pre-validate
    out.info(f"Validating environment for {platform}...")
    checks = _validate_environment(root, app_dir, platform, check_build_tools=False)
    failures = sum(1 for c in checks if c["status"] == "fail")
    if failures:
        _show_checks(out, f"Pre-add validation — {app_name}", checks)
        raise typer.Exit(1)

    # Ensure platform package is installed
    pkg_name = _ANDROID_CAP_PACKAGE if platform == "android" else _IOS_CAP_PACKAGE
    deps = _get_pkg_deps(app_dir)
    if pkg_name not in deps:
        out.info(f"Installing {pkg_name}...")
        try:
            run_pnpm(["add", pkg_name, f"--filter=@kodemeio/{app_name}"], cwd=root, capture=False, timeout=60)
        except CommandError as e:
            out.error(f"Failed to install {pkg_name}: {e}")
            raise typer.Exit(1) from None

    # Ensure build exists
    dist = app_dir / "dist"
    if not dist.is_dir():
        out.info("Building app first (cap add requires dist/)...")
        run_turbo("build", root, filter_app=app_name, capture=False, timeout=300)

    out.info(f"Adding {platform} platform to {app_name}...")
    try:
        _run_cap(["add", platform], app_dir, timeout=120)
    except CommandError as e:
        out.error(f"Failed to add {platform}: {e}")
        raise typer.Exit(1) from None

    # Post-add fixes for Android
    if platform == "android":
        _fix_android_project(out, app_dir / "android")

    out.success(f"Added {platform} to {app_name}")


def _fix_android_project(out: object, android_dir: Path) -> None:
    """Apply required fixes to a freshly-scaffolded Android project."""
    # Fix 1: Upgrade Gradle wrapper to 8.11.1
    props = android_dir / "gradle" / "wrapper" / "gradle-wrapper.properties"
    if props.exists():
        text = props.read_text()
        old_ver = re.search(r"gradle-(\d+\.\d+(?:\.\d+)?)", text)
        if old_ver:
            old = old_ver.group(1)
            old_parts = [int(x) for x in old.split(".")[:2]]
            min_parts = [int(x) for x in _MIN_GRADLE_VERSION.split(".")[:2]]
            if old_parts < min_parts:
                new_text = re.sub(r"gradle-[\d.]+-(all|bin)", "gradle-8.11.1-all", text)
                props.write_text(new_text)
                out.info(f"  Upgraded Gradle: {old} → 8.11.1")

    # Fix 2: Bump minSdkVersion and compileSdkVersion
    variables = android_dir / "variables.gradle"
    if variables.exists():
        text = variables.read_text()
        changed = False

        min_sdk = _get_android_min_sdk(android_dir)
        if min_sdk is not None and min_sdk < _MIN_ANDROID_SDK:
            text = re.sub(r"minSdkVersion\s*=\s*\d+", f"minSdkVersion = {_MIN_ANDROID_SDK}", text)
            changed = True
            out.info(f"  Bumped minSdkVersion: {min_sdk} → {_MIN_ANDROID_SDK}")

        compile_match = re.search(r"compileSdkVersion\s*=\s*(\d+)", text)
        if compile_match and int(compile_match.group(1)) < _COMPILE_SDK:
            text = re.sub(r"compileSdkVersion\s*=\s*\d+", f"compileSdkVersion = {_COMPILE_SDK}", text)
            text = re.sub(r"targetSdkVersion\s*=\s*\d+", f"targetSdkVersion = {_COMPILE_SDK}", text)
            changed = True
            out.info(f"  Bumped compileSdkVersion/targetSdkVersion → {_COMPILE_SDK}")

        if changed:
            variables.write_text(text)

    # Fix 3: Make gradlew executable
    gradlew = android_dir / "gradlew"
    if gradlew.exists() and not os.access(gradlew, os.X_OK):
        gradlew.chmod(0o755)
        out.info("  Made gradlew executable")


@app.command()
def sync(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    platform: Annotated[str | None, typer.Argument(help="Platform (omit for all)")] = None,
    skip_build: Annotated[bool, typer.Option("--skip-build", help="Skip Vite build, only sync")] = False,
) -> None:
    """Build web assets and sync to native platforms."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    if not _has_capacitor(app_dir):
        out.error(f"{app_name}: No Capacitor config — run `kctl-react cap init {app_name}` first")
        raise typer.Exit(1)

    if not skip_build:
        out.info(f"Building {app_name}...")
        try:
            run_turbo("build", root, filter_app=app_name, capture=False, timeout=300)
        except CommandError as e:
            out.error(f"Build failed: {e}")
            raise typer.Exit(1) from None

    sync_args = ["sync"]
    if platform:
        sync_args.append(platform)

    out.info("Syncing web assets to native platform(s)...")
    try:
        _run_cap(sync_args, app_dir, timeout=120)
        out.success(f"Synced {app_name}" + (f" ({platform})" if platform else ""))
    except CommandError as e:
        out.error(f"Sync failed: {e}")
        raise typer.Exit(1) from None


@app.command("run")
def run_native(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    platform: Annotated[str, typer.Argument(help="Platform: android or ios")],
    target: Annotated[str | None, typer.Option("--target", "-t", help="Device/emulator target ID")] = None,
) -> None:
    """Build, sync, and deploy to a device or emulator."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    if platform not in ("android", "ios"):
        out.error("Platform must be 'android' or 'ios'")
        raise typer.Exit(1)

    if not _has_platform(app_dir, platform):
        out.error(f"{app_name}: No {platform}/ directory — run `kctl-react cap add {app_name} {platform}` first")
        raise typer.Exit(1)

    _preflight(out, root, app_dir, platform)

    out.info(f"Building and syncing {app_name}...")
    run_turbo("build", root, filter_app=app_name, capture=False, timeout=300)

    run_args = ["run", platform]
    if target:
        run_args.extend(["--target", target])

    out.info(f"Deploying {app_name} to {platform}...")
    try:
        _run_cap(run_args, app_dir, timeout=300)
        out.success(f"Deployed {app_name} to {platform}")
    except CommandError as e:
        out.error(f"Run failed: {e}")
        raise typer.Exit(1) from None


@app.command("open")
def open_ide(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    platform: Annotated[str, typer.Argument(help="Platform: android or ios")],
) -> None:
    """Open native project in Android Studio or Xcode."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    if platform not in ("android", "ios"):
        out.error("Platform must be 'android' or 'ios'")
        raise typer.Exit(1)

    if not _has_platform(app_dir, platform):
        out.error(f"{app_name}: No {platform}/ directory — run `kctl-react cap add {app_name} {platform}` first")
        raise typer.Exit(1)

    ide = "Android Studio" if platform == "android" else "Xcode"
    out.info(f"Opening {app_name} in {ide}...")
    try:
        _run_cap(["open", platform], app_dir, timeout=30)
    except CommandError as e:
        out.error(f"Failed to open {ide}: {e}")
        raise typer.Exit(1) from None


@app.command()
def build(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    platform: Annotated[str, typer.Argument(help="Platform: android or ios")],
    release: Annotated[bool, typer.Option("--release", help="Build a release (signed) artifact")] = False,
) -> None:
    """Build native artifact (APK/AAB for Android, IPA for iOS). Validates everything first."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    if platform not in ("android", "ios"):
        out.error("Platform must be 'android' or 'ios'")
        raise typer.Exit(1)

    if not _has_platform(app_dir, platform):
        out.error(f"{app_name}: No {platform}/ directory")
        raise typer.Exit(1)

    # Full preflight validation
    _preflight(out, root, app_dir, platform)

    # Build web + sync
    out.info(f"Building web assets for {app_name}...")
    run_turbo("build", root, filter_app=app_name, capture=False, timeout=300)

    out.info("Syncing to native project...")
    _run_cap(["sync", platform], app_dir, timeout=120)

    build_type = "release" if release else "debug"
    out.info(f"Building {build_type} {platform} artifact...")

    if platform == "android":
        gradle_task = "assembleRelease" if release else "assembleDebug"
        gradle_dir = app_dir / "android"
        try:
            run(
                ["./gradlew", gradle_task],
                cwd=gradle_dir,
                capture=False,
                timeout=600,
            )
            apk_dir = gradle_dir / "app" / "build" / "outputs" / "apk" / build_type
            apks = list(apk_dir.glob("*.apk")) if apk_dir.is_dir() else []
            if apks:
                from kctl_react.commands.build import _format_size

                size = apks[0].stat().st_size
                out.success(f"APK: {apks[0].name} ({_format_size(size)})")
            else:
                out.success("Android build complete")
        except CommandError as e:
            out.error(f"Gradle build failed: {e}")
            raise typer.Exit(1) from None

    elif platform == "ios":
        out.info("Use Xcode to build iOS (or run `xcodebuild` manually)")
        out.info(f"  kctl-react cap open {app_name} ios")


@app.command()
def dev(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    platform: Annotated[str, typer.Argument(help="Platform: android or ios")],
) -> None:
    """Start Vite dev server with live-reload on a native device."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name
    app_info = actx.apps[app_name]
    port = app_info["port"]

    if not _has_platform(app_dir, platform):
        out.error(f"{app_name}: No {platform}/ directory — run `kctl-react cap add {app_name} {platform}` first")
        raise typer.Exit(1)

    import socket

    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        local_ip = "localhost"

    out.info(f"Starting live-reload dev for {app_name} on {platform}")
    out.info(f"  Dev server: http://{local_ip}:{port}")
    out.info("  The native app will connect to the Vite dev server for hot-reload.")
    out.info("  Make sure your device is on the same network.")

    try:
        run(
            ["npx", "cap", "run", platform, "--livereload", f"--host={local_ip}", f"--port={port}"],
            cwd=app_dir,
            capture=False,
            timeout=0,
        )
    except CommandError:
        pass
    except KeyboardInterrupt:
        out.info("Stopped")


# ── ADB device management ─────────────────────────────────────────


def _get_adb_path() -> str:
    """Get adb binary path from ANDROID_HOME or PATH."""
    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT", "")
    if android_home:
        adb = Path(android_home) / "platform-tools" / "adb"
        if adb.exists():
            return str(adb)
    return "adb"


def _list_devices(root: Path) -> list[dict]:
    """List connected ADB devices."""
    adb = _get_adb_path()
    try:
        result = run([adb, "devices", "-l"], cwd=root, capture=True, timeout=10)
    except Exception:
        return []

    devices: list[dict] = []
    for line in result.stdout.strip().splitlines()[1:]:
        if not line.strip() or "offline" in line:
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        serial = parts[0]
        state = parts[1]

        # Extract model and product from key:value pairs
        info: dict[str, str] = {}
        for part in parts[2:]:
            if ":" in part:
                k, v = part.split(":", 1)
                info[k] = v

        devices.append(
            {
                "serial": serial,
                "state": state,
                "model": info.get("model", ""),
                "product": info.get("product", ""),
                "transport_id": info.get("transport_id", ""),
            }
        )
    return devices


def _get_app_id(app_dir: Path) -> str:
    """Read appId from capacitor.config.ts or .json."""
    for config_name in ("capacitor.config.ts", "capacitor.config.json"):
        config_file = app_dir / config_name
        if not config_file.exists():
            continue
        try:
            text = config_file.read_text()
            match = re.search(r'appId["\s:]+["\']([^"\']+)["\']', text)
            if match:
                return match.group(1)
        except Exception:
            pass
    return ""


def _find_apk(app_dir: Path, build_type: str = "debug") -> Path | None:
    """Find the APK file for a given build type."""
    apk_dir = app_dir / "android" / "app" / "build" / "outputs" / "apk" / build_type
    if not apk_dir.is_dir():
        return None
    apks = sorted(apk_dir.glob("*.apk"), key=lambda f: f.stat().st_mtime, reverse=True)
    return apks[0] if apks else None


@app.command()
def devices(ctx: typer.Context) -> None:
    """List connected Android devices and emulators via ADB."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    devs = _list_devices(root)

    if not devs:
        out.warn("No devices connected")
        out.info("  Connect a phone via USB (enable USB Debugging)")
        out.info("  Or start an emulator: kctl-react cap emulator --start")
        return

    rows: list[list[str]] = []
    for d in devs:
        model = d["model"] or d["product"] or "unknown"
        is_emulator = d["serial"].startswith("emulator-")
        dtype = "emulator" if is_emulator else "device"
        rows.append([d["serial"], model, d["state"], dtype])

    out.table(
        "Connected Devices",
        [("Serial", "cyan"), ("Model", ""), ("State", "green"), ("Type", "dim")],
        rows,
        data_for_json=devs,
    )


@app.command()
def install(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    device: Annotated[str | None, typer.Option("--device", "-d", help="Device serial (omit for first)")] = None,
    build_type: Annotated[str, typer.Option("--type", help="Build type: debug or release")] = "debug",
) -> None:
    """Install APK on a connected device or emulator."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    # Find APK
    apk = _find_apk(app_dir, build_type)
    if not apk:
        out.error(f"No {build_type} APK found — run `kctl-react cap build {app_name} android` first")
        raise typer.Exit(1) from None

    # Check device
    devs = _list_devices(root)
    if not devs:
        out.error("No devices connected — connect a phone or start an emulator")
        raise typer.Exit(1)

    target = device or devs[0]["serial"]
    target_model = next((d["model"] or d["serial"] for d in devs if d["serial"] == target), target)

    from kctl_react.commands.build import _format_size

    out.info(f"Installing {apk.name} ({_format_size(apk.stat().st_size)}) on {target_model}...")

    adb = _get_adb_path()
    try:
        run([adb, "-s", target, "install", "-r", str(apk)], cwd=root, capture=False, timeout=120)
        out.success(f"Installed on {target_model}")
    except CommandError as e:
        out.error(f"Install failed: {e}")
        raise typer.Exit(1) from None


@app.command()
def launch(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    device: Annotated[str | None, typer.Option("--device", "-d", help="Device serial")] = None,
) -> None:
    """Launch the app on a connected device or emulator."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    app_id = _get_app_id(app_dir)
    if not app_id:
        out.error("Cannot read appId from capacitor config")
        raise typer.Exit(1)

    devs = _list_devices(root)
    if not devs:
        out.error("No devices connected")
        raise typer.Exit(1)

    target = device or devs[0]["serial"]

    adb = _get_adb_path()
    activity = f"{app_id}/.MainActivity"

    out.info(f"Launching {app_id} on {target}...")
    try:
        run(
            [adb, "-s", target, "shell", "am", "start", "-n", activity],
            cwd=root,
            capture=True,
            timeout=10,
        )
        out.success(f"Launched {app_name}")
    except CommandError as e:
        # Try with generic activity launcher
        try:
            run(
                [adb, "-s", target, "shell", "monkey", "-p", app_id, "-c", "android.intent.category.LAUNCHER", "1"],
                cwd=root,
                capture=True,
                timeout=10,
            )
            out.success(f"Launched {app_name}")
        except CommandError:
            out.error(f"Launch failed: {e}")
            raise typer.Exit(1) from None


@app.command()
def logs(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    device: Annotated[str | None, typer.Option("--device", "-d", help="Device serial")] = None,
    clear: Annotated[bool, typer.Option("--clear", "-c", help="Clear logcat before tailing")] = False,
) -> None:
    """Show live logcat output filtered to the app (Ctrl+C to stop)."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)
    app_dir = root / "apps" / app_name

    app_id = _get_app_id(app_dir)
    if not app_id:
        out.error("Cannot read appId from capacitor config")
        raise typer.Exit(1)

    devs = _list_devices(root)
    if not devs:
        out.error("No devices connected")
        raise typer.Exit(1)

    target = device or devs[0]["serial"]
    adb = _get_adb_path()

    if clear:
        with contextlib.suppress(Exception):
            run([adb, "-s", target, "logcat", "-c"], cwd=root, capture=True, timeout=5)

    out.info(f"Tailing logcat for {app_id} on {target} (Ctrl+C to stop)...")

    # Get PID of the app for filtering
    try:
        pid_result = run(
            [adb, "-s", target, "shell", "pidof", app_id],
            cwd=root,
            capture=True,
            timeout=5,
        )
        pid = pid_result.stdout.strip()
        if pid:
            cmd = [adb, "-s", target, "logcat", f"--pid={pid}"]
        else:
            # App not running — filter by Capacitor/Chromium tags
            cmd = [adb, "-s", target, "logcat", "-s", "Capacitor:V", "Capacitor/Console:V", "chromium:V"]
    except Exception:
        cmd = [adb, "-s", target, "logcat", "-s", "Capacitor:V", "chromium:V"]

    try:
        run(cmd, cwd=root, capture=False, timeout=0)
    except (CommandError, KeyboardInterrupt):
        out.info("Stopped")


# ── Release signing ────────────────────────────────────────────────


_KEYSTORE_DIR = ".kctl-react"


def _keystore_path(root: Path, app_name: str) -> Path:
    return root / _KEYSTORE_DIR / f"{app_name}.keystore"


@app.command()
def keystore(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    alias: Annotated[str, typer.Option("--alias", help="Key alias")] = "release",
    validity: Annotated[int, typer.Option("--validity", help="Validity in days")] = 10000,
) -> None:
    """Generate a signing keystore for release builds.

    Stores in .kctl-react/<app>.keystore (gitignored). Keep this file safe!
    """
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    actx.validate_app(app_name)

    ks_path = _keystore_path(root, app_name)
    if ks_path.exists():
        out.warn(f"Keystore already exists: {ks_path}")
        out.info("Delete it first if you want to regenerate")
        return

    actx.apps[app_name]

    out.info(f"Generating signing keystore for {app_name}...")
    out.info("  You will be prompted for a keystore password and key details.")

    ks_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        run(
            [
                "keytool",
                "-genkeypair",
                "-v",
                "-keystore",
                str(ks_path),
                "-alias",
                alias,
                "-keyalg",
                "RSA",
                "-keysize",
                "2048",
                "-validity",
                str(validity),
                "-dname",
                f"CN=Kodemeio {app_name.upper()}, OU=Mobile, O=Kodemeio, L=Jakarta, ST=DKI, C=ID",
                "-storepass",
                "kodemeio",
                "-keypass",
                "kodemeio",
            ],
            cwd=root,
            capture=True,
            timeout=30,
        )
        out.success(f"Keystore created: {ks_path}")
        out.warn("Default password is 'kodemeio' — change it for production!")
        out.info("This file is gitignored. Back it up securely (e.g. 1Password).")
    except CommandError as e:
        out.error(f"keytool failed: {e}")
        raise typer.Exit(1) from None

    # Write signing config snippet
    _write_signing_config(out, root, app_name, ks_path, alias)


def _write_signing_config(out: object, root: Path, app_name: str, ks_path: Path, alias: str) -> None:
    """Write or update signing config in android/app/build.gradle."""
    app_dir = root / "apps" / app_name
    gradle_file = app_dir / "android" / "app" / "build.gradle"
    if not gradle_file.exists():
        out.info("  android/app/build.gradle not found — signing config will be applied when platform is added")
        return

    text = gradle_file.read_text()
    if "signingConfigs" in text:
        out.info("  Signing config already exists in build.gradle")
        return

    # Insert signing config before the first buildTypes block
    signing_block = f"""
    signingConfigs {{
        release {{
            storeFile file('{ks_path}')
            storePassword 'kodemeio'
            keyAlias '{alias}'
            keyPassword 'kodemeio'
        }}
    }}
"""
    # Add signingConfig to release buildType
    text = text.replace(
        "buildTypes {",
        signing_block + "\n    buildTypes {",
    )
    text = text.replace(
        "release {",
        "release {\n            signingConfig signingConfigs.release",
        1,
    )
    gradle_file.write_text(text)
    out.success("  Added signing config to android/app/build.gradle")


@app.command()
def emulator(
    ctx: typer.Context,
    start: Annotated[bool, typer.Option("--start", help="Start the first available AVD")] = False,
    create: Annotated[str | None, typer.Option("--create", help="Create a new AVD with this name")] = None,
) -> None:
    """List, create, or start Android emulators."""
    actx: AppContext = ctx.obj
    out = actx.output
    root = actx.project_root

    android_home = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT", "")
    if not android_home:
        out.error("ANDROID_HOME not set")
        raise typer.Exit(1)

    emulator_bin = Path(android_home) / "emulator" / "emulator"
    avdmanager = Path(android_home) / "cmdline-tools" / "latest" / "bin" / "avdmanager"

    # Create new AVD
    if create:
        out.info(f"Creating AVD: {create}...")
        sdkmanager = Path(android_home) / "cmdline-tools" / "latest" / "bin" / "sdkmanager"

        # Install system image if needed
        out.info("  Ensuring system image is installed...")
        try:
            run(
                [str(sdkmanager), "system-images;android-35;google_apis;x86_64"],
                cwd=root,
                capture=False,
                timeout=300,
            )
        except Exception:
            out.warn("  Could not install system image — it may already exist")

        try:
            run(
                [
                    str(avdmanager),
                    "create",
                    "avd",
                    "-n",
                    create,
                    "-k",
                    "system-images;android-35;google_apis;x86_64",
                    "-d",
                    "pixel_6",
                    "--force",
                ],
                cwd=root,
                capture=False,
                timeout=30,
            )
            out.success(f"Created AVD: {create}")
        except CommandError as e:
            out.error(f"Failed to create AVD: {e}")
            raise typer.Exit(1) from None
        return

    # List AVDs
    avds: list[str] = []
    try:
        result = run([str(avdmanager), "list", "avd", "-c"], cwd=root, capture=True, timeout=10)
        avds = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
    except Exception:
        # Try emulator -list-avds as fallback
        if emulator_bin.exists():
            try:
                result = run([str(emulator_bin), "-list-avds"], cwd=root, capture=True, timeout=10)
                avds = [line.strip() for line in result.stdout.strip().splitlines() if line.strip()]
            except Exception:
                pass

    if not avds:
        out.warn("No AVDs found")
        out.info("  Create one: kctl-react cap emulator --create kodemeio-test")
        return

    if start:
        avd_name = avds[0]
        out.info(f"Starting emulator: {avd_name}...")
        if not emulator_bin.exists():
            out.error("emulator binary not found — install via: sdkmanager 'emulator'")
            raise typer.Exit(1) from None
        try:
            # Run in background — emulator is long-running
            import subprocess

            subprocess.Popen(
                [str(emulator_bin), "-avd", avd_name, "-no-snapshot-load"],
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            out.success(f"Emulator {avd_name} starting (takes ~30s)")
            out.info("  Once booted, run: kctl-react cap install sfa")
        except Exception as e:
            out.error(f"Failed to start emulator: {e}")
            raise typer.Exit(1) from None
        return

    # Just list
    rows = [[avd, "available"] for avd in avds]
    out.table(
        "Android Virtual Devices",
        [("AVD", "cyan"), ("Status", "green")],
        rows,
        data_for_json=[{"name": avd} for avd in avds],
    )
