# kctl-opencloud

Kodemeio OpenCloud CLI — manage your OpenCloud file platform.

## Installation

```bash
uv tool install kctl-opencloud
```

## Usage

```bash
kctl-opencloud --help
kctl-opencloud health check
kctl-opencloud users list
kctl-opencloud groups list
kctl-opencloud spaces list
kctl-opencloud shares list
kctl-opencloud dashboard show
```

## Configuration

```bash
kctl-opencloud config init
```

Or set environment variables:
- `KCTL_OPENCLOUD_URL` — API URL
- `KCTL_OPENCLOUD_TOKEN` — API token (machine auth key)
