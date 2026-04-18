"""Diff and conflict detection for .env files."""

from collections import OrderedDict
from dataclasses import dataclass
from enum import Enum


def normalize_value(value: str) -> str:
    """Normalize a value for comparison.

    Handles differences in escape sequences and whitespace that may occur
    when values are stored and retrieved from 1Password.
    """
    if not value:
        return ""

    # Normalize escape sequences
    normalized = value.replace("\\n", "\n").replace("\\t", "\t")
    normalized = normalized.replace("\\\\", "\\")

    # Normalize line endings
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # Strip trailing whitespace from each line
    lines = [line.rstrip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)

    return normalized


def values_equal(local: str, remote: str) -> bool:
    """Compare two values with normalization."""
    return normalize_value(local) == normalize_value(remote)


class ChangeType(Enum):
    """Type of change detected."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class FieldChange:
    """Represents a change to a single field."""

    key: str
    change_type: ChangeType
    local_value: str | None = None
    remote_value: str | None = None

    @property
    def is_changed(self) -> bool:
        return self.change_type != ChangeType.UNCHANGED


@dataclass
class DiffResult:
    """Result of comparing local and remote .env files."""

    local_fields: OrderedDict[str, str]
    remote_fields: OrderedDict[str, str]
    changes: list[FieldChange]

    @property
    def has_changes(self) -> bool:
        return any(c.is_changed for c in self.changes)

    @property
    def added(self) -> list[FieldChange]:
        return [c for c in self.changes if c.change_type == ChangeType.ADDED]

    @property
    def removed(self) -> list[FieldChange]:
        return [c for c in self.changes if c.change_type == ChangeType.REMOVED]

    @property
    def modified(self) -> list[FieldChange]:
        return [c for c in self.changes if c.change_type == ChangeType.MODIFIED]

    @property
    def unchanged(self) -> list[FieldChange]:
        return [c for c in self.changes if c.change_type == ChangeType.UNCHANGED]


def compute_diff(
    local: OrderedDict[str, str],
    remote: OrderedDict[str, str],
) -> DiffResult:
    """Compute differences between local and remote .env files.

    'local' represents the local .env file.
    'remote' represents the 1Password stored version.

    Returns changes from remote's perspective (what needs to change in remote to match local).
    """
    changes: list[FieldChange] = []
    all_keys = set(local.keys()) | set(remote.keys())

    for key in sorted(all_keys):
        local_value = local.get(key)
        remote_value = remote.get(key)

        if local_value is None:
            # Key exists in remote but not local (will be removed)
            changes.append(
                FieldChange(
                    key=key,
                    change_type=ChangeType.REMOVED,
                    local_value=None,
                    remote_value=remote_value,
                )
            )
        elif remote_value is None:
            # Key exists in local but not remote (will be added)
            changes.append(
                FieldChange(
                    key=key,
                    change_type=ChangeType.ADDED,
                    local_value=local_value,
                    remote_value=None,
                )
            )
        elif not values_equal(local_value, remote_value):
            # Key exists in both but values differ
            changes.append(
                FieldChange(
                    key=key,
                    change_type=ChangeType.MODIFIED,
                    local_value=local_value,
                    remote_value=remote_value,
                )
            )
        else:
            # Values are the same (after normalization)
            changes.append(
                FieldChange(
                    key=key,
                    change_type=ChangeType.UNCHANGED,
                    local_value=local_value,
                    remote_value=remote_value,
                )
            )

    return DiffResult(
        local_fields=local,
        remote_fields=remote,
        changes=changes,
    )


def format_diff(diff: DiffResult, show_values: bool = False) -> str:
    """Format diff result for display.

    Args:
        diff: The diff result to format.
        show_values: If True, show actual values (may expose secrets).
    """
    lines: list[str] = []

    if not diff.has_changes:
        return "No changes detected."

    # Summary
    added_count = len(diff.added)
    removed_count = len(diff.removed)
    modified_count = len(diff.modified)

    lines.append(f"Changes: +{added_count} added, -{removed_count} removed, ~{modified_count} modified")
    lines.append("")

    # Added
    if diff.added:
        lines.append("Added:")
        for change in diff.added:
            if show_values:
                value_preview = _truncate_value(change.local_value or "")
                lines.append(f"  + {change.key}={value_preview}")
            else:
                lines.append(f"  + {change.key}")

    # Removed
    if diff.removed:
        if diff.added:
            lines.append("")
        lines.append("Removed:")
        for change in diff.removed:
            lines.append(f"  - {change.key}")

    # Modified
    if diff.modified:
        if diff.added or diff.removed:
            lines.append("")
        lines.append("Modified:")
        for change in diff.modified:
            if show_values:
                old_preview = _truncate_value(change.remote_value or "")
                new_preview = _truncate_value(change.local_value or "")
                lines.append(f"  ~ {change.key}")
                lines.append(f"    - {old_preview}")
                lines.append(f"    + {new_preview}")
            else:
                lines.append(f"  ~ {change.key}")

    return "\n".join(lines)


def _truncate_value(value: str, max_length: int = 50) -> str:
    """Truncate a value for display, masking sensitive content."""
    if not value:
        return '""'

    # Mask if looks like a secret
    lower_value = value.lower()
    if any(s in lower_value for s in ["password", "secret", "key", "token"]):
        if len(value) > 8:
            return value[:4] + "*" * (len(value) - 8) + value[-4:]

    if len(value) > max_length:
        return value[: max_length - 3] + "..."

    return value
