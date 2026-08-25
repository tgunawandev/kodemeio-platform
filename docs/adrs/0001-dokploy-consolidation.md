# ADR 0001: Consolidate platform operations under kodemeio-dokploy

- Status: Accepted
- Date: 2026-08-25

## Context

`kodemeio-platform` had become the active source of truth for declarative
Dokploy deployments, infrastructure, monitoring, and runbooks. The repository
named `kodemeio-dokploy` contained an older Bash toolkit whose Python successor
had already moved first into the Platform monorepo and then into
`kodemeio-cli`.

Keeping both names made ownership unclear. The Platform repository also
retained obsolete references to deleted `packages/*` paths.

## Decision

1. Archive the original shell repository as
   `tgunawandev/kodemeio-dokploy-legacy`.
2. Rename `tgunawandev/kodemeio-platform` to
   `tgunawandev/kodemeio-dokploy`.
3. Preserve the active repository's full Git history.
4. Keep CLI implementation in `kodemeio-cli`.
5. Keep deployment manifests, Terraform, monitoring, and operations here.
6. Preserve a pointer to the legacy toolkit rather than copying its code.

## Migration record

- Active pre-consolidation tag: `pre-consolidation-20260825`
- Legacy final tag: `legacy-final-20260825`
- Legacy final commit: `626bffc1a4b9926d1909b9ad401ca1668d9204ce`
- Terraform module source: `kodemeio-cli` commit
  `7528f3e7dc8a22a08cbadd36e1d7f0ac0c0cecc1`

## Consequences

- The repository name now matches its primary operational platform.
- Existing Platform history and GitHub issues remain with the active project.
- The archived shell toolkit remains recoverable but receives no development.
- CLI release cadence is independent from deployment desired state.
- Terraform modules are no longer referenced through deleted local packages.
