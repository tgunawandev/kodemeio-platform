# Changelog

All notable changes to kctl-dokploy.

## [0.4.3] — 2026-04-19

### Added
- `backups pull` / `run-wait` / `download` log lines now carry an `[HH:MM:SS]`
  wall-clock prefix. Operators can see elapsed time between phases (trigger →
  S3 poll → download → decompress → drop-recreate → pg_restore) at a glance.
  Implemented via a local `_TimestampedLog` wrapper that delegates to the
  shared `OutputManager` — no cross-CLI behavior change.

## [0.4.2] — 2026-04-19

### Fixed
- `backups pull` (and `backups run-wait`) now discover backups under the
  NEW hierarchical S3 layout used by current Dokploy versions. Previous
  Dokploy releases wrote objects under a flat
  `<backup.prefix>-<timestamp>.<ext>` layout; recent Dokploy versions now
  write them under `<compose.appName>_<serviceName>/<backup.prefix>/<timestamp>.<ext>`
  (falling back to `<compose.appName>/<backup.prefix>/<timestamp>.<ext>`
  when no `serviceName` is set on the backup config). The pull helper was
  only scanning `<backup.prefix>` and therefore picked stale files (or
  timed out waiting for a fresh trigger) on upgraded instances. The
  helper now scans all candidate prefixes and returns the globally-newest
  object. Non-compose backup types (postgres/mysql/mariadb/mongo) retain
  the single-prefix behavior. Matches are filtered by DB name as
  defense-in-depth.

## [0.4.1] — 2026-04-19

### Added
- `backups pull <backup_id> --target-db ...` — one-command end-to-end flow:
  trigger (optional) → wait → download → decompress → drop+recreate target
  DB → pg_restore. Supports both Dokploy-managed target composes
  (`--target-compose`) and raw postgres hosts (`--target-host` for local
  dev). Auto-detects custom vs plain SQL format via PGDMP magic bytes.
- `backups run-wait <backup_id>` — trigger a manual backup and poll S3
  until the new object appears. Prints the resulting S3 key.
- `backups download <s3_key> --destination <id>` — standalone S3 download
  using a Dokploy destination's stored credentials.

### Fixed
- `backups list-files` now talks to S3 directly via boto3, bypassing
  Dokploy's buggy `/backup.listBackupFiles` endpoint. No longer errors
  with "Input validation failed" when called without `--search`; lists
  everything under the destination by default. Added `--prefix` for
  S3-side filtering and `--limit` (default 200). Removed the `--server`
  flag which was not actually needed for direct S3 access.
- `dokploy-admin` SKILL.extra.md runbook now matches the actual CLI
  surface — previously documented 5 commands (`dump-compose`, `download`,
  `run-wait`, `refresh`, `restore-local`) that had been removed in the
  Dokploy-native redesign. `download` / `run-wait` / `pull` (formerly
  `refresh`) are now re-introduced as thin boto3 helpers.

### Notes
- SSH-based commands (`dump-compose`, `restore-local`, `refresh`) remain
  deleted — the Dokploy-native SSE restore (`backups restore`) is the
  right tool for Dokploy-managed targets. `backups pull` fills the gap
  for dev loops targeting a raw postgres on the developer's workstation.
