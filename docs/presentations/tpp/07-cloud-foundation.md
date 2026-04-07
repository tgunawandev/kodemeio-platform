## Fondasi Cloud / Cloud Foundation

Fondasi teknologi yang tidak terlihat tapi selalu bekerja — melindungi data, menjaga performa, dan memastikan bisnis tetap berjalan.

---

### 1. Keandalan / Reliability

**Infrastruktur kelas enterprise, dirancang untuk bisnis yang tidak boleh berhenti.**

| Komponen | Manfaat untuk TPP |
|----------|-------------------|
| **Hetzner Cloud** | Data center Eropa, sertifikasi ISO 27001, uptime SLA 99.9% — standar yang sama digunakan bank dan perusahaan Fortune 500 |
| **Server dedicated** | Database TPP tidak dicampur dengan perusahaan lain — performa terjamin, data terisolasi |
| **Connection pooling (PgBouncer)** | Tetap cepat dan responsif walau 50+ user akses sistem secara bersamaan |
| **Staging environment** | Uji setiap perubahan dengan aman sebelum diterapkan ke production — tidak ada "coba-coba" di sistem live |

> **Analogi:** Seperti punya 2 gedung kantor — satu untuk kerja sehari-hari, satu untuk uji coba. Perubahan dites dulu, baru diterapkan. Tidak ada risiko sistem tiba-tiba bermasalah karena update yang belum teruji.

---

### 2. Perlindungan Data / Data Protection

**Data adalah aset terpenting bisnis Anda. Kami jaga berlapis.**

- **Backup otomatis harian** — Terenkripsi, tersimpan di lokasi terpisah dari server utama. Bukan di hard disk yang sama — bukan di gedung yang sama.
- **Retensi 30 hari** — Bisa recover data dari hari manapun dalam sebulan terakhir. Kesalahan input data 2 minggu lalu? Bisa dikembalikan.
- **Point-in-time recovery** — Jika diperlukan, data bisa dipulihkan ke jam atau menit tertentu, bukan hanya per hari.
- **Data milik TPP sepenuhnya** — Bisa diekspor kapan saja dalam format standar. Tidak terkunci di satu vendor. Tidak ada ketergantungan paksa.

**Perbandingan situasi sebelum dan sesudah:**

| Kondisi | Risiko | Dengan Platform Ini |
|---------|--------|-----------------|
| Accurate di 1 komputer | Hard disk rusak = data hilang permanen | Backup otomatis harian, recovery kapan saja |
| Google Sheets | Google bisa ubah kebijakan, naikkan harga, tutup akun sewaktu-waktu | Data di server dedicated TPP sendiri |
| Tanpa backup strategy | Tidak ada jalan kembali jika terjadi kesalahan | 30 hari retensi, point-in-time recovery |

> **Prinsip sederhana:** Data Anda adalah milik Anda. Bukan milik Google, bukan milik vendor software, bukan milik siapapun selain TPP.

---

### 3. Monitoring 24/7 / Round-the-Clock Monitoring

**Kami tahu ada masalah sebelum Anda menyadarinya. Dan biasanya sudah diperbaiki sebelum Anda bertanya.**

Sistem monitoring berjalan penuh waktu, mengawasi seluruh infrastruktur TPP secara otomatis:

- **Grafana dashboards** — Kesehatan semua 13 layanan TPP dalam satu tampilan. Tim engineering bisa melihat kondisi sistem secara real-time kapanpun dibutuhkan.
- **Prometheus metrics** — CPU, memory, disk, dan response time semua terukur dan tercatat. Anomali terdeteksi otomatis.
- **Loki logs** — Log aplikasi yang bisa dicari — untuk troubleshooting cepat jika ada insiden.
- **GlitchTip error tracking** — Tim engineering tahu ada error di aplikasi sebelum user melaporkannya.
- **Telegram alerts** — Notifikasi otomatis ke tim engineering dalam hitungan detik jika ada yang tidak beres.
- **20 alert rules aktif** — Mencakup infrastructure, container, endpoint, dan stack-level issues — tidak ada celah yang terlewat.

> Tidak ada orang yang perlu "mengecek manual" apakah sistem berjalan. Sistem yang memonitor dirinya sendiri dan melaporkan masalah secara proaktif.

---

### 4. Infrastruktur TPP

Gambaran sederhana bagaimana semua lapisan bekerja bersama melindungi bisnis TPP:

```
Internet
  └── Cloudflare (CDN + proteksi DDoS)
        └── Traefik (reverse proxy + SSL otomatis)
              ├── 13 layanan TPP
              │     (Odoo ERP, apps, email, chat, dll.)
              │       ├── PostgreSQL 16 (database dedicated)
              │       ├── Redis (cache untuk performa)
              │       └── S3 Storage (backup terenkripsi)
              └── Monitoring & Alerting
                    ├── Grafana + Prometheus (monitoring 24/7)
                    ├── GlitchTip (error tracking)
                    └── Telegram Bot (alert otomatis)
```

Setiap lapisan memiliki peran spesifik:

| Lapisan | Peran |
|---------|-------|
| **Cloudflare** | Pintu masuk pertama — blokir serangan sebelum sampai ke server |
| **Traefik** | Pengatur lalu lintas — arahkan request ke layanan yang tepat, SSL otomatis |
| **13 layanan TPP** | Aplikasi bisnis yang berjalan — Odoo, email, chat, dan lainnya |
| **Database dedicated** | Penyimpanan data utama — dedicated untuk TPP, tidak dibagi |
| **Backup S3** | Salinan data terenkripsi di lokasi terpisah — jaring pengaman terakhir |
| **Monitoring stack** | Pengawas 24/7 — deteksi dan alerting otomatis |

---

**Data Anda dilindungi berlapis — dari server dedicated, backup otomatis, sampai monitoring 24/7. Bisnis bisa fokus pada operasional, bukan khawatir soal teknologi.**
