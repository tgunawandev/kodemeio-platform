# Mattermost → Singapore Migration Plan (mm.idtpp.com + mac-mm.idtpp.com)

> **Status:** PLAN / pre-execution. Assessment complete 2026-06-15. Awaiting go-ahead.
> **Goal:** Relocate both production Mattermost instances from Hetzner Germany to the
> Singapore server `tpp-prod-06` (5.223.69.142) to fix attachment + voice-call latency
> for Indonesian users, with **zero attachment loss** and a clean rollback path.

---

## 1. Assessment (measured 2026-06-15, read-only)

| Metric | mm.idtpp.com (tpp-prod-04) | mac-mm.idtpp.com (tpp-prod-05) | Total |
|---|---|---|---|
| Server / IP | tpp-prod-04 / 178.104.169.250 (Germany) | tpp-prod-05 / 178.104.171.122 (Germany) | — |
| Postgres DB | 28 MB | 23 MB | 51 MB |
| Attachments (S3 bucket) | 655 MB / 1,309 objects | 393 MB / 2,096 objects | **~1.05 GB / 3,405 obj** |
| FileInfo rows (DB) | 555 | 991 | — |
| Active users | 188 | 34 | 222 |
| Posts | 3,354 | 2,995 | — |
| S3 bucket | `hz-tpp-mattermost-data` | `hz-mac-mattermost-data` | (endpoint `fsn1.your-objectstorage.com`) |
| Authentik provider | id 10 (`LE1Em…`) | id 15 | (apps already scoped to the real domains) |
| Source container prefix | `compose-back-up-open-source-driver-jkvtl2` | `compose-input-bluetooth-pixel-w6wlc6` | — |

**Target tpp-prod-06 (SG):** 4 vCPU / 7.7 GB / 150 GB disk, **140 GB free**. Docker + Swarm + Traefik + `rclone` present (Dokploy-managed). Dokploy server id `2-3nUPC6FJqt7QWabzFp1`.

### Space requirement
Total data to move is **~1.1 GB** (1.05 GB files + 51 MB DBs). SG has 140 GB free → **~130× headroom**. No Hetzner Volume needed for capacity. Plan keeps a comfortable >95% free.

### Decisions (confirmed)
- **Sizing:** keep CPX32 for now; monitor RTC under real load; resize to CPX42 (8 vCPU/16 GB — a ~2-min reboot) only if concurrent calls strain 4 vCPU.
- **Storage:** **local disk** on SG (`MM_FILESETTINGS_DRIVERNAME=local`) + nightly offsite backup. R2 rejected as primary (adds a server→storage hop; MM proxies files so R2 gives no edge benefit). R2 test procedure kept as Appendix B if ops priorities change.
- **DNS at cutover:** `mm`/`mac-mm` set to **grey-cloud (DNS-only)** → 5.223.69.142 (matches the validated `sg-mm` test). Cloudflare proxy/Argo is a later optional enhancement.
- **SSO:** domains are unchanged, so the **existing Authentik apps (provider 10 / 15) work as-is** — reuse the prod env client_id/secret. No Authentik changes.

### Risks & mitigations
| Risk | Mitigation |
|---|---|
| Attachment loss | Checksum-verified `rclone check` gate + FileInfo-path existence check + two-phase sync (Phase 4). |
| Data written during migration lost | Final incremental `rclone sync` + final `pg_dump` taken AFTER source is stopped (Phase 4). |
| RTC port clash (two instances, one host) | Per-instance `MM_CALLS_PORT` (mm=8466, mac=8467); compose parametrized. |
| Bad cutover | Source servers stopped-but-intact for 2 weeks; rollback = flip DNS back + restart source. |
| LE cert delay after DNS flip | HTTP-01 issues in ~30–60 s once DNS points to SG; inside the maintenance window. |
| CPX32 under-sized for 2 tenants' calls | Monitor; CPX42 resize is a 2-min reboot. |

---

## 2. Prerequisite repo change (compose port parametrization)

**File:** `kodemeio-mattermost/docker-compose.prod.yml` — make the Calls port configurable so two instances can coexist on one host.

- [ ] Change the `mattermost.ports` block from hardcoded `8466` to:
```yaml
    ports:
      - "${MM_CALLS_PORT:-8466}:${MM_CALLS_PORT:-8466}/udp"
      - "${MM_CALLS_PORT:-8466}:${MM_CALLS_PORT:-8466}/tcp"
```
- [ ] Commit on a branch, push, merge to `main` (Dokploy deploys from `main`).
- [ ] Each instance sets `MM_CALLS_PORT` (mm=8466, mac=8467) and the Calls plugin `udpserverport`/`tcpserverport` to match.

---

## 3. Phase 0 — Preparation (no downtime)

