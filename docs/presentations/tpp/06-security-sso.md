## Keamanan & Akses Terpusat / Security & Single Sign-On

**Satu pintu masuk untuk semua sistem. Satu tombol untuk menutup semua akses.**

---

### 1. Single Sign-On (SSO) — Satu Login untuk Semua

Dengan Platform Ini, setiap karyawan TPP hanya perlu **satu username dan satu password** untuk mengakses seluruh ekosistem digital perusahaan:

- Odoo Trading ✓
- Odoo HRMS ✓
- Email @idtpp.com ✓
- Zulip Chat ✓
- SFA App ✓
- WMS App ✓
- HRM App ✓
- BIA App ✓
- Website Admin ✓

> **9 sistem, 1 login. Tidak perlu ingat 9 password berbeda.**

Tidak ada lagi sticky note di meja, tidak ada lagi "lupa password" yang menghambat kerja, tidak ada lagi password yang dishare antar kolega via WhatsApp.

---

### 2. Karyawan Resign? Satu Klik. Selesai.

Ini adalah fitur yang paling dirasakan manfaatnya oleh manajemen. Mari kita bandingkan situasi nyata yang terjadi hari ini versus dengan platform ini.

#### Sekarang — Tanpa SSO

Saat karyawan resign atau diberhentikan, ini yang harus dilakukan secara manual:

- Ganti password Accurate — *kalau ingat, dan kalau tahu siapa yang perlu dihubungi*
- Cabut dari grup WhatsApp — *tapi chat history perusahaan tetap ada di HP mereka*
- Email Gmail pribadi yang pernah menerima file perusahaan? *Masih ada di sana, selamanya*
- Google Sheet yang pernah dibagikan? *Masih bisa diakses sampai ada yang ingat untuk menghapus sharing-nya*
- Akses sistem lain yang mungkin terlupakan? *Tidak ada yang tahu pasti*

**Hasil:** Proses berhari-hari. Manual. Tidak pernah tuntas. Risiko kebocoran data nyata — dan tidak bisa diaudit.

#### Dengan Platform Ini SSO

Saat karyawan resign atau diberhentikan:

1. Admin menonaktifkan 1 akun di Authentik (sistem SSO)
2. **Dalam hitungan detik** — akses ke seluruh 9 sistem langsung terputus
3. Email @idtpp.com: tidak bisa login
4. Zulip Chat: tidak bisa masuk
5. Odoo ERP: tidak bisa masuk
6. SFA, WMS, HRM, BIA App: tidak bisa masuk
7. Website Admin: tidak bisa masuk

**Data tetap aman di server perusahaan.** Tidak ada yang pergi bersama karyawan tersebut.

> **"Satu klik. Selesai. Aman."**

Tidak ada yang terlewat. Tidak ada yang lupa. Tidak ada risiko.

---

### 3. Siapa Bisa Lihat Apa — Role-Based Access Control (RBAC)

Setiap karyawan hanya melihat yang perlu mereka lihat untuk bekerja, tidak lebih. Ini bukan hanya soal keamanan — ini juga soal fokus dan kejelasan tanggung jawab.

| Jabatan / Role | Bisa Akses | Tidak Bisa Akses |
|---|---|---|
| **Staff Gudang** | WMS, data stok & penerimaan barang | Data keuangan, margin, data gaji |
| **Tim Sales** | SFA, daftar produk & harga jual | Data cost/HPP, inventory edit, data HR |
| **HR / Personalia** | HRMS, data karyawan & absensi | Margin trading, data supplier, laporan keuangan |
| **Finance / Accounting** | Laporan keuangan, AP/AR, Odoo | Data HR rahasia, edit gaji |
| **Management** | Dashboard overview semua departemen | *(full access atau read-only sesuai kebutuhan)* |

> **Prinsip "least privilege"** — setiap orang mendapat akses minimum yang diperlukan untuk menjalankan tugasnya, tidak lebih.

Ketika ada perubahan jabatan atau tanggung jawab, akses bisa disesuaikan dalam hitungan menit — bukan berhari-hari menghubungi berbagai pihak.

---

### 4. Fitur Keamanan Tambahan

**Password Policy**
Sistem memastikan password yang digunakan memenuhi standar keamanan minimum — panjang, kombinasi karakter, dan opsional masa berlaku password.

**Two-Factor Authentication (2FA)**
Tersedia dan bisa diaktifkan per role atau per individu. Untuk akun dengan akses tinggi (Finance, Management), 2FA bisa diwajibkan — sehingga meski password bocor, akun tetap aman.

**HTTPS / TLS Encryption**
Semua komunikasi antara perangkat karyawan dan server TPP dienkripsi. Data tidak bisa disadap, bahkan di jaringan publik sekalipun.

**Audit Trail Lengkap**
Sistem mencatat siapa login, kapan, dari perangkat mana, dan mengakses apa. Jika ada insiden keamanan, investigasi bisa dilakukan dengan data yang lengkap — bukan mengandalkan ingatan orang.

**Tidak Ada Shared Password**
Setiap karyawan memiliki credential sendiri. Jika terjadi masalah, accountability jelas — bisa ditelusuri ke individu, bukan ke "akun bersama" yang tidak jelas siapa yang menggunakannya.

---

### 5. Before vs After — Ringkasan

| Aspek | Sekarang | Dengan Platform Ini |
|---|---|---|
| Jumlah password per orang | 4+ password berbeda | 1 (SSO) |
| Proses offboarding karyawan | Berhari-hari, manual, tidak tuntas | Detik, otomatis, tuntas |
| Audit trail akses | Tidak ada | Lengkap & bisa dicari |
| Role-based access | Terbatas, sulit dikelola | Granular per sistem, mudah diubah |
| Two-Factor Authentication (2FA) | Tidak ada | Tersedia, bisa diwajibkan |
| Shared passwords | Umum terjadi | Tidak diperbolehkan oleh sistem |

---

> **"Keamanan bukan fitur tambahan — ini adalah fondasi.**
> **Setiap data TPP dilindungi, setiap akses tercatat, dan setiap karyawan hanya melihat yang perlu mereka lihat."**
