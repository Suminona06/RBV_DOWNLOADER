# TASK-06: Penyusun PDF & Pengoptimal Kompresi Gambar

## 📌 Gambaran Umum
Fitur ini adalah tahap perakitan akhir (*assembly pipeline*) yang mengambil citra halaman yang telah diunduh di disk cache, mengombinasikannya dengan lapisan teks (*text layer*) dan *bookmarks*, serta menghasilkan berkas PDF final yang terkompresi secara optimal. Fitur ini menyediakan dua mode keluaran: satu buku utuh (*Merged Single PDF*) atau terpisah per modul (*Split PDFs*).

---

## 🎯 Target Berkas
- `src/ut_rbv/pdf/builder.py`
- `src/ut_rbv/pdf/optimizer.py`
- `tests/test_pdf.py`

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Penyusunan Halaman Menjadi PDF Utuh (Streaming Pipeline)
Sebagai pengguna, saya ingin seluruh halaman modul dirangkai dengan urutan yang sempurna tanpa ada halaman terbalik atau hilang, dan tanpa menghabiskan RAM komputer saya.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Menggunakan `PyMuPDF` (`pymupdf`) dengan pendekatan streaming / penambahan halaman bertahap (`new_page()`, `insert_image()`).
- [x] Mendukung dua mode pengorganisasian berkas:
  - **Mode Merged (Default):** Satu file buku utuh (contoh: `EKMA4111_Pengantar_Bisnis.pdf`).
  - **Mode Split:** File terpisah per bab (contoh: `EKMA4111_Modul_01.pdf`, `EKMA4111_Modul_02.pdf`).
- [x] Penggunaan memori (RAM) tetap berada di bawah 250 MB selama proses pembuatan buku setebal 600 halaman.

### User Story 2: Metadata Dokumen PDF
Sebagai mahasiswa yang mengelola perpustakaan digital, saya ingin file PDF memiliki metadata standar industri saat dilihat di properti file atau aplikasi manajemen ebook (seperti Calibre / Zotero).

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Menetapkan metadata PDF:
  - `title`: `[KODE_MK] - [NAMA_MATA_KULIAH]`
  - `author`: `Universitas Terbuka`
  - `subject`: `Buku Materi Pokok (BMP) UT`
  - `keywords`: `UT, BMP, Ruang Baca Virtual, Modul Kuliah`
  - `creator`: `UT-RBV Downloader`

### User Story 3: Kompresi Cerdas Ukuran Berkas (Smart Optimizer)
Sebagai pengguna dengan penyimpanan terbatas di tablet/smartphone, saya ingin ukuran file PDF tidak membengkak tanpa membuat kualitas gambar/teks menjadi buram.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Menyediakan opsi kompresi:
  - `none`: Kualitas asli 100% tanpa re-kompresi.
  - `medium` (Rekomendasi): Kompresi JPEG kualitas ~80-85, deflasi stream PDF (reduksi ukuran 40% - 60%).
  - `high`: Kompresi JPEG kualitas ~70 untuk file sangat ringkas (reduksi > 70%).
- [x] Membersihkan objek yang tidak terpakai dan metadata duplikat pada file PDF saat penyimpanan (`deflate=True`, `garbage=3`).

---

## 🛠️ Langkah Implementasi Teknis

1. **Implementasikan `PDFBuilder` di `pdf/builder.py`:**
   ```python
   import fitz
   from PIL import Image

   class PDFBuilder:
       def __init__(self, book: Book, output_dir: Path):
           self.book = book
           self.output_dir = output_dir

       def build_merged_pdf(self, page_files: list[dict], compress_level: str = "medium") -> Path:
           doc = fitz.open()
           for page_info in page_files:
               img_path = page_info["image_path"]
               json_path = page_info.get("json_path")
               
               with Image.open(img_path) as img:
                   w, h = img.size
               
               page = doc.new_page(width=w, height=h)
               page.insert_image(page.rect, filename=str(img_path))
               
               if json_path and json_path.exists():
                   # Inject text layer dari TASK-04
                   inject_text_layer(page, json_path, w, h)
                   
           # Terapkan bookmarks dari TASK-05
           apply_toc(doc, self.book)
           
           # Simpan dengan optimasi
           out_file = self.output_dir / f"{self.book.code} - {self.book.title}.pdf"
           doc.save(str(out_file), garbage=3, deflate=True)
           doc.close()
           return out_file
   ```

2. **Implementasikan `PDFOptimizer` di `pdf/optimizer.py`:**
   - Opsi re-encode gambar cache menggunakan Pillow jika kompresi level `high` dipilih.

---

## 🧪 Rencana Pengujian
- Buat 5 dummy images JPEG, gabungkan menjadi PDF, dan verifikasi jumlah halaman adalah 5.
- Uji perbandingan ukuran file antara `compress_level="none"` dan `compress_level="medium"`.
- Validasi metadata dokumen (`doc.metadata`) setelah disimpan.
