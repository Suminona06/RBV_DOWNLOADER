# TASK-04: Injeksi Searchable Text Layer via JSONP

## 📌 Gambaran Umum
Keunggulan utama perkakas ini adalah menghasilkan file PDF yang teksnya dapat dicari (*searchable*) dan disalin (*selectable/copyable*). Layanan RBV UT (`services/view.php?format=jsonp`) menyediakan data posisi teks, bounding box, dan ukuran font asli. Fitur ini bertugas mengonversi payload data JSONP tersebut menjadi lapisan teks transparan (*invisible text layer*) yang disematkan tepat di atas gambar halaman pada dokumen PDF tanpa memerlukan proses OCR pihak ketiga yang lambat dan boros CPU.

---

## 🎯 Target Berkas
- `src/ut_rbv/pdf/text_layer.py`
- `tests/test_pdf.py`

---

## 📋 Kebutuhan Fungsional (User Story & AC)

### User Story 1: Parsing Data JSONP RBV
Sebagai engine pembuat PDF, saya ingin membaca data JSONP dari RBV yang berisi posisi koordinat huruf/kata agar dapat dipetakan ke koordinat halaman PDF.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Sistem memvalidasi payload JSONP / JSON. Jika respons diawali callback wrapper (contoh: `callback({...})`), sistem membersihkan wrapper sehingga menjadi JSON valid.
- [x] Mengekstrak atribut halaman:
  - `width` (lebar halaman asli gambar)
  - `height` (tinggi halaman asli gambar)
  - Array elemen teks: `text`, posisi `top`/`height`, `left`/`width`, `font`, `font_size`.

### User Story 2: Injeksi Teks Transparan ke Halaman PDF (PyMuPDF / FitZ)
Sebagai mahasiswa yang membaca modul di iPad/laptop, saya ingin bisa menandai (*highlight*) teks dengan stylus dan mencari kata kunci menggunakan fitur *Search* (Ctrl + F).

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Menggunakan library `PyMuPDF` (`pymupdf`) untuk menyisipkan teks ke halaman PDF.
- [x] Menghitung rasio skala (*scaling factor*) antara ukuran gambar asli dengan dimensi halaman PDF standar (Point 72 DPI).
- [x] Menyisipkan teks dengan mode rendering invisible (*render_mode=3* atau warna transparan) tepat pada titik koordinat yang sesuai.
- [x] Menjaga urutan pembacaan teks (*reading order*) dari atas ke bawah dan kiri ke kanan.

### User Story 3: Penanganan Modul Tanpa JSONP (Graceful Fallback)
Sebagai pengguna, jika ada modul cetakan lama yang tidak memiliki endpoint JSONP, sistem tidak boleh crash dan tetap melanjutkan proses pembuatan PDF berbasis gambar.

**Kriteria Penerimaan (Acceptance Criteria):**
- [x] Jika endpoint `format=jsonp` mengembalikan 404 atau JSON kosong, sistem mencatat peringatan di log (*warning*) dan melanjutkan halaman hanya dengan citra gambar.
- [x] (Opsional/Next Phase) Fallback ke engine OCR lokal jika user mengaktifkan flag `--ocr`.

---

## 🛠️ Langkah Implementasi Teknis

1. **Parser JSONP di `pdf/text_layer.py`:**
   ```python
   def clean_jsonp_response(raw_text: str) -> dict:
       # Tangani jika dibungkus callback function
       if raw_text.startswith("(") and raw_text.endswith(")"):
           raw_text = raw_text[1:-1]
       return json.loads(raw_text)
   ```
2. **Injektor Teks pada Halaman PyMuPDF:**
   ```python
   import fitz

   def inject_text_layer(page: fitz.Page, text_data: dict, img_width: int, img_height: int):
       pdf_width = page.rect.width
       pdf_height = page.rect.height
       
       scale_x = pdf_width / img_width
       scale_y = pdf_height / img_height
       
       for item in text_data.get("text", []):
           rect = fitz.Rect(
               item["left"] * scale_x,
               item["top"] * scale_y,
               (item["left"] + item["width"]) * scale_x,
               (item["top"] + item["height"]) * scale_y,
           )
           # Sisipkan teks transparan
           page.insert_textbox(rect, item["text"], fontsize=item.get("fontsize", 10) * scale_y, render_mode=3)
   ```

---

## 🧪 Rencana Pengujian
- Unit test parser JSONP dengan sample data representatif dari portal RBV UT.
- Verifikasi teks hasil injeksi dapat diekstrak kembali menggunakan `page.get_text()`.
- Verifikasi pencarian kata kunci (*search*) pada dokumen PDF yang dihasilkan.
