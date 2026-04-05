---
name: dokploy-admin
description: >
  Dokploy deployment platform administration via kctl-dokploy CLI (49 groups, ~286 commands).
  MUST use for ANY kctl-dokploy operation.
  Triggers on: "add-destination", "add-manager", "add-worker", "applications", "apply", "apply-all", "audit", "backup", "backups", "bl", "branches", "build-servers", "bulk", "by-server", "by-type", "cancel", "certificates", "check", "cl", "clean", "cleanup", "clear-deployments", "cluster", "compliance", "compose", "config", "container-logs", "containers", "count", "cr", "create-mariadb", "create-mongo", "create-mysql", "create-postgres", "create-redis", "create-ssh-key", "cs", "dashboard", "databases", "delete-destination", "delete-rollback", "deploy", "deploy-all", "deployments", "destinations", "dg", "diagnose", "dl", "docker", "domains", "ds", "duplicate", "env", "env-set", "environments", "export", "find", "generate", "get-env", "git", "health", "history", "images", "import", "import-file", "init", "integrity", "kctl-dokploy", "kill", "kill-build", "list-by-service", "logs", "maintenance", "mark-delete", "metrics", "migrate", "monitor", "monitoring", "mounts", "move".
  Auto-generated: 2026-04-05
  registry_hash: ee64dbbf39c1
---

# dokploy-admin — kctl-dokploy CLI Reference

> Auto-generated from `kctl-dokploy` command registry. Do not edit manually.
> To regenerate: `kctl-dokploy skill generate`
> To add custom content: edit `SKILL.extra.md` in the same directory.

## Overview

**CLI:** `kctl-dokploy`
**Command groups:** 49
**Total commands:** ~286
**Install:** `cd cli && uv tool install --editable .`

## Global Options

| Flag | Description |
|------|-------------|
| `--json` | JSON output |
| `--quiet`, `-q` | Suppress info messages |
| `--format`, `-f` | Output format: pretty/json/csv/yaml |
| `--no-header` | Omit CSV header row |
| `--profile`, `-p` | Config profile name |
| `--version`, `-V` | Show version |

## Command Reference

### `kctl-dokploy applications`

Manage Dokploy applications.

| Command | Description |
|---------|-------------|
| `applications cancel <app_id>` | Cancel a running deployment for an application. |
| `applications clear-deployments <app_id> [--force]` | Clear all deployment history for an application (destructive). |
| `applications create <name> <project_id> [--description] [--server_id]` | Create a new application. |
| `applications delete <application_id> [--force]` | Delete an application (destructive). |
| `applications deploy <application_id>` | Trigger deployment for an application. |
| `applications get <application_id>` | Get application details. |
| `applications kill-build <app_id> [--force]` | Kill a running build for an application (destructive). |
| `applications list [--project]` | List all applications across projects. |
| `applications monitoring <app_id>` | Show monitoring data for an application. |
| `applications move <app_id> <environment>` | Move an application to a different environment. |
| `applications redeploy <application_id>` | Stop and redeploy an application. |
| `applications search <name>` | Search applications by name. |
| `applications show-traefik <app_id>` | Show Traefik configuration for an application. |
| `applications start <application_id>` | Start (deploy) a stopped application. |
| `applications stop <application_id> [--force]` | Stop a running application. |
| `applications update <application_id> [--name] [--description] [--docker_image]` | Update an application configuration. |

### `kctl-dokploy audit`

Security audit and compliance checks.

| Command | Description |
|---------|-------------|
| `audit config` | Check platform configuration against best practices. |
| `audit security` | Run a comprehensive security review across the platform. |
| `audit ssl` | Detailed SSL certificate audit with expiry tracking. |
| `audit users` | User access review grouped by role. |

### `kctl-dokploy backups`

Manage Dokploy backups and S3 destinations.

