# Odoo: Satu Sumber Kebenaran untuk Bisnis TPP
## Single Source of Truth — TPP (idtpp.com)

---

## A. Apa Itu "Satu Sumber Kebenaran"?

> **"Semua data bisnis — pembelian, penjualan, inventory, keuangan, HR — ada di satu tempat. Tidak perlu ketik ulang. Tidak ada data yang bertentangan antar sistem."**

### Kondisi Saat Ini vs Odoo

| Kondisi Saat Ini | Dengan Odoo |
|---|---|
| Accurate di 1 komputer untuk akuntansi | Satu sistem cloud, akses dari mana saja |
| Google Sheets untuk laporan & budget | Laporan real-time, otomatis dari data transaksi |
| WhatsApp untuk approval PO & pembayaran | Approval workflow terstruktur, terlacak, ada SLA |
| Data di 3 tempat berbeda — sering tidak cocok | Satu database, satu kebenaran |
| Rekonsiliasi manual setiap bulan | Tidak ada rekonsiliasi — data sudah sinkron |

### Aliran Data yang Terintegrasi (Satu Klik, Satu Aliran)

```
Purchase Order
     ↓
Goods Receipt (Penerimaan Barang)
     ↓
Inventory (Stok otomatis terupdate)
     ↓
Invoice Vendor
     ↓
Payment & Jurnal Otomatis
     ↓
Laporan Keuangan Real-Time
```

**Tidak ada satu data pun yang diketik dua kali.** Setiap transaksi mengalir otomatis dari awal hingga laporan akhir.

---

## B. Dua Odoo Instance untuk TPP

TPP menjalankan **dua sistem Odoo terpisah** — satu untuk operasional bisnis, satu untuk SDM — keduanya terhubung.

---

### B1. Odoo Trading (`tpp-odoo-trad`) — Inti Operasional Bisnis

**Dirancang khusus untuk perusahaan impor & trading.**

#### Import & Multi-Currency
- Transaksi dalam **USD, EUR, JPY, CNY** — konversi ke IDR otomatis sesuai kurs terkini
- **Landed cost** (ongkos kirim, bea masuk, asuransi, biaya pelabuhan) dihitung dan dialokasikan otomatis ke **Harga Pokok Penjualan (HPP)**
- Tidak ada lagi hitung manual di Excel untuk landed cost

#### Alur Operasional Penuh

| Tahap | Modul | Manfaat |
|---|---|---|
| Purchase Order | Purchasing | Multi-currency, approval workflow |
| Penerimaan Barang | Inventory / WMS | Stok terupdate real-time |
| Inventory Management | Warehouse | FIFO/AVCO, multi-gudang |
| Sales Order | Sales / SFA | Terhubung ke tim lapangan via mobile |
| Invoicing | Accounting | Invoice otomatis dari SO, compliant PPN |
| Pembayaran | Accounting | Rekonsiliasi bank otomatis |
| Laporan | BI & Reporting | 40+ laporan siap pakai |

#### Approval Workflow — Bukan WhatsApp Lagi

- **PO Approval**: Setiap Purchase Order di atas nilai tertentu wajib approval berjenjang
- **Payment Approval**: Pembayaran diverifikasi sebelum dieksekusi
- Setiap approval **tercatat siapa, kapan, dan berapa nilainya** — bukan sekadar centang di grup WA
- Ada **SLA (batas waktu respons)** — tidak bisa diabaikan

#### Terhubung ke Mobile Apps
- **SFA** (Sales Force Automation) — tim penjualan di lapangan
- **WMS** (Warehouse Management) — staf gudang
- **BIA** (Business Intelligence & Analytics) — dashboard eksekutif

#### Perbandingan: Accurate vs Odoo Trading

| | Accurate (Saat Ini) | Odoo Trading |
|---|---|---|
| Akses | 1 komputer, 1 user | Cloud, semua tim, dari mana saja |
| Multi-currency | Manual/terbatas | USD, EUR, JPY, CNY otomatis |
| Landed cost | Hitung manual | Otomatis ke HPP |
| Approval | WhatsApp | Workflow terstruktur dengan SLA |
| Laporan | Export manual | Real-time, terjadwal, drill-down |
| Mobile | Tidak ada | SFA, WMS, BIA |

