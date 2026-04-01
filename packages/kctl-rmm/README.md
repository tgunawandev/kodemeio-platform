# kctl-rmm

Kodemeio Tactical RMM CLI - manage remote monitoring and management.

## Install

```bash
uv tool install ./cli/
```

## Setup

```bash
kctl-rmm config init
kctl-rmm config add abcfood --url https://api-rmm.abcfood.app --api-key $KEY --mesh-url https://mesh.abcfood.app
```

## Usage

```bash
# Remote Access (opens browser)
kctl-rmm remote takecontrol PCTMIGBJ     # Take Control by hostname
kctl-rmm remote rmm                      # Open RMM dashboard
kctl-rmm remote mesh                     # Open MeshCentral

# Agents
kctl-rmm agents list
kctl-rmm agents summary
kctl-rmm agents offline

# Scripts
kctl-rmm scripts list
kctl-rmm scripts run 136 --agent <id>

# Monitoring
kctl-rmm dashboard
kctl-rmm health

# Multi-profile
kctl-rmm -p abcfood agents list
kctl-rmm -p abcfood remote takecontrol DESKTOP-KR118VQ
```
