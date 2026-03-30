---
name: dokploy-admin
description: >
  Dokploy deployment platform administration via kctl-dokploy CLI (dokploy.kodeme.io). MUST use for ANY deployment, compose service, domain, backup, or Dokploy operation. Triggers on: "kctl-dokploy", "dokploy", "deploy service", "compose service", "add domain", "deployment status", "dokploy backup", "environment variable", or ANY Dokploy platform task.
version: 2.0.0
allowed-tools:
  - Bash
  - Read
  - Write
  - Edit
  - Glob
  - Grep
---

# Dokploy Administration for Kodemeio

## System Overview

- **URL**: dokploy.kodeme.io
- **Server**: Hetzner cx42 (8 vCPU, 16 GB, 168.119.233.161)
- **Architecture**: Cloudflare Edge → cloudflared tunnel → Traefik → Dokploy → ~55 containers
- **CLI**: `kctl-dokploy` (Python, installed via `uv tool install ./cli`)
- **Config**: `~/.config/kodemeio/config.yaml` → `profiles.<profile>.dokploy`

## Commands

### Status & Health

| Command | Description |
|---------|-------------|
| `kctl-dokploy status show` | Platform dashboard (projects, services) |
| `kctl-dokploy health check` | API connectivity check |

### Projects

| Command | Description |
|---------|-------------|
| `kctl-dokploy projects list` | List all projects |
| `kctl-dokploy projects get <name>` | Project details |

### Apps (legacy)

| Command | Description |
|---------|-------------|
| `kctl-dokploy apps list` | All compose services across projects |

### Applications

| Command | Description |
|---------|-------------|
| `kctl-dokploy applications list [--project <name>]` | List applications (optionally filter by project) |
| `kctl-dokploy applications get <app-id>` | Application details |
| `kctl-dokploy applications create --name <n> --project <id> [--description] [--server]` | Create application |
| `kctl-dokploy applications update <app-id> [--name] [--description] [--image]` | Update application |
| `kctl-dokploy applications delete <app-id> [--force]` | Delete application |
| `kctl-dokploy applications deploy <app-id>` | Deploy application |
| `kctl-dokploy applications stop <app-id> [--force]` | Stop application |

### Compose

| Command | Description |
|---------|-------------|
| `kctl-dokploy compose list [--project <id>]` | List compose services (optionally filter by project) |
| `kctl-dokploy compose get <compose-id>` | Compose service details |
| `kctl-dokploy compose create <project-id> --name <n> [--description] [--server]` | Create compose service |
| `kctl-dokploy compose update <compose-id> [--env] [--compose-file] [--source-type]` | Update compose service |
| `kctl-dokploy compose delete <compose-id> [--force]` | Delete compose service |
| `kctl-dokploy compose stop <compose-id> [--force]` | Stop compose service |
| `kctl-dokploy compose start <compose-id>` | Start compose service |
| `kctl-dokploy compose redeploy <compose-id>` | Redeploy compose service |
| `kctl-dokploy compose logs <compose-id> [--lines N]` | View compose service logs |
| `kctl-dokploy compose env <compose-id>` | Show environment variables |
| `kctl-dokploy compose env-set <compose-id> --key <k> --value <v>` | Set environment variable |

### Servers

| Command | Description |
|---------|-------------|
| `kctl-dokploy servers list` | List all servers |
| `kctl-dokploy servers get <server-id>` | Server details |
| `kctl-dokploy servers create --name <n> --ip <addr> [--ssh-key] [--port] [--username]` | Add server |
| `kctl-dokploy servers remove <server-id> [--force]` | Remove server |

### Deployments

| Command | Description |
|---------|-------------|
| `kctl-dokploy deployments list [--compose <id>] [--application <id>] [--limit N]` | Recent deployments |
| `kctl-dokploy deployments get <deployment-id>` | Deployment details |
| `kctl-dokploy deployments logs <deployment-id>` | Deployment build logs |
| `kctl-dokploy deployments redeploy <compose-id>` | Trigger redeployment |
| `kctl-dokploy deployments cancel <deployment-id>` | Cancel running deployment |

### Deploy (shortcut)

| Command | Description |
|---------|-------------|
| `kctl-dokploy deploy run <compose-id>` | Trigger deployment |

### Domains