| Command | Description |
|---------|-------------|
| `backups add-destination <name> <bucket> <access_key> <secret_key> [--region] [--endpoint]` | Add an S3 backup destination. |
| `backups create <destination_id> <database> [--db_type] [--postgres_id] [--mysql_id] [--mariadb_id] [--mongo_id] [--compose_id] [--service_name] [--schedule] [--prefix] [--enabled]` | Create a backup configuration for a database or compose service. |
| `backups delete-destination <destination_id> [--force]` | Delete an S3 backup destination. |
| `backups delete-rollback <rollback_id> [--force]` | Delete a rollback record (destructive). |
| `backups destinations` | List all S3 backup destinations. |
| `backups list [--compose_id]` | List all backup configurations. |
| `backups restore <backup_id> [--force]` | Restore from a backup snapshot (destructive). |
| `backups rollback <rollback_id> [--force]` | Rollback to a previous state (destructive). |
| `backups run <backup_id> [--backup_type]` | Trigger a manual backup run. |
| `backups test-destination <destination_id>` | Test S3 connection for a destination. |
| `backups update-destination <destination_id> [--name] [--bucket] [--region] [--endpoint] [--access_key] [--secret_key]` | Update an S3 backup destination. |

### `kctl-dokploy bl`

Alias: backups list

### `kctl-dokploy bulk`

Bulk operations across multiple services.

| Command | Description |
|---------|-------------|
| `bulk deploy-all <project> [--exclude] [--force]` | Deploy all compose services in a project. |
| `bulk env-set <project> <key> <value> [--services]` | Set an environment variable across multiple compose services. |
| `bulk restart-all <project> [--exclude] [--force]` | Restart all compose services (stop + deploy) in a project. |
| `bulk stop-all <project> [--exclude] [--force]` | Stop all compose services in a project. |

### `kctl-dokploy certificates`

Manage SSL certificates.

| Command | Description |
|---------|-------------|
| `certificates create <name> [--domain] [--auto_renew]` | Create a new Let's Encrypt certificate. |
| `certificates get <certificate_id>` | Get certificate details. |
| `certificates import <name> <cert_path> <key_path> [--chain_path]` | Import a custom SSL certificate. |
| `certificates list` | List all SSL certificates. |
| `certificates remove <certificate_id> [--force]` | Remove a certificate (destructive). |
| `certificates renew <certificate_id>` | Trigger certificate renewal. |

### `kctl-dokploy cl`

Alias: compose list

### `kctl-dokploy cluster`

Manage Docker Swarm cluster and nodes.

| Command | Description |
|---------|-------------|
| `cluster add-manager <server_id>` | Get the command to add a server as a Swarm manager. |
| `cluster add-worker <server_id>` | Get the command to add a server as a Swarm worker. |
| `cluster nodes <server_id>` | List cluster nodes for a server. |
| `cluster remove-worker <node_id> [--force]` | Remove a worker node from the cluster (destructive). |
| `cluster swarm-apps <server_id>` | List applications running on Swarm nodes. |
| `cluster swarm-info <node_id> <server_id>` | Get detailed info for a Swarm node. |
| `cluster swarm-nodes <server_id>` | List Swarm nodes for a server. |

### `kctl-dokploy compose`

Manage Dokploy compose services.

| Command | Description |
|---------|-------------|
| `compose backups` | Manage Dokploy backups and S3 destinations. |
| `compose bulk` | Bulk operations across multiple services. |
| `compose cancel <compose_id>` | Cancel a running deployment for a compose service. |
| `compose clear-deployments <compose_id> [--force]` | Clear all deployment history for a compose service (destructive). |
| `compose create <environment_id> <name> [--description] [--server_id] [--compose_file]` | Create a new compose service in a project environment. |
| `compose delete <compose_id> [--force]` | Delete a compose service (destructive). |
| `compose deployments` | Manage Dokploy deployments. |
| `compose domains` | Manage Dokploy domains. |
| `compose env` | Manage compose environment variables. |
| `compose get <compose_id>` | Get details for a compose service. |
| `compose import <compose_id> <file>` | Import a docker-compose file into a compose service. |
| `compose kill-build <compose_id> [--force]` | Kill a running build for a compose service (destructive). |
| `compose list [--project_id]` | List compose services, optionally filtered by project. |
| `compose logs <compose_id> [--lines]` | Show logs for a compose service (fetches from deployment history). |
| `compose mounts` | Manage volume and bind mounts. |
| `compose move <compose_id> <environment>` | Move a compose service to a different environment. |
| `compose patches` | Manage file patches for services. |
| `compose ports` | Manage port mappings for applications. |
| `compose redeploy <compose_id>` | Stop and redeploy a compose service. |
| `compose redirects` | Manage URL redirect rules. |
| `compose schedules` | Manage scheduled tasks (cron jobs). |
| `compose search <name>` | Search compose services by name. |
| `compose security` | Manage HTTP basic auth protection. |
| `compose service-logs <compose_id> [--service] [--tail]` | Show Docker container runtime logs for a compose service. |
| `compose services <compose_id>` | List services defined in a compose service. |
| `compose start <compose_id>` | Start (deploy) a compose service. |
| `compose stop <compose_id> [--force]` | Stop a running compose service. |
| `compose update <compose_id> [--name] [--description] [--env_content] [--compose_file] [--source_type] [--repository] [--owner] [--branch] [--compose_path] [--github_id] [--command] [--trigger_type] [--watch_paths] [--enable_submodules] [--auto_deploy]` | Update a compose service configuration. |
| `compose volume-backups` | Manage volume-level backups. |

