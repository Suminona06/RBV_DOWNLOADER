# TASK-07: Antarmuka CLI Interaktif (Rich & Click)

## 📌 Gambaran Umum
Fitur ini menyediakan antarmuka baris perintah (*Command Line Interface*) yang elegan, interaktif, dan mudah digunakan bagi mahasiswa serta power user. CLI ini dibangun menggunakan pustaka `click` (untuk struktur perintah dan argumen) serta `rich` (untuk progress bar visual, tabel berwarna, dan status spinner).

---

## 🎯 Target Berkas
- `src/ut_rbv/cli.py`
- `tests/test_cli.py`

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Perintah Unduh Sederhana (One-Liner Download)
Sebagai pengguna, saya ingin cukup mengetikkan perintah `ut-rbv download EKMA4111` di terminal dan aplikasi otomatis menjalankan alur login, deteksi modul, unduh, hingga kompilasi PDF.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Perintah CLI terdaftar global setelah instalasi via `pip install .` atau `pipx`.
- [x] Input kode mata kuliah di-case-insensitive (misal: `ekma4111` otomatis dikonversi ke `EKMA4111`).
- [x] Menampilkan pesan banner pembuka yang menarik dan informatif:
  ```text
  ╔══════════════════════════════════════════════════════════════════╗
  ║                UT-RBV Downloader v1.0.0                          ║
  ║  Alat Pengunduh E-Book Ruang Baca Virtual Universitas Terbuka    ║
  ╚══════════════════════════════════════════════════════════════════╝
  ```

### User Story 2: Indikator Progres Interaktif (Rich Progress Bars)
Sebagai pengguna, saat mengunduh buku berhalaman tebal, saya ingin melihat progress bar yang akurat (jumlah halaman selesai, persentase, estimasi sisa waktu).

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Menampilkan tabel ringkasan mata kuliah sebelum unduhan dimulai:
  - Kode MK, Judul, Jumlah Modul, Estimasi Total Halaman.
- [x] Menampilkan multi-progress bar (Rich):
  - Bar 1: Progress Total Buku (Contoh: `[████████░░░░░░░░] 52% (234/450 Halaman)`).
  - Bar 2: Status Modul Aktif yang sedang diunduh.
- [x] Menampilkan spinner saat proses perakitan PDF dan kompresi sedang berlangsung.

### User Story 3: Pilihan Opsi & Parameter Fleksibel
Sebagai power user, saya ingin mengontrol modul mana yang diunduh, lokasi penyimpanan, dan opsi kompresi melalui parameter flag.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Mendukung flag CLI:
  - `-m, --modules`: Filter modul spesifik (contoh: `--modules 1,2,3` atau `--modules 1-4`).
  - `-o, --output`: Folder tujuan penyimpanan berkas PDF (default: `./downloads`).
  - `-c, --cookie`: String session cookie `PHPSESSID` bagi pengguna SSO.
  - `-u, --username` & `-p, --password`: Kredensial akun RBV.
  - `--merge / --split`: Memilih apakah digabung menjadi satu PDF atau dipisah per bab.
  - `--compress [none|medium|high]`: Tingkat kompresi berkas.
  - `--workers`: Jumlah concurrent worker (default: 4).
  - `-v, --verbose`: Mode debug log rinci.

---

## 🛠️ Langkah Implementasi Teknis

1. **Struktur Perintah di `src/ut_rbv/cli.py`:**
   ```python
   import click
   from rich.console import Console
   from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeRemainingColumn

   console = Console()

   @click.group()
   @click.version_option()
   def main():
       """UT-RBV Downloader - Unduh E-Book BMP Universitas Terbuka ke PDF."""
       pass

   @main.command()
   @click.argument("code")
   @click.option("-m", "--modules", help="Pilih modul spesifik, cth: 1,2,3 atau 1-4")
   @click.option("-o", "--output", default="./downloads", help="Direktori penyimpanan PDF")
   @click.option("-c", "--cookie", help="Session cookie PHPSESSID")
   @click.option("--merge/--split", default=True, help="Gabung menjadi satu PDF (default) atau pisah")
   @click.option("--compress", type=click.Choice(["none", "medium", "high"]), default="medium")
   def download(code, modules, output, cookie, merge, compress):
       ...
   ```

2. **Koneksi Controller:**
   - Memanggil `SessionManager`, `CatalogParser`, `PageDownloader`, dan `PDFBuilder`.
   - Menghubungkan callback progress ke `rich.progress.Progress`.

---

## 🧪 Rencana Pengujian
- Test parsing argumen CLI (misal parse string modul `"1,2,5"` menjadi list `[1, 2, 5]`, string `"1-3"` menjadi `[1, 2, 3]`).
- Test CLI `--help` memastikan seluruh deskripsi opsi tampil dengan benar.
- Test penanganan exit code: `0` jika sukses, `1` jika input tidak valid atau gagal otentikasi.
