# Operator onboarding

## 1. Clone and install

```bash
git clone https://github.com/tgunawandev/kodemeio-dokploy.git
cd kodemeio-dokploy
uv sync
uv tool install "kctl-dokploy==0.16.6"
```

Install Terraform 1.5+ and `just` if you will change infrastructure or run the
repository task runner.

## 2. Configure profiles

Create profile data through the `kctl` configuration tools and 1Password.
Every command must specify a profile explicitly:

```bash
kctl-dokploy -p <profile> config show
kctl-dokploy -p <profile> doctor ai-summary
```

Do not place API keys in this repository or shell history.

## 3. Restore local environment files

Real values live under:

```text
deploys/env/local/
deploys/env/staging/
deploys/env/production/
```

Each real file must have a sanitized `.example` counterpart. Real files are
ignored by Git and must be restored from the approved 1Password workflow.

## 4. Validate the checkout

```bash
just test
just lint
just fmt-check
terraform -chdir=infra init -backend=false
terraform -chdir=infra validate
```

## 5. Preview a deployment

```bash
kctl-dokploy -p <profile> deploy validate -f <manifest>
kctl-dokploy -p <profile> deploy apply -f <manifest> --dry-run
```

Review DNS, database, compose, environment, domain, backup, and schedule
changes before requesting production approval.

## 6. Operational safety

- Do not stop or delete `dokploy` or `traefik`.
- Standard HTTP services use `dokploy-network` and Traefik.
- Wait for deployment verification; queue submission is not completion.
- Follow `ops/runbooks/` for incidents, backups, and migrations.
