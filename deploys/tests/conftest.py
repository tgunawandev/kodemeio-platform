"""Pytest config for deploys/ tests.

Adds the deploys/ directory to sys.path so tests can `import generate`.
"""

from __future__ import annotations

import sys
from pathlib import Path

DEPLOYS_DIR = Path(__file__).resolve().parent.parent
if str(DEPLOYS_DIR) not in sys.path:
    sys.path.insert(0, str(DEPLOYS_DIR))
