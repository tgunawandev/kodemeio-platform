## Summary

-

## Area

- [ ] Deployment manifest or base
- [ ] Tenant or environment contract
- [ ] Dokploy/Traefik bootstrap
- [ ] Infrastructure
- [ ] Monitoring or runbook
- [ ] Repository tooling/documentation

## Deployment impact

- Target environment:
- Manifest(s):
- Dokploy profile:
- Rollback:

## Checklist

- [ ] `just check` passes
- [ ] Changed manifests pass `kctl-dokploy -p <profile> deploy validate`
- [ ] Live-facing changes were previewed with `--dry-run`
- [ ] No real environment files, credentials, or Terraform state are committed
- [ ] HTTP services use `dokploy-network` and Traefik routing
- [ ] Production rollback steps are documented

## Test plan

-
