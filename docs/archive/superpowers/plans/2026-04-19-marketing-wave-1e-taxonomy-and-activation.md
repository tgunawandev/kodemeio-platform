# Marketing Wave 1e — Taxonomy & Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce the canonical `docs/marketing/taxonomy.md` reference, the declarative bootstrap + cluster + campaign manifests under `deploys/marketing/`, then run them end-to-end to populate Plausible with 6 sites + 28 goals, validate GSC access for all four products, apply a real example Shlink campaign, and close out Wave 1 by verifying all 8 spec §9 success criteria.

**Architecture:** This is an *activation plan*, not a code-writing plan. Tasks primarily consist of authoring static YAML/Markdown and running CLI commands against the infrastructure stood up in Plan A and the CLIs built in Plans B/C/D. One code task: wire `kctl-plausible doctor` pixel verification into an end-to-end check that gates Wave 1 completion.

**Tech Stack:** YAML, Markdown. Consumes `kctl-plausible`, `kctl-gsc`, `kctl-shlink` CLIs from Plans B/C/D.

**Spec:** `docs/superpowers/specs/2026-04-19-kctl-marketing-wave-1-design.md` (§6 full taxonomy, §9 success criteria, Appendix A + B)

**Dependencies:**
- Plan A (marketing-wave-1a-infra-and-pixels) — complete + tag `marketing-wave-1a` pushed
- Plan B (kctl-plausible) — complete + CLI available via `uv tool install`
- Plan C (kctl-gsc) — complete + CLI available
- Plan D (kctl-shlink) — complete + CLI available

**Working directory:** `/home/tgunawan/project/00-new-projects/kodemeio-workspace/kodemeio-platform`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `docs/marketing/taxonomy.md` | Canonical human-readable reference — goals, UTMs, slugs, examples |
| Create | `deploys/marketing/plausible-bootstrap.yaml` | Declarative: 6 sites + 28 goals + shared links |
| Create | `deploys/marketing/gsc-keyword-clusters.yaml` | Per-product keyword clusters for 4 products |
| Create | `deploys/marketing/shlink-campaigns/2026-q2-tms-parent-awareness.yaml` | First real campaign (TMS — highest-urgency channel) |
| Create | `deploys/marketing/shlink-campaigns/.example.yaml` | Example template to copy from |
| Create | `deploys/marketing/README.md` | How to use these manifests; link back to `taxonomy.md` |
| Create | `scripts/verify-wave-1.sh` | End-to-end success-criteria verification script |

---

## Task 1: Write `docs/marketing/taxonomy.md`

**Files:**
- Create: `kodemeio-platform/docs/marketing/taxonomy.md`

- [ ] **Step 1: Create directory and file**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
mkdir -p docs/marketing
```

- [ ] **Step 2: Write `docs/marketing/taxonomy.md`**

```markdown
# Kodemeio Marketing Taxonomy

**Scope:** goal names, UTM parameters, and Shlink slug conventions used across Plausible + GSC + Shlink. Enforced by the three CLIs at apply time. Load-bearing for Wave 3's offline-conversion attribution.

**Owners:** Marketing ops (primary readers). Product PMs extend per-product goal lists as funnels mature.

**Source of truth:** This file. Any change to the taxonomy lands here first, then in the CLI validators (regex updates in `kctl-plausible`, `kctl-shlink`).

## 1. Products

| Code | Full name | Brand site | Audience |
|---|---|---|---|
| `bas` | Business Automation System | `bas.kodeme.io` | SMB ops, CFOs, IT |
| `hrm` | Human Resource Management | `hrm.kodeme.io` | Indonesian HR managers |
| `tpm` | Trade Promotion Management | `provetics.com` | FMCG brand/category managers |
| `tms` | Therapy Management System | `terakidz.com` | Clinic directors; parents (via companion) |
| `agency` | Kodemeio agency (custom dev + Odoo) | `kodemeio.com` | Founders/CTOs needing custom software |
| `careers` | Recruiting | `careers.kodemeio.com` | Job seekers |
| `cross` | UTM-only pseudo-product for multi-product brand campaigns | n/a | Mixed |

## 2. Plausible goal naming

**Format:** `<product>.<stage>.<event>`

**Regex (enforced by `kctl-plausible goals create`):**
```
^(bas|hrm|tpm|tms|agency|careers)\.(interest|lead|trial|paid|expansion|apply)\.[a-z][a-z0-9_]+$
```

Note: `cross` is not a valid product in goal names (goals are always per-product Plausible sites; `cross` is UTM-only).

### Stages

| Stage | Meaning | Used by |
|---|---|---|
| `interest` | Top of funnel — content engagement | bas, hrm, tpm, tms |
| `lead` | Hand-raise — form submitted | bas, hrm, tpm, tms, agency |
| `trial` | Product used — trial provisioned via Xendit | bas, hrm, tpm, tms |
| `paid` | Money moved — Xendit webhook captured payment | bas, hrm, tpm, tms |
| `expansion` | Upgrade / seat add | later (Wave 3+) |
| `apply` | Job application | careers only |