### `kctl-dokploy config`

Manage CLI configuration and profiles.

| Command | Description |
|---------|-------------|
| `config export` | Export current configuration as YAML. |
| `config init [--url] [--api_key] [--name]` | Initialize CLI configuration. |
| `config remove <name> [--force]` | Remove a profile. |
| `config show` | Show configuration (keys masked). |
| `config test` | Test API connection. |
| `config use <name>` | Switch default profile. |

### `kctl-dokploy cr`

Alias: compose redeploy <id>

Usage: `kctl-dokploy cr <compose_id>`

### `kctl-dokploy cs`

Alias: compose start <id>

Usage: `kctl-dokploy cs <compose_id>`

### `kctl-dokploy dashboard`

Dashboard overview of Dokploy instance.

| Command | Description |
|---------|-------------|
| `dashboard show` | Show comprehensive Dokploy dashboard. |

### `kctl-dokploy databases`

Manage Dokploy database services.

| Command | Description |
|---------|-------------|
| `databases create-mariadb <name> <project_id> [--version] [--password]` | Create a MariaDB database service. |
| `databases create-mongo <name> <project_id> [--version] [--password]` | Create a MongoDB database service. |
| `databases create-mysql <name> <project_id> [--version] [--password]` | Create a MySQL database service. |
| `databases create-postgres <name> <environment_id> [--db_name] [--db_user] [--password] [--version] [--server_id] [--description]` | Create a PostgreSQL database service. |
| `databases create-redis <name> <project_id> [--version]` | Create a Redis database service. |
| `databases deploy <db_id> <db_type>` | Deploy/redeploy a database service. |
| `databases get <db_id> <db_type>` | Get database service details. |
| `databases get-env <db_id> <db_type>` | Show environment variables for a database service. |
| `databases list` | List all database services across all projects. |
| `databases remove <db_id> <db_type> [--force]` | Remove a database service (destructive). |
| `databases set-env <db_id> <db_type> [--env_content] [--env_file]` | Set environment variables on a database service. |
| `databases stop <db_id> <db_type>` | Stop a database service. |

### `kctl-dokploy deploy`

Declarative deployment from YAML manifests.

| Command | Description |
|---------|-------------|
| `deploy apply <file> [--dry_run] [--skip_deploy] [--skip_verify] [--skip_preflight]` | All-in-one: setup + deploy + post-deploy in sequence. |
| `deploy apply-all [--dir] [--dry_run]` | Apply all manifests in a directory sequentially. |
| `deploy list` | List all instance manifests and their status. |
| `deploy migrate` | Server-to-server migration pipeline. |
| `deploy post <file> [--dry_run]` | Stage 3: Post-deploy — backup config, schedules, Odoo bundle install. |
| `deploy preflight <file> [--gates]` | Run preflight checks before deployment. |
| `deploy preflight-all <directory> [--server] [--gates]` | Run preflight checks on all manifests in a directory. |
| `deploy run <file> [--skip_verify] [--dry_run]` | Stage 2: Deploy + verify — trigger redeploy and wait for healthy. |
| `deploy setup <file> [--dry_run]` | Stage 1: Infrastructure setup — DNS, database, compose, env, domain. |
| `deploy status <file>` | Check current state vs manifest (dry-run preview). |
| `deploy troubleshoot [--file] [--compose_id]` | Diagnose why a deployment failed. |
| `deploy validate <file>` | Validate a deploy manifest without deploying. |
| `deploy verify <file>` | Run pre-deploy validation and post-deploy smoke tests. |