- [ ] **Decommission the `sg-mm` test instance** to free port 8466 and avoid confusion:
  - `kctl-dokploy -p idtpp compose stop hRJuWwEAyi0MWZDiXt2C4`
  - After prod is validated, `compose delete hRJuWwEAyi0MWZDiXt2C4 --force` and delete DNS `sg-mm`.
- [ ] **Rotate** the leaked test Authentik secret for app `mattermost-sg` (or delete that test app entirely).
- [ ] **Create production SG instance manifests** (mirror the test, real domains, local storage, prod Authentik creds, distinct RTC ports):
  - `deploys/instances/production/tpp-infra-mattermost-sg-prod.yaml` → host `mm.idtpp.com`, server `tpp-prod-06`.
  - `deploys/instances/production/mac-infra-mattermost-sg-prod.yaml` → host `mac-mm.idtpp.com`, server `tpp-prod-06`.
- [ ] **Create env files** (gitignored) copied from the current prod env of each tenant, with these overrides:
  - `MM_FILESETTINGS_DRIVERNAME=local`; clear all `MM_FILESETTINGS_AMAZONS3*`.
  - `MM_CALLS_PORT=8466` (mm) / `8467` (mac).
  - Keep prod `AUTHENTIK_*` (provider 10 / 15) and Mailcow SMTP unchanged.
  - Fresh `MM_POSTGRESQL_PASSWORD` (the SG postgres is new); DB name `mattermost`.
  - `COMPOSE_PROJECT_NAME` unique per instance.
- [ ] Validate: `kctl-dokploy -p idtpp deploy validate -f <manifest>` for both → "Manifest is valid".

---

## 4. Phase 1 — Deploy empty SG production stacks (no downtime, no DNS flip)

- [ ] Deploy both stacks (DNS not flipped yet; LE cert will issue at cutover):
  - `kctl-dokploy -p idtpp deploy apply -f instances/production/tpp-infra-mattermost-sg-prod.yaml --skip-preflight`
  - `kctl-dokploy -p idtpp deploy apply -f instances/production/mac-infra-mattermost-sg-prod.yaml --skip-preflight`
- [ ] Verify containers healthy on tpp-prod-06: `docker ps` shows 2× mattermost + 2× postgres healthy.
- [ ] Verify each MM answers internally:
  - `docker exec <mm-container> curl -s http://localhost:8065/api/v4/system/ping` → `{"status":"OK"}`
- [ ] Patch each instance's Calls plugin config (in its `mm-config` volume `config.json`): set
  `udpserverport`/`tcpserverport` = the instance's `MM_CALLS_PORT`, `icehostoverride` = `5.223.69.142`,
  `Enable=true`, `defaultenabled=true`; restart the container. Confirm "rtc: server is listening on udp …:<port>".

---

## 5. Phase 2 — Bulk file copy (live, no downtime) + verify gate

Run **on tpp-prod-06** (rclone present; copy goes Germany→SG directly). Repeat per tenant.

- [ ] Configure an rclone remote for the source bucket using the source env creds (env-var config, not persisted):
```bash
export RCLONE_CONFIG_HZ_TYPE=s3 RCLONE_CONFIG_HZ_PROVIDER=Other
export RCLONE_CONFIG_HZ_ACCESS_KEY_ID=<from source env MM_FILESETTINGS_AMAZONS3ACCESSKEYID>
export RCLONE_CONFIG_HZ_SECRET_ACCESS_KEY=<from source env>
export RCLONE_CONFIG_HZ_ENDPOINT=https://fsn1.your-objectstorage.com
```
- [ ] Find the destination volume path (Mattermost local storage root):
```bash
DST=$(docker volume inspect -f '{{.Mountpoint}}' <proj>_mm-data)/   # files live at the data root
```
- [ ] **Bulk copy** (keys → identical relative paths; MM local layout == S3 layout):
```bash
rclone copy hz:hz-tpp-mattermost-data "$DST" --transfers 16 --checksum --stats 10s
```
- [ ] **VERIFY GATE — must be clean before proceeding:**
```bash
rclone check hz:hz-tpp-mattermost-data "$DST" --checksum    # expect "0 differences found"
rclone size  hz:hz-tpp-mattermost-data                      # expect 1309 obj / 687319065 (mm)  | 2096 / 412458738 (mac)
find "$DST" -type f | wc -l                                 # destination object count == source
```
- [ ] `chown -R` the copied files to the container's mattermost uid (so MM can read them).
- [ ] Repeat for mac (`hz-mac-mattermost-data` → mac instance volume).

---

## 6. Phase 3 — Dry-run DB restore + integrity validation (no downtime)

