"""1Password CLI wrapper."""

import hashlib
import json
import subprocess
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from typing import Any


class OnePasswordError(Exception):
    """Error from 1Password CLI."""
    pass


class NotSignedInError(OnePasswordError):
    """User is not signed in to 1Password."""
    pass


class NotInstalledError(OnePasswordError):
    """1Password CLI is not installed."""
    pass


@dataclass
class OnePasswordItem:
    """Represents a 1Password item."""
    id: str
    title: str
    vault: str
    fields: OrderedDict[str, str]
    tags: list[str]
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, str] | None = None


def run_op_command(args: list[str], capture_output: bool = True) -> str:
    """Run an op CLI command and return output."""
    cmd = ["op"] + args

    try:
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            stderr = result.stderr.strip() if result.stderr else ""
            if "not currently signed in" in stderr or "sign in" in stderr.lower():
                raise NotSignedInError("Not signed in to 1Password. Run: op signin")
            raise OnePasswordError(f"op command failed: {stderr}")

        return result.stdout.strip() if result.stdout else ""

    except FileNotFoundError:
        raise NotInstalledError("1Password CLI not installed. Run: ./bin/install-op-cli")


def is_signed_in() -> bool:
    """Check if user is signed in to 1Password.

    Raises NotInstalledError if op CLI is not installed.
    Works with both regular accounts and service accounts.
    """
    try:
        # Use 'whoami' which works for both regular and service accounts
        run_op_command(["whoami"])
        return True
    except NotInstalledError:
        raise
    except (OnePasswordError, NotSignedInError):
        return False


def get_vault_id(vault_name: str) -> str | None:
    """Get vault ID by name."""
    try:
        output = run_op_command(["vault", "get", vault_name, "--format", "json"])
        data = json.loads(output)
        return data.get("id")
    except OnePasswordError:
        return None


def create_vault(vault_name: str, description: str = "") -> str:
    """Create a new vault and return its ID."""
    args = ["vault", "create", vault_name]
    if description:
        args.extend(["--description", description])
    args.extend(["--format", "json"])

    output = run_op_command(args)
    data = json.loads(output)
    return data.get("id", "")


def list_items(vault: str) -> list[dict[str, Any]]:
    """List all items in a vault."""
    try:
        output = run_op_command(["item", "list", "--vault", vault, "--format", "json"])
        if not output:
            return []
        return json.loads(output)
    except OnePasswordError:
        return []


def get_item(title: str, vault: str) -> OnePasswordItem | None:
    """Get an item by title from a vault."""
    try:
        output = run_op_command(["item", "get", title, "--vault", vault, "--format", "json"])
        data = json.loads(output)

        # Extract fields
        fields = OrderedDict()
        for field in data.get("fields", []):
            label = field.get("label", "")
            value = field.get("value", "")
            if label and label not in ("notesPlain", "notes"):
                fields[label] = value

        # Extract metadata from notes
        metadata = {}
        for field in data.get("fields", []):
            if field.get("id") == "notesPlain" or field.get("label") == "notesPlain":
                notes = field.get("value", "")
                for line in notes.split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        metadata[key.strip()] = val.strip()

        # Parse timestamps
        created_at = None
        updated_at = None
        if data.get("created_at"):
            try:
                created_at = datetime.fromisoformat(data["created_at"].replace("Z", "+00:00"))
            except ValueError:
                pass
        if data.get("updated_at"):
            try:
                updated_at = datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00"))
            except ValueError:
                pass

        return OnePasswordItem(
            id=data.get("id", ""),
            title=data.get("title", ""),
            vault=vault,
            fields=fields,
            tags=data.get("tags", []),
            created_at=created_at,
            updated_at=updated_at,
            metadata=metadata,
        )

    except OnePasswordError:
        return None


def create_item(
    title: str,
    vault: str,
    fields: OrderedDict[str, str],
    tags: list[str] | None = None,
    metadata: dict[str, str] | None = None,
) -> str:
    """Create a new Secure Note item with fields.

    Returns the item ID.
    """
    args = [
        "item", "create",
        "--category", "Secure Note",
        "--title", title,
        "--vault", vault,
    ]

    # Add tags
    if tags:
        args.extend(["--tags", ",".join(tags)])

    # Add metadata as notes
    if metadata:
        notes_lines = [f"{k}: {v}" for k, v in metadata.items()]
        notes = "\n".join(notes_lines)
        args.append(f"notesPlain={notes}")

    # Add fields - use password type for secrets
    for key, value in fields.items():
        # op CLI handles escaping when passed as arguments
        args.append(f"{key}[password]={value}")

    args.extend(["--format", "json"])

    output = run_op_command(args)
    data = json.loads(output)
    return data.get("id", "")


def update_item(
    title: str,
    vault: str,
    fields: OrderedDict[str, str],
    tags: list[str] | None = None,
    metadata: dict[str, str] | None = None,
) -> None:
    """Update an existing item's fields."""
    # Get existing item to find its ID
    existing = get_item(title, vault)
    if not existing:
        raise OnePasswordError(f"Item not found: {title}")

    # Delete and recreate to ensure clean field state
    # (op item edit has limitations with field updates)
    delete_item(title, vault)
    create_item(title, vault, fields, tags, metadata)


def delete_item(title: str, vault: str) -> None:
    """Delete an item from a vault."""
    try:
        run_op_command(["item", "delete", title, "--vault", vault])
    except OnePasswordError as e:
        if "not found" not in str(e).lower():
            raise


def item_exists(title: str, vault: str) -> bool:
    """Check if an item exists in a vault."""
    return get_item(title, vault) is not None


def compute_hash(fields: OrderedDict[str, str]) -> str:
    """Compute a hash of field values for comparison."""
    content = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    return hashlib.sha256(content.encode()).hexdigest()[:16]
