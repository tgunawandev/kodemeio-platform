# Terraform modules

These modules are owned by `kodemeio-dokploy` because they provision the
infrastructure on which the Dokploy fleet runs.

They were copied from `tgunawandev/kodemeio-cli` commit
`7528f3e7dc8a22a08cbadd36e1d7f0ac0c0cecc1` during the repository
consolidation on 2026-08-25:

- `packages/kctl-cf/terraform` → `infra/modules/cloudflare`
- `packages/kctl-hz/infra/hetzner` → `infra/modules/hetzner`

Future Terraform changes belong here. Python CLI implementation remains in
`kodemeio-cli`.