### `kctl-dokploy deployments`

Manage Dokploy deployments.

| Command | Description |
|---------|-------------|
| `deployments by-server <server>` | List all deployments for a specific server. |
| `deployments by-type <type_>` | List deployments filtered by type. |
| `deployments cancel <deployment_id>` | Cancel a running deployment. |
| `deployments get <deployment_id>` | Get deployment details. |
| `deployments kill <deployment_id> [--force]` | Kill a running deployment process (destructive). |
| `deployments list [--compose_id] [--application_id] [--limit]` | List deployments, optionally filtered by compose or application. |
| `deployments logs [--deployment_id] [--compose_id] [--application_id]` | Show deployment logs via SSH to server. |
| `deployments queue` | List queued deployments. |
| `deployments redeploy <compose_id>` | Trigger a redeployment for a compose service (stop + deploy). |
| `deployments remove <deployment_id> [--force]` | Remove a deployment record (destructive). |

### `kctl-dokploy dg`

Alias: diagnose run

### `kctl-dokploy diagnose`

Diagnostic health scoring for Dokploy platform.

| Command | Description |
|---------|-------------|
| `diagnose maintenance` | Maintenance, integrity checks, and cleanup. |
| `diagnose run` | Run all diagnostic sections and display the health report. |
| `diagnose section <name>` | Run a single diagnostic section. |

### `kctl-dokploy dl`

Alias: deployments list

### `kctl-dokploy docker`

Docker container and resource management.

| Command | Description |
|---------|-------------|
| `docker config <container_id>` | Show configuration for a Docker container. |
| `docker containers [--server]` | List Docker containers. |
| `docker find <app_name>` | Find Docker containers by application name. |
| `docker images` | List Docker images (not available in current Dokploy API). |
| `docker networks` | List Docker networks (not available in current Dokploy API). |
| `docker prune [--force]` | Prune unused Docker resources. |
| `docker restart <container_id> [--force]` | Restart a Docker container (destructive). |
| `docker stats` | Show Docker disk usage statistics. |
| `docker volumes` | List Docker volumes (not available in current Dokploy API). |

### `kctl-dokploy domains`

Manage Dokploy domains.

| Command | Description |
|---------|-------------|
| `domains create <compose_id> <host> [--port] [--https] [--cert_type] [--service_name]` | Add a domain to a compose service. |
| `domains delete <domain_id> [--force]` | Remove a domain. |
| `domains get <compose_id>` | Get domains for a specific compose service. |
| `domains list` | List all domains across all projects. |
| `domains update <domain_id> [--host] [--port] [--https] [--cert_type] [--service_name]` | Update a domain configuration. |

### `kctl-dokploy ds`

Alias: dashboard show

### `kctl-dokploy env`

Manage compose environment variables.

| Command | Description |
|---------|-------------|
| `env delete <compose_id> <key> [--force]` | Remove an environment variable from a compose service. |
| `env get <compose_id> <key>` | Get a single environment variable. |
| `env list <compose_id>` | List environment variables for a compose service. |
| `env pull <compose_id> [--output_file]` | Pull environment variables from a compose service to file or stdout. |
| `env push <compose_id> <file> [--force]` | Push an entire .env file to a compose service (overwrites all env vars). |
| `env set <compose_id> <key> <value>` | Set an environment variable on a compose service. |

### `kctl-dokploy environments`

Manage deployment environments (dev/staging/prod).

| Command | Description |
|---------|-------------|
| `environments create <name> <project> [--description]` | Create a new environment. |
| `environments duplicate <env_id> <name>` | Duplicate an environment. |
| `environments get <env_id>` | Get environment details. |
| `environments list <project>` | List environments for a project. |
| `environments remove <env_id> [--force]` | Remove an environment (destructive). |
| `environments search [--name] [--project]` | Search environments by name or project. |
| `environments update <env_id> [--name] [--description]` | Update an environment. |

### `kctl-dokploy git`

Manage Git providers and repositories.

