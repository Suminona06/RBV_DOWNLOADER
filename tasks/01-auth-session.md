# TASK-01: Autentikasi & Manajemen Sesi (SSO + Captcha Solver)

## 📌 Gambaran Umum
Fitur ini bertanggung jawab untuk menangani seluruh proses autentikasi ke portal Ruang Baca Virtual (RBV) Universitas Terbuka (`https://pustaka.ut.ac.id/reader/`). Fitur harus mendukung dua metode masuk: login kredensial langsung (dengan pemecah captcha otomatis) dan impor *session cookie* untuk pengguna SSO Microsoft Office 365 (`ecampus.ut.ac.id`).

---

## 🎯 Target Berkas
- `src/ut_rbv/core/auth.py`
- `src/ut_rbv/core/session.py`
- `tests/test_auth.py`

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Login Kredensial Langsung dengan Auto-Captcha
Sebagai mahasiswa dengan akun RBV/Tuton, saya ingin memasukkan username dan password tanpa harus mengetik captcha manual, sehingga proses otomatisasi berjalan lancar tanpa intervensi manusia.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Sistem mampu mendeteksi form login saat mengakses `index.php?modul={KODE}`.
- [x] Sistem mengekstrak teks pertanyaan matematika dari tag label captcha (contoh: `"Berapa hasil dari 7 + 8 ="`).
- [x] Sistem mengevaluasi operator dasar (`+`, `-`, `*`, `x`, `/`, `:`) dan menghasilkan jawaban integer yang tepat.
- [x] Sistem mengirim POST request dengan payload:
  ```json
  {
    "_submit_check": "1",
    "username": "<USERNAME>",
    "password": "<PASSWORD>",
    "ccaptcha": "<HASIL_PERHITUNGAN>",
    "submit": "Submit"
  }
  ```
- [x] Jika kredensial salah, sistem memunculkan exception `InvalidCredentialsError` yang informatif.

### User Story 2: Impor Sesi SSO Microsoft Office 365
Sebagai mahasiswa yang menggunakan login SSO `ecampus.ut.ac.id`, saya ingin menggunakan *session cookie* dari browser saya agar tidak terhalang oleh mekanisme 2FA/SSO Microsoft.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Sistem menerima argumen string cookie (contoh: `"PHPSESSID=38fe76d..."` atau file cookie).
- [x] Sistem menginjeksi cookie ke sesi HTTP dan memvalidasi apakah sesi tersebut aktif.
- [x] Jika sesi kedaluwarsa, sistem memberikan pesan peringatan yang jelas dan petunjuk cara memperbarui cookie.

### User Story 3: Session Persistence & Re-auth
Sebagai sistem pengunduh, sesi harus bertahan lama selama proses pengunduhan berjalan.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Kredensial atau cookie disimpan sementara dalam sesi terisolasi (tidak diekspos ke log publik).
- [x] Jika respons server tiba-tiba mengembalikan halaman form login ("About RBV V.2"), sistem otomatis memicu re-autentikasi tanpa membuat proses unduh terhenti (*fail-safe*).

---

## 🛠️ Langkah Implementasi Teknis

1. **Buat Exception Khusus di `core/auth.py`:**
   - `AuthError` (Base)
   - `InvalidCredentialsError`
   - `CaptchaSolveError`
   - `SessionExpiredError`
2. **Implementasikan `solve_math_captcha(html_text: str) -> str`:**
   - Gunakan `BeautifulSoup` atau regex untuk menemukan input `name="ccaptcha"`.
   - Ambil teks instruksi sebelumnya, ekstrak angka A, operator O, dan angka B.
   - Kembalikan nilai string hasil kalkulasi.
3. **Implementasikan `SessionManager` di `core/session.py`:**
   - Gunakan `httpx.AsyncClient` atau `requests.Session` dengan default header browser:
     ```python
     DEFAULT_HEADERS = {
         "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
         "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
     }
     ```
   - Sediakan method `login_with_credentials(username, password)`.
   - Sediakan method `set_session_cookie(cookie_str)`.
   - Sediakan method `is_authenticated() -> bool`.

---

## 🧪 Rencana Pengujian
- Unit test regex captcha dengan berbagai variasi teks:
  - `"Berapa hasil dari 12 + 5 ="` -> `17`
  - `"Berapa hasil dari 20 - 7 ="` -> `13`
  - `"Berapa hasil dari 4 x 6 ="` -> `24`
- Mock response form login HTML dan verifikasi payload POST yang dikirimkan.