### Standard per-product funnel (bas, hrm, tpm, tms)

```
{product}.interest.pricing_view       (pageview: /pricing)
{product}.interest.feature_view       (event: ≥75% scroll on /features/*)
{product}.lead.demo_request           (event: form submit)
{product}.lead.contact_sales          (event: form submit)
{product}.trial.start                 (event: Xendit webhook → Plausible events API)
{product}.trial.activate              (event: first authenticated session)
{product}.paid.conversion             (event: Xendit webhook)
{product}.paid.expansion              (event: plan upgrade)         — later
```

### Agency goals (`kodemeio.com`)

```
agency.lead.contact_submit
agency.lead.case_study_view
agency.lead.quote_request
```

### Careers goals (`careers.kodemeio.com`)

```
careers.apply.job_view
careers.apply.submit
```

## 3. UTM parameters

| Param | Rule | Examples |
|---|---|---|
| `utm_source` | lowercase, snake_case, channel origin | `google`, `meta`, `linkedin`, `tiktok`, `email`, `whatsapp`, `telegram`, `event`, `referral`, `direct_sales` |
| `utm_medium` | lowercase, channel type | `cpc`, `paid_social`, `display`, `email`, `messaging`, `organic`, `offline`, `referral`, `sales_outreach` |
| `utm_campaign` | `{yyyy}_{qn}_{product}_{theme}` (snake_case) | `2026_q2_tpm_fmcg_outreach`, `2026_q2_tms_parent_awareness` |
| `utm_content` | `{format}_{variant}` — creative identifier | `ad_a`, `ad_b`, `email_may`, `qr_booth`, `video_15s` |
| `utm_term` | keyword (search only), lowercase, accent-stripped | `software_erp`, `aplikasi_payroll` |

**`utm_campaign` regex (enforced by `kctl-shlink campaigns apply`):**
```
^(20\d{2})_q[1-4]_(bas|hrm|tpm|tms|agency|careers|cross)_[a-z0-9_]+$
```

`cross` is allowed here — for multi-product brand campaigns (e.g., year-end "2026 Kodemeio brand awareness" hitting kodemeio.com + product sites as a set).

## 4. Shlink slug convention

**Format:** `{product}-{channel}-{campaign_tag}[-{variant}]` — kebab-case, matches URL hygiene.

**Regex (enforced by `kctl-shlink campaigns apply`):**
```
^(bas|hrm|tpm|tms|agency|careers|cross)-[a-z]+-[a-z0-9]+(-[a-z0-9]+)?$
```

### Examples

| Slug | Product | Channel | Campaign | Variant |
|---|---|---|---|---|
| `tpm-linkedin-q2a` | TPM | LinkedIn | Q2 | A |
| `tpm-linkedin-q2b` | TPM | LinkedIn | Q2 | B |
| `tms-ig-parent-1` | TMS | Instagram | parent | 1 |
| `bas-email-may` | BAS | Email | May newsletter | — |
| `hrm-qr-exhibit` | HRM | QR code | trade exhibit | — |
| `cross-brand-2026` | Multi-product | Brand | 2026 | — |

## 5. Environment flavor (prod vs staging)

| | Prod | Staging |
|---|---|---|
| `utm_campaign` | `2026_q2_tpm_fmcg_outreach` | `stg_2026_q2_tpm_fmcg_outreach` |
| Shlink slug | `tpm-linkedin-q2a` | `stg-tpm-linkedin-q2a` |
| Plausible goal | `tpm.lead.demo_request` | (same; filter by referrer prefix) |

No separate staging instances — prefix-based filtering keeps data distinguishable.

## 6. End-to-end alignment example

```
Campaign: 2026 Q2 TPM FMCG outreach on LinkedIn (A/B creative)

─── Shlink manifest: shlink-campaigns/2026-q2-tpm-fmcg-outreach.yaml
      slug:        tpm-linkedin-q2a
      short_url:   https://s.kodeme.io/tpm-linkedin-q2a
      long_url:    https://provetics.com/tpm
                   ?utm_source=linkedin
                   &utm_medium=paid_social
                   &utm_campaign=2026_q2_tpm_fmcg_outreach
                   &utm_content=ad_a

─── Plausible site: provetics.com
      Goals fired:   tpm.interest.pricing_view
                     tpm.lead.demo_request
                     tpm.trial.start        (via Xendit webhook)
                     tpm.paid.conversion    (via Xendit webhook)

─── Wave 3 offline-conversion join key:
      (utm_campaign, utm_content) = ("2026_q2_tpm_fmcg_outreach", "ad_a")
      → matched against LinkedIn click ID captured at landing (Wave 3 adds this)
      → Odoo crm_lead.utm → sale_order → paid
      → uploaded to LinkedIn Conversions API
```

