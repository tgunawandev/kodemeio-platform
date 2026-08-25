# React PWA + Odoo Deployment Checklist

## Before Deploy

### Odoo Instance
- [ ] Profile selected (distribution, hrms, trading, etc.)
- [ ] `.env` file populated (PGHOST, PGPASSWORD, ODOO_ADMIN_PASSWD, etc.)
- [ ] Database name follows convention: `odoo_{profile}_{customer}`

### React PWA
- [ ] `.env` file populated with ALL VITE vars (NOT blank)
- [ ] `VITE_{APP}_API_BASE_URL` includes FastAPI root path (e.g., `/wms/api`)
- [ ] `VITE_AUTH_MODE` set explicitly (`native` or `oidc`)
- [ ] `openapi.json` committed in git for the app (`git add -f apps/spa/{app}/openapi.json`)
- [ ] Docker build tested locally: `NODE_OPTIONS='--experimental-strip-types' pnpm turbo build --filter=@kodemeio/{app}`

### Deploy Manifest
- [ ] `compose_path` points to correct compose file
- [ ] `domain.service` matches service name in docker-compose.yml
- [ ] `env_overrides` API URL includes `/{app}/api` path

## Deploy

```bash
# 1. Dry-run first
kctl-dokploy -p <profile> deploy apply -f deploys/instances/{manifest}.yaml --dry-run

# 2. Deploy Odoo first (takes 5-10 min for init)
kctl-dokploy -p <profile> deploy apply -f deploys/instances/{customer}-odoo-{profile}.yaml

# 3. Deploy React apps (after Odoo is healthy)
kctl-dokploy -p <profile> deploy apply -f deploys/instances/{customer}-react-{app}.yaml

# 4. If env vars changed, prune Docker cache and redeploy
ssh root@{server} docker builder prune -f
kctl-dokploy -p <profile> compose redeploy {compose-id}
```

## After Deploy

### Auto-verified (by base_management post_init_hook)
- [x] JWT secrets generated for all apps
- [x] CORS origins set to `*` on all app records

### Manual verification
- [ ] Odoo web login works: `https://{odoo-host}/web/login`
- [ ] React app loads: `https://{app-host}/`
- [ ] React app login works (admin/admin or configured credentials)
- [ ] Enable Cloudflare proxy after Let's Encrypt cert is issued
