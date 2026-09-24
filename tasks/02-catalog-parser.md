# TASK-02: Katalog & Parser Struktur Modul Buku

## 📌 Gambaran Umum
Fitur ini bertugas menguraikan (*parse*) struktur mata kuliah dari portal RBV setelah pengguna menginputkan kode mata kuliah (misalnya `EKMA4111`). Fitur akan memetakan seluruh modul/bab (seperti `DAFIS.pdf`, `M1.pdf` s/d `Mn.pdf`), mendeteksi judul masing-masing bagian, dan menentukan total halaman yang ada pada tiap dokumen.

---

## 🎯 Target Berkas
- `src/ut_rbv/core/catalog.py`
- `tests/test_catalog.py`

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Menemukan dan Memvalidasi Buku Berdasarkan Kode MK
Sebagai pengguna, saya ingin memasukkan kode mata kuliah (misalnya `EKMA4111`) dan mendapatkan informasi lengkap apakah buku tersebut tersedia di RBV beserta judulnya.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Sistem memvalidasi format kode mata kuliah (4 huruf kapital + 4 angka, atau variasi alfanumerik UT).
- [x] Sistem mengakses `https://pustaka.ut.ac.id/reader/index.php?modul={KODE}`.
- [x] Jika buku tidak ditemukan (respons kosong atau error 404), sistem melempar exception `BookNotFoundError`.
- [x] Jika buku ditemukan, sistem mengembalikan objek `BookMetadata` (kode, judul buku, daftar section).

### User Story 2: Ekstraksi Daftar Modul / Section
Sebagai pengguna, saya ingin melihat rincian seluruh modul (Daftar Isi, Modul 1 sampai Modul N, Lampiran) agar saya bisa memilih mengunduh semua atau sebagian.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Sistem menguraikan elemen HTML `<th>` dan link `<a>` di dalam tabel navigasi RBV.
- [x] Mengekstrak nama tampilan modul (contoh: `"Daftar Isi"`, `"Modul 01"`, `"Modul 02"`).
- [x] Mengekstrak nama dokumen internal (contoh: `DAFIS.pdf` -> `DAFIS`, `M1.pdf` -> `M1`).
- [x] Menjaga urutan modul agar sesuai dengan susunan asli buku fisik.

### User Story 3: Menentukan Total Halaman per Modul
Sebagai mesin pengunduh, sistem perlu mengetahui jumlah halaman per modul agar dapat mengatur batas perulangan pengunduhan.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Sistem membaca respons halaman pertama dari layanan `services/view.php?doc={DOC}&format=jsonp&subfolder={KODE}/&page=1` atau melakukan probing jumlah halaman.
- [x] Mendapatkan nilai atribut `pages` atau mendeteksi batas akhir halaman dengan akurat.
- [x] Menyediakan estimasi total halaman keseluruhan buku untuk keperluan kalkulasi progress bar.

---

## 🛠️ Langkah Implementasi Teknis

1. **Definisikan Data Class / Pydantic Models di `core/catalog.py`:**
   ```python
   @dataclass
   class BookSection:
       title: str         # "Modul 01: Pengantar Bisnis"
       doc_id: str        # "M1"
       subfolder: str     # "EKMA4111"
       url: str           # "index.php?subfolder=EKMA4111/&doc=M1.pdf"
       total_pages: int = 0

   @dataclass
   class Book:
       code: str          # "EKMA4111"
       title: str         # "Pengantar Bisnis"
       sections: list[BookSection]
       
       @property
       def total_pages(self) -> int:
           return sum(s.total_pages for s in self.sections)
   ```
2. **Implementasikan `CatalogParser`:**
   - Method `parse_book_index(html_content: str, code: str) -> Book`.
   - Method `detect_section_pages(session, section: BookSection) -> int`.
3. **Penyaringan Modul Kustom:**
   - Method `filter_sections(book: Book, target_modules: list[int] | None) -> list[BookSection]`.

---

## 🧪 Rencana Pengujian
- Unit test HTML parser dengan sample fixture HTML tabel navigasi RBV UT.
- Verifikasi ekstraksi clean doc name (menghilangkan ekstensi `.pdf`).
- Test penanganan kasus buku dengan modul non-standar (misal hanya 3 modul, atau ada modul lampiran).
