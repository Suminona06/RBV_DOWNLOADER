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

## ⚖️ Catatan Hak Cipta & Penggunaan Beretika (Fair Use)

Materi Buku Materi Pokok (BMP) adalah milik dan dilindungi hak cipta Universitas Terbuka. Perkakas ini dirancang khusus untuk memfasilitasi mahasiswa aktif UT membaca materi perkuliahan secara offline (*personal study fair use*). Dilarang keras memperjualbelikan atau menyebarluaskan hasil unduhan ke ranah publik.