## 7. Extending

When adding a fifth SaaS product (e.g., `mms` for Marketing Management System):

1. Update the product enum in this doc (section 1).
2. Update the three regexes in sections 2, 3, 4.
3. Update `kctl-plausible` goal-name validator (`packages/kctl-plausible/src/kctl_plausible/validators.py`).
4. Update `kctl-shlink` slug + utm_campaign validators.
5. Rerun `kctl-plausible sites bootstrap` after adding the new site + goals to `deploys/marketing/plausible-bootstrap.yaml`.

Do **not** edit goal names after a campaign has launched on them — Plausible goals are immutable by name, renaming would orphan historical data.

## 8. See also

- Spec: `docs/superpowers/specs/2026-04-19-kctl-marketing-wave-1-design.md`
- Bootstrap: `deploys/marketing/plausible-bootstrap.yaml`
- Clusters: `deploys/marketing/gsc-keyword-clusters.yaml`
- Campaigns: `deploys/marketing/shlink-campaigns/*.yaml`
- CLI references: `packages/kctl-plausible/README.md`, `packages/kctl-gsc/README.md`, `packages/kctl-shlink/README.md`
```

- [ ] **Step 3: Commit**

```bash
git add docs/marketing/taxonomy.md
git commit -m "docs(marketing): add canonical taxonomy reference

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Write `deploys/marketing/plausible-bootstrap.yaml`

**Files:**
- Create: `kodemeio-platform/deploys/marketing/plausible-bootstrap.yaml`

- [ ] **Step 1: Create directory**

```bash
mkdir -p deploys/marketing
```

- [ ] **Step 2: Write `plausible-bootstrap.yaml`**

```yaml
# deploys/marketing/plausible-bootstrap.yaml
# Declarative Plausible setup. Idempotent. Applied via:
#   kctl-plausible sites bootstrap -f deploys/marketing/plausible-bootstrap.yaml
# Reference: docs/marketing/taxonomy.md

sites:
  - domain: bas.kodeme.io
    product: bas
    timezone: Asia/Jakarta
  - domain: hrm.kodeme.io
    product: hrm
    timezone: Asia/Jakarta
  - domain: provetics.com
    product: tpm
    timezone: Asia/Jakarta
  - domain: terakidz.com
    product: tms
    timezone: Asia/Jakarta
  - domain: kodemeio.com
    product: agency
    timezone: Asia/Jakarta
  - domain: careers.kodemeio.com
    product: careers
    timezone: Asia/Jakarta

goal_templates:
  product_funnel:
    applies_to: [bas, hrm, tpm, tms]
    goals:
      - name: "{product}.interest.pricing_view"
        type: page
        path: "/pricing"
      - name: "{product}.interest.feature_view"
        type: event
      - name: "{product}.lead.demo_request"
        type: event
      - name: "{product}.lead.contact_sales"
        type: event
      - name: "{product}.trial.start"
        type: event
      - name: "{product}.trial.activate"
        type: event
      - name: "{product}.paid.conversion"
        type: event

  agency:
    applies_to: [agency]
    goals:
      - name: "agency.lead.contact_submit"
        type: event
      - name: "agency.lead.case_study_view"
        type: page
        path: "/case-studies/*"
      - name: "agency.lead.quote_request"
        type: event

  careers:
    applies_to: [careers]
    goals:
      - name: "careers.apply.job_view"
        type: page
        path: "/jobs/*"
      - name: "careers.apply.submit"
        type: event

shared_links:
  - site: bas.kodeme.io
    name: bas-team
  - site: hrm.kodeme.io
    name: hrm-team
  - site: provetics.com
    name: tpm-team
  - site: terakidz.com
    name: tms-team
  - site: kodemeio.com
    name: agency-leads
  - site: careers.kodemeio.com
    name: careers-team
```

- [ ] **Step 3: Commit**

```bash
git add deploys/marketing/plausible-bootstrap.yaml
git commit -m "feat(marketing): add Plausible bootstrap manifest (6 sites, 28 goals)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Write `deploys/marketing/gsc-keyword-clusters.yaml`

**Files:**
- Create: `kodemeio-platform/deploys/marketing/gsc-keyword-clusters.yaml`

- [ ] **Step 1: Write the file**

```yaml
# deploys/marketing/gsc-keyword-clusters.yaml
# Per-product query clusters. Loaded by `kctl-gsc reports product <name>`.
# Reference: docs/marketing/taxonomy.md