| Command | Description |
|---------|-------------|
| `kctl-dokploy domains list` | All configured domains |
| `kctl-dokploy domains get <compose-id>` | Domains for a compose service |
| `kctl-dokploy domains create <compose-id> --host <h> [--port] [--https/--no-https] [--cert] [--service]` | Add domain |
| `kctl-dokploy domains delete <domain-id> [--force]` | Remove domain |

### Backups

| Command | Description |
|---------|-------------|
| `kctl-dokploy backups list [--compose <id>]` | Backup inventory |
| `kctl-dokploy backups trigger <compose-id> [--destination <id>]` | Trigger backup |
| `kctl-dokploy backups restore <backup-id> [--force]` | Restore from backup |
| `kctl-dokploy backups destinations` | List backup destinations |
| `kctl-dokploy backups add-destination --name <n> --bucket <b> --access-key --secret-key [--region] [--endpoint]` | Add S3 destination |
| `kctl-dokploy backups test-destination <destination-id>` | Test backup destination |
| `kctl-dokploy backups delete-destination <destination-id> [--force]` | Remove backup destination |

### Environment Variables

| Command | Description |
|---------|-------------|
| `kctl-dokploy env list <compose-id>` | List environment variables |
| `kctl-dokploy env get <compose-id> <key>` | Get single env var |
| `kctl-dokploy env set <compose-id> <key> <value>` | Set env var |
| `kctl-dokploy env delete <compose-id> <key>` | Delete env var |
| `kctl-dokploy env push <compose-id> <file>` | Push .env file to compose service |
| `kctl-dokploy env pull <compose-id> [<output-file>]` | Pull env vars to file or stdout |

### Logs

| Command | Description |
|---------|-------------|
| `kctl-dokploy logs show <compose-id> [--lines N]` | Service logs |

### Registry

| Command | Description |
|---------|-------------|
| `kctl-dokploy registry list` | List container registries |
| `kctl-dokploy registry get <registry-id>` | Registry details |
| `kctl-dokploy registry create --name <n> --url <u> --username <u> --password --type <t>` | Add registry |
| `kctl-dokploy registry update <registry-id> [--name] [--url] [--username] [--password]` | Update registry |
| `kctl-dokploy registry remove <registry-id> [--force]` | Remove registry |
| `kctl-dokploy registry test <registry-id>` | Test registry connection |

### Users

| Command | Description |
|---------|-------------|
| `kctl-dokploy users list` | List all users |
| `kctl-dokploy users get <user-id>` | User details |
| `kctl-dokploy users create --email <e> --password [--role admin/user]` | Create user |
| `kctl-dokploy users update <user-id> [--role] [--email] [--password]` | Update user |
| `kctl-dokploy users remove <user-id> [--force]` | Remove user |
| `kctl-dokploy users permissions <user-id>` | View user permissions |

### Git Providers

| Command | Description |
|---------|-------------|
| `kctl-dokploy git list` | List git providers |
| `kctl-dokploy git get <provider-id>` | Provider details |
| `kctl-dokploy git create --name <n> --type <github/gitlab/bitbucket> [--org] [--token]` | Add git provider |
| `kctl-dokploy git update <provider-id> [--name] [--org] [--token]` | Update git provider |
| `kctl-dokploy git remove <provider-id> [--force]` | Remove git provider |
| `kctl-dokploy git test <provider-id>` | Test git connection |
| `kctl-dokploy git branches <provider-id> --owner <o> --repo <r>` | List repository branches |

### Databases

| Command | Description |
|---------|-------------|
| `kctl-dokploy databases list` | List all database services |
| `kctl-dokploy databases get <db-id> --type <postgres/redis/mysql/mariadb/mongo>` | Database details |
| `kctl-dokploy databases create-postgres --name <n> --project <id> [--version 16] [--password]` | Create PostgreSQL |
| `kctl-dokploy databases create-redis --name <n> --project <id> [--version 7]` | Create Redis |
| `kctl-dokploy databases create-mysql --name <n> --project <id> [--version 8] [--password]` | Create MySQL |
| `kctl-dokploy databases create-mariadb --name <n> --project <id> [--version 11] [--password]` | Create MariaDB |
| `kctl-dokploy databases create-mongo --name <n> --project <id> [--version 7] [--password]` | Create MongoDB |
| `kctl-dokploy databases remove <db-id> --type <type>` | Remove database service |

### Monitoring

