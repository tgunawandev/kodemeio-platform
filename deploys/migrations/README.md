# Migration manifests

Store reviewed server and application migration manifests here.

Before applying a migration:

1. select explicit Dokploy, PostgreSQL, Cloudflare, and Hetzner profiles;
2. validate and plan the migration;
3. capture current backups and health checks;
4. document rollback and soak-period cleanup.

Do not commit database dumps, credentials, or generated environment files.