- [ ] Dump source DB (read-only on source) and restore into the SG instance postgres:
```bash
# on source server:
docker exec <src-pg> pg_dump -U mmuser -Fc mattermost > /tmp/mm.dump
# transfer to SG, then:
docker exec -i <sg-pg> pg_restore -U mmuser -d mattermost --clean --if-exists < /tmp/mm.dump
```
- [ ] **Attachment integrity check** — every FileInfo path must exist on disk (100% of files):
```bash
docker exec <sg-pg> psql -U mmuser -d mattermost -tAc \
  "SELECT path FROM fileinfo WHERE deleteat=0" > /tmp/paths.txt
missing=0; while read p; do [ -f "$DST$p" ] || { echo "MISSING: $p"; missing=$((missing+1)); }; done < /tmp/paths.txt
echo "missing files: $missing"   # MUST be 0
```
  Also check thumbnails/previews (`*_thumb.jpg`, `*_preview.jpg`) for image FileInfos.
- [ ] Validate app via `--resolve` (force hostname→SG IP) with a local admin account: open a channel, open an existing attachment, confirm it renders.
- [ ] Record validation results. If `missing > 0` or `rclone check` not clean → **STOP**, do not cut over.

---

## 7. Phase 4 — Cutover (maintenance window, ~20–30 min/tenant)

> Announce maintenance to users. Do one tenant fully, verify, then the other.

- [ ] **Freeze source:** stop the source Mattermost container (postgres stays up for the final dump):
  `docker stop <src-mattermost>` (users see "cannot reach" — start of window).
- [ ] **Final incremental file sync** (catches anything uploaded since Phase 2):
  `rclone sync hz:<bucket> "$DST" --checksum` → then re-run the `rclone check` gate (0 differences).
- [ ] **Final DB dump + restore** (now frozen): repeat Phase 3 dump/restore.
- [ ] **Re-run the FileInfo-path integrity check** → missing MUST be 0.
- [ ] **Flip DNS** (Cloudflare, grey-cloud):
  - `kctl-cf -p idtpp records update <id> --type A --name mm --content 5.223.69.142 --no-proxied`
  - same for `mac-mm`, and point the RTC records (`calls.idtpp.com` + mac's calls record) → 5.223.69.142.
- [ ] **Update SG instance** SITEURL/domain to the real host if it was staged; ensure Dokploy domain = real host so **Traefik issues the LE cert** (verify `https://mm.idtpp.com` returns 200 with a valid LE cert within ~60 s).
- [ ] **Smoke test on the real domain:** SSO login (Authentik), open an old attachment, upload a new one, start a voice call. Confirm latency (~22 ms) and that history/files are intact.
- [ ] End maintenance window. Repeat for the second tenant.

---

## 8. Phase 5 — Post-cutover

- [ ] **Configure SG backups:** nightly `pg_dump` (existing `mm-backup` sidecar → Hetzner backup bucket) + nightly `rclone sync` of the local `mm-data` volume → an offsite bucket (durability for local files).
- [ ] Monitor RTC/CPU on tpp-prod-06 for a few days of real calls. If strained → resize to CPX42.
- [ ] Keep **source servers stopped but intact for 2 weeks** (rollback safety). Do not delete source DB/buckets.
- [ ] After the stability window: decommission source MM stacks; retain the Germany buckets a further period as cold backup before deleting.

### Rollback (any time before source teardown)
1. Flip DNS `mm`/`mac-mm` (+ calls records) back to the Germany IPs (178.104.169.250 / .171.122, proxied as before).
2. Start the source Mattermost containers.
3. Any messages/files created on SG during the window would need manual reconciliation — keep the window short and low-traffic (e.g., off-hours) to minimize this.

---

## Appendix A — Per-instance parameters (quick reference)

| | mm.idtpp.com | mac-mm.idtpp.com |
|---|---|---|
| Source server | tpp-prod-04 / 178.104.169.250 | tpp-prod-05 / 178.104.171.122 |
| Source bucket | hz-tpp-mattermost-data (1309 / 655 MB) | hz-mac-mattermost-data (2096 / 393 MB) |
| Source container prefix | compose-back-up-open-source-driver-jkvtl2 | compose-input-bluetooth-pixel-w6wlc6 |
| Authentik provider | id 10 | id 15 |
| SG RTC port | 8466 | 8467 |
| Target | tpp-prod-06 / 5.223.69.142 (local storage) | tpp-prod-06 / 5.223.69.142 (local storage) |

## Appendix B — Optional Cloudflare R2 evaluation (only if ops priorities change)
1. `kctl-cf r2 create mm-sg-files --location apac`; create an R2 API token.
2. Point the `sg-mm` test instance at R2 (`MM_FILESETTINGS_*` → R2 endpoint).
3. From tpp-prod-06: time a GET of a 10 MB object SG→R2 vs local disk read.
4. Expected: local ≈ 0 ms; R2 adds the SG→R2 round-trip per file. Choose R2 only if its durability/zero-egress/offload benefits outweigh that hop (e.g., multi-node or large growth).
