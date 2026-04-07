# TPP C-Level Presentation — Design Spec

## Purpose

Create a bilingual (EN/ID) markdown-based executive presentation for PT Pakerti Trading (TPP) C-level leadership, demonstrating the full Kodemeio enterprise technology platform.

## Context

### Audience
- TPP C-level executives (directors, commissioners)
- Technical knowledge: minimal ("they know they have an app")
- Language: Bilingual English/Bahasa Indonesia

### Goal
Build **confidence and trust** — "Our technology is enterprise-grade, your operations are in good hands, this justifies the investment."

### Business Context
- TPP is an **import & trading company** (idtpp.com)
- Domain recently migrated to idtpp.com

### Current State (Before Kodemeio)
| Tool | Current Usage | Pain Points |
|------|--------------|-------------|
| **WhatsApp** | Primary communication, approval workflows, status updates, info sharing | No audit trail, data on personal phones, lost in chat scroll, no delegation, approval by emoji, mixing personal/work, employee leaves = data gone |
| **Personal Gmail** | Business email | No company identity (@gmail.com), no admin control, no compliance, no spam/virus protection |
| **Accurate** | ERP (accounting, inventory) | Local install, single machine, no mobile access, no real-time multi-user, limited import/trading features, no multi-currency/landed costs |
| **Google Sheets** | Custom reporting, data tracking | Manual data entry, version conflicts ("final_v3_REAL.xlsx"), no real-time data, formula breakdowns, no access control, copy-paste errors |

### TPP Kodemeio Deployment (13 Services)
**Production instances (kod-prod-01):**
- `tpp-odoo-trad` — Odoo 18 Trading (import/export, multi-currency, landed costs, SFA+BIA+WMS apps)
- `tpp-odoo-hrms` — Odoo 18 HRMS (employees, attendance, payroll, leaves, expenses, HRM app)
- `tpp-react-sfa` — Sales Force Automation mobile PWA
- `tpp-react-wms` — Warehouse Management mobile PWA
- `tpp-react-hrm` — Human Resource Management mobile PWA
- `tpp-react-bia` — Business Intelligence & Analytics PWA
- `tpp-nextjs-web` — Corporate website (idtpp.com)
- `tpp-nextjs-careers` — Careers portal
- `tpp-hono-notify` — Real-time notification service
- `tpp-infra-authentik` — SSO/identity provider
- `tpp-infra-mailcow` — Company email (@idtpp.com)
- `tpp-infra-postgres` — Dedicated database
- `tpp-infra-alloy` — Monitoring agent

**Staging instances (kod-prod-02):** 9 services mirroring production for safe testing

**Shared infrastructure (used by TPP):**
- Grafana monitoring stack (Prometheus + Loki + Alertmanager)
- GlitchTip error tracking
- Redis caching
- Zulip team chat
- Telegram bot alerts

## Narrative Strategy

### Core Message
"TPP is moving from fragmented consumer-grade tools to an integrated enterprise technology ecosystem — purpose-built for import & trading operations."

