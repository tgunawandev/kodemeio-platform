"""Internal profile-migration logic for Stage A cleanup.

This module is intentionally marked private (leading underscore). In Stage B
of the profile standardization work it will be promoted into the public
`kctl-profiles` meta-CLI.
"""

from __future__ import annotations

from typing import Any

MigrationResult = dict[str, Any]
