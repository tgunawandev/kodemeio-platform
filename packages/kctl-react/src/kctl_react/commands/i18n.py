"""Translation management for react-i18next apps."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kctl_react.core.analyzers import check_interpolation_vars
from kctl_react.core.callbacks import AppContext

app = typer.Typer(help="Translation management (react-i18next).")


def _find_i18n_dir(app_dir: Path) -> Path | None:
    """Find the i18n directory — src/i18n/ (react-i18next) or messages/ (next-intl)."""
    for candidate in (app_dir / "src" / "i18n", app_dir / "messages"):
        if candidate.is_dir() and any(candidate.glob("*.json")):
            return candidate
    return None


def _load_translations(app_dir: Path) -> dict[str, dict]:
    """Load translation JSON files from app's i18n directory."""
    i18n_dir = _find_i18n_dir(app_dir)
    if i18n_dir is None:
        return {}
    result = {}
    for f in i18n_dir.glob("*.json"):
        lang = f.stem
        try:
            result[lang] = json.loads(f.read_text())
        except json.JSONDecodeError:
            result[lang] = {}
    return result


def _flatten_keys(d: dict, prefix: str = "") -> set[str]:
    """Flatten nested dict into dot-separated key set."""
    keys = set()
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.update(_flatten_keys(v, full_key))
        else:
            keys.add(full_key)
    return keys


@app.command()
def coverage(
    ctx: typer.Context,
    app_name: Annotated[str | None, typer.Argument(help="App name")] = None,
    all_apps: Annotated[bool, typer.Option("--all", help="All apps")] = False,
) -> None:
    """Translation coverage — compare en.json vs id.json."""
    actx: AppContext = ctx.obj
    out = actx.output
    apps_to_check = list(actx.apps.keys()) if all_apps else ([app_name] if app_name else [])
    if not apps_to_check:
        out.error("Specify app name or --all")
        raise typer.Exit(1) from None
    rows, json_data = [], []
    for name in apps_to_check:
        actx.validate_app(name)
        translations = _load_translations(actx.get_app_dir(name))
        en_keys = _flatten_keys(translations.get("en", {}))
        id_keys = _flatten_keys(translations.get("id", {}))
        total = len(en_keys)
        translated = len(en_keys & id_keys)
        pct = (translated / total * 100) if total > 0 else 0
        missing = len(en_keys - id_keys)
        rows.append([name, str(total), str(translated), f"{pct:.0f}%", str(missing)])
        json_data.append(
            {
                "app": name,
                "total_keys": total,
                "translated": translated,
                "coverage_pct": round(pct, 1),
                "missing": missing,
            }
        )
    out.table(
        "i18n Coverage",
        [("App", "cyan"), ("Total", ""), ("Translated", "green"), ("Coverage", ""), ("Missing", "red")],
        rows,
        data_for_json=json_data,
    )


