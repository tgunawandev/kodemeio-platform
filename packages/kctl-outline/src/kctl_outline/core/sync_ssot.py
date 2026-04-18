"""SSoT marker walker for kctl-outline.

Each directory in a synced repo can have a .ssot file containing exactly
one word: 'git' or 'outline'. The walker finds the nearest marker for a
given file by walking upward toward the configured root.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path


class SSoTMode(StrEnum):
    GIT = "git"
    OUTLINE = "outline"


_VALID = {m.value for m in SSoTMode}


def find_ssot_mode(path: Path, root: Path) -> SSoTMode | None:
    """Walk upward from `path` (a file) looking for the nearest .ssot marker.

    Returns the parsed mode or None if no marker is found before reaching root.
    Marker files containing anything other than exactly 'git' or 'outline'
    (after .strip()) are treated as missing.
    """
    current = path.parent.resolve()
    root_resolved = root.resolve()
    while True:
        marker = current / ".ssot"
        if marker.is_file():
            value = marker.read_text().strip()
            if value in _VALID:
                return SSoTMode(value)
            return None
        if current == root_resolved or current == current.parent:
            return None
        current = current.parent
