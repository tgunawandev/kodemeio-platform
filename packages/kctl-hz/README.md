# kctl-hz

Kodemeio Hetzner Cloud CLI — manage Hetzner Cloud infrastructure.

## Features

- **122 commands** across 21 groups (servers, volumes, firewalls, networks, load-balancers, IPs, DNS, S3, storage-boxes, and more)
- **Terraform IaC** — production-ready infrastructure definitions with 3 architecture options
- **Multi-API support** — Hetzner Cloud API + DNS API + Robot API + S3
- **Profile-based config** — multiple named profiles with token/credential storage
- **Multiple output formats** — pretty (Rich tables), JSON, CSV, YAML
- **Cost estimation** — monthly cost calculator for running resources
- **10 quick aliases** — `sl`, `sg`, `sc`, `hc`, `ss`, `vl`, `fl`, `nl`, `ce`, `dz`

## Install

```bash
uv tool install kctl-hz
kctl-hz config init
```

## Structure

```
kctl-hz/
├── src/kctl_hz/     # Python CLI (122 commands)
├── tests/                # 108 pytest tests
├── infra/hetzner/        # Terraform IaC (13 .tf files + cloud-init templates)
├── docs/                 # Deployment guide, infrastructure reference, API reference
├── skills/               # Claude Code skill definitions
└── .env.example          # Required environment variables
```

## Terraform

Three production architecture options in `infra/hetzner/`:

| Option | Servers | Cost | Use Case |
|--------|---------|------|----------|
| A — Single | 1x cx52 | ~EUR75/mo | Dev/staging |
| B — 2-Server | cx42 + cx32 | ~EUR75/mo | Production <500 users |
| C — 3-Server | cx32 + cx42 + cx42 | ~EUR100/mo | Scale-ready 500+ users |

```bash
cd infra/hetzner
terraform init
terraform plan
terraform apply
```
