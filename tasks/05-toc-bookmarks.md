# TASK-05: Injeksi Daftar Isi & Bookmarks Hierarkis (TOC)

## 📌 Gambaran Umum
Buku Materi Pokok (BMP) UT memiliki ketebalan antara 200 hingga 700 halaman yang terbagi dalam beberapa modul dan kegiatan belajar. Membaca file PDF setebal ini tanpa daftar isi interaktif sangat menyulitkan navigasi. Fitur ini bertanggung jawab untuk menyusun dan menyuntikkan *Table of Contents (TOC)* atau *Outline / Bookmarks* berjenjang ke dalam berkas PDF akhir.

---

## 🎯 Target Berkas
- `src/ut_rbv/pdf/bookmarks.py`
- `tests/test_pdf.py`

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Pembuatan Hierarki Bookmark Utama
Sebagai pembaca, saya ingin membuka panel Bookmarks di Adobe Acrobat, Apple Books, atau PDF viewer apa pun dan langsung melihat daftar bab buku yang dapat diklik untuk melompat langsung ke halaman terkait.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Bookmark tingkat 1 (Level 1) mewakili bagian utama buku:
  - `Cover / Judul Buku` (Halaman 1)
  - `Daftar Isi (DAFIS)`
  - `Modul 1: [Judul Modul]`
  - `Modul 2: [Judul Modul]`
  - ...
  - `Modul N: [Judul Modul]`
  - `Lampiran / Glosarium` (jika ada)
- [x] Setiap item bookmark mengarah ke nomor halaman absolut yang tepat pada file PDF gabungan.

### User Story 2: Ekstraksi Sub-Bab / Kegiatan Belajar (Level 2 Bookmarks)
Sebagai pembaca, saya ingin dapat melihat sub-bab (*Kegiatan Belajar 1*, *Kegiatan Belajar 2*, *Tes Formatif*, *Rangkuman*) di bawah modul terkait jika data tersebut tersedia.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Sistem memindai teks pada halaman awal modul (atau membaca struktur DAFIS) untuk mendeteksi judul "Kegiatan Belajar 1", "Kegiatan Belajar 2", dst.
- [x] Menambahkan bookmark Level 2 sebagai anak (*children*) dari modul terkait.
- [x] Nomor halaman sub-bab terpetakan secara presisi.

### User Story 3: Integritas Struktur PDF Outline
Sebagai pengguna aplikasi PDF reader standar industri, outline yang disematkan harus sesuai standar spesifikasi ISO 32000 (PDF Specification).

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Menggunakan format TOC `PyMuPDF` (`doc.set_toc(toc_list)`):
  ```python
  # Format PyMuPDF: [level, title, page_number]
  toc = [
      [1, "Daftar Isi", 1],
      [1, "Modul 1: Konsep Dasar Bisnis", 5],
      [2, "Kegiatan Belajar 1: Pengertian Bisnis", 7],
      [2, "Kegiatan Belajar 2: Lingkungan Bisnis", 20],
      [1, "Modul 2: Etika Bisnis", 35]
  ]
  ```
- [x] TOC dapat dibuka dengan sempurna di pembaca PDF populer (Acrobat, Foxit, PDF Expert, GoodNotes, Chrome PDF Viewer).

---

## 🛠️ Langkah Implementasi Teknis

1. **Definisikan Struktur TOC Item di `pdf/bookmarks.py`:**
   ```python
   @dataclass
   class BookmarkItem:
       level: int       # 1 untuk Modul, 2 untuk Kegiatan Belajar
       title: str       # "Modul 01: Pengantar Bisnis"
       page_number: int # 1-indexed nomor halaman tujuan
   ```
2. **Implementasikan `TOCBuilder`:**
   - Menghitung offset akumulatif nomor halaman saat menggabungkan banyak modul menjadi satu PDF.
   - Mengonversi daftar `BookmarkItem` menjadi representasi list `[level, title, page_number]` yang diterima oleh PyMuPDF.
   - Menerapkan outline ke dokumen:
     ```python
     def apply_toc_to_pdf(doc: fitz.Document, bookmarks: list[BookmarkItem]):
         toc_matrix = [[b.level, b.title, b.page_number] for b in bookmarks]
         doc.set_toc(toc_matrix)
     ```

---

## 🧪 Rencana Pengujian
- Test kalkulasi offset halaman ketika menggabungkan 3 section dengan jumlah halaman berbeda (misal Section A: 10 hlm, Section B: 25 hlm, Section C: 15 hlm).
- Validasi bahwa pemanggilan `doc.get_toc()` mengembalikan list TOC yang identik dengan yang disuntikkan.