---

### B2. Odoo HRMS (`tpp-odoo-hrms`) — Manajemen SDM

**Dari absensi hingga slip gaji — semua otomatis.**

#### Alur SDM yang Terintegrasi

```
Data Karyawan → Absensi → Cuti → Penggajian → Slip Gaji
```

#### Fitur Utama

| Fitur | Detail |
|---|---|
| **Database Karyawan** | Profil lengkap, dokumen, riwayat jabatan |
| **Attendance** | Integrasi mesin absensi / mobile check-in |
| **Leave Management** | Pengajuan, approval, saldo cuti — semua online |
| **Payroll** | Penggajian otomatis dari data absensi & cuti |
| **Slip Gaji** | Digital, bisa diakses karyawan via portal |
| **BPJS Kesehatan & TK** | Perhitungan iuran otomatis sesuai regulasi |
| **PPh 21 & PTKP** | Pajak penghasilan karyawan — built-in, bukan hitung manual |
| **Expense Claims** | Pengajuan & approval klaim biaya karyawan |

#### Terhubung ke Mobile App
- **HRM App** — karyawan bisa cek slip gaji, ajukan cuti, klaim expense dari smartphone

---

## C. Custom Reporting Engine — 15 Modul Laporan

> **"Google Sheets = ketik manual, data kemarin, formula bisa rusak. Odoo Reports = data real-time, otomatis, akurat, bisa dijadwalkan."**

Ini adalah **pengganti total Google Sheets** untuk pelaporan bisnis TPP.

### Kategori Laporan

#### Laporan Keuangan
| Laporan | Keterangan |
|---|---|
| Profit & Loss (P&L) | Laba rugi per periode, per divisi |
| Neraca (Balance Sheet) | Posisi keuangan real-time |
| Arus Kas (Cash Flow) | Aliran kas masuk & keluar |
| Trial Balance | Saldo semua akun |
| Buku Besar (General Ledger) | Detail setiap jurnal per akun |
| Rasio Keuangan | Likuiditas, profitabilitas, solvabilitas |

Format sesuai **PSAK Indonesia** — siap untuk audit dan pelaporan ke bank/investor.

#### Sales & Piutang
- Analitik penjualan per produk, pelanggan, wilayah, sales rep
- **Aging piutang** — siapa yang belum bayar, sudah berapa lama
- Performa customer — repeat order, nilai transaksi, tren

#### Purchase & Hutang
- Performa vendor — ketepatan pengiriman, harga, kualitas
- **Aging hutang** — kewajiban yang jatuh tempo
- Tracking status PO dari pemesanan hingga penerimaan

#### Kas & Bank
- Buku kas dan buku bank per akun
- Laporan penerimaan & pengeluaran harian
- Posisi kas real-time

#### Pajak & Kepatuhan
| Jenis Pajak | Fitur |
|---|---|
| PPN | Laporan pajak keluaran & masukan, siap e-Faktur |
| PPh 21 | Pajak gaji karyawan otomatis |
| PPh 23 | Withholding tax jasa & royalti |
| PPh 25 | Cicilan pajak badan |
| e-Faktur | Format CSV siap upload ke DJP |

#### SFA (Sales Force Automation) — 10 Tipe Laporan
- Activity report — kunjungan & aktivitas sales
- Performance report — target vs realisasi per sales
- Coverage report — area yang dikunjungi
- Collection report — penagihan piutang
- KPI dashboard — pencapaian per individu & tim
- Revenue growth — tren pertumbuhan

#### Inventory & Gudang
- Stock balance per lokasi, per produk, per kategori
- Stock movement — masuk, keluar, transfer
- Stock card — riwayat lengkap per item
- Inventory valuation — nilai stok (FIFO/AVCO)
- Analytics gudang — perputaran stok, dead stock

#### HR & Payroll
- Laporan absensi — per karyawan, per departemen
- Ringkasan penggajian — total biaya SDM per bulan
- KPI karyawan — pencapaian target individu

#### Expense & Approval
- Klaim per karyawan & per kategori
- Status approval real-time
- Turnaround time — berapa lama approval berjalan

### Fitur Teknis Laporan