| Command | Description |
|---------|-------------|
| `git branches <provider_id> <owner> <repo>` | List branches for a repository on a Git provider. |
| `git create <name> <provider_type> [--organization] [--access_token]` | Create a new Git provider. |
| `git get <provider_id>` | Get Git provider details. |
| `git list` | List all configured Git providers. |
| `git remove <provider_id> [--force]` | Remove a Git provider (destructive). |
| `git resolve [--provider_id]` | Resolve a git provider to its GitHub App ID (for compose linking). |
| `git test <provider_id>` | Test connection to a Git provider. |
| `git update <provider_id> [--name] [--organization] [--access_token]` | Update a Git provider. |

### `kctl-dokploy maintenance`

Maintenance, integrity checks, and cleanup.

| Command | Description |
|---------|-------------|
| `maintenance cleanup [--dry_run] [--force]` | Safe cleanup of orphaned and stale resources. |
| `maintenance integrity` | Run data integrity checks across all resources. |
| `maintenance orphans` | List orphaned resources (disconnected services, domains). |
| `maintenance stale [--threshold]` | List stale/stuck deployments beyond a time threshold. |

### `kctl-dokploy monitoring`

Monitoring, metrics, and resource usage.

| Command | Description |
|---------|-------------|
| `monitoring container-logs <container_name> [--tail] [--server]` | Show logs from a Docker container. |
| `monitoring containers` | Show Docker container stats (CPU, memory, network). |
| `monitoring resources` | Show system resource usage (disk, CPU, RAM). |
| `monitoring server-stats [--server_id]` | Show server monitoring statistics. |

### `kctl-dokploy mounts`

Manage volume and bind mounts.

| Command | Description |
|---------|-------------|
| `mounts create <application_id> <mount_type> <host_path> <mount_path>` | Create a new mount. |
| `mounts get <mount_id>` | Get mount details. |
| `mounts list <application_id>` | List all named mounts for an application. |
| `mounts list-by-service <service_id> <mount_type>` | List mounts by service ID and type. |
| `mounts remove <mount_id> [--force]` | Remove a mount (destructive). |
| `mounts update <mount_id> [--host_path] [--mount_path]` | Update a mount configuration. |

### `kctl-dokploy notifications`

Manage notification channels.

| Command | Description |
|---------|-------------|
| `notifications create <name> <provider> [--webhook_url] [--email] [--chat_id] [--bot_token] [--api_key] [--url]` | Create a notification channel (routes to provider-specific API). |
| `notifications get <notification_id>` | Get notification channel details. |
| `notifications list` | List all notification channels. |
| `notifications providers` | List available email providers. |
| `notifications remove <notification_id> [--force]` | Remove a notification channel (destructive). |
| `notifications test <notification_id> <provider>` | Test a notification channel connection. |
| `notifications update <notification_id> <provider> [--name] [--webhook_url] [--enabled]` | Update a notification channel (routes to provider-specific API). |

### `kctl-dokploy patches`

Manage file patches for services.

| Command | Description |
|---------|-------------|
| `patches clean [--compose_id] [--application_id] [--force]` | Clean patch repos (destructive). |
| `patches create [--compose_id] [--application_id] [--name] [--file_path] [--content] [--content_file]` | Create a new patch. |
| `patches delete <patch_id> [--force]` | Delete a patch (destructive). |
| `patches get <patch_id>` | Get patch details. |
| `patches list <entity_id> [--entity_type]` | List all patches for a service. |
| `patches mark-delete <patch_id> <file_path>` | Mark a file for deletion in the patch. |
| `patches read-dirs <patch_id>` | List directories in the patch repo. |
| `patches read-file <patch_id> <file_path>` | Read a file from the patch repo. |
| `patches save-file <patch_id> <file_path> [--content] [--content_file]` | Save a file as a patch. |
| `patches toggle <patch_id>` | Toggle a patch enabled/disabled. |
| `patches update <patch_id> [--name] [--content] [--content_file]` | Update a patch. |

### `kctl-dokploy pipeline`

Deployment pipeline operations.

| Command | Description |
|---------|-------------|
| `pipeline deploy <name> <project> <file> [--env] [--domain] [--port] [--https] [--cert] [--service] [--wait] [--notify] [--dry_run] [--rollback_on_failure]` | Full atomic deployment pipeline. |
| `pipeline history <compose_id> [--limit]` | Show deployment timeline for a compose service. |
| `pipeline rollback <compose_id> [--force]` | Roll back to the previous successful deployment. |
| `pipeline status <compose_id>` | Show current deployment status for a compose service. |
| `pipeline verify <compose_id> [--domain] [--service_hint]` | Quick health verification for a compose service. |