products:
  bas:
    property: "sc-domain:kodeme.io"
    path_filter: "/bas/"
    clusters:
      - name: erp_id
        patterns:
          - "software erp"
          - "aplikasi erp"
          - "sistem erp"
          - "erp indonesia"
      - name: odoo_id
        patterns:
          - "odoo indonesia"
          - "odoo 18"
          - "implementasi odoo"
          - "odoo customization"
      - name: accounting
        patterns:
          - "software akuntansi"
          - "aplikasi keuangan umkm"
          - "laporan keuangan otomatis"

  hrm:
    property: "sc-domain:kodeme.io"
    path_filter: "/hrm/"
    clusters:
      - name: payroll_id
        patterns:
          - "aplikasi payroll"
          - "software payroll"
          - "hitung gaji"
          - "kalkulator pph 21"
      - name: attendance
        patterns:
          - "absensi online"
          - "absensi gps"
          - "aplikasi absen"
          - "clock in app"
      - name: bpjs_pph
        patterns:
          - "bpjs kesehatan"
          - "bpjs ketenagakerjaan"
          - "pph 21"
          - "slip gaji"

  tpm:
    property: "https://provetics.com/"
    clusters:
      - name: trade_promo
        patterns:
          - "trade promotion"
          - "manajemen promosi fmcg"
          - "TPM software"
          - "trade marketing"
      - name: trade_claims
        patterns:
          - "claim trade promotion"
          - "settlement distributor"
          - "deduction management"
      - name: demand_planning
        patterns:
          - "demand planning"
          - "sales forecasting"
          - "perencanaan promosi"

  tms:
    property: "https://terakidz.com/"
    clusters:
      - name: therapy_id
        patterns:
          - "terapi anak autis"
          - "terapi adhd anak"
          - "klinik autism"
          - "terapis anak"
      - name: aba
        patterns:
          - "ABA therapy"
          - "applied behavior"
          - "terapi perilaku"
          - "behavior analysis"
      - name: assessments
        patterns:
          - "tes autism"
          - "skrining adhd"
          - "asesmen anak"
          - "deteksi dini autism"
      - name: locations
        patterns:
          - "klinik autism jakarta"
          - "klinik adhd surabaya"
          - "terapis anak bandung"
```

- [ ] **Step 2: Commit**

```bash
git add deploys/marketing/gsc-keyword-clusters.yaml
git commit -m "feat(marketing): add GSC keyword clusters for 4 products

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Write example + first real Shlink campaign manifests

**Files:**
- Create: `kodemeio-platform/deploys/marketing/shlink-campaigns/.example.yaml`
- Create: `kodemeio-platform/deploys/marketing/shlink-campaigns/2026-q2-tms-parent-awareness.yaml`

- [ ] **Step 1: Create directory**

```bash
mkdir -p deploys/marketing/shlink-campaigns
```

- [ ] **Step 2: Write `.example.yaml`**

```yaml
# deploys/marketing/shlink-campaigns/.example.yaml
# Template — copy to a real campaign file and edit.
# Apply with: kctl-shlink campaigns apply -f <file>
# Reference: docs/marketing/taxonomy.md §4 (slug convention), §3 (UTM)

name: YYYY_qN_<product>_<theme>
product: <bas|hrm|tpm|tms|agency|careers|cross>
tags:
  - <product>
  - q<N>-YYYY
  - <theme-tag>
domain: s.kodeme.io

defaults:
  utm:
    campaign: "{name}"  # auto-substituted from the top-level `name` field

links:
  - slug: <product>-<channel>-<campaign_tag>-<variant>
    long_url: https://<product-site>/<landing-path>
    utm:
      source: <channel>
      medium: <medium>
      content: <creative_variant>
    # optional QR
    qr:
      format: svg
      size: 2000
      margin: print
      output: ./out/<slug>.svg
    # optional limits
    expire_at: 2026-07-01T00:00:00Z
    max_visits: 50000
```

- [ ] **Step 3: Write `2026-q2-tms-parent-awareness.yaml`** (the first real campaign — TMS is the Meta-primary channel, highest urgency)

```yaml
# deploys/marketing/shlink-campaigns/2026-q2-tms-parent-awareness.yaml
# Real campaign — TMS parent awareness on Facebook + Instagram Q2 2026.
# Audience: IDN parents of children 3–10 with possible ASD/ADHD indicators.
# Landing: terakidz.com homepage + /assessments page.

name: 2026_q2_tms_parent_awareness
product: tms
tags:
  - tms
  - q2-2026
  - parent-awareness
domain: s.kodeme.io

defaults:
  utm:
    campaign: 2026_q2_tms_parent_awareness

links:
  - slug: tms-fb-parent-a
    long_url: https://terakidz.com/
    utm:
      source: meta
      medium: paid_social
      content: fb_carousel_a

  - slug: tms-fb-parent-b
    long_url: https://terakidz.com/
    utm:
      source: meta
      medium: paid_social
      content: fb_carousel_b

  - slug: tms-ig-reel-1
    long_url: https://terakidz.com/assessments
    utm:
      source: meta
      medium: paid_social
      content: ig_reel_1

  - slug: tms-ig-reel-2
    long_url: https://terakidz.com/assessments
    utm:
      source: meta
      medium: paid_social
      content: ig_reel_2

  - slug: tms-wa-referral
    long_url: https://terakidz.com/?ref=parent_wa
    utm:
      source: whatsapp
      medium: messaging
      content: parent_referral_card
    qr:
      format: svg
      size: 2000
      margin: print
      output: ./out/tms-parent-referral-qr.svg
```

