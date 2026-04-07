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
All 13 services backed up — 2026-04-07 02:00 WIB
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

### Penutup

Tidak ada yang salah dengan cara TPP berkomunikasi selama ini — WhatsApp membawa perusahaan sampai ke titik ini. Yang perlu diubah adalah menyesuaikan alat komunikasi dengan skala bisnis yang akan datang.

*There is nothing wrong with how TPP has communicated so far — WhatsApp brought the company to where it is today. What needs to change is aligning the communication tools with the scale of business that is coming.*

Sistem komunikasi terpadu ini — email @idtpp.com, Zulip, dan Telegram alerts — dirancang bukan untuk menggantikan cara kerja tim, melainkan untuk memberikan fondasi yang aman, terstruktur, dan sepenuhnya milik perusahaan.

---

> **"Dari komunikasi yang tersebar dan rentan, menjadi komunikasi yang terstruktur, aman, dan sepenuhnya milik perusahaan."**
