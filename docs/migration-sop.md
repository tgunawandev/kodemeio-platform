# Migration SOP

Migration manifests live in `deploys/migrations/`. Use the current
`kctl-dokploy` migration pipeline with explicit service profiles.

## Before the window

- Confirm source and target access.
- Confirm current database and volume backups.
- Reduce DNS TTL where appropriate.
- Inventory affected services, databases, domains, and schedules.
- Define validation checks, rollback, and the post-cutover soak period.
- Notify affected users.

## Validate and plan

```bash
kctl-dokploy -p <dokploy-profile> deploy migrate validate \
  -f deploys/migrations/<migration>.yaml

kctl-dokploy -p <dokploy-profile> deploy migrate plan \
  -f deploys/migrations/<migration>.yaml
```

Review every database, service, DNS record, server, and dependent profile in
the plan. A plan is not approval to execute.

## Execute

Run during the approved maintenance window:

```bash
kctl-dokploy -p <dokploy-profile> deploy migrate apply \
  -f deploys/migrations/<migration>.yaml
```

If execution fails after saving state, fix the cause and resume:

```bash
kctl-dokploy -p <dokploy-profile> deploy migrate apply \
  -f deploys/migrations/<migration>.yaml --resume
```

## Verify

- Confirm deployment completion and health.
- Compare pre/post database validation evidence.
- Test public domains, authentication, background jobs, and backups.
- Keep the source available throughout the declared soak period.

## Roll back

```bash
kctl-dokploy -p <dokploy-profile> deploy migrate rollback \
  -f deploys/migrations/<migration>.yaml
```

Verify DNS and application health after rollback.

## Cleanup

Only after the soak period and explicit approval:

```bash
kctl-dokploy -p <dokploy-profile> deploy migrate cleanup \
  -f deploys/migrations/<migration>.yaml
```

Cleanup can remove temporary dumps and finalize migration state. Never combine
cutover and cleanup into the same approval.
