## Komunikasi Terpadu / Unified Communications

**Komunikasi bisnis yang terorganisir, aman, dan milik perusahaan — bukan di HP pribadi karyawan.**

---

### Situasi Hari Ini

WhatsApp telah menjadi tulang punggung komunikasi TPP — dan itu wajar. Platform ini mudah, semua orang sudah pakai, dan tidak memerlukan setup apapun. Namun seiring bisnis yang berkembang, kebutuhan komunikasi juga berkembang. Yang cukup untuk 10 orang belum tentu cukup untuk 50 orang — dan yang cukup untuk hari ini belum tentu aman untuk tahun depan.

*Today, WhatsApp is the backbone of TPP's communication — and that makes sense. It's familiar, fast, and requires no setup. But as the business grows, communication needs grow too. What works for 10 people may not scale to 50 — and what's convenient today may carry real risk tomorrow.*

---

### Pilar 1: Email Perusahaan — @idtpp.com

**Platform: Mailcow (self-hosted)**

#### Identitas Profesional

Setiap email keluar dari TPP hari ini — ke supplier, ke customer, ke mitra — dikirim dari alamat Gmail pribadi karyawan. Ini bukan soal teknologi, ini soal kesan pertama.

> **"Email dari budi.santoso@gmail.com vs budi.santoso@idtpp.com — mana yang lebih meyakinkan bagi supplier di luar negeri?"**

Email @idtpp.com menyampaikan pesan yang jelas: ini organisasi yang serius, terstruktur, dan profesional. Bagi mitra internasional, ini standar minimum yang diharapkan.

*Every outbound email from TPP today — to suppliers, customers, partners — is sent from a personal Gmail address. This is not a technology issue; it's a first impression issue. An @idtpp.com address signals to international partners that TPP is a serious, structured organization. For many overseas suppliers, this is a baseline expectation.*

#### Data Milik Perusahaan, Bukan Milik Karyawan

Ketika karyawan menggunakan Gmail pribadi untuk urusan bisnis, seluruh riwayat korespondensi — negosiasi harga, konfirmasi PO, kontrak — tersimpan di akun pribadi mereka. Ketika karyawan resign, data itu ikut pergi.

Dengan Mailcow self-hosted di server TPP: karyawan resign hari ini, akses dinonaktifkan hari ini, email tetap ada dan bisa diakses manajemen. Data tetap milik perusahaan.

*When staff use personal Gmail for business, all correspondence history — price negotiations, PO confirmations, contracts — lives in their personal accounts. When they leave, that data leaves with them. With Mailcow hosted on TPP's own server: employee exits today, access is revoked today, emails remain and management can access them. Data stays with the company.*

#### Keamanan Built-In

| Fitur | Fungsi |
|-------|--------|
| **ClamAV** | Anti-virus — lampiran berbahaya diblokir sebelum sampai ke inbox |
| **Rspamd** | Anti-spam — email phishing dan spam difilter otomatis |
| **DKIM/SPF/DMARC** | Email TPP tidak masuk folder spam di penerima — deliverability tinggi |

DKIM/SPF/DMARC adalah protokol standar yang membuktikan kepada server email penerima bahwa email memang dikirim dari TPP, bukan dari pihak yang menyamar sebagai TPP.

#### Akses Fleksibel

- Webmail di browser: bisa diakses dari komputer mana saja
- App HP (IMAP): tersambung ke Gmail, Apple Mail, atau app email lainnya
- Tidak perlu ganti kebiasaan — cukup ganti alamat email

---

### Pilar 2: Team Chat — Zulip

**Platform: Zulip**

#### Komunikasi yang Terorganisir, Bukan Satu Grup Besar

Zulip menggunakan struktur **Stream** (saluran topik) dan **Topic** (thread diskusi) — komunikasi bisnis tersusun rapi, mudah dicari, dan tidak bercampur dengan hal-hal yang tidak relevan.

Contoh nyata untuk operasional TPP:

| Stream | Topic | Isi Diskusi |
|--------|-------|-------------|
| `#import-ops` | Container LC-2026-042 — ETA & customs clearance | Koordinasi pengiriman, update bea cukai, dokumen LC |
| `#sales` | Target Q2 review — progress per region | Review pencapaian target, breakdown per area |
| `#finance` | AR aging report — follow up outstanding | Koordinasi penagihan piutang jatuh tempo |
| `#hr` | Jadwal cuti bersama Lebaran 2026 | Pengumuman, persetujuan jadwal cuti |

Setiap diskusi ada konteksnya. Tidak perlu scroll ke atas ratusan pesan untuk menemukan keputusan yang diambil minggu lalu.

*Every discussion has its context. No more scrolling through hundreds of messages to find a decision made last week.*

#### History yang Bisa Dicari

> **"Keputusan apa yang diambil soal supplier X bulan Agustus tahun lalu?"**

Di WhatsApp: scroll ke atas, mungkin ketemu, mungkin tidak — dan hanya bisa dicari per chat.

Di Zulip: ketik keyword, hasil muncul dalam detik, dari semua stream, semua topik, semua waktu. Pengetahuan perusahaan tidak hilang hanya karena ada yang resign atau ganti HP.

*In Zulip: type a keyword, results appear in seconds, across all streams, all topics, all time. Company knowledge does not disappear when someone resigns or changes phones.*

#### File Sharing yang Aman

Dokumen yang dikirim di Zulip tersimpan di server perusahaan — bukan di HP pribadi karyawan, bukan di cloud pihak ketiga tanpa kontrol. Akses bisa diatur, bisa dicabut, dan ada audit trail lengkap.

#### Single Sign-On (SSO)

Login Zulip menggunakan credential yang sama dengan Odoo dan email @idtpp.com. Satu username, satu password, semua sistem. Karyawan baru aktif dalam satu langkah — karyawan resign dinonaktifkan dari semua sistem sekaligus.

---

### Pilar 3: Smart Alerts — Telegram Bots

**Bukan untuk chatting — untuk notifikasi otomatis yang actionable.**

Manajemen mendapat informasi penting tanpa perlu buka aplikasi, tanpa perlu tanya ke tim, tanpa perlu menunggu laporan mingguan. Alert dikirim otomatis ke Telegram ketika ada sesuatu yang perlu perhatian.

*Management receives critical information without opening another app, without asking the team, without waiting for the weekly report. Alerts are sent automatically to Telegram when something needs attention.*

#### Contoh Alert yang Terkirim Otomatis ke Management

```
SALES ALERT
Sales target achieved: Tim Jakarta 110% of target
Selamat — target bulan ini tercapai lebih awal dari jadwal.
```

```
PROCUREMENT ALERT
New PO pending approval — Rp 450 juta
Status: Waiting > 24 hours — action required
[Buka Odoo untuk approve]
```

```
INVENTORY ALERT
Low stock: Product ABC-123
Current: 47 units | Minimum threshold: 100 units
Reorder diperlukan sebelum akhir minggu.
```

```
SYSTEM ALERT
Backup completed successfully
All 14 services backed up — 2026-04-07 02:00 WIB
Storage used: 84 GB | Status: OK
```

```
SYSTEM WARNING
Server health: disk usage 85%
Server: kod-prod-01 | Volume: /data
Tindakan diperlukan dalam 48 jam.
```

Setiap alert dirancang untuk satu tujuan: informasi yang tepat, ke orang yang tepat, pada waktu yang tepat — tanpa noise.

---

### Masalah WhatsApp — Penilaian Risiko

WhatsApp bukan alat yang buruk. Untuk komunikasi personal, ia sangat baik. Namun untuk komunikasi bisnis perusahaan yang berkembang, ia membawa risiko yang perlu dipahami secara jelas — bukan sebagai kritik, melainkan sebagai penilaian risiko yang jujur.

*WhatsApp is not a bad tool. For personal communication, it excels. But for a growing company's business communication, it carries risks that need to be understood clearly — not as criticism, but as an honest risk assessment.*

---

#### Risiko Data