### `kctl-dokploy pl`

Alias: projects list

### `kctl-dokploy ports`

Manage port mappings for applications.

| Command | Description |
|---------|-------------|
| `ports create <application_id> <published> <target> [--protocol] [--mode]` | Create a new port mapping. |
| `ports delete <port_id> [--force]` | Delete a port mapping (destructive). |
| `ports get <port_id>` | Get port mapping details. |
| `ports update <port_id> [--published] [--target] [--protocol] [--mode]` | Update a port mapping. |

### `kctl-dokploy pp`

Alias: pipeline deploy

Usage: `kctl-dokploy pp <name> <project> <file>`

### `kctl-dokploy projects`

Manage Dokploy projects.

| Command | Description |
|---------|-------------|
| `projects create <name> [--description]` | Create a new project. |
| `projects delete <project_id> [--force]` | Delete a project (destructive). |
| `projects environments` | Manage deployment environments (dev/staging/prod). |
| `projects get <name>` | Get project details. |
| `projects list` | List all projects. |
| `projects update <project_id> [--name] [--description]` | Update a project. |

### `kctl-dokploy redirects`

Manage URL redirect rules.

| Command | Description |
|---------|-------------|
| `redirects create <application_id> <regex> <replacement> [--permanent]` | Create a new URL redirect rule. |
| `redirects delete <redirect_id> [--force]` | Delete a redirect rule (destructive). |
| `redirects get <redirect_id>` | Get redirect rule details. |
| `redirects update <redirect_id> [--regex] [--replacement] [--permanent]` | Update a redirect rule. |

### `kctl-dokploy registry`

Manage Docker registries.

| Command | Description |
|---------|-------------|
| `registry create <name> <url> <username> <password> [--registry_type]` | Create a new Docker registry. |
| `registry get <registry_id>` | Get registry details. |
| `registry list` | List all configured Docker registries. |
| `registry remove <registry_id> [--force]` | Remove a Docker registry (destructive). |
| `registry test <registry_id>` | Test connection to a Docker registry. |
| `registry update <registry_id> [--name] [--url] [--username] [--password]` | Update a Docker registry. |

### `kctl-dokploy report`

Deployment reports and analytics.

| Command | Description |
|---------|-------------|
| `report deployments [--period]` | Deployment analytics with temporal filtering. |
| `report domains` | Domain health report across all projects. |
| `report resources` | Resource utilization summary across servers. |
| `report summary` | Overall platform summary across all projects. |

### `kctl-dokploy schedules`

Manage scheduled tasks (cron jobs).

| Command | Description |
|---------|-------------|
| `schedules create <name> <cron> <command> [--schedule_type] [--compose] [--service_name] [--application] [--server_id] [--shell_type] [--timezone]` | Create a new scheduled task on a compose, application, or server. |
| `schedules delete <schedule_id> [--force]` | Delete a scheduled task (destructive). |
| `schedules get <schedule_id>` | Get schedule details. |
| `schedules list <resource_id> [--schedule_type]` | List scheduled tasks for a resource. |
| `schedules run <schedule_id>` | Manually run a scheduled task. |
| `schedules update <schedule_id> [--name] [--cron] [--command] [--enabled]` | Update a scheduled task. |

### `kctl-dokploy security`

Manage HTTP basic auth protection.

| Command | Description |
|---------|-------------|
| `security create <application_id> <username> <password>` | Create a new HTTP basic auth entry. |
| `security delete <security_id> [--force]` | Delete a security entry (destructive). |
| `security get <security_id>` | Get security entry details. |
| `security update <security_id> [--username] [--password]` | Update a security entry. |

### `kctl-dokploy servers`

Manage Dokploy servers.

