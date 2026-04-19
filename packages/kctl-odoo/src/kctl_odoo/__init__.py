"""kctl-odoo: Kodemeio Odoo CLI."""

__version__ = "0.3.0"

# Trigger service-schema registration on import.
from kctl_odoo import schema  # noqa: F401