### Storytelling Arc
1. **Recognition** — "This is what we do today" (validate current reality, no blame)
2. **Revelation** — "This is what's now possible" (show the transformation)
3. **Evidence** — "Here's what's already built and running" (prove it's real, not vapor)
4. **Vision** — "Here's what we can activate next" (show growth path)

### Tone
- Respectful of current tools (they got TPP this far)
- Confident but not arrogant
- Business language first, tech as proof
- Bilingual: English headers/terms, Indonesian explanations where natural

## Document Structure

### Output Location
```
docs/presentations/tpp/
├── 00-cover-executive-summary.md
├── 01-before-after.md
├── 02-odoo-single-source-of-truth.md
├── 03-mobile-apps-power.md
├── 04-hrms-advantage.md
├── 05-unified-communications.md
├── 06-security-sso.md
├── 07-cloud-foundation.md
├── 08-cost-analysis.md
├── 09-whats-next.md
├── 10-platform-summary.md
└── README.md
```

### Section Details

#### 00 — Cover + Executive Summary
- Title: "Transformasi Digital PT Pakerti Trading"
- Subtitle: "Enterprise Technology Platform — Dibangun untuk Import & Trading"
- One-paragraph summary (EN + ID)
- Key headline stat: "13 layanan terintegrasi menggantikan 4 alat terpisah"
- Visual concept: before (4 scattered icons) → after (unified ecosystem)

#### 01 — Before & After (Sebelum & Sesudah)
- Full comparison table: WhatsApp/Gmail/Accurate/Sheets vs Kodemeio stack
- Each row: pain point → solution → business impact
- Specific scenarios TPP will recognize:
  - "Approval PO via WhatsApp — siapa yang approve? kapan? scroll ke atas..."
  - "Laporan bulanan dari 3 Google Sheet yang berbeda, data tidak cocok"
  - "Karyawan resign, chat history WhatsApp hilang"
  - "Accurate hanya bisa diakses dari 1 komputer di kantor"

#### 02 — Odoo: Single Source of Truth (Satu Sumber Kebenaran)
- What "single source of truth" means in business terms
- Two Odoo instances explained:
  - **Trading**: Purchase orders, import management, multi-currency, landed costs, inventory, sales, accounting — all connected
  - **HRMS**: Employee database, attendance, leave, payroll (BPJS, PPh 21), expenses
- Key message: "Data mengalir otomatis — tidak perlu ketik ulang"
- Approval workflows: tracked, delegated, SLA-enforced (vs WhatsApp thumbs-up)
- Contrast with Accurate: cloud vs local, multi-user vs single-user, mobile vs desktop-only

**Custom Reporting Engine (vs Google Sheets):**
- 15 specialized report modules built into the platform — all pulling live data from ERP (no manual entry)
- Report categories available to TPP:
  - **Financial**: P&L, Balance Sheet, Cash Flow, Trial Balance, PSAK-compliant Indonesian formats (Neraca, Laba Rugi, Arus Kas, Perubahan Ekuitas, Buku Besar, Rasio Keuangan)
  - **Sales & AR**: Sales analytics, AR aging, customer performance, revenue analysis
  - **Purchase & AP**: Vendor performance, AP aging, purchase order tracking
  - **Cash & Bank**: Cash/bank ledger, receipts, disbursements, cash flow tracking
  - **Tax Compliance**: PPN (VAT), PPh 21/23/25, e-Faktur, WHT — Indonesian tax reports ready to file
  - **SFA (Sales Force)**: Activity, performance, coverage, collection, effective calls, revenue growth, KPI reports (10 report types)
  - **Inventory**: Stock balance, stock movement, stock card, inventory valuation, warehouse analytics
  - **HR & Payroll**: Attendance, payroll summary, employee performance, HR KPIs
  - **Expense**: By employee, by category, approval status, reimbursement tracking
  - **Approval**: Pending approvals, history, turnaround time analysis
- Export formats: Excel, PDF, HTML — no more copy-paste from system to spreadsheet
- AI-powered insights and recommendations on reports
- Report scheduling: auto-generate and distribute reports on schedule
- ECharts visualizations: interactive charts, not flat spreadsheet tables
- Drill-down: click any number to see the underlying transactions
- Key contrast: "Google Sheets = ketik manual, data kemarin. Odoo Reports = data real-time, otomatis."

**Budget Management:**
- Budget creation with line items linked to GL accounts
- Budget by department, operating unit, and project
- Approval workflows for budget submissions
- Automatic actual vs budget comparison from posted journal entries
- Variance analysis (amount and percentage)
- Rolling forecast support
- Key contrast: "Budget di Google Sheet = angka mati. Budget di Odoo = hidup, otomatis dibandingkan dengan aktual."

**Document Reports (report_layout):**
- Professional branded document templates replacing manual formats:
  - Invoice (PPN/PPH23 compliant), Sales Order, Purchase Order
  - Delivery Order (DO), Surat Jalan, Goods Receipt, BAST
  - Picking List, Packing List, Shipping Manifest
  - Payment reports, Credit notes, Miscellaneous journals
- All auto-generated from ERP data — no manual formatting

#### 03 — Power of Mobile Apps (Kekuatan Aplikasi Mobile)
Each app gets a "Tanpa → Dengan" (Without → With) story:

**SFA (Sales Force Automation)**
- Without: Sales team reports via WhatsApp photos, manual order recap, no visit verification
- With: GPS check-in/out, instant order entry, customer visit history, offline mode for remote areas, dashboard targets
- TPP relevance: Track sales team visits to trading partners, instant order pipeline visibility

**WMS (Warehouse Management)**
- Without: Paper-based picking, manual stock counting, "where is this item?"
- With: Barcode scanning, location-guided picking, real-time stock accuracy, FEFO for perishables, cycle counting
- TPP relevance: Import container receiving, put-away, accurate stock for trading operations

**HRM (Human Resource Management)**
- Without: Manual attendance sheets, leave requests via WhatsApp, payslip by email/print
- With: GPS clock-in/out, self-service leave requests, payslip on phone, expense claims with photo receipts
- TPP relevance: Field staff attendance, transparent payroll, paperless HR

**BIA (Business Intelligence & Analytics)**
- Without: Monthly Excel reports compiled manually from multiple Google Sheets
- With: Live dashboards, KPI tracking, drill-down reports, auto-generated from real ERP data
- TPP relevance: Sales performance, inventory levels, financial overview — real-time on your phone

All apps: installable on phone (PWA), work offline, no app store needed

#### 04 — HRMS Advantage (Keunggulan HRMS)
- Full Indonesian labor law compliance built-in:
  - BPJS Kesehatan & Ketenagakerjaan
  - PPh 21 calculation (progressive rates)
  - PTKP (tax allowance by marital status)
  - UMR/UMP regional minimum wage
- Employee lifecycle: recruit → onboard → manage → offboard
- Self-service: employees handle their own leave, expenses, payslips
- Manager visibility: team calendar, approval queues, department analytics
- Fraud prevention: GPS-verified attendance (no "titip absen")
- Cost: replaces separate HR software + manual payroll calculation

#### 05 — Unified Communications (Komunikasi Terpadu)
Three communication pillars replacing WhatsApp + Gmail:

**Company Email (@idtpp.com) — Mailcow**
- Professional identity (not @gmail.com to suppliers/customers)
- Company owns all email data (employee leaves, email stays)
- Spam/virus protection (ClamAV + Rspamd)
- DKIM/SPF/DMARC (emails don't land in spam)
- Webmail + mobile app access

**Team Chat — Zulip**
- Organized by topics within streams (not one endless group chat)
- Searchable history (find any decision ever made)
- File sharing with company control
- Topic threads: "#purchasing > Container XYZ update" vs lost in WhatsApp scroll
- Company owns all data

**Smart Alerts — Telegram Bots**
- Automated notifications: server health, sales targets achieved, low stock warnings
- Not for chatting — for **business intelligence alerts**
- Instant notification to management when something needs attention

**The WhatsApp Problem (detailed):**
- Data lives on personal phones — employee leaves, data walks out the door
- No audit trail — "siapa yang approve ini? scroll ke atas 3 bulan"
- No topic organization — business mixed with personal chats
- No delegation — manager on leave, approvals stuck
- No search across history — institutional knowledge lost
- No admin control — can't enforce policies, can't revoke access

#### 06 — Security & SSO (Keamanan & Akses Terpusat)
- **Single Sign-On (SSO)**: One username/password for everything
  - Odoo Trading ✓ Odoo HRMS ✓ Email ✓ Chat ✓ Mobile Apps ✓ Website Admin ✓
- **Employee offboarding**: Disable one account = locked out of ALL systems instantly
  - vs current: need to change passwords on each system, revoke WhatsApp group access, hope they deleted company data from phone
- **Role-based access**: Warehouse staff can't see financials, HR can't see trading margins
- **Password policies**: Enforced strength, optional 2FA
- **All traffic encrypted**: HTTPS/TLS everywhere
- **No shared passwords**: Each person has their own credentials
- **Audit trail**: Know who accessed what and when

#### 07 — Cloud Foundation (Fondasi Cloud)
Presented as "what protects your business" not as technical specs:

**Reliability:**
- Hetzner Cloud (European data center, ISO 27001 certified)
- Dedicated database server (not shared with other companies)
- Connection pooling for performance under load
- Staging environment: test changes safely before going live

**Data Protection:**
- Automated daily backups (encrypted)
- 30-day retention (recover data from any day in the last month)
- Point-in-time recovery capability
- Data belongs to TPP (not locked in a SaaS vendor)

**Monitoring (24/7):**
- Grafana dashboards: real-time health of all services
- Prometheus metrics: server performance, response times
- Loki logs: searchable application logs
- GlitchTip: knows about application errors before users report them
- Telegram alerts: engineering team notified within seconds of any issue

**Cost Advantage:**
- Self-hosted on Hetzner (not expensive SaaS subscriptions per-user)
- No per-user licensing fees that grow with headcount
- One platform vs paying for: ERP + HR software + email service + chat tool + BI tool + monitoring
- Data sovereignty: TPP owns everything, can export anytime

#### 08 — Cost Analysis (Analisis Biaya)
Present what TPP would need to pay if they bought equivalent capabilities as separate SaaS subscriptions:

**SaaS Equivalent Comparison (per month, estimated):**
| Capability | SaaS Alternative | Est. Cost/month |
|-----------|-----------------|----------------|
| ERP (Trading) | SAP Business One / Oracle NetSuite | $2,000 - $5,000+ |
| HRMS + Payroll | Talenta / Gadjian Pro | $500 - $1,500 |
| Sales Force Automation | Salesforce Essentials | $750 - $2,000 |
| Warehouse Management | Fishbowl / Cin7 | $500 - $1,500 |
| Business Intelligence | Tableau / Power BI Pro | $500 - $1,000 |
| Company Email (50 users) | Google Workspace / M365 | $300 - $600 |
| Team Chat | Slack Business+ | $400 - $800 |
| SSO / Identity | Okta / Auth0 | $300 - $1,000 |
| Monitoring | Datadog / New Relic | $500 - $1,500 |
| Error Tracking | Sentry Business | $100 - $300 |
| Backup & DR | Managed backup service | $200 - $500 |
| Website + Careers | WordPress + hosting | $100 - $300 |
| **Total (SaaS)** | **12+ vendors to manage** | **$6,150 - $16,000/mo** |
| **Kodemeio Platform** | **1 integrated platform** | **Fraction of above** |

**Hidden costs of SaaS avoided:**
- Per-user licensing fees that scale with headcount
- Integration costs between 12+ different vendors
- Data migration costs when switching vendors
- Vendor lock-in (your data format, their rules)
- Annual price increases (typically 5-15%/year)
- Implementation consultants per system
- Training for 12 different interfaces

**Kodemeio cost advantages:**
- Self-hosted: infrastructure cost is fixed (Hetzner servers), not per-user
- Open source base: no licensing fees for Odoo Community + OCA modules
- One platform: one login, one data model, one training
- Data ownership: export everything, no lock-in
- Scale freely: add users without per-seat cost increase

*Note: Exact Kodemeio pricing to be filled by Tri based on TPP's actual contract*

#### 09 — What's Next (Langkah Selanjutnya)
Modules ready to activate when TPP is ready (no new development needed):

| Module | Business Value | Ready? |
|--------|---------------|--------|
| **LFA** (Logistics) | Track deliveries, route optimization, proof of delivery with photo | Ready |
| **Shop** (B2B Portal) | Let customers order online 24/7, real-time stock/pricing | Ready |
| **DMS** (Distribution) | Manage distributors, territories, agreements, primary orders | Ready |
| **TPM** (Trade Promotions) | Plan promotions, manage funds, track ROI | Ready |
| **EAM** (Asset Management) | Track company assets, maintenance schedules, depreciation | Ready |
| **OpenCloud** (File Storage) | Company file storage, document collaboration (replace Google Drive) | Ready |
| **Plane** (Project Management) | Track internal projects, assign tasks, deadlines | Ready |

Message: "Ini bukan roadmap — ini sudah dibangun. Tinggal diaktifkan."

#### 10 — Platform Summary (Ringkasan Platform)
The "wow" numbers in a clean visual layout:

**What TPP Gets Today:**
- 13 integrated services (production)
- 9 staging services (safe testing environment)
- 4 mobile apps (offline-capable, installable, no app store)
- 2 ERP instances (Trading + HRMS)
- 2 websites (corporate + careers)
- Company email (@idtpp.com) with spam/virus protection
- Team chat (organized, searchable, company-owned)
- Single Sign-On (one login for everything)
- Automated daily backups (encrypted, 30-day retention)
- 24/7 real-time monitoring with instant alerts
- Full Indonesian HR/payroll compliance
- Staging environment for safe testing
- Dedicated engineering support

**What It Replaces:**
- WhatsApp (for business communication & approvals)
- Personal Gmail (for company email)
- Accurate (for ERP/accounting)
- Google Sheets (for reporting & data tracking)

**The Bottom Line:**
"Satu platform terintegrasi. Data mengalir otomatis. Keputusan berdasarkan data real-time. Bisnis Anda terlindungi."

## Self-Review Checklist
- [x] No TBD/TODO placeholders (one intentional note for Tri to fill actual pricing)
- [x] All sections consistent with each other
- [x] Scope is focused (TPP only, C-level only)
- [x] No ambiguous requirements
- [x] All TPP services accurately listed (verified from tenant config: 13 production, 9 staging)
- [x] Before/after comparisons are fair and accurate
- [x] No technical jargon without business explanation
- [x] Bilingual balance is natural (not forced translation)
- [x] Custom reporting capabilities highlighted (15 report modules + budget management)
- [x] Cost analysis section with SaaS comparison
- [x] WhatsApp/Gmail/Accurate/Sheets pain points woven throughout
