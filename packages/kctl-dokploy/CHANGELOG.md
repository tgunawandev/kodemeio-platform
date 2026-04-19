# Changelog

All notable changes to kctl-dokploy.

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
