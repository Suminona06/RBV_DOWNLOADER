# UT-RBV Downloader 📚

Alat pengunduh otomatis Buku Materi Pokok (BMP) dari Ruang Baca Virtual (RBV) Universitas Terbuka (`pustaka.ut.ac.id`) menjadi dokumen PDF berkualitas tinggi, dilengkapi dengan **Table of Contents (Bookmarks)** dan **Searchable Text Layer**.

---

## 📑 Dokumentasi Kebutuhan Produk (PRD)

Dokumen spesifikasi lengkap telah disusun di:
👉 **[PRD_UT_RBV_DOWNLOADER.md](file:///home/itpc/UT-RBV/PRD_UT_RBV_DOWNLOADER.md)**

### Ringkasan Fitur Utama:
1. **Dukungan Autentikasi Ganda:**
   - Login form RBV/Tuton otomatis dengan auto-solver matematika captcha.
   - Dukungan SSO Microsoft Office 365 (`ecampus.ut.ac.id`) via import session cookie `PHPSESSID`.
2. **Mesin Unduh Cerdas (Smart Async Fetcher):**
   - Unduh paralel adaptif dengan rate-limiting beretika (tidak membebani server UT).
   - Fitur *Resumable Download* (melanjutkan unduhan yang terputus menggunakan cache disk lokal).
3. **Penyusunan PDF Unggul:**
   - Injeksi teks transparan langsung dari format `.jsonp` RBV tanpa perlu OCR lambat (teks dapat dicari dan disalin).
   - Injeksi hierarki daftar isi (*bookmarks/outlines*) otomatis.
   - Optimasi kompresi ukuran file (hemat kuota dan memori tablet/smartphone).
4. **Fleksibilitas Antarmuka:**
   - Mode CLI interaktif (dengan progress bar berwarna).
   - Mode Local Web Dashboard / Desktop GUI untuk pengguna non-teknis.

---

## 🚀 Panduan Instalasi & Penggunaan

### 1. Prasyarat & Instalasi
Pastikan sistem telah terpasang **Python 3.10+**.

```bash
# Clone repositori
git clone git@github.com:Suminona06/RBV_DOWNLOADER.git
cd RBV_DOWNLOADER

# Buat virtual environment & aktifkan
python3 -m venv .venv
source .venv/bin/activate

# Install aplikasi
pip install -e .
```

Setelah instalasi, perintah `ut-rbv` akan langsung tersedia di terminal Anda.

---

### 2. Penggunaan Antarmuka Baris Perintah (CLI)

#### A. Memeriksa Informasi Buku (`inspect`)
Sebelum mengunduh, Anda dapat memeriksa daftar modul dan jumlah halaman:
```bash
ut-rbv inspect EKMA4111
```

#### B. Mengunduh Buku (`download`)

1. **Menggunakan Cookie Sesi (Rekomendasi untuk Akun SSO ECAMPUS):**
   ```bash
   ut-rbv download EKMA4111 --cookie "PHPSESSID=isi_token_cookie_anda"
   ```
   *Tip: Cara mendapatkan cookie `PHPSESSID`: Login ke pustaka.ut.ac.id di browser, buka Developer Tools (F12) -> tab Application/Storage -> Cookies -> salin nilai `PHPSESSID`.*

2. **Menggunakan NIM dan Password (dengan Auto-Solver Captcha):**
   ```bash
   ut-rbv download EKMA4111 -u "012345678" -p "password_anda"
   ```
   Atau simpan kredensial ke environment variable:
   ```bash
   export UT_USERNAME="012345678"
   export UT_PASSWORD="password_anda"
   ut-rbv download EKMA4111
   ```

3. **Opsi Lanjutan:**
   - **Pilih modul tertentu saja:**
     ```bash
     ut-rbv download EKMA4111 --modules "1,2,3"
     # atau rentang modul:
     ut-rbv download EKMA4111 --modules "1-4"
     ```
   - **Pisahkan file per modul (tidak digabung):**
     ```bash
     ut-rbv download EKMA4111 --split
     ```
   - **Tingkat kompresi gambar:**
     ```bash
     ut-rbv download EKMA4111 --compress high   # high (kecil), medium (default), none (kualitas asli)
     ```
   - **Tentukan folder tujuan:**
     ```bash
     ut-rbv download EKMA4111 --output "./my_books"
     ```

---

### 3. Penggunaan Antarmuka Web Dashboard (GUI Browser)

Bagi pengguna yang lebih menyukai antarmuka visual grafis, jalankan server lokal:

```bash
ut-rbv web
```
Perintah ini akan menyalakan server lokal dan otomatis membuka browser ke:
👉 **`http://127.0.0.1:8000`**

**Fitur Web Dashboard:**
- 🔍 **Cari & Periksa Katalog:** Masukkan kode mata kuliah (cth: `EKMA4111`), sistem akan menampilkan detail buku, nama penulis, dan daftar modul.
- ☑️ **Pilih Modul:** Checklist modul mana saja yang ingin diunduh.
- ⚙️ **Konfigurasi Fleksibel:** Pengaturan gabung PDF (*Merge*) serta tingkat kompresi citra.
- 📊 **Visual Progress Bar Real-time:** Menampilkan persentase selesai, halaman terunduh, dan log tahapan.
- 📥 **One-Click Download:** Tombol unduh langsung berkas PDF yang telah selesai dirakit.

---

### 4. Menjalankan Rangkaian Pengujian (Testing)

```bash
pytest -v --cov=ut_rbv
```

## ⚖️ Catatan Hak Cipta & Penggunaan Beretika (Fair Use)

Materi Buku Materi Pokok (BMP) adalah milik dan dilindungi hak cipta Universitas Terbuka. Perkakas ini dirancang khusus untuk memfasilitasi mahasiswa aktif UT membaca materi perkuliahan secara offline (*personal study fair use*). Dilarang keras memperjualbelikan atau menyebarluaskan hasil unduhan ke ranah publik.