| Fitur | Detail |
|---|---|
| **Export** | Excel, PDF, HTML — satu klik |
| **Drill-down** | Klik angka → lihat transaksi di baliknya |
| **Jadwal Otomatis** | Laporan dikirim ke email setiap Senin pagi, misalnya |
| **AI Insights** | Anomali & tren otomatis disorot |
| **Grafik Interaktif** | ECharts — bar, line, pie, heatmap |
| **Filter Fleksibel** | Per periode, departemen, proyek, cost center |

---

## D. Budget Management — Anggaran yang Hidup

> **"Budget di Google Sheet = angka mati, harus cross-check manual. Budget di Odoo = hidup, otomatis dibandingkan dengan realisasi setiap hari."**

### Fitur Budget Management

| Fitur | Manfaat Bisnis |
|---|---|
| **Budget per Departemen** | Setiap kepala divisi pegang anggarannya sendiri |
| **Budget per Operating Unit** | Pisah anggaran per unit bisnis / cabang |
| **Budget per Proyek** | Kontrol biaya proyek impor atau ekspansi |
| **Terhubung ke GL** | Budget langsung terkait ke akun buku besar |
| **Actual vs Budget Otomatis** | Perbandingan update setiap ada jurnal diposting |
| **Variance Analysis** | Selisih nominal & persentase — langsung kelihatan |
| **Rolling Forecast** | Proyeksi ulang berdasarkan realisasi berjalan |
| **Approval Workflow** | Pengajuan budget disetujui berjenjang, terdokumentasi |

### Contoh Dashboard Budget

```
Departemen: Operasional — April 2026

  Budget    :  Rp 850.000.000
  Aktual    :  Rp 623.000.000  (73,3%)
  Sisa      :  Rp 227.000.000
  Variance  :  -26,7% (Under Budget)  ← hijau, bagus
  Forecast  :  Rp 840.000.000  (projected full month)
```

Angka ini tersedia **setiap saat**, bukan hanya saat tim finance selesai rekap di akhir bulan.

---

## E. Document Reports — Dokumen Bisnis Profesional

> **"Tidak perlu format manual di Word/Excel — semua keluar dari sistem, konsisten, profesional, compliant."**

Setiap dokumen bisnis TPP di-generate otomatis dari data ERP — dengan template berlogo perusahaan, sudah terformat, dan compliant terhadap regulasi.

### Daftar Dokumen

| Kategori | Dokumen |
|---|---|
| **Penjualan** | Sales Order, Invoice (PPN/PPh23 compliant), Credit Note |
| **Pembelian** | Purchase Order, Goods Receipt |
| **Logistik** | Delivery Order (DO), Surat Jalan, Picking List, Packing List, Shipping Manifest |
| **Penerimaan** | Berita Acara Serah Terima (BAST) |
| **Keuangan** | Payment Receipt, Bukti Bank Masuk/Keluar |

### Keunggulan

- **Branded** — logo, warna, footer perusahaan sudah built-in
- **Compliant** — format invoice sesuai ketentuan PPN & PPh 23
- **Konsisten** — tidak ada format berbeda antar staff
- **Otomatis** — satu klik dari transaksi → dokumen siap kirim ke customer/vendor
- **Digital** — bisa dikirim via email langsung dari sistem, tidak perlu print dulu

---

## Penutup: Keputusan Berbasis Data yang Sama

**Dengan satu sumber kebenaran, setiap keputusan didasarkan pada data yang sama — akurat, real-time, dan dapat dipertanggungjawabkan.**

Tidak ada lagi:
- "Data saya beda dengan data Finance"
- "Belum bisa laporan, masih nunggu rekap"
- "Sudah approve di WA tapi tidak ada yang jalankan"
- "Formula Sheets-nya salah, angkanya keliru"

Yang ada:
- **Satu angka** yang disepakati semua departemen
- **Laporan siap** kapan pun dibutuhkan — bukan akhir bulan saja
- **Approval terlacak** — siapa, kapan, berapa, sudah atau belum
- **Data akurat** — karena diinput satu kali, dipakai seluruh perusahaan

---

*Dokumen ini bagian dari presentasi platform digital TPP (idtpp.com)*
*Disiapkan oleh tim teknologi TPP*
