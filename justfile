# Kodemeio Platform — Common Commands
# Install: brew install just | cargo install just | apt install just
# Usage:  just <recipe>      List: just --list

set dotenv-load := false

# Default: show available recipes
default:
    @just --list

# ---------------------------------------------------------------------------
# Development
# ---------------------------------------------------------------------------

# Install all workspace dependencies
install:
    uv sync --all-extras --all-packages

# Run kctl-lib tests (fast gate)
test:
    uv run pytest packages/kctl-lib/tests/ -v --tb=short

# Run tests for a specific package
test-pkg pkg:
    uv run pytest packages/{{pkg}}/tests/ -v --tb=short

# Run ALL package tests sequentially
test-all:
    #!/usr/bin/env bash
    set -euo pipefail
    failed=()
    for pkg in packages/kctl-*/; do
        name=$(basename "$pkg")
        if [ -d "$pkg/tests" ] && ls "$pkg"/tests/test_*.py >/dev/null 2>&1; then
            echo "=== $name ==="
            uv run pytest "$pkg/tests/" -v --tb=short || failed+=("$name")
        fi
    done
    echo "=== integration ==="
    uv run pytest tests/test_integration.py -v --tb=short || failed+=("integration")
    if [ ${#failed[@]} -gt 0 ]; then
        echo "FAILED: ${failed[*]}"
        exit 1
    fi
    echo "All tests passed."

# Run integration tests only
test-integration:
    uv run pytest tests/test_integration.py -v --tb=short

# ---------------------------------------------------------------------------
# Code Quality
# ---------------------------------------------------------------------------

# Lint all packages
lint:
    uv run ruff check packages/*/src/

# Lint a specific package
lint-pkg pkg:
    uv run ruff check packages/{{pkg}}/src/ packages/{{pkg}}/tests/

# Format check all packages
fmt-check:
    uv run ruff format --check packages/*/src/

# Auto-format all packages
fmt:
    uv run ruff format packages/*/src/ packages/*/tests/

# Type-check a specific package
typecheck pkg:
    uv run mypy packages/{{pkg}}/src/

# Full quality gate (lint + format + test)
check: lint fmt-check test

# ---------------------------------------------------------------------------
# Documentation
# ---------------------------------------------------------------------------

# Regenerate CLI reference docs for all 22 CLIs
docs:
    uv run python scripts/generate-cli-docs.py

# ---------------------------------------------------------------------------
# Deployment
# ---------------------------------------------------------------------------

# Validate a deploy manifest
deploy-validate file:
    uv run kctl-dokploy deploy validate -f {{file}}

# Validate ALL deploy manifests
deploy-validate-all:
    #!/usr/bin/env bash
    set -euo pipefail
    failed=()
    for f in deploys/instances/*.yaml; do
        echo "--- $(basename $f) ---"
        uv run kctl-dokploy deploy validate -f "$f" || failed+=("$(basename $f)")
    done
    if [ ${#failed[@]} -gt 0 ]; then
        echo "FAILED: ${failed[*]}"
        exit 1
    fi
    echo "All manifests valid."

# Show deploy status for a manifest
deploy-status file:
    uv run kctl-dokploy deploy status -f {{file}}

# ---------------------------------------------------------------------------
# Backup & Monitoring
# ---------------------------------------------------------------------------

# Verify backups for all instances
verify-backups:
    uv run python scripts/verify-backups.py

# Check environment variable parity across instances
check-env:
    uv run python scripts/check-env-parity.py

# ---------------------------------------------------------------------------
# Scaffolding
# ---------------------------------------------------------------------------

# Scaffold a new kctl-* CLI package
new-cli name:
    copier copy templates/kctl-cli/ packages/{{name}}/

# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

# Generate resource inventory report
inventory:
    uv run python scripts/inventory.py

# Generate resource inventory as JSON
inventory-json:
    uv run python scripts/inventory.py --json

# ---------------------------------------------------------------------------
# Maintenance
# ---------------------------------------------------------------------------

# Update uv lock file
lock:
    uv lock

# Clean build artifacts
clean:
    find packages -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    find packages -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
    find packages -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
    find packages -type d -name .ruff_cache -exec rm -rf {} + 2>/dev/null || true
    find packages -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