| Command | Description |
|---------|-------------|
| `servers build-servers` | List servers available for builds. |
| `servers cluster` | Manage Docker Swarm cluster and nodes. |
| `servers count` | Get total server count. |
| `servers create <name> <ip_address> [--ssh_key_id] [--port] [--username]` | Register a new server. |
| `servers deployments <server_id>` | List all deployments on a server. |
| `servers get <server_id>` | Get server details. |
| `servers list` | List all servers. |
| `servers metrics <server_id>` | Get server resource metrics (CPU, memory, disk). |
| `servers monitoring` | Monitoring, metrics, and resource usage. |
| `servers public-ip <server_id>` | Get public IP address of a server. |
| `servers reload` | Reload the Dokploy server configuration. |
| `servers remove <server_id> [--force]` | Remove a server from Dokploy (destructive). |
| `servers security <server_id>` | Get server security information. |
| `servers setup <server_id>` | Run initial setup on a server (install Docker, configure SSH). |
| `servers setup-monitoring <server_id>` | Set up monitoring agent on a server. |
| `servers ssh-keys` | List servers with their SSH key assignments. |
| `servers time <server_id>` | Get current server time. |
| `servers update <server_id> [--name] [--ip_address] [--port] [--username]` | Update a server configuration. |
| `servers validate <server_id>` | Validate server connectivity and configuration. |

### `kctl-dokploy settings`

Manage Dokploy global settings.

| Command | Description |
|---------|-------------|
| `settings create-ssh-key <name> [--public_key] [--public_key_path] [--private_key_path]` | Create/add an SSH key. |
| `settings openapi [--endpoint] [--output_file]` | Fetch the Dokploy OpenAPI spec and list all endpoints. |
| `settings remove-ssh-key <ssh_key_id> [--force]` | Remove an SSH key (destructive). |
| `settings show` | Show platform settings derived from servers. |
| `settings ssh-keys` | List SSH keys configured in Dokploy. |
| `settings update [--letsencrypt_email] [--cleanup_enabled]` | Update global settings. |

### `kctl-dokploy setup`

Setup and pre-flight checks.

| Command | Description |
|---------|-------------|
| `setup check` | Run pre-flight deployment checklist (15+ checks). |
| `setup wizard` | Interactive guided setup for Dokploy CLI. |

### `kctl-dokploy skill`

Claude Code skill management.

| Command | Description |
|---------|-------------|
| `skill generate [--output] [--install] [--check]` | Auto-generate SKILL.md from CLI command registry. |

**Examples:**
```bash
kctl-dokploy skill generate
kctl-dokploy skill generate --install
kctl-dokploy skill generate --check
```

### `kctl-dokploy sl`

Alias: servers list

### `kctl-dokploy status`

Platform status and dashboard.

| Command | Description |
|---------|-------------|
| `status health` | Check Dokploy API health. |

### `kctl-dokploy template`

Service templates — save and apply configurations.

| Command | Description |
|---------|-------------|
| `template apply <name> <project> [--service_name]` | Create a new compose service from a saved template. |
| `template delete <name> [--force]` | Remove a saved template. |
| `template export <name> <output>` | Export a template to a file. |
| `template import-file <file>` | Import a template from an external YAML file. |
| `template list` | List all saved templates. |
| `template save <compose_id> <name> [--description]` | Save a compose service as a reusable template. |
| `template show <name>` | Display template contents. |

### `kctl-dokploy users`

Manage Dokploy users and access.

| Command | Description |
|---------|-------------|
| `users create <email> <password> [--role]` | Create a new user. |
| `users get <user_id>` | Get user details. |
| `users list` | List all users. |
| `users permissions <user_id>` | Show user permissions and project access. |
| `users remove <user_id> [--force]` | Remove a user (destructive). |
| `users update <user_id> [--role] [--email] [--password]` | Update a user. |

### `kctl-dokploy volume-backups`

Manage volume-level backups.

| Command | Description |
|---------|-------------|
| `volume-backups create <name> <cron> <backup_type> <destination_id> [--resource_id]` | Create a new volume backup. |
| `volume-backups delete <backup_id> [--force]` | Delete a volume backup (destructive). |
| `volume-backups get <backup_id>` | Get volume backup details. |
| `volume-backups list <resource_id> <backup_type>` | List volume backups for a resource. |
| `volume-backups run <backup_id>` | Manually trigger a volume backup. |
| `volume-backups update <backup_id> [--name] [--cron] [--enabled]` | Update a volume backup. |

## Configuration

Shared config: `~/.config/kodemeio/config.yaml`

```bash
kctl-dokploy config init       # Interactive setup
kctl-dokploy config show       # Show current config
kctl-dokploy config profiles   # List profiles
kctl-dokploy config current    # Show active profile
kctl-dokploy config validate   # Verify config
```