@app.command()
def missing(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """List keys in en.json but not in id.json."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    translations = _load_translations(actx.get_app_dir(app_name))
    en_keys = _flatten_keys(translations.get("en", {}))
    id_keys = _flatten_keys(translations.get("id", {}))
    missing_keys = sorted(en_keys - id_keys)
    if not missing_keys:
        out.success("All keys translated")
        return
    rows = [[k] for k in missing_keys]
    out.table(f"Missing Translations — {app_name}", [("Key", "yellow")], rows)


@app.command()
def unused(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Find translation keys not referenced in source code."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    app_dir = actx.get_app_dir(app_name)
    translations = _load_translations(app_dir)
    all_keys = _flatten_keys(translations.get("en", {}))
    # Grep source for t("key") or t('key') patterns
    import re

    used_keys: set[str] = set()
    src_dir = app_dir / "src"
    for f in src_dir.rglob("*.tsx"):
        content = f.read_text(errors="ignore")
        used_keys.update(re.findall(r't\(["\']([^"\']+)["\']\)', content))
    unused_keys = sorted(all_keys - used_keys)
    if not unused_keys:
        out.success("No unused keys found")
        return
    rows = [[k] for k in unused_keys[:50]]
    out.table(
        f"Unused Keys — {app_name} (showing {min(50, len(unused_keys))}/{len(unused_keys)})", [("Key", "dim")], rows
    )


@app.command()
def sort(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Sort translation JSON keys alphabetically."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    i18n_dir = _find_i18n_dir(actx.get_app_dir(app_name))
    if i18n_dir is None:
        out.error(f"No i18n directory found for {app_name}")
        raise typer.Exit(1) from None
    for f in i18n_dir.glob("*.json"):
        data = json.loads(f.read_text())
        sorted_data = json.dumps(dict(sorted(data.items())), indent=2, ensure_ascii=False) + "\n"
        f.write_text(sorted_data)
        out.success(f"Sorted {f.name}")


def _sync_stub_recursive(en: dict, id_: dict) -> int:
    """Recursively add missing keys from en to id with [ID] prefix."""
    added = 0
    for key, value in en.items():
        if key not in id_:
            if isinstance(value, dict):
                id_[key] = {}
                added += _sync_stub_recursive(value, id_[key])
            else:
                id_[key] = f"[ID] {value}"
                added += 1
        elif isinstance(value, dict) and isinstance(id_[key], dict):
            added += _sync_stub_recursive(value, id_[key])
    return added


@app.command()
def diff(
    ctx: typer.Context,
    app_name: Annotated[str, typer.Argument(help="App name")],
    base: Annotated[str, typer.Option("--base", help="Git ref to compare")] = "HEAD~1",
) -> None:
    """Show keys added/removed between git refs."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    from kctl_react.core.runner import run_quiet

    i18n_dir = _find_i18n_dir(actx.get_app_dir(app_name))
    if i18n_dir is None:
        out.info("No i18n directory found")
        return
    en_path = str((i18n_dir / "en.json").relative_to(actx.project_root))
    result = run_quiet(["git", "diff", base, "--", en_path], cwd=actx.project_root)
    if result.returncode != 0 or not result.stdout.strip():
        out.info("No translation changes")
        return
    out.text(result.stdout)


@app.command()
def validate(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Validate all translation JSON files for syntax and required keys."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    i18n_dir = _find_i18n_dir(actx.get_app_dir(app_name))

    if i18n_dir is None:
        out.error(f"No i18n directory found for {app_name} (checked src/i18n/ and messages/)")
        raise typer.Exit(1) from None

    issues: list[list[str]] = []
    json_data: list[dict] = []

    for f in sorted(i18n_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            if not isinstance(data, dict):
                issues.append([f.name, "root is not an object"])
                json_data.append({"file": f.name, "valid": False, "issue": "root is not an object"})
            else:
                json_data.append({"file": f.name, "valid": True, "issue": ""})
        except json.JSONDecodeError as exc:
            issues.append([f.name, str(exc)])
            json_data.append({"file": f.name, "valid": False, "issue": str(exc)})

    # Check required files
    for required in ("en.json", "id.json"):
        if not (i18n_dir / required).exists():
            issues.append([required, "file missing"])
            json_data.append({"file": required, "valid": False, "issue": "file missing"})

    if issues:
        out.table(
            f"i18n Validation Issues — {app_name}",
            [("File", "yellow"), ("Issue", "red")],
            issues,
            data_for_json=json_data,
        )
        raise typer.Exit(1) from None

    out.success(f"All translation files valid for {app_name}")


@app.command()
def interpolation(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Check {{var}} placeholder consistency between en.json and id.json."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    app_dir = actx.get_app_dir(app_name)

    translations = _load_translations(app_dir)
    en = translations.get("en", {})
    id_ = translations.get("id", {})

    mismatches = check_interpolation_vars(en, id_)

    if not mismatches:
        out.success(f"No interpolation mismatches in {app_name}")
        return

    rows = [
        [
            m["key"],
            ", ".join(sorted(m["en_vars"])) or "(none)",  # type: ignore[arg-type]
            ", ".join(sorted(m["id_vars"])) or "(none)",  # type: ignore[arg-type]
            ", ".join(sorted(m["missing_in_id"])) or "",  # type: ignore[arg-type]
        ]
        for m in mismatches
    ]
    json_data = [
        {
            "key": m["key"],
            "en_vars": sorted(m["en_vars"]),  # type: ignore[arg-type]
            "id_vars": sorted(m["id_vars"]),  # type: ignore[arg-type]
            "missing_in_id": sorted(m["missing_in_id"]),  # type: ignore[arg-type]
        }
        for m in mismatches
    ]
    out.table(
        f"Interpolation Mismatches — {app_name}",
        [("Key", "cyan"), ("EN vars", ""), ("ID vars", ""), ("Missing in ID", "red")],
        rows,
        data_for_json=json_data,
    )


@app.command(name="sync-stub")
def sync_stub(ctx: typer.Context, app_name: Annotated[str, typer.Argument(help="App name")]) -> None:
    """Generate stub entries in id.json for keys missing from en.json."""
    actx: AppContext = ctx.obj
    out = actx.output
    actx.validate_app(app_name)
    i18n_dir = _find_i18n_dir(actx.get_app_dir(app_name))
    if i18n_dir is None:
        out.error(f"No i18n directory found for {app_name}")
        raise typer.Exit(1) from None
    en_file = i18n_dir / "en.json"
    id_file = i18n_dir / "id.json"

    if not en_file.exists():
        out.error(f"en.json not found: {en_file}")
        raise typer.Exit(1) from None

    en = json.loads(en_file.read_text())
    id_ = json.loads(id_file.read_text()) if id_file.exists() else {}

    added = _sync_stub_recursive(en, id_)

    id_file.write_text(json.dumps(id_, indent=2, ensure_ascii=False) + "\n")

    if added == 0:
        out.success(f"No missing keys in {app_name} — id.json is complete")
    else:
        out.success(f"Added {added} stub entr{'y' if added == 1 else 'ies'} to id.json for {app_name}")