| Command | Description |
|---------|-------------|
| `kctl-dokploy monitoring containers` | Running container overview |
| `kctl-dokploy monitoring resources` | Resource usage summary |
| `kctl-dokploy monitoring server-stats [--server <id>]` | Server resource stats |
| `kctl-dokploy monitoring container-logs <container-name> [--tail N]` | Docker container logs |

### Notifications

| Command | Description |
|---------|-------------|
| `kctl-dokploy notifications list` | List notification channels |
| `kctl-dokploy notifications get <notification-id>` | Channel details |
| `kctl-dokploy notifications create --name <n> --type <slack/discord/telegram/email> [--webhook-url] [--email] [--chat-id] [--bot-token]` | Create channel |
| `kctl-dokploy notifications update <notification-id> [--name] [--webhook-url] [--enabled/--disabled]` | Update channel |
| `kctl-dokploy notifications remove <notification-id> [--force]` | Remove channel |
| `kctl-dokploy notifications test <notification-id>` | Test notification channel |

### Certificates

| Command | Description |
|---------|-------------|
| `kctl-dokploy certificates list` | List all certificates |
| `kctl-dokploy certificates get <certificate-id>` | Certificate details |
| `kctl-dokploy certificates create --name <n> [--domain] [--auto-renew/--no-auto-renew]` | Create Let's Encrypt certificate |
| `kctl-dokploy certificates import --name <n> --cert <path> --key <path> [--chain <path>]` | Import PEM certificate |
| `kctl-dokploy certificates remove <certificate-id> [--force]` | Remove certificate |
| `kctl-dokploy certificates renew <certificate-id>` | Renew certificate |

### Settings

| Command | Description |
|---------|-------------|
| `kctl-dokploy settings show` | Show platform settings |
| `kctl-dokploy settings update [--letsencrypt-email] [--docker-cleanup/--no-docker-cleanup]` | Update settings |
| `kctl-dokploy settings ssh-keys` | List SSH keys |
| `kctl-dokploy settings ssh-key-create --name <n> [--public-key] [--public-key-file] [--private-key-file]` | Add SSH key |
| `kctl-dokploy settings ssh-key-remove <ssh-key-id> [--force]` | Remove SSH key |
| `kctl-dokploy settings destinations` | List backup destinations |

### Notify (legacy shortcut)

| Command | Description |
|---------|-------------|
| `kctl-dokploy notify test` | Test notification channel |

### Cleanup

| Command | Description |
|---------|-------------|
| `kctl-dokploy cleanup stats` | Docker container stats |

### Config

| Command | Description |
|---------|-------------|
| `kctl-dokploy config init` | First-time setup |
| `kctl-dokploy config show` | Show config (masked) |
| `kctl-dokploy config test` | Test connection |
| `kctl-dokploy config use <profile>` | Switch profile |

## Global Options

`--json` `--quiet` `-q` `--profile` `-p` `--url` `--api-key` `--version` `-V`

## Deployment Workflow

```bash
kctl-dokploy status show           # Dashboard
kctl-dokploy apps list             # Find compose ID
kctl-dokploy deploy run <id>       # Deploy
kctl-dokploy logs show <id>        # Check logs
```

## Application Management

```bash
kctl-dokploy applications create --name my-app --project <project-id>
kctl-dokploy applications deploy <app-id>
kctl-dokploy applications stop <app-id>
```

## Compose Service Management

```bash
kctl-dokploy compose create <project-id> --name my-service
kctl-dokploy compose update <compose-id> --compose-file ./docker-compose.yml
kctl-dokploy compose redeploy <compose-id>
kctl-dokploy compose logs <compose-id> --lines 100
```

## Database Provisioning

```bash
kctl-dokploy databases create-postgres --name my-db --project <id> --version 16
kctl-dokploy databases list
kctl-dokploy databases remove <db-id> --type postgres
```

## Backup & Restore

```bash
kctl-dokploy backups add-destination --name s3-backup --bucket my-bucket --access-key <key> --secret-key <secret> --endpoint https://s3.example.com
kctl-dokploy backups trigger <compose-id> --destination <dest-id>
kctl-dokploy backups restore <backup-id>
```

## Troubleshooting

- Deployment stuck: `deployments list` → `deployments logs <id>` → `deployments cancel <id>`
- Service down: `health check` → `domains list` → Traefik logs
- Env issues: `env list <id>` → compare with .env.example → `env push <id> .env`
- Registry auth: `registry test <id>` → check credentials
- Certificate issues: `certificates list` → `certificates renew <id>`
