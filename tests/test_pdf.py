"""Unit tests for PDF text layer injection, bookmarks, and assembly."""

import pytest
import pymupdf
from pathlib import Path

from ut_rbv.pdf.text_layer import (
    clean_jsonp_text,
    parse_page_text_data,
    inject_text_layer,
)

SAMPLE_JSONP_CALLBACK = """
myCallback([
  {
    "number": 1,
    "pages": 45,
    "height": 1200,
    "width": 800,
    "fonts": [],
    "text": [
      {"top": 100, "left": 150, "width": 500, "height": 28, "text": "MODUL 1"},
      {"top": 140, "left": 150, "width": 500, "height": 24, "text": "Pengantar Ilmu Administrasi"},
      {"top": 200, "left": 100, "width": 600, "height": 18, "text": "Universitas Terbuka Indonesia"}
    ]
  }
]);
"""

SAMPLE_JSONP_PARENTHESIS = """
([
  {
    "number": 2,
    "pages": 45,
    "height": 1200,
    "width": 800,
    "text": [
      {"top": 80, "left": 100, "width": 400, "height": 20, "text": "Kegiatan Belajar 1"}
    ]
  }
])
"""


class TestTextLayer:
    """Test suite for parsing JSONP and injecting invisible text layers into PDF."""

    def test_clean_jsonp_text_callback(self):
        data = clean_jsonp_text(SAMPLE_JSONP_CALLBACK)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["number"] == 1
        assert len(data[0]["text"]) == 3

    def test_clean_jsonp_text_parenthesis(self):
        data = clean_jsonp_text(SAMPLE_JSONP_PARENTHESIS)
        assert isinstance(data, list)
        assert data[0]["number"] == 2
        assert data[0]["text"][0]["text"] == "Kegiatan Belajar 1"

    def test_clean_jsonp_empty_raises_error(self):
        with pytest.raises(ValueError):
            clean_jsonp_text("")

    def test_inject_text_layer_onto_pdf_page(self):
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)

        # Inject sample text
        success = inject_text_layer(page, SAMPLE_JSONP_CALLBACK, img_width=800, img_height=1200)
        assert success is True

        # Verify extracted text matches
        extracted = page.get_text()
        assert "MODUL 1" in extracted
        assert "Pengantar Ilmu Administrasi" in extracted
        assert "Universitas Terbuka Indonesia" in extracted

        # Verify PDF searchability
        matches = page.search_for("Pengantar")
        assert len(matches) > 0

        doc.close()

    def test_inject_text_layer_from_file_path(self, tmp_path):
        json_file = tmp_path / "M1_001.json"
        json_file.write_text(SAMPLE_JSONP_PARENTHESIS, encoding="utf-8")

        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)

        success = inject_text_layer(page, json_file)
        assert success is True

        extracted = page.get_text()
        assert "Kegiatan Belajar 1" in extracted

        doc.close()

    def test_inject_text_layer_graceful_fallback(self):
        doc = pymupdf.open()
        page = doc.new_page(width=600, height=800)

        # Missing file path
        assert inject_text_layer(page, Path("/non/existent/path.json")) is False

        # Corrupted JSON string
        assert inject_text_layer(page, "corrupted { invalid json") is False

        # Empty text items
        assert inject_text_layer(page, {"text": []}) is False

        doc.close()


