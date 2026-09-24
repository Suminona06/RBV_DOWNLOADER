# TASK-03: Mesin Pengunduh Halaman Asinkron & Cache Lokal

## 📌 Gambaran Umum
Fitur ini adalah mesin inti (*engine*) yang bertugas mengunduh aset halaman (gambar JPEG dan berkas teks JSONP) secara efisien melalui asynchronous HTTP requests. Fitur ini dilengkapi dengan kontrol konkurensi, rate limiter beretika, sistem retry otomatis, serta disk caching granular untuk mendukung fitur *resumable download*.

---

## 🎯 Target Berkas
- `src/ut_rbv/core/downloader.py`
- `src/ut_rbv/utils/paths.py`
- `tests/test_downloader.py`

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Unduhan Asinkron Terkontrol (Concurrency & Rate Limiting)
Sebagai pengguna, saya ingin proses pengunduhan berjalan cepat tanpa memicu pemblokiran IP atau membuat server UT kelebihan beban (*overloaded*).

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Menggunakan asynchronous HTTP client (`httpx.AsyncClient` atau `aiohttp`).
- [x] Mengimplementasikan semaphore untuk membatasi worker simultan (default: 4–6 worker).
- [x] Menerapkan jeda acak (*jitter* 100ms – 250ms) di antara request berturut-turut.
- [x] Menyertakan header HTTP yang sah pada setiap request:
  - `Referer: https://pustaka.ut.ac.id/reader/index.php?modul={KODE}`
  - `User-Agent: Mozilla/5.0 ...`

### User Story 2: Resumable Download & Disk Caching
Sebagai mahasiswa dengan jaringan internet fluktuatif, jika koneksi saya putus di tengah proses, saya ingin proses unduhan melanjutkan dari halaman terakhir yang belum selesai tanpa mengunduh ulang yang sudah ada.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Lokasi cache standar mengikuti aturan OS (`~/.cache/ut-rbv/{KODE_MK}/` atau configurable via env `UT_RBV_CACHE_DIR`).
- [x] Struktur penamaan file cache:
  - Gambar: `{DOC}_{PAGE}.jpg` (contoh: `M1_001.jpg`)
  - Teks: `{DOC}_{PAGE}.json` (contoh: `M1_001.json`)
- [x] Sebelum melakukan request network, sistem memeriksa apakah file cache sudah ada dan memiliki ukuran > 0 bytes:
  - Jika valid, lewati unduhan jaringan (*cache hit*).
  - Jika tidak ada / korup (0 bytes), lakukan unduhan (*cache miss*).

### User Story 3: Toleransi Kegagalan & Exponential Backoff
Sebagai sistem otomatis, jika server merespons dengan status HTTP error (429 Too Many Requests, 500, 502, 504) atau timeout, sistem harus mencoba kembali secara cerdas.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Sistem mencoba kembali (*retry*) hingga maksimal 5 kali per halaman.
- [x] Waktu jeda antar retry meningkat secara eksponensial (misal: 1s, 2s, 4s, 8s, 16s).
- [x] Jika setelah 5 kali retry tetap gagal, halaman ditandai dalam daftar kegagalan dan sistem melanjutkan ke halaman berikutnya agar tidak macet total.
- [x] Menampilkan rekapitulasi halaman yang gagal di akhir proses unduh.

---

## 🛠️ Langkah Implementasi Teknis

1. **Struktur Helper Path di `utils/paths.py`:**
   ```python
   def get_cache_dir(book_code: str) -> Path: ...
   def get_output_dir() -> Path: ...
   ```
2. **Implementasikan `PageDownloader` di `core/downloader.py`:**
   ```python
   class PageDownloader:
       def __init__(self, session_manager, max_concurrency: int = 4):
           self.semaphore = asyncio.Semaphore(max_concurrency)
           ...

       async def download_page(self, section: BookSection, page_num: int, fetch_text: bool = True) -> tuple[Path, Path | None]:
           # 1. Cek disk cache
           # 2. Ambil gambar JPEG
           # 3. Ambil data JSONP (jika fetch_text=True)
           # 4. Simpan ke disk cache
           # 5. Return (image_path, json_path)
   ```
3. **Integrasikan Event Callback untuk Progress Bar:**
   - Parameter callback `on_progress(completed_pages: int, total_pages: int)`.

---

## 🧪 Rencana Pengujian
- Test download task dengan mock server HTTP: verifikasi rate-limiting dan jumlah max concurrent request.
- Test resume capability: buat file mock di folder cache, pastikan tidak ada panggilan network untuk file tersebut.
- Test simulasi HTTP 429 dan 500: verifikasi mekanisme retry dan exponential backoff.
