"""Push and pull operations for syncing .env files with 1Password."""

import shutil
from collections import OrderedDict
from datetime import datetime
from pathlib import Path

from kctl_op.core.op_config import get_config
from kctl_op.core.diff import DiffResult, compute_diff
from kctl_op.core.discovery import EnvFile, discover_env_files
from kctl_op.core.op_client import (
    compute_hash,
    create_item,
    get_item,
    update_item,
)
from kctl_op.core.parser import parse_env_file, serialize_env_vars


def create_backup(env_file: EnvFile) -> Path | None:
    """Create a backup of a local .env file before overwriting."""
    config = get_config()

    if not config.backup_enabled:
        return None

    if not env_file.path.exists():
        return None

    backup_dir = config.backup_directory / env_file.project / env_file.environment
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{env_file.path.name}.{timestamp}.bak"

    shutil.copy2(env_file.path, backup_path)

    # Clean up old backups
    cleanup_old_backups(backup_dir, config.max_backups)

    return backup_path


def cleanup_old_backups(backup_dir: Path, max_backups: int) -> None:
    """Remove old backups exceeding the max count."""
    backups = sorted(backup_dir.glob("*.bak"), key=lambda p: p.stat().st_mtime, reverse=True)

    for old_backup in backups[max_backups:]:
        old_backup.unlink()


def get_sync_metadata(env_file: EnvFile, fields: OrderedDict[str, str]) -> dict[str, str]:
    """Generate metadata for a sync operation."""
    return {
        "source_path": str(env_file.path),
        "sync_time": datetime.now().isoformat(),
        "content_hash": compute_hash(fields),
        "field_count": str(len(fields)),
    }


def push_env_file(
    env_file: EnvFile,
    vault: str,
    dry_run: bool = False,
    force: bool = False,
) -> tuple[bool, str, DiffResult | None]:
    """Push a local .env file to 1Password.

    Returns:
        Tuple of (success, message, diff_result)
    """
    if not env_file.path.exists():
        return False, f"File not found: {env_file.path}", None

    # Parse local file
    local_fields = parse_env_file(env_file.path)

    if not local_fields:
        return False, f"No variables found in: {env_file.path}", None

    # Check if item exists in 1Password
    existing = get_item(env_file.item_title, vault)

    if existing:
        # Compute diff
        diff = compute_diff(local_fields, existing.fields)

        if not diff.has_changes:
            return True, "Already in sync, no changes needed", diff

        if dry_run:
            return True, "Would update (dry run)", diff

        if not force:
            # Return diff for user confirmation
            return True, "Changes detected, confirmation required", diff

        # Update existing item
        metadata = get_sync_metadata(env_file, local_fields)
        update_item(
            title=env_file.item_title,
            vault=vault,
            fields=local_fields,
            tags=env_file.tags,
            metadata=metadata,
        )
        return True, f"Updated {len(local_fields)} variables", diff

    else:
        # Create new item
        diff = compute_diff(local_fields, OrderedDict())

        if dry_run:
            return True, f"Would create with {len(local_fields)} variables (dry run)", diff

        metadata = get_sync_metadata(env_file, local_fields)
        create_item(
            title=env_file.item_title,
            vault=vault,
            fields=local_fields,
            tags=env_file.tags,
            metadata=metadata,
        )
        return True, f"Created with {len(local_fields)} variables", diff


def pull_env_file(
    env_file: EnvFile,
    vault: str,
    dry_run: bool = False,
    force: bool = False,
    backup: bool = True,
) -> tuple[bool, str, DiffResult | None]:
    """Pull from 1Password to a local .env file.

    Returns:
        Tuple of (success, message, diff_result)
    """
    # Get item from 1Password
    remote = get_item(env_file.item_title, vault)

    if not remote:
        return False, f"Not found in 1Password: {env_file.item_title}", None

    if not remote.fields:
        return False, f"No variables in 1Password item: {env_file.item_title}", None

    # Parse local file if it exists
    if env_file.path.exists():
        local_fields = parse_env_file(env_file.path)
        diff = compute_diff(remote.fields, local_fields)  # Note: reversed for pull

        if not diff.has_changes:
            return True, "Already in sync, no changes needed", diff

        if dry_run:
            return True, "Would update local file (dry run)", diff

        if not force:
            return True, "Changes detected, confirmation required", diff

        # Create backup before overwriting
        if backup:
            backup_path = create_backup(env_file)
            if backup_path:
                pass  # Backup created silently

    else:
        # File doesn't exist locally
        diff = compute_diff(remote.fields, OrderedDict())

        if dry_run:
            return True, f"Would create with {len(remote.fields)} variables (dry run)", diff

        # Ensure parent directory exists
        env_file.path.parent.mkdir(parents=True, exist_ok=True)

    # Write to local file
    content = serialize_env_vars(remote.fields)
    env_file.path.write_text(content)

    return True, f"Pulled {len(remote.fields)} variables", diff


def push_all(
    vault: str,
    dry_run: bool = False,
    force: bool = False,
) -> list[tuple[EnvFile, bool, str]]:
    """Push all discovered .env files to 1Password.

    Returns:
        List of (env_file, success, message) tuples.
    """
    env_files = discover_env_files()
    results: list[tuple[EnvFile, bool, str]] = []

    for env_file in env_files:
        success, message, _ = push_env_file(env_file, vault, dry_run, force)
        results.append((env_file, success, message))

    return results


def pull_all(
    vault: str,
    dry_run: bool = False,
    force: bool = False,
    backup: bool = True,
) -> list[tuple[EnvFile, bool, str]]:
    """Pull all .env files from 1Password.

    Only pulls items that have a matching local project/environment.

    Returns:
        List of (env_file, success, message) tuples.
    """
    env_files = discover_env_files()
    results: list[tuple[EnvFile, bool, str]] = []

    for env_file in env_files:
        success, message, _ = pull_env_file(env_file, vault, dry_run, force, backup)
        results.append((env_file, success, message))

    return results


def get_sync_status(env_file: EnvFile, vault: str) -> dict:
    """Get sync status for a single .env file."""
    local_exists = env_file.path.exists()
    remote = get_item(env_file.item_title, vault)

    status = {
        "project": env_file.project,
        "environment": env_file.environment,
        "local_exists": local_exists,
        "remote_exists": remote is not None,
        "in_sync": False,
        "local_vars": 0,
        "remote_vars": 0,
    }

    if local_exists:
        local_fields = parse_env_file(env_file.path)
        status["local_vars"] = len(local_fields)

        if remote:
            status["remote_vars"] = len(remote.fields)
            diff = compute_diff(local_fields, remote.fields)
            status["in_sync"] = not diff.has_changes
        else:
            status["in_sync"] = False
    elif remote:
        status["remote_vars"] = len(remote.fields)
        status["in_sync"] = False

    return status