class TestTOCBookmarks:
    """Test suite for Table of Contents generation and outline injection."""

    def test_bookmark_item_to_pymupdf(self):
        from ut_rbv.pdf.bookmarks import BookmarkItem
        item = BookmarkItem(level=1, title="Modul 01", page_number=5)
        assert item.to_pymupdf() == [1, "Modul 01", 5]

    def test_extract_subsections_from_page_text(self):
        from ut_rbv.pdf.bookmarks import TOCBuilder

        page_text = {
            "text": [
                {"text": "Selamat datang di modul ini"},
                {"text": "Kegiatan Belajar 1: Konsep Dasar"},
                {"text": "Uraian materi pembelajaran"},
                {"text": "Tes Formatif 1"},
                {"text": "Rangkuman"},
            ]
        }

        items = TOCBuilder.extract_subsections_from_page_text(page_text, absolute_page=7)
        assert len(items) == 3
        assert items[0].title == "Kegiatan Belajar 1: Konsep Dasar"
        assert items[0].page_number == 7
        assert items[0].level == 2
        assert items[1].title == "Tes Formatif 1"
        assert items[2].title == "Rangkuman"

    def test_generate_toc_accumulates_page_offsets(self):
        from ut_rbv.core.catalog import BookSection
        from ut_rbv.pdf.bookmarks import TOCBuilder

        s1 = BookSection(title="Daftar Isi", doc_id="DAFIS", subfolder="EKMA4111", url="")
        s2 = BookSection(title="Modul 01", doc_id="M1", subfolder="EKMA4111", url="", module_number=1)
        s3 = BookSection(title="Modul 02", doc_id="M2", subfolder="EKMA4111", url="", module_number=2)

        page_counts = {
            "DAFIS": 5,
            "M1": 20,
            "M2": 15,
        }

        sub_texts = {
            "M1": {
                3: {"text": [{"text": "Kegiatan Belajar 1: Teori Organisasi"}]},
                12: {"text": [{"text": "Kegiatan Belajar 2: Struktur Organisasi"}]},
            }
        }

        toc = TOCBuilder.generate_toc(
            sections=[s1, s2, s3],
            section_page_counts=page_counts,
            text_layers_by_section=sub_texts,
            book_title="Pengantar Bisnis",
        )

        # Expected:
        # 1. Cover -> page 1
        # 2. DAFIS -> page 1
        # 3. Modul 01 -> page 1 + 5 = 6
        #    - KB 1 -> page 6 + (3 - 1) = 8
        #    - KB 2 -> page 6 + (12 - 1) = 17
        # 4. Modul 02 -> page 6 + 20 = 26
        titles_and_pages = [(b.level, b.title, b.page_number) for b in toc]

        assert (1, "Cover: Pengantar Bisnis", 1) in titles_and_pages
        assert (1, "Daftar Isi", 1) in titles_and_pages
        assert (1, "Modul 01", 6) in titles_and_pages
        assert (2, "Kegiatan Belajar 1: Teori Organisasi", 8) in titles_and_pages
        assert (2, "Kegiatan Belajar 2: Struktur Organisasi", 17) in titles_and_pages
        assert (1, "Modul 02", 26) in titles_and_pages

    def test_apply_toc_to_pymupdf_document(self):
        from ut_rbv.pdf.bookmarks import TOCBuilder, BookmarkItem

        doc = pymupdf.open()
        # Create a 30-page mock document
        for _ in range(30):
            doc.new_page(width=595, height=842)

        bookmarks = [
            BookmarkItem(level=1, title="Daftar Isi", page_number=1),
            BookmarkItem(level=1, title="Modul 01", page_number=5),
            BookmarkItem(level=2, title="Kegiatan Belajar 1", page_number=7),
            BookmarkItem(level=1, title="Modul 02", page_number=20),
        ]

        TOCBuilder.apply_toc(doc, bookmarks)

        # Verify TOC in PyMuPDF
        actual_toc = doc.get_toc()
        assert len(actual_toc) == 4
        assert actual_toc[0] == [1, "Daftar Isi", 1]
        assert actual_toc[1] == [1, "Modul 01", 5]
        assert actual_toc[2] == [2, "Kegiatan Belajar 1", 7]
        assert actual_toc[3] == [1, "Modul 02", 20]

        doc.close()


