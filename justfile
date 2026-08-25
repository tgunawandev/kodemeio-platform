# Kodemeio Dokploy — common operations

set dotenv-load := false

default:
    @just --list

# Install repository-only Python dependencies.
install:
    uv sync

# Run generator and manifest unit tests.
test:
    uv run pytest deploys/tests -q

# Lint repository Python.
lint:
    uv run ruff check deploys ops/scripts

# Check repository Python formatting.
fmt-check:
    uv run ruff format --check deploys ops/scripts

# Format repository Python.
fmt:
    uv run ruff format deploys ops/scripts

# Run the local quality gate.
check: test lint fmt-check terraform-validate

# Validate one manifest using an explicit Dokploy profile.
deploy-validate profile file:
    kctl-dokploy -p {{profile}} deploy validate -f {{file}}

# Validate all checked-in instance manifests.
deploy-validate-all profile:
    #!/usr/bin/env bash
    set -euo pipefail
    failed=()
    while IFS= read -r file; do
        echo "--- $file ---"
        kctl-dokploy -p "{{profile}}" deploy validate -f "$file" || failed+=("$file")
    done < <(find deploys/instances -type f \( -name '*.yaml' -o -name '*.yml' \) | sort)
    if [ ${#failed[@]} -gt 0 ]; then
        echo "FAILED: ${failed[*]}"
        exit 1
    fi

# Preview a manifest without changing live state.
deploy-plan profile file:
    kctl-dokploy -p {{profile}} deploy apply -f {{file}} --dry-run

# Show deployment state for a manifest.
deploy-status profile file:
    kctl-dokploy -p {{profile}} deploy status -f {{file}}

# Verify backup freshness.
verify-backups profile:
    uv run python ops/scripts/verify-backups.py --profile {{profile}}

# Check environment example parity.
check-env:
    uv run python ops/scripts/check-env-parity.py

# Generate a sanitized resource inventory.
inventory:
    uv run python ops/scripts/inventory.py

inventory-json:
    uv run python ops/scripts/inventory.py --json

# Validate Terraform without configuring a remote backend.
terraform-validate:
    terraform -chdir=infra fmt -check -recursive
    terraform -chdir=infra init -backend=false
    terraform -chdir=infra validate