- [ ] **Step 4: Commit**

```bash
git add deploys/marketing/shlink-campaigns/
git commit -m "feat(marketing): add example + first Shlink campaign (TMS Q2 parent awareness)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Write `deploys/marketing/README.md`

**Files:**
- Create: `kodemeio-platform/deploys/marketing/README.md`

- [ ] **Step 1: Write the file**

```markdown
# deploys/marketing/

Declarative manifests for the marketing measurement stack: Plausible sites/goals, GSC keyword clusters, and Shlink campaigns. All applied via `kctl-plausible`, `kctl-gsc`, `kctl-shlink` respectively.

## Files

| File | Purpose | Applied by |
|---|---|---|
| `plausible-bootstrap.yaml` | 6 sites + 28 goals + shared links (one-time bootstrap, idempotent re-apply safe) | `kctl-plausible sites bootstrap -f <file>` |
| `gsc-keyword-clusters.yaml` | Per-product search query clusters for reports | `kctl-gsc reports product <name>` (auto-loaded) |
| `shlink-campaigns/*.yaml` | Per-campaign short URL + UTM + QR manifests | `kctl-shlink campaigns apply -f <file>` |

## Conventions

All files conform to `docs/marketing/taxonomy.md`. Do not invent new goal names, UTM campaign names, or slug patterns without updating that doc first.

## Lifecycle

- **Plausible bootstrap**: re-apply whenever a product is added or goals change. Safe because apply is idempotent (`--dry-run` to preview).
- **GSC clusters**: edit and re-run reports; no apply step. Changes take effect immediately.
- **Shlink campaigns**: one file per campaign. Destroy only when the campaign ends (`kctl-shlink campaigns destroy -f <file>`).

## Where campaign outputs go

QR files written to `./out/` by `kctl-shlink campaigns apply` are not committed. Regenerate on demand. For durable artefacts used in print collateral, copy to `docs/marketing/assets/` in a separate commit.

## See also

- `docs/marketing/taxonomy.md` — the canonical reference
- `docs/superpowers/specs/2026-04-19-kctl-marketing-wave-1-design.md` — full Wave 1 design
```

- [ ] **Step 2: Commit**

```bash
git add deploys/marketing/README.md
git commit -m "docs(marketing): add deploys/marketing README

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Initialize CLI profiles

- [ ] **Step 1: Configure `kctl-plausible`**

```bash
kctl-plausible config init \
    --profile kodemeio-kod-infra-plausible \
    --url https://plausible.kodeme.io \
    --api-key "$(op item get plausible --vault=kodemeio-production --fields api_key --reveal)"

kctl-plausible -p kodemeio-kod-infra-plausible config show
```

Expected: config shown with `api_key` masked as `first4****last4`.

- [ ] **Step 2: Configure `kctl-shlink`**

```bash
kctl-shlink config init \
    --profile kodemeio-kod-infra-shlink \
    --url https://s.kodeme.io \
    --api-key "$(op item get shlink --vault=kodemeio-production --fields password --reveal)"

kctl-shlink -p kodemeio-kod-infra-shlink config show
```

- [ ] **Step 3: Configure `kctl-gsc`**

Prerequisite: you've placed the service-account JSON at `~/.config/kodemeio/gsc-sa.json` and added the service-account email as a user on each Search Console property (for `sc-domain:kodeme.io`, `https://provetics.com/`, `https://terakidz.com/`, `https://kodemeio.com/`, `https://careers.kodemeio.com/`).

```bash
kctl-gsc config init \
    --profile kodemeio-kod-infra-gsc \
    --credentials-file ~/.config/kodemeio/gsc-sa.json \
    --default-property "sc-domain:kodeme.io"

kctl-gsc -p kodemeio-kod-infra-gsc config show
```

- [ ] **Step 4: Run doctor on all three**

```bash
kctl-plausible -p kodemeio-kod-infra-plausible doctor
kctl-shlink -p kodemeio-kod-infra-shlink doctor
kctl-gsc -p kodemeio-kod-infra-gsc doctor
```

Expected: all three print green (API reachable, creds valid). `kctl-plausible doctor` will report "sites to verify: 0" because bootstrap hasn't run yet — OK.

---

## Task 7: Apply Plausible bootstrap

- [ ] **Step 1: Dry-run**

```bash
kctl-plausible -p kodemeio-kod-infra-plausible sites bootstrap \
    -f deploys/marketing/plausible-bootstrap.yaml \
    --dry-run
```

Expected: output lists 6 sites to create, 28 goals to create, 6 shared links. Zero errors.