**Data di HP pribadi karyawan.**
Setiap percakapan bisnis — negosiasi harga dengan supplier, persetujuan PO, history komunikasi dengan customer — tersimpan di HP pribadi karyawan. Ketika karyawan resign, semua data itu ikut pergi. Tidak ada cara untuk menariknya kembali.

**HP hilang atau dicuri.**
Satu HP yang hilang bisa mengekspos seluruh riwayat komunikasi bisnis — termasuk informasi pricing, nama supplier, dan detail kontrak yang seharusnya bersifat rahasia perusahaan.

---

#### Risiko Operasional

**Tidak ada audit trail.**
"Siapa yang approve PO ini? Kapan disetujui? Apa kondisinya?"
Di WhatsApp, jawabannya: scroll ke atas, cari di chat, mungkin ketemu — mungkin sudah dihapus.

**Tidak ada organisasi.**
Bisnis bercampur dengan chat pribadi, stiker, forward berita, dan hal-hal yang tidak relevan. Tidak ada cara untuk memisahkan komunikasi bisnis dari noise.

**Approval macet saat manager tidak tersedia.**
Manager cuti dua minggu — siapa yang approve PO? Di WhatsApp, tidak ada mekanisme delegasi. Bisnis terhenti karena komunikasi tergantung pada satu orang di satu grup chat.

**Pengetahuan perusahaan tidak bisa dicari.**
Keputusan yang diambil enam bulan lalu, negosiasi yang terjadi setahun lalu — hilang di antara ribuan pesan yang tidak bisa dicari secara efektif.

---

#### Risiko Kepatuhan

**Tidak ada kontrol admin.**
Tidak ada cara untuk menegakkan kebijakan komunikasi perusahaan di WhatsApp. Siapapun bisa membuat grup, menambah siapapun, dan membagikan informasi apapun.

**Karyawan resign masih punya akses.**
Setelah keluar dari perusahaan, mantan karyawan masih menjadi anggota grup chat bisnis — masih bisa membaca history, masih bisa melihat update terbaru. Tidak ada mekanisme offboarding yang efektif.

**Tidak ada retensi dan backup.**
Chat bisa dihapus — oleh siapapun, kapanpun. Tidak ada backup bisnis, tidak ada jaminan ketersediaan data untuk keperluan audit atau dispute.

---

#### Perbandingan Langsung

| | WhatsApp | Zulip + Email + Telegram |
|--|----------|--------------------------|
| **Kepemilikan data** | Di HP karyawan | Di server perusahaan |
| **Audit trail** | Tidak ada | Lengkap dan tercatat |
| **Organisasi** | Satu grup campur aduk | Stream & topic terstruktur |
| **Search** | Terbatas per chat | Lintas semua history |
| **Kontrol admin** | Tidak ada | Penuh — kebijakan bisa ditegakkan |
| **Offboarding** | Manual, tidak tuntas | Otomatis via SSO — satu klik |
| **Backup** | Tidak ada | Terjadwal, terverifikasi |
| **Delegasi approval** | Tidak ada | Workflow terstruktur di Odoo |

---

### Pilar 4: Integrasi Mendalam dengan Odoo — Komunikasi yang Hidup

**Inilah yang membedakan platform ini dari sekadar "punya email dan chat."**

Semua kanal komunikasi — email, Zulip, Telegram, bahkan WhatsApp — terhubung langsung ke Odoo. Bukan koneksi manual, bukan copy-paste. Otomatis, real-time, dan cerdas.

*This is what separates this platform from just "having email and chat." Every communication channel — email, Zulip, Telegram, even WhatsApp — connects directly to Odoo. Not manually, not copy-paste. Automatic, real-time, and intelligent.*

---

#### Odoo → Zulip: Notifikasi Bisnis Otomatis

Ketika sesuatu terjadi di Odoo, Zulip langsung tahu — tanpa ada orang yang perlu mengirim pesan manual.

