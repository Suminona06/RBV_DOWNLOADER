# TASK-08: Web Dashboard Lokal / GUI Minimalis

## 📌 Gambaran Umum
Bagi pengguna yang tidak terbiasa menggunakan terminal (non-teknis), fitur ini menyediakan antarmuka visual berbasis peramban web lokal (*Local Web Dashboard*) yang ringan dan modern. Dashboard ini dijalankan dengan perintah `ut-rbv web` dan dapat diakses langsung melalui browser di `http://127.0.0.1:8000`.

---

## 🎯 Target Berkas
- `src/ut_rbv/web/app.py`
- `src/ut_rbv/web/templates/index.html`
- `src/ut_rbv/web/static/style.css`
- `src/ut_rbv/web/static/app.js`

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Menjalankan Server Dashboard Lokal
Sebagai pengguna biasa, saya ingin menjalankan perintah sederhana di terminal atau mengklik shortcut untuk membuka halaman grafis di browser saya.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Perintah `ut-rbv web --port 8000` menjalankan server lokal dan otomatis membuka browser bawaan (*auto-open*).
- [x] Server dibangun dengan framework Python asinkron ringan (FastAPI atau Starlette + Uvicorn) tanpa dependensi berat.
- [x] Menampilkan banner status di terminal bahwa web server telah aktif.

### User Story 2: Eksplorasi & Pencarian Modul Visual
Sebagai mahasiswa, saya ingin mengetik kode mata kuliah di kotak pencarian dan melihat thumbnail cover modul beserta checklist bab yang bisa saya pilih dengan mouse.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Form input kode mata kuliah dengan validasi real-time.
- [x] Tombol "Periksa Buku" (*Check Book*): Mengambil metadata dan menampilkan:
  - Judul Buku / Mata Kuliah.
  - Daftar Modul dengan checkbox (default: semua modul tercentang).
  - Estimasi jumlah halaman dan ukuran file.
- [x] Switch toggle opsi: "Gabungkan Semua Modul (Merged PDF)" vs "Unduh Terpisah".

### User Story 3: Visual Progress Bar & Download Langsung
Sebagai pengguna, saya ingin melihat animasi progress bar saat pengunduhan berjalan dan memiliki tombol untuk langsung mengunduh/membuka file PDF yang sudah jadi.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Komunikasi real-time status pengunduhan melalui Server-Sent Events (SSE) atau polling status endpoint.
- [x] Progress bar dinamis (persentase, modul aktif, log terminal).
- [x] Setelah selesai, tampil tombol hijau:
  - "Unduh Berkas ke Browser" (mengunduh berkas langsung dari server lokal ke folder Downloads browser).

---

## 🛠️ Langkah Implementasi Teknis

1. **Backend Server di `src/ut_rbv/web/app.py`:**
   ```python
   from fastapi import FastAPI, BackgroundTasks
   from fastapi.responses import HTMLResponse, FileResponse
   from fastapi.staticfiles import StaticFiles

   app = FastAPI(title="UT-RBV Downloader Web")
   app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

   @app.get("/")
   async def root():
       return FileResponse(TEMPLATE_DIR / "index.html")

   @app.post("/api/inspect")
   async def inspect_book(req: BookInspectRequest):
       ...

   @app.post("/api/download")
   async def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
       ...

   @app.get("/api/progress/{task_id}")
   async def progress_stream(task_id: str):
       # Server-Sent Events (SSE)
       ...
   ```

2. **Frontend UI Minimalis (Glassmorphism & Dark Mode) di `web/templates/index.html`:**
   - Desain bersih bertema modern (warna biru dongker khas akademik dengan aksen cyan/emas).
   - Form kredensial / cookie yang aman.
   - Tanpa framework JavaScript berat (menggunakan Vanilla JS modern + Fetch API/EventSource).

---

## 🧪 Rencana Pengujian
- Test endpoint API `/api/inspect` mengembalikan JSON struktur buku yang valid.
- Test endpoint stream `/api/progress/{task_id}` mengirimkan event progress secara berkala.
- Verifikasi keamanan: server hanya menerima koneksi dari `127.0.0.1` (localhost) demi keamanan data sesi.