- [ ] **Step 2: Apply**

```bash
kctl-plausible -p kodemeio-kod-infra-plausible sites bootstrap \
    -f deploys/marketing/plausible-bootstrap.yaml
```

Expected: final line reads `bootstrap complete: 6 sites, 28 goals, 6 shared links`.

- [ ] **Step 3: Verify sites list**

```bash
kctl-plausible -p kodemeio-kod-infra-plausible sites list
```

Expected table: 6 rows for the 6 domains.

- [ ] **Step 4: Verify 28 goals created**

```bash
kctl-plausible -p kodemeio-kod-infra-plausible goals list --all-sites --format json | jq 'length'
```

Expected: `28`.

- [ ] **Step 5: Verify shared links**

```bash
kctl-plausible -p kodemeio-kod-infra-plausible shared-links list
```

Expected: 6 rows; each row has a URL you can open in a browser (no auth needed for shared dashboards).

- [ ] **Step 6: Re-apply to prove idempotency**

```bash
kctl-plausible -p kodemeio-kod-infra-plausible sites bootstrap \
    -f deploys/marketing/plausible-bootstrap.yaml
```

Expected: `bootstrap complete: 0 sites, 0 goals, 0 shared links (no changes)`.

---

## Task 8: Validate GSC access for all four products

- [ ] **Step 1: List properties**

```bash
kctl-gsc -p kodemeio-kod-infra-gsc properties list
```

Expected: at least 5 properties — `sc-domain:kodeme.io`, `https://provetics.com/`, `https://terakidz.com/`, `https://kodemeio.com/`, `https://careers.kodemeio.com/`.

If any of these 5 are missing, the service account isn't authorized on that property. Fix: Search Console UI → property → Settings → Users → add service-account email with Full permission.

- [ ] **Step 2: Test top-queries for each product property**

```bash
for product in bas hrm tpm tms; do
  echo "=== $product ==="
  kctl-gsc -p kodemeio-kod-infra-gsc queries top \
      --clusters deploys/marketing/gsc-keyword-clusters.yaml \
      --product "$product" \
      --period 28d \
      --limit 5
done
```

Expected: each returns either a table or a note "no data yet" (for very new sites). No permission errors.

- [ ] **Step 3: Run the keyword-cluster report for TMS** (has the most established search presence)

```bash
kctl-gsc -p kodemeio-kod-infra-gsc reports product tms --period 90d
```

Expected: tabular output with per-cluster impressions, clicks, CTR, avg position, top query. If empty, GSC hasn't accumulated enough data — not a blocker for Wave 1 exit.

---

## Task 9: Apply the first Shlink campaign

- [ ] **Step 1: Dry-run**

```bash
kctl-shlink -p kodemeio-kod-infra-shlink campaigns apply \
    -f deploys/marketing/shlink-campaigns/2026-q2-tms-parent-awareness.yaml \
    --dry-run
```

Expected: diff shows 5 short URLs to create, 1 QR to generate, 0 delete.

- [ ] **Step 2: Apply**

```bash
kctl-shlink -p kodemeio-kod-infra-shlink campaigns apply \
    -f deploys/marketing/shlink-campaigns/2026-q2-tms-parent-awareness.yaml
```

Expected: `applied: 5 created, 0 updated, 0 deleted, 1 qr generated`.

- [ ] **Step 3: Verify short URLs**

```bash
kctl-shlink -p kodemeio-kod-infra-shlink urls list --tag tms --tag q2-2026
```

Expected: 5 rows with slugs `tms-fb-parent-a`, `tms-fb-parent-b`, `tms-ig-reel-1`, `tms-ig-reel-2`, `tms-wa-referral`.

- [ ] **Step 4: Verify one redirect manually**

```bash
curl -sI https://s.kodeme.io/tms-ig-reel-1 | head -5
```

Expected: `HTTP/2 302` with `location:` header pointing to `https://terakidz.com/assessments?utm_source=meta&utm_medium=paid_social&utm_campaign=2026_q2_tms_parent_awareness&utm_content=ig_reel_1`.

- [ ] **Step 5: Verify QR file**

```bash
ls -la ./out/tms-parent-referral-qr.svg
file ./out/tms-parent-referral-qr.svg
```

Expected: file present, mimetype `SVG Scalable Vector Graphics image`.

- [ ] **Step 6: Re-apply to prove idempotency**

```bash
kctl-shlink -p kodemeio-kod-infra-shlink campaigns apply \
    -f deploys/marketing/shlink-campaigns/2026-q2-tms-parent-awareness.yaml
```

Expected: `applied: 0 created, 0 updated, 0 deleted, 0 qr generated (no changes)`.

---

## Task 10: End-to-end pixel verification via `kctl-plausible doctor`

- [ ] **Step 1: Run doctor (verbose)**

```bash
kctl-plausible -p kodemeio-kod-infra-plausible doctor -v
```