| Event di Odoo | Notifikasi di Zulip | Stream / Topic |
|--------------|---------------------|----------------|
| **Sales Order dikonfirmasi** | "SO-2026-0042 confirmed — Rp 180 juta — Customer: PT ABC" | `#odoo-notifications` > Sales |
| **Invoice diposting** | "INV-2026-0128 posted — Rp 95 juta — Due: 2026-05-07" | `#odoo-notifications` > Invoice |
| **Pengiriman selesai** | "Delivery DO-0089 completed — 50 cartons to PT ABC" | `#odoo-notifications` > Delivery |
| **Purchase Order di-approve** | "PO-2026-0015 approved — Rp 320 juta — Vendor: Shanghai Trading" | `#odoo-notifications` > Purchase |
| **Approval menunggu** | DM langsung ke reviewer: "PO-0015 needs your approval — Rp 320 juta" | Direct Message |

**Fitur lanjutan:**
- **Daily Digest**: Setiap pagi, ringkasan otomatis di Zulip — berapa approval yang menunggu, berapa invoice yang overdue
- **Overdue Invoice Alert**: Tabel otomatis dikirim ke stream Finance — siapa yang belum bayar, berapa lama, total outstanding
- **Approval Workflow Integration**: Ketika PO butuh persetujuan, reviewer mendapat DM di Zulip. Bisa approve langsung. Jika reviewer tidak tersedia — delegasi otomatis ke atasan

---

#### Odoo → Telegram: Alert Cerdas untuk Management

Tidak semua notifikasi perlu masuk Zulip. Yang penting dan mendesak dikirim langsung ke Telegram management.

| Event di Odoo | Alert Telegram |
|--------------|----------------|
| Sales order besar dikonfirmasi | "Sales Alert: SO baru Rp 450 juta dari PT XYZ — confirmed" |
| Invoice posted | "Finance: Invoice INV-0128 posted — Rp 95 juta — due 30 hari" |
| Delivery selesai | "Logistics: DO-0089 delivered — 50 cartons to PT ABC" |
| PO menunggu approval > 24 jam | "Action Required: PO-0015 Rp 320 juta — pending > 24 hours" |

**Cara kerjanya:**
- Odoo mendeteksi perubahan status (misalnya: SO dari draft → confirmed)
- Rule otomatis mengevaluasi: apakah event ini perlu dikirim ke Telegram?
- Jika ya, pesan dikirim dalam detik — langsung ke HP management
- Setiap rule bisa dikonfigurasi: model mana, status apa, kirim ke siapa

*Odoo detects a state change. Rules automatically evaluate whether the event warrants a Telegram alert. If yes, the message arrives on management's phone within seconds.*

---

#### Odoo → Email (@idtpp.com): Transaksional Otomatis

Odoo mengirim email transaksional melalui server Mailcow @idtpp.com — bukan melalui pihak ketiga.

| Email Otomatis | Penerima | Trigger |
|---------------|----------|---------|
| Quotation PDF | Customer | Sales order created |
| Invoice PDF | Customer | Invoice posted |
| Payment confirmation | Customer | Payment received |
| Delivery notification | Customer | Stock picking validated |
| PO confirmation | Supplier | Purchase order confirmed |

- Semua email keluar dengan domain @idtpp.com — profesional dan konsisten
- DKIM/SPF/DMARC memastikan email tidak masuk spam
- Email history tersimpan di server — audit trail lengkap

---

#### Odoo → WhatsApp: Notifikasi Customer Otomatis

Untuk customer yang sudah terbiasa dengan WhatsApp, sistem bisa mengirim notifikasi otomatis:

| Trigger di Odoo | Pesan WhatsApp ke Customer |
|----------------|---------------------------|
| **Invoice jatuh tempo** | "Yth. Bapak/Ibu {nama}, invoice {no_invoice} sejumlah {amount} telah jatuh tempo. Mohon untuk segera melakukan pembayaran. Terima kasih — TPP" |
| **Quotation dikirim** | "Yth. {nama}, quotation {no_SO} senilai {amount} telah kami kirimkan. Silakan review. — TPP" |
| **Pengiriman dalam perjalanan** | "Yth. {nama}, pesanan {no_SO} sedang dikirim via {carrier}. No. resi: {tracking}. — TPP" |

**Fitur anti-deteksi:**
- Pesan dikirim dengan pola manusiawi — bukan blast massal
- Typing indicator muncul dulu, delay proporsional dengan panjang pesan
- Rate-limited: maksimum 1 pesan per 30 detik
- "Sistem mengirim seperti manusia — bukan robot"