class TestPDFBuilder:
    """Test suite for PDFBuilder and PDFOptimizer pipelines."""

    def test_pdf_optimizer_image_bytes(self):
        from ut_rbv.pdf.optimizer import PDFOptimizer
        from PIL import Image
        import io

        # Create uncompressed PNG/JPEG
        img = Image.new("RGB", (300, 300), color="blue")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=100)
        raw_bytes = buf.getvalue()

        compressed_bytes = PDFOptimizer.optimize_image_bytes(raw_bytes, compress_level="high")
        assert len(compressed_bytes) <= len(raw_bytes)

    def test_build_section_pdf(self, tmp_path):
        from ut_rbv.core.catalog import BookSection
        from ut_rbv.core.downloader import PageDownloadResult
        from ut_rbv.pdf.builder import PDFBuilder
        from PIL import Image

        # Create 2 dummy images
        img1 = tmp_path / "M1_001.jpg"
        img2 = tmp_path / "M1_002.jpg"
        Image.new("RGB", (400, 600), color="white").save(img1)
        Image.new("RGB", (400, 600), color="white").save(img2)

        json1 = tmp_path / "M1_001.json"
        json1.write_text('{"text": [{"text": "Bab Satu", "top": 50, "left": 50, "width": 100, "height": 20}]}', encoding="utf-8")

        section = BookSection(title="Modul 01: Dasar Bisnis", doc_id="M1", subfolder="EKMA4111", url="", module_number=1)
        pages = [
            PageDownloadResult(doc_id="M1", page_num=1, image_path=img1, json_path=json1),
            PageDownloadResult(doc_id="M1", page_num=2, image_path=img2, json_path=None),
        ]

        out_pdf = tmp_path / "EKMA4111_Modul_01.pdf"
        result_path = PDFBuilder.build_section_pdf(
            section=section,
            page_results=pages,
            output_file=out_pdf,
            book_title="Pengantar Bisnis",
        )

        assert result_path.exists()
        doc = pymupdf.open(str(result_path))
        assert len(doc) == 2
        assert "EKMA4111" in doc.metadata["title"]
        assert "Bab Satu" in doc[0].get_text()
        doc.close()

    def test_build_merged_book_pdf(self, tmp_path):
        from ut_rbv.core.catalog import Book, BookSection
        from ut_rbv.core.downloader import PageDownloadResult
        from ut_rbv.pdf.builder import PDFBuilder
        from PIL import Image

        # DAFIS (1 page), M1 (2 pages)
        d_img = tmp_path / "DAFIS_001.jpg"
        m1_img1 = tmp_path / "M1_001.jpg"
        m1_img2 = tmp_path / "M1_002.jpg"
        Image.new("RGB", (400, 600), color="white").save(d_img)
        Image.new("RGB", (400, 600), color="white").save(m1_img1)
        Image.new("RGB", (400, 600), color="white").save(m1_img2)

        s1 = BookSection(title="Daftar Isi", doc_id="DAFIS", subfolder="EKMA4111", url="")
        s2 = BookSection(title="Modul 01", doc_id="M1", subfolder="EKMA4111", url="", module_number=1)
        book = Book(code="EKMA4111", title="Pengantar Bisnis", sections=[s1, s2])

        downloads = {
            "DAFIS": [PageDownloadResult(doc_id="DAFIS", page_num=1, image_path=d_img)],
            "M1": [
                PageDownloadResult(doc_id="M1", page_num=1, image_path=m1_img1),
                PageDownloadResult(doc_id="M1", page_num=2, image_path=m1_img2),
            ],
        }

        merged_pdf = tmp_path / "EKMA4111 - Pengantar Bisnis.pdf"
        result_path = PDFBuilder.build_merged_book_pdf(
            book=book,
            download_results=downloads,
            output_file=merged_pdf,
        )

        assert result_path.exists()
        doc = pymupdf.open(str(result_path))
        assert len(doc) == 3
        assert doc.metadata["author"] == "Universitas Terbuka"
        toc = doc.get_toc()
        assert len(toc) >= 2  # Cover, DAFIS, Modul 01
        doc.close()


