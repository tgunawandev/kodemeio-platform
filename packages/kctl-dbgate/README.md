# kctl-dbgate

CLI for managing [DBGate](https://dbgate.org/) deployments — web-based database management UI.

Part of the `kctl-*` family (shared config at `~/.config/kodemeio/config.yaml`, scoped under `dbgate`).

## Install

```bash
uv pip install -e packages/kctl-dbgate
```

Or from the workspace root:

```bash
uv sync
```

## Configure

```bash
# Interactive
kctl-dbgate config init

# Or set directly
kctl-dbgate config set url https://dbgate.kodeme.io
kctl-dbgate config set login admin
kctl-dbgate config set password <your-password>
```

Config is saved under the current profile in `~/.config/kodemeio/config.yaml`:

```yaml
default_profile: kodemeio
profiles:
  kodemeio:
    dbgate:
      url: https://dbgate.kodeme.io
      login: admin
      password: ****
```

## Commands

```bash
kctl-dbgate --help

# Config & profiles
kctl-dbgate config init
kctl-dbgate config show
kctl-dbgate config set <key> <value>

# Health & diagnostics
kctl-dbgate health check
kctl-dbgate doctor

# Connections (pre-configured via env)
kctl-dbgate connections list
```

## Profiles

Use `-p <profile>` to target a different tenant or environment:

```bash
kctl-dbgate -p idtpp health check
```

## Env var overrides

| Variable | Purpose |
|----------|---------|
| `KCTL_DBGATE_URL` | Override URL |
| `KCTL_DBGATE_LOGIN` | Override login |
| `KCTL_DBGATE_PASSWORD` | Override password |
| `KCTL_DBGATE_PROFILE` | Default profile name |