---

#### WhatsApp → Odoo: Customer Inquiry Otomatis

Ketika customer mengirim pesan WhatsApp yang mengandung kata kunci bisnis (nomor SO, nomor invoice, "order status", "delivery", "payment"), sistem secara otomatis:

1. Menerima pesan via WAHA (WhatsApp API self-hosted — server sendiri, bukan Meta cloud)
2. Mengklasifikasikan pesan: apakah bisnis atau umum?
3. Jika bisnis → diteruskan ke Odoo untuk ditindaklanjuti (create lead / update record)

**Alur lengkap:**
```
Customer WhatsApp
    ↓
WAHA (WhatsApp API — server sendiri)
    ↓
Bridge Service (klasifikasi otomatis)
    └── Jika kata kunci bisnis terdeteksi → Odoo (create lead / update record)
    
Odoo memproses inquiry → Tim sales/CS ditugaskan otomatis
```

**Siap diaktifkan:** Platform customer service (Chatwoot) juga tersedia untuk TPP — memungkinkan agent membalas WhatsApp customer dari satu dashboard terpusat, tanpa perlu buka WhatsApp di HP. Aktivasi sesuai kebutuhan.

---

#### Satu Ekosistem, Semua Terhubung

```
┌─────────────────────────────────────────────────────────┐
│                     ODOO (ERP)                          │
│         Satu Sumber Kebenaran untuk Semua Data          │
│                                                         │
│  Sales ─── Purchase ─── Inventory ─── Finance ─── HR   │
└───┬──────────┬──────────────┬──────────────┬────────────┘
    │          │              │              │
    ▼          ▼              ▼              ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌────────────────┐
│ Zulip  │ │Telegram│ │  Email   │ │   WhatsApp     │
│        │ │  Bots  │ │@idtpp.com│ │  (via WAHA)    │
│ Team   │ │        │ │          │ │                │
│ Chat   │ │ Alert  │ │Transak-  │ │ Customer       │
│ +Notif │ │ Cerdas │ │ sional   │ │ Notification   │
│ +Digest│ │ ke Mgmt│ │ Otomatis │ │ + Inquiry      │
└────────┘ └────────┘ └──────────┘ └────────────────┘
    │          │              │              │
    └──────────┴──────────────┴──────────────┘
                      │
              Semua terintegrasi
              Semua otomatis
              Semua tercatat
```

**Yang tidak bisa dilakukan WhatsApp + Gmail:**
- Mengirim notifikasi otomatis saat SO confirmed ❌
- Mengirim daily digest pending approval ❌
- Meneruskan inquiry customer ke ERP secara otomatis ❌
- Mengirim invoice reminder terjadwal ❌
- Mencatat semua komunikasi bisnis dalam audit trail ❌

**Yang bisa dilakukan platform ini:**
- Semua hal di atas ✅ — otomatis, tercatat, dan terkontrol

---

### Penutup

Tidak ada yang salah dengan cara TPP berkomunikasi selama ini — WhatsApp membawa perusahaan sampai ke titik ini. Yang perlu diubah adalah menyesuaikan alat komunikasi dengan skala bisnis yang akan datang.

*There is nothing wrong with how TPP has communicated so far — WhatsApp brought the company to where it is today. What needs to change is aligning the communication tools with the scale of business that is coming.*

Platform ini bukan hanya "punya email dan chat" — ini adalah **ekosistem komunikasi yang hidup**, terhubung langsung ke jantung operasional bisnis di Odoo. Setiap transaksi menghasilkan notifikasi yang tepat, ke orang yang tepat, di kanal yang tepat — otomatis.

*This is not just "having email and chat" — this is a **living communication ecosystem**, connected directly to the heart of business operations in Odoo. Every transaction generates the right notification, to the right person, on the right channel — automatically.*

---

> **"Dari komunikasi yang tersebar dan rentan, menjadi ekosistem komunikasi yang hidup, terintegrasi, dan sepenuhnya milik perusahaan."**