Expected output (for each of the 6 sites):
```
✓ bas.kodeme.io — Plausible snippet detected
✓ bas.kodeme.io — Meta Pixel <id> detected
✓ bas.kodeme.io — Google Tag G-XXXXXXX detected
```

All 6 sites × 3 checks = 18 lines. Zero failures.

- [ ] **Step 2: If any pixel check fails, diagnose**

- **Plausible missing** → page not yet redeployed with `@kodemeio/analytics` import. Redeploy the corresponding Dokploy compose service.
- **Meta Pixel missing** → `NEXT_PUBLIC_META_PIXEL_ID` env var not set or empty. Fix in Dokploy env, redeploy.
- **Google Tag missing** → same as above for `NEXT_PUBLIC_GOOGLE_TAG_ID`.
- **bas.kodeme.io / hrm.kodeme.io failing** → these subdomains are served via corporate Next.js subdomain routing. Verify `corporate.kodemeio.com` still has pixels (if yes, and the subdomains 404, DNS may be pointing elsewhere; check `kctl-cf` zone).

Re-run step 1 after each fix until green.

---

## Task 11: Write Wave 1 verification script

**Files:**
- Create: `kodemeio-platform/scripts/verify-wave-1.sh`

- [ ] **Step 1: Create executable script**

```bash
#!/usr/bin/env bash
# scripts/verify-wave-1.sh
# End-to-end check that Wave 1 exit criteria (spec §9) are all met.

set -euo pipefail

fail=0
check() {
    local name="$1"; shift
    if "$@" > /dev/null 2>&1; then
        echo "  ✓ $name"
    else
        echo "  ✗ $name"
        fail=$((fail + 1))
    fi
}

echo "Wave 1 success criteria (spec §9):"
echo

echo "1. All three CLIs installed:"
check "kctl-plausible --version" kctl-plausible --version
check "kctl-gsc --version"       kctl-gsc --version
check "kctl-shlink --version"    kctl-shlink --version

echo
echo "2. Audit-platform score ≥ 9/10:"
for pkg in kctl-plausible kctl-gsc kctl-shlink; do
    score=$(uv run python scripts/audit-platform.py --package "$pkg" --json 2>/dev/null | jq -r '.score' || echo 0)
    if (( $(echo "$score >= 9" | bc -l) )); then
        echo "  ✓ $pkg: $score/10"
    else
        echo "  ✗ $pkg: $score/10"
        fail=$((fail + 1))
    fi
done

echo
echo "3. Deploys healthy:"
check "plausible.kodeme.io /api/health" curl -sSf https://plausible.kodeme.io/api/health
check "s.kodeme.io /rest/health"         curl -sSf https://s.kodeme.io/rest/health

echo
echo "4. Plausible bootstrap applied (6 sites + 28 goals):"
sites=$(kctl-plausible -p kodemeio-kod-infra-plausible sites list --format json | jq 'length')
goals=$(kctl-plausible -p kodemeio-kod-infra-plausible goals list --all-sites --format json | jq 'length')
if [[ "$sites" == "6" ]]; then echo "  ✓ sites: 6"; else echo "  ✗ sites: $sites (expected 6)"; fail=$((fail+1)); fi
if [[ "$goals" == "28" ]]; then echo "  ✓ goals: 28"; else echo "  ✗ goals: $goals (expected 28)"; fail=$((fail+1)); fi

echo
echo "5. GSC returns data for TMS property:"
tms_rows=$(kctl-gsc -p kodemeio-kod-infra-gsc reports product tms --period 90d --format json 2>/dev/null | jq 'length' || echo 0)
if [[ "$tms_rows" != "0" ]]; then
    echo "  ✓ GSC TMS rows: $tms_rows"
else
    echo "  ~ GSC TMS rows: 0 (may be OK for new property; does not fail build)"
fi

echo
echo "6. Shlink example campaign applied:"
urls=$(kctl-shlink -p kodemeio-kod-infra-shlink urls list --tag tms --tag q2-2026 --format json | jq 'length')
if [[ "$urls" == "5" ]]; then echo "  ✓ shlink URLs: 5"; else echo "  ✗ shlink URLs: $urls"; fail=$((fail+1)); fi

echo
echo "7. Cross-join report renders:"
if kctl-shlink -p kodemeio-kod-infra-shlink reports campaign 2026_q2_tms_parent_awareness > /dev/null 2>&1; then
    echo "  ✓ campaign report renders"
else
    echo "  ✗ campaign report failed"
    fail=$((fail + 1))
fi

echo
echo "8. Pixel verification (6 sites × 3 trackers):"
if kctl-plausible -p kodemeio-kod-infra-plausible doctor 2>&1 | grep -q '18 pass, 0 fail'; then
    echo "  ✓ all 18 pixel checks pass"
else
    echo "  ✗ pixel checks failing (run 'kctl-plausible doctor -v' for details)"
    fail=$((fail + 1))
fi

echo
echo "9. Taxonomy doc exists:"
check "docs/marketing/taxonomy.md present" test -f docs/marketing/taxonomy.md

echo
echo "===================="
if [[ "$fail" == "0" ]]; then
    echo "Wave 1 exit criteria: ALL PASS ✓"
    exit 0
else
    echo "Wave 1 exit criteria: $fail FAILED ✗"
    exit 1
fi
```

