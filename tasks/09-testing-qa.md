# TASK-09: Pengujian Terotomasi (Unit, Mock & E2E)

## 📌 Gambaran Umum
Fitur ini bertujuan membangun rangkaian pengujian (*test suite*) terotomasi untuk memastikan seluruh komponen aplikasi (pemecah captcha, parser katalog, pengunduh asinkron, perakit PDF, antarmuka CLI, dan dashboard web) berfungsi dengan benar, memiliki toleransi kesalahan yang tinggi, dan tahan terhadap regresi (*regression proof*).

---

## 🎯 Target Berkas
- `tests/test_auth.py`
- `tests/test_catalog.py`
- `tests/test_downloader.py`
- `tests/test_pdf.py`
- `tests/test_cli.py`
- `tests/fixtures/` (HTML sample data, sample image, sample JSONP)

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Unit Testing Komponen Kritis
Sebagai pengembang, saya ingin setiap fungsi logika murni (seperti solver matematika captcha, parser string argumen, kalkulator offset bookmarks) memiliki unit test dengan cakupan kasus tepi (*edge cases*).

**Kriteria Penerimaan (Acceptance Criteria):**
- [ ] Pengujian matematika captcha mencakup operasi penjumlahan, pengurangan, perkalian, dan pembagian.
- [ ] Pengujian parser URL dan sanitasi nama modul (misal `M1.pdf` -> `M1`, handling nama modul dengan spasi atau karakter khusus).
- [ ] Pengujian parser payload JSONP: memvalidasi penanganan callback wrapper dan struktur koordinat teks.

### User Story 2: Pengujian Jaringan Terisolasi (Mock Server)
Sebagai pengembang, saya ingin menjalankan pengujian unduh tanpa perlu terhubung langsung ke server produksi UT atau memerlukan kredensial asli setiap kali tes dijalankan.

**Kriteria Penerimaan (Acceptance Criteria):**
- [ ] Menggunakan library mock HTTP seperti `respx` (untuk `httpx`) atau `pytest-httpx`.
- [ ] Mensimulasikan skenario server UT:
  - Sukses login dan pengunduhan normal.
  - Simulasi error HTTP 429 Too Many Requests untuk memverifikasi exponential backoff.
  - Simulasi sesi kedaluwarsa ("About RBV V.2") untuk memverifikasi re-autentikasi otomatis.
  - Simulasi modul tidak ditemukan (HTTP 404 / empty response).

### User Story 3: Verifikasi Integritas File PDF yang Dihasilkan
Sebagai pengguna, saya ingin memastikan bahwa PDF yang dibuat oleh sistem selalu valid, tidak korup, dan memenuhi standar spesifikasi PDF.

**Kriteria Penerimaan (Acceptance Criteria):**
- [ ] Tes membuka PDF hasil generate dengan `PyMuPDF` tanpa ada peringatan sintaks.
- [ ] Memverifikasi jumlah halaman PDF sesuai dengan jumlah citra input.
- [ ] Memverifikasi bahwa outline / bookmarks yang disuntikkan dapat dibaca kembali dengan struktur hierarki yang benar.
- [ ] Memverifikasi bahwa teks yang disuntikkan dapat dicari menggunakan `doc[page_num].get_text()`.

---

## 🛠️ Langkah Implementasi Teknis

1. **Konfigurasi `pytest` dan `respx` di `pyproject.toml`:**
   ```toml
   [tool.pytest.ini_options]
   testpaths = ["tests"]
   asyncio_mode = "auto"
   ```

2. **Buat Fixture Data di `tests/fixtures/`:**
   - `rbv_login_form.html`: Mock halaman form login dengan captcha.
   - `rbv_module_index.html`: Mock tabel navigasi daftar modul.
   - `sample_page.jsonp`: Mock respons JSONP koordinat teks.
   - `sample_page.jpg`: 1x1 atau 100x100 dummy JPEG image.

3. **Perintah Eksekusi Test:**
   ```bash
   pytest -v --tb=short
   ```

---

## 🧪 Kriteria Sukses
- Seluruh rangkaian test suite lulus 100% (`All tests passed`).
- Test dapat dijalankan di lingkungan CI/CD lokal tanpa ketergantungan koneksi internet eksternal (*hermetic testing*).
