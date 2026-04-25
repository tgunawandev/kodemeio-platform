# kctl-litellm

Kodemeio CLI for managing [LiteLLM](https://github.com/BerriAI/litellm) proxy instances. Part of the [kodemeio-platform](https://github.com/tgunawandev/kodemeio-platform) monorepo.

## Installation

```bash
uv pip install -e packages/kctl-litellm
```

## Configuration

Add a profile to `~/.config/kodemeio/config.yaml`:

```yaml
profiles:
  production:
    litellm:
      url: https://llm.terakidz.com
      master_key: ${KCTL_LITELLM_MASTER_KEY}
      container_name: litellm
```

Or use the CLI:

```bash
kctl-litellm config add production --url https://llm.terakidz.com --master-key sk-...
```

## Usage

```bash
# Health
kctl-litellm health check         # Full health check with model status
kctl-litellm health ping          # Quick connectivity check
kctl-litellm health liveliness    # Liveness probe (no auth)

# Models
kctl-litellm models list          # List available models
kctl-litellm models info          # Detailed model info with pricing

# Key Management
kctl-litellm keys generate --key-alias my-app --max-budget 100
kctl-litellm keys list
kctl-litellm keys info <token>
kctl-litellm keys delete <token>

# Teams & Budgets
kctl-litellm teams create --team-alias engineering --max-budget 500
kctl-litellm teams list
kctl-litellm budgets create --budget-id dev-tier --max-budget 200
kctl-litellm budgets list

# Spend & Logs
kctl-litellm spend summary        # Total spend by model
kctl-litellm spend daily          # Daily activity (last 7 days)
kctl-litellm logs list --limit 50 # Recent request logs

# Config
kctl-litellm config profiles      # List profiles
kctl-litellm config show          # Show current config (secrets masked)
kctl-litellm config use staging   # Switch default profile
```

## Global Options

```
--json         Output as JSON
--quiet, -q    Suppress info messages
--profile, -p  Config profile name
--url          LiteLLM URL override
--version, -V  Show version
```

## Dependencies

- Python >= 3.12
- [kctl-lib](../kctl-lib) >= 0.4.0