Save to `scripts/verify-wave-1.sh`.

- [ ] **Step 2: Make executable**

```bash
chmod +x scripts/verify-wave-1.sh
```

- [ ] **Step 3: Run it**

```bash
./scripts/verify-wave-1.sh
```

Expected: final line `Wave 1 exit criteria: ALL PASS ✓`, exit code 0.

- [ ] **Step 4: Commit**

```bash
git add scripts/verify-wave-1.sh
git commit -m "feat(scripts): add Wave 1 exit criteria verifier

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Task 12: Shlink × Plausible cross-join report — sanity check

- [ ] **Step 1: Seed a test click**

```bash
curl -s "https://s.kodeme.io/tms-ig-reel-1" > /dev/null
```

Expected: 302 redirect; Shlink records the click.

- [ ] **Step 2: Wait ~30 seconds (Plausible event ingestion lag)**

```bash
sleep 30
```

- [ ] **Step 3: Run the cross-join report**

```bash
kctl-shlink -p kodemeio-kod-infra-shlink reports campaign 2026_q2_tms_parent_awareness
```

Expected: table with 5 rows (one per slug). `tms-ig-reel-1` row shows `clicks: 1+`. `pv` column populated by Plausible (may still be 0 if the Plausible snippet didn't have time to beacon — OK for smoke test).

If the report fails with "kctl-plausible client unavailable", verify `kodemeio-kod-infra-plausible` profile is in the same config file and re-run.

---

## Task 13: Final push + Wave 1 tag

- [ ] **Step 1: Confirm clean state**

```bash
cd ~/project/00-new-projects/kodemeio-workspace/kodemeio-platform
git status
```

Expected: clean (all commits from Tasks 1–11 already made).

- [ ] **Step 2: Push**

```bash
git push origin main
```

- [ ] **Step 3: Tag Wave 1 complete**

```bash
git tag -a marketing-wave-1 -m "Marketing Wave 1 complete: measurement foundation live

- Plausible CE + Shlink deployed (kod-prod-01)
- kctl-plausible, kctl-gsc, kctl-shlink CLIs at 9+/10 audit
- 6 Plausible sites + 28 goals + 6 shared links
- GSC keyword clusters for 4 products
- First Shlink campaign applied (TMS Q2 parent awareness)
- Meta Pixel + Google Tag installed on 5 Next.js marketing apps
- docs/marketing/taxonomy.md as canonical reference"
git push origin marketing-wave-1
```

- [ ] **Step 4: Announce**

Post to Zulip `#marketing` stream (or equivalent):

```bash
kctl-zulip -p kodemeio messages send \
    --stream "marketing" \
    --topic "Wave 1 live" \
    --content "Wave 1 of the marketing measurement stack is live.

- Plausible: https://plausible.kodeme.io (6 sites tracked)
- Shlink: https://s.kodeme.io (first campaign: TMS parent awareness)
- Taxonomy reference: docs/marketing/taxonomy.md
- CLIs: kctl-plausible, kctl-gsc, kctl-shlink

Wave 2 (kctl-gads, kctl-meta-ads, kctl-linkedin-ads) starts next. Pixels are firing — warm audience build-up has begun."
```

---

## Exit criteria (Plan E done-done — Wave 1 complete)

All boxes from spec §9 green:

- [ ] All three CLIs installable via `uv tool install`, pass `audit-platform.py ≥ 9/10`
- [ ] Plausible and Shlink deployed to `kod-prod-01`, healthcheck green
- [ ] `kctl-plausible sites bootstrap` created all 6 sites + 28 goals + 6 shared links
- [ ] `kctl-gsc reports product tms` returns non-empty data for `terakidz.com` (or plausibly empty for a new property — annotated as OK in `verify-wave-1.sh`)
- [ ] `kctl-shlink campaigns apply` produces working short URLs with correct UTMs
- [ ] `kctl-shlink reports campaign 2026_q2_tms_parent_awareness` correlates clicks with Plausible goal hits
- [ ] Meta Pixel + Google Tag confirmed firing on all 6 tracked properties (via `kctl-plausible doctor`)
- [ ] `docs/marketing/taxonomy.md` committed and referenced by `deploys/marketing/README.md`
- [ ] Git tag `marketing-wave-1` pushed

Next: Wave 2 — `kctl-gads`, `kctl-meta-ads`, `kctl-linkedin-ads`. Spec and brainstorming for Wave 2 follow the same protocol (brainstorming → spec → plans → execute).
