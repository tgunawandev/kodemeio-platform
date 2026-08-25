# kctl-* Marketing Wave 1 — Design Spec

**Date:** 2026-04-19
**Status:** Draft — awaiting user review
**Scope:** Foundation of the digital marketing / digital ads ecosystem for the four Kodemeio SaaS products (BAS, HRM, TPM, TMS)
**Approach:** Measurement-first wave. Build three thin per-service CLIs (`kctl-plausible`, `kctl-gsc`, `kctl-shlink`), deploy two self-hosted services (Plausible CE, Shlink), establish a durable goal/UTM/slug taxonomy that anchors later waves.

## 1. Context and motivation

Kodemeio sells four SaaS products, each with a distinct audience and channel profile:

| Product | Go-to-market site | Audience | Primary channels |
|---|---|---|---|
| **BAS** (Business Automation System — Odoo CE + OCA + Reports) | `bas.kodeme.io` | SMB ops / CFOs / IT | Google Search, SEO, content |
| **HRM** (Human Resource Management, standalone) | `hrm.kodeme.io` | IDN HR managers, SMB owners | Google Search, LinkedIn |
| **TPM** (Trade Promotion Management) | `provetics.com` (dedicated brand) | FMCG brand / category / trade-marketing managers | LinkedIn, sales outbound |
| **TMS** (Therapy Management System — ASD/ADHD clinics) | `terakidz.com` (dedicated brand) | Clinic directors; parents via companion app | Meta (FB/IG) parent communities, Google Search |

Plus two non-product growth surfaces:

- `kodemeio.com` — agency site (Tri Gunawan's custom-dev / Odoo implementation leads)
- `careers.kodemeio.com` — recruiting

All four product audiences differ enough that one dashboard, one tool, or one ad platform cannot serve them. But they share the same three primitives: **what happened on the site**, **what Google sees of the site**, and **what short-links drove the visit**.

Wave 1 locks down those three primitives. Wave 2 (paid ads — `kctl-gads`, `kctl-meta-ads`, `kctl-linkedin-ads`) and Wave 3 (cross-channel orchestrator — `kctl-growth` with closed-loop offline-conversion upload from Odoo sale_order) depend on the taxonomy and instrumentation laid down here.

Not in Wave 1: ad-platform CLIs, email/SMS CLIs, content-scheduling CLIs, PostHog-scale experimentation, GA4.

## 2. Out of scope (explicit)

- **GA4** — deferred indefinitely. Smart-bidding integration can go direct from `kctl-gads` (Wave 2) to Google Ads API via offline conversions from Odoo (Wave 3). No GA4 Measurement Protocol middleman.
- **PostHog** — reconsider in Wave 6+ if experimentation / feature flags become core. B2B volumes too low today to justify ClickHouse + Kafka for analytics.
- **Meta Ads / Google Ads / LinkedIn Ads management** — Wave 2.
- **Offline conversion upload, audience sync, campaign manifest orchestration** — Wave 3.
- **Tenant brand sites** (`mandiriagro.com`, `pakerti.com`, `trigunawan.com`) — customer-owned. Not Kodemeio growth surfaces.

## 3. Architecture

### 3.1 Components

Three new CLIs inside `kodemeio-platform/packages/`:

| CLI | API | Purpose |
|---|---|---|
| `kctl-plausible` | Plausible CE Stats + Sites Provisioning API | Site + goal + funnel + shared-link CRUD; stats query; curated per-product reports |
| `kctl-gsc` | Google Search Console API v1 + URL Inspection API | Property browsing; per-product keyword-cluster reports; bulk indexing audit |
| `kctl-shlink` | Shlink REST API v3 | Short URL CRUD; campaign-manifest apply; QR generation; Shlink×Plausible cross-join reports |

Two new self-hosted services deployed via Dokploy on `kod-prod-01` (Hetzner `kodemeio` account):

| Service | Domain | Stack | Datastores |
|---|---|---|---|
| Plausible CE | `plausible.kodeme.io` | Elixir app + ClickHouse | ClickHouse (events, new) + shared Postgres (config) |
| Shlink | `s.kodeme.io` | PHP app | Shared Postgres (URLs + visits) |

One day-one dev task outside of kctl-* scope:

- **Meta Pixel + Google Tag JS snippets** installed in the Next.js / React PWA apps for all 6 tracked properties. Not a CLI. Unblocks Wave 2 Meta Ads launch by building warm audiences starting day 1. Verified by `kctl-plausible doctor`.

### 3.2 Repository layout

New repos (following existing `kodemeio-<service>` convention):

```
kodemeio-plausible/                    (new repo)
├── compose/plausible.prod.yml
├── clickhouse/
│   ├── config.xml
│   └── users.xml
├── scripts/backup-clickhouse.sh
├── README.md
└── CHANGELOG.md

kodemeio-shlink/                       (new repo)
├── compose/shlink.prod.yml
├── README.md
└── CHANGELOG.md
```

No `kodemeio-gsc` repo — GSC is external SaaS.

Additions to `kodemeio-platform/` (this repo):

```
packages/
├── kctl-plausible/                    (new — CLI)
├── kctl-gsc/                          (new — CLI)
└── kctl-shlink/                       (new — CLI)

deploys/
├── bases/
│   ├── plausible.yaml                 (new — base template → kodemeio-plausible)
│   └── shlink.yaml                    (new — base template → kodemeio-shlink)
├── instances/production/
│   ├── kod-infra-plausible.yaml       (new — production instance)
│   └── kod-infra-shlink.yaml          (new — production instance)
├── env/production/
│   ├── .env.kod-infra-plausible       (new — gitignored)
│   └── .env.kod-infra-shlink          (new — gitignored)
└── marketing/                         (new directory)
    ├── plausible-bootstrap.yaml       (declarative site/goal setup)
    ├── gsc-keyword-clusters.yaml      (per-product cluster definitions)
    └── shlink-campaigns/              (per-campaign manifests)

docs/marketing/
└── taxonomy.md                        (new — canonical goal/UTM/slug reference)
```

### 3.3 Data flow

```
Marketing site (Next.js / React PWA)
    │ Plausible snippet + Meta Pixel + Google Tag
    ▼
Plausible (events) ──┐
Google Search Console ├── read by CLIs
Shlink (clicks) ─────┘
```

Three CLIs are independent; only `kctl-shlink reports campaign` soft-depends on `kctl-plausible` (for the click × goal cross-join).

### 3.4 Profile model

All profiles follow the platform's 4-segment rule: `platform-tenant-stack-app`.

```yaml
profiles:
  kodemeio-kod-infra-plausible:
    plausible:
      url: https://plausible.kodeme.io
      api_key: ${PLAUSIBLE_API_KEY}
      default_site: bas.kodeme.io

  kodemeio-kod-infra-shlink:
    shlink:
      url: https://s.kodeme.io
      api_key: ${SHLINK_API_KEY}
      default_domain: s.kodeme.io

  kodemeio-kod-infra-gsc:
    gsc:
      credentials_file: ~/.config/kodemeio/gsc-sa.json
      default_property: sc-domain:kodeme.io
```

Profile names follow the platform 4-segment rule `<platform>-<tenant>-<stack>-<app>`. Tenant code `kod` aligns with the existing Kodemeio Dokploy project. GSC uses `stack=infra` by convention even though the service is external SaaS — keeps administrative profiles grouped consistently.

GSC uses a **Google Cloud service account**, not OAuth. The service-account email is added as a user on each Search Console property (Full for submit operations, Restricted for read-only).

## 4. CLI designs

### 4.1 `kctl-plausible`

Standard kctl-* groups: `config`, `doctor`, `self-update`, `completions`, `skill`.

Domain groups:

| Group | Commands |
|---|---|
| `sites` | `list`, `show`, `create`, `update`, `delete`, `bootstrap` (declarative apply) |
| `goals` | `list`, `show`, `create`, `delete` (regex-validated names) |
| `funnels` | `list`, `show`, `create`, `delete` |
| `stats` | `aggregate`, `timeseries`, `breakdown`, `realtime` |
| `shared-links` | `list`, `create`, `delete` |
| `guests` | `list`, `invite`, `remove` |
| `reports` | `overview`, `product <bas\|hrm\|tpm\|tms>`, `funnel`, `acquisition` |
| `export` | `csv`, `json` |

~35 commands total.

**`sites bootstrap`** applies a declarative YAML (`deploys/marketing/plausible-bootstrap.yaml`) that creates all 6 sites, per-product goals, and shared links in one idempotent pass. Supports `--dry-run`.

**`reports product <name>`** is the daily-use entry point. Executes several `stats` + `funnels` calls internally and renders a single Rich panel with the canonical per-product funnel (pricing_view → lead → trial → paid) plus UTM source breakdown and WoW delta. This is where the CLI earns its keep over the Plausible web UI.

**`doctor`** additionally verifies the Meta Pixel + Google Tag snippets on each tracked URL via HEAD/GET, reporting per-site pass/fail.

### 4.2 `kctl-gsc`

Standard kctl-* groups: `config`, `doctor`, `self-update`, `completions`, `skill`.

Domain groups:

| Group | Commands |
|---|---|
| `properties` | `list`, `show`, `verify` |
| `queries` | `top`, `search`, `trends` |
| `pages` | `top`, `impressions`, `orphans` |
| `sitemaps` | `list`, `submit`, `status`, `delete` |
| `inspect` | `url`, `bulk`, `request-index` |
| `reports` | `overview`, `product <bas\|hrm\|tpm\|tms>`, `opportunities`, `drift` |
| `export` | `csv`, `json` |

~25 commands total.

Properties use **domain-property form** (`sc-domain:kodeme.io`) for all `*.kodeme.io` subdomains, and **URL-prefix form** for external brand domains (`https://provetics.com/`, `https://terakidz.com/`, `https://kodemeio.com/`).

**Keyword clusters** are the CLI's opinionated abstraction over raw SEO noise. Defined in `deploys/marketing/gsc-keyword-clusters.yaml` — per-product pattern lists that group thousands of long-tail queries into a few meaningful buckets.

**`reports drift`** flags queries that lost ≥3 rank positions WoW — SEO regression alert, no equivalent in the GSC web UI.

**`inspect bulk`** exploits the URL Inspection API's 2000/day per-property quota to audit indexing across entire site maps.

### 4.3 `kctl-shlink`

Standard kctl-* groups: `config`, `doctor`, `self-update`, `completions`, `skill`.

Domain groups:

| Group | Commands |
|---|---|
| `domains` | `list`, `add`, `remove`, `set-default` |
| `urls` | `list`, `create`, `show`, `update`, `delete` |
| `tags` | `list`, `create`, `rename`, `delete`, `stats` |
| `visits` | `list`, `stats`, `realtime`, `by-tag`, `by-url`, `orphans` |
| `qr` | `generate`, `bulk` |
| `campaigns` | `apply`, `diff`, `destroy`, `list` |
| `reports` | `campaign`, `channel`, `product`, `compare` |
| `redirects` | `list`, `set`, `clear` |
| `export` | `csv`, `json` |

~30 commands total.

Single short domain `s.kodeme.io` for all products. Per-product differentiation comes from tags and slug convention.

**`campaigns apply`** is the flagship — declarative YAML manifest per campaign (parallel to `deploys/instances/*.yaml`) that creates all short URLs + QR codes in one idempotent pass. This is the shape Wave 3's `kctl-growth` will extend to multi-channel.

**`reports campaign`** is the only Wave 1 cross-channel surface: correlates Shlink click data with Plausible goal hits via matching `utm_campaign` + `utm_content`. Calls `kctl-plausible`'s client library when that profile is available (soft-dependency).

**`qr generate`** produces print-ready QR codes (PNG/SVG with web/print/billboard margin presets, optional logo overlay). The Indonesian B2B market leans heavily on printed collateral and exhibition booths.

## 5. Deploy manifests

### 5.1 Base: `deploys/bases/plausible.yaml`

- Image: `ghcr.io/plausible/community-edition:v2.1.5`
- ClickHouse: `clickhouse/clickhouse-server:24.12-alpine`
- Registration disabled post-bootstrap (`DISABLE_REGISTRATION=true`)
- SMTP via `mail.kodeme.io` (Mailcow)
- Resource limits: Plausible 1 CPU / 1 GB, ClickHouse 1 CPU / 2 GB
- Traefik: `Host(plausible.kodeme.io)`, Let's Encrypt resolver
- Healthcheck: `wget http://localhost:8000/api/health`
- Config (DATABASE_URL): shared Postgres at `10.0.0.2:5432`, database `plausible` owned by user `plausible`
- Events (CLICKHOUSE_DATABASE_URL): `http://clickhouse:8123/plausible_events`
- ClickHouse volume: `clickhouse-data` persistent

### 5.2 Base: `deploys/bases/shlink.yaml`

- Image: `shlinkio/shlink:4.4`
- Resource limits: 0.5 CPU / 512 MB
- Traefik: `Host(s.kodeme.io)`, Let's Encrypt resolver
- Healthcheck: `curl http://localhost:8080/rest/health`
- Database: shared Postgres at `10.0.0.2:5432`, database `shlink` owned by user `shlink`
- MaxMind GeoLite2 license key wired for IP→country resolution

### 5.3 Production instances

```
deploys/instances/production/kod-infra-plausible.yaml
  server: kod-prod-01
  project: kod
  dokploy_env: production
  domain: plausible.kodeme.io
  dns: { zone: kodeme.io, record: plausible, proxied: false }
  database_host: <kodemeio shared postgres private IP>

deploys/instances/production/kod-infra-shlink.yaml
  server: kod-prod-01
  project: kod
  dokploy_env: production
  domain: s.kodeme.io
  dns: { zone: kodeme.io, record: s, proxied: true }
  database_host: <kodemeio shared postgres private IP>
```

The shared Postgres private-IP endpoint on the kodemeio Hetzner account is resolved during implementation by inspecting current infra state (`kctl-hz servers` + `kctl-pg` lookup). Per the cross-compose infra rule, cross-service references always use private IPs, never container names.

Cloudflare proxy is off for Plausible (future LiveView / WebSocket features) and on for Shlink (caching benefit for redirect hot-paths is real).

### 5.4 Secrets

Stored in 1Password vault `kodemeio-production/` under entries `plausible` and `shlink`. Pulled during provisioning via `kctl-op`. `.env.kod-infra-*` files are gitignored.

### 5.5 ClickHouse backup

Dokploy's native backup covers only Postgres. A cron schedule in the Plausible manifest dumps ClickHouse `plausible_events` to the existing Hetzner Object Storage bucket at 03:00 daily. Retention matches existing Postgres backup retention (14 days rolling).

### 5.6 Resource budget impact on `kod-prod-01`

Adds ~3.5 GB memory, up to 2.5 CPU under load. Verified comfortable on `kod-prod-01` current specs during implementation (confirm via `kctl-hz servers show kod-prod-01` before deploy).

## 6. Goal + UTM + Slug taxonomy

The durable load-bearing asset of Wave 1. Committed to `docs/marketing/taxonomy.md` as the human-readable reference and enforced by the three CLIs.

### 6.1 Plausible goal names

Format: `<product>.<stage>.<event>`

- **Products:** `bas`, `hrm`, `tpm`, `tms`, `agency`, `careers`
- **Stages:** `interest`, `lead`, `trial`, `paid`, `expansion`, `apply` (careers only)

Standard per-product funnel:

```
{product}.interest.pricing_view         (pageview: /pricing)
{product}.interest.feature_view         (event: ≥75% scroll on /features/*)
{product}.lead.demo_request             (event: form submit)
{product}.lead.contact_sales            (event: form submit)
{product}.trial.start                   (event: Xendit webhook → Plausible events API)
{product}.trial.activate                (event: first authenticated session)
{product}.paid.conversion               (event: Xendit webhook)
{product}.paid.expansion                (event: plan upgrade)         — later
```

Non-product surfaces:

```
agency.lead.contact_submit
agency.lead.case_study_view
agency.lead.quote_request

careers.apply.job_view
careers.apply.submit
```

Enforcement regex in `kctl-plausible goals create`:

```
^(bas|hrm|tpm|tms|agency|careers)\.(interest|lead|trial|paid|expansion|apply)\.[a-z][a-z0-9_]+$
```

### 6.2 UTM parameters

| Param | Rule | Examples |
|---|---|---|
| `utm_source` | lowercase, snake_case, channel origin | `google`, `meta`, `linkedin`, `tiktok`, `email`, `whatsapp`, `telegram`, `event`, `referral`, `direct_sales` |
| `utm_medium` | lowercase, channel type | `cpc`, `paid_social`, `display`, `email`, `messaging`, `organic`, `offline`, `referral`, `sales_outreach` |
| `utm_campaign` | `{yyyy}_{qn}_{product}_{theme}` | `2026_q2_tpm_fmcg_outreach`, `2026_q2_tms_parent_awareness` |
| `utm_content` | `{format}_{variant}` | `ad_a`, `ad_b`, `email_may`, `qr_booth`, `video_15s` |
| `utm_term` | keyword, lowercase, accent-stripped | `software_erp`, `aplikasi_payroll` |

Enforcement regex on `utm_campaign`:

```
^(20\d{2})_q[1-4]_(bas|hrm|tpm|tms|agency|careers|cross)_[a-z0-9_]+$
```

The `cross` pseudo-product is for multi-product brand campaigns.

### 6.3 Shlink slug format

Format: `{product}-{channel}-{campaign_tag}[-{variant}]` — kebab-case.

Enforcement regex:

```
^(bas|hrm|tpm|tms|agency|careers|cross)-[a-z]+-[a-z0-9]+(-[a-z0-9]+)?$
```

### 6.4 Environment flavor

Staging prefixes on campaign IDs keep data distinguishable:

| | Prod | Staging |
|---|---|---|
| `utm_campaign` | `2026_q2_tpm_fmcg_outreach` | `stg_2026_q2_tpm_fmcg_outreach` |
| Shlink slug | `tpm-linkedin-q2a` | `stg-tpm-linkedin-q2a` |

No separate Plausible or Shlink instances for staging; prefix-based filtering is enough.

### 6.5 Cross-CLI alignment example

```
Campaign: 2026 Q2 TPM FMCG outreach on LinkedIn (A/B creative)

Shlink manifest → slugs: tpm-linkedin-q2a, tpm-linkedin-q2b
                         utm_campaign=2026_q2_tpm_fmcg_outreach
                         utm_content=ad_a | ad_b

Plausible site: provetics.com
  Goals firing: tpm.interest.pricing_view
                tpm.lead.demo_request
                tpm.trial.start        (via Xendit webhook)
                tpm.paid.conversion    (via Xendit webhook)

Wave 3 offline-conversion join key:
  (utm_campaign, utm_content) matched to
    - LinkedIn click ID captured at landing (Wave 3 adds this)
    - Odoo crm_lead.utm → sale_order → paid
    - Uploaded to LinkedIn Conversions API
```

### 6.6 Enforcement layers

1. `kctl-shlink campaigns apply` validates slug + UTM regex; refuses apply on violation.
2. `kctl-plausible goals create` validates goal regex.
3. `kctl-growth lint` (Wave 3) validates cross-CLI consistency (every Shlink slug has a reachable goal, etc.).

## 7. Standards compliance

All three CLIs meet the platform's Quality Baseline (per `CLAUDE.md`):

- Standard global options (`--json`, `--quiet`, `--format`, `--no-header`, `--profile`, `--version`)
- Standard `config` subcommands (init, add, use, show, validate, remove, set, profiles, current)
- Standard common commands (`doctor`, `self-update`, `completions`, `skill generate`)
- README.md ≥ 60 lines
- SKILL.md in `skills/<name>-admin/`
- conftest.py with standard fixtures
- Lint + format + pytest + mypy pass
- Coverage ≥ 0.3 tests per command
- Score ≥ 9/10 per `scripts/audit-platform.py`

Shared kctl-lib modules used: `APIClient` (plausible, shlink), Google client libs layered over `APIClient` patterns (gsc), `Output`, `config` / profiles, `callbacks` (`AppContext(AppContextBase)`), `history`, `completions`, `self_update`, `doctor_base`.

## 8. Testing strategy

Unit tests (pytest + `kctl-lib.testing.mock_app_context`):

- Command parsing, flag validation
- Regex validators for goal / UTM / slug formats
- Declarative-manifest idempotency (same apply twice → no changes)
- API client request shape (mock server responses, verify request body / params)

Integration tests (optional, gated on live profile):

- `kctl-plausible doctor` against a real test Plausible instance
- `kctl-gsc queries top` against a test GSC property
- `kctl-shlink campaigns apply --dry-run` against a test Shlink

E2E tests: not needed for Wave 1 (no UI layer). Revisit in Wave 3 for `kctl-growth`.

## 9. Success criteria

Wave 1 is done when:

1. All three CLIs installable via `uv tool install`, pass audit-platform.py at ≥ 9/10.
2. Plausible and Shlink deployed to `kod-prod-01`, healthcheck green.
3. `kctl-plausible sites bootstrap` creates all 6 sites + goals + shared links.
4. `kctl-gsc reports product tms` returns non-empty data for `terakidz.com`.
5. `kctl-shlink campaigns apply` produces working short URLs with correct UTMs.
6. `kctl-shlink reports campaign <name>` correlates clicks with Plausible goal hits.
7. Meta Pixel + Google Tag confirmed firing on all 6 tracked properties (via `kctl-plausible doctor`).
8. `docs/marketing/taxonomy.md` committed; marketing team has a reference.

## 10. Risks and mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Plausible ClickHouse schema migration on upgrade | Medium | Medium | Pin image tag; test upgrades in staging first |
| GSC API rate limits hit mid-report | Low | Low | URL Inspection quota check in `doctor`; built-in backoff in `kctl-lib.api_client` |
| Shlink × Plausible cross-join fragile if UTMs drift | Medium | High | Regex enforcement at CLI layer; `kctl-growth lint` in Wave 3 |
| Meta Pixel / Google Tag install regresses silently | Medium | High | `kctl-plausible doctor` verification check |
| Cookie banner regulation change (IDN UU PDP) | Low | Low | Plausible is cookie-free by design |
| Taxonomy design mistakes lock us in | Medium | High | Committed to text file, not a database schema — cheap to refactor |

## 11. Dependencies and sequencing for implementation

Rough ordering for the implementation plan (produced by the `writing-plans` skill):

1. Create `kodemeio-plausible` repo — compose + ClickHouse configs + backup scripts.
2. Create `kodemeio-shlink` repo — compose.
3. Scaffold `packages/kctl-plausible/` with copier template; wire `APIClient`, auth, profile.
4. Scaffold `packages/kctl-gsc/` with copier template; set up service-account auth.
5. Scaffold `packages/kctl-shlink/` with copier template; wire API client.
6. Write `deploys/bases/plausible.yaml` + `shlink.yaml`.
7. Write `deploys/instances/production/kod-infra-plausible.yaml` + `kod-infra-shlink.yaml`.
8. Provision Postgres `plausible` + `shlink` databases on shared Postgres (via `kctl-pg`).
9. Secrets into 1Password, `.env` files into `deploys/env/production/`.
10. Deploy Plausible + Shlink to kod-prod-01.
11. Implement each CLI's command groups bottom-up (API client → low-level CRUD → curated reports).
12. Install Meta Pixel + Google Tag snippets in Next.js / React PWA apps.
13. Write `deploys/marketing/plausible-bootstrap.yaml`, `gsc-keyword-clusters.yaml`, one example `shlink-campaigns/*.yaml`.
14. Write `docs/marketing/taxonomy.md`.
15. Run `kctl-plausible sites bootstrap` and `kctl-plausible doctor`; verify all success criteria.

## 12. References

- Existing kctl-* conventions: `packages/kctl-zulip/` (most recent scaffolded CLI)
- Deploy manifest pattern: `deploys/instances/production/kod-infra-grafana.yaml`
- Profile standardization: `docs/superpowers/specs/2026-04-19-kctl-profiles-standardization-design.md`
- Plausible CE docs: `plausible.io/docs/self-hosting`
- Shlink REST API v3: `shlink.io/documentation/api-docs`
- Google Search Console API: `developers.google.com/webmaster-tools/v1/api_reference_index`

---

## Appendix A — Full goal taxonomy

```
# Products (×4)
bas, hrm, tpm, tms

# Non-product surfaces
agency       — kodemeio.com
careers      — careers.kodemeio.com
cross        — UTM-only pseudo-product for multi-product brand campaigns

# Stages
interest     — top of funnel, content engagement
lead         — hand-raise, demo / contact form
trial        — product used
paid         — Xendit payment captured
expansion    — upsell (Wave 2+)
apply        — careers only
```

## Appendix B — Minimum per-product goals to create at Wave 1 launch

```
bas.interest.pricing_view        bas.lead.demo_request       bas.lead.contact_sales
bas.trial.start                  bas.trial.activate          bas.paid.conversion

hrm.interest.pricing_view        hrm.lead.demo_request       hrm.lead.contact_sales
hrm.trial.start                  hrm.trial.activate          hrm.paid.conversion

tpm.interest.pricing_view        tpm.lead.demo_request       tpm.lead.contact_sales
tpm.trial.start                  tpm.trial.activate          tpm.paid.conversion

tms.interest.pricing_view        tms.lead.demo_request       tms.lead.contact_sales
tms.trial.start                  tms.trial.activate          tms.paid.conversion

agency.lead.contact_submit       agency.lead.case_study_view
agency.lead.quote_request

careers.apply.job_view           careers.apply.submit
```

28 goals total at Wave 1 launch.
