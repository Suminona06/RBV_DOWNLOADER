"""Unit tests for catalog and book module parsing in UT-RBV."""

import pytest
import respx
import httpx

from ut_rbv.core.catalog import (
    Book,
    BookSection,
    CatalogParser,
    BookNotFoundError,
    CatalogParseError,
)
from ut_rbv.core.session import SessionManager

SAMPLE_CATALOG_HTML = """
<!DOCTYPE html>
<html>
<head><title>EKMA4111 - Pengantar Bisnis</title></head>
<body>
    <div class="header">
        <h2>EKMA4111 Pengantar Bisnis</h2>
    </div>
    <div class="content">
        <table class="table-modules">
            <tr>
                <th><a href="index.php?subfolder=EKMA4111/&doc=DAFIS.pdf">Daftar Isi</a></th>
            </tr>
            <tr>
                <th><a href="index.php?subfolder=EKMA4111/&doc=M1.pdf">Modul 01: Pengantar Bisnis</a></th>
            </tr>
            <tr>
                <th><a href="index.php?subfolder=EKMA4111/&doc=M2.pdf">Modul 02: Lingkungan Usaha</a></th>
            </tr>
            <tr>
                <th><a href="index.php?subfolder=EKMA4111/&doc=M3.pdf">Modul 03: Bentuk Badan Usaha</a></th>
            </tr>
            <tr>
                <th><a href="index.php?subfolder=EKMA4111/&doc=LAMP.pdf">Lampiran</a></th>
            </tr>
        </table>
    </div>
</body>
</html>
"""

SAMPLE_NOT_FOUND_HTML = """
<!DOCTYPE html>
<html>
<head><title>Ruang Baca Virtual</title></head>
<body>
    <p>Data buku tidak ditemukan di sistem.</p>
</body>
</html>
"""

SAMPLE_JSONP_PAGE1 = """
([{"number":1,"pages":42,"height":1188,"width":840,"fonts":[],"text":[]}])
"""


class TestCatalogParser:
    """Test suite for catalog and module structure extraction."""

    def test_validate_code_normalization(self):
        assert CatalogParser.validate_code("ekma4111") == "EKMA4111"
        assert CatalogParser.validate_code("  mkdu4110  ") == "MKDU4110"
        assert CatalogParser.validate_code("msim-4103") == "MSIM-4103"

    def test_validate_code_invalid_raises_error(self):
        with pytest.raises(ValueError):
            CatalogParser.validate_code("abc")  # too short
        with pytest.raises(ValueError):
            CatalogParser.validate_code("EKMA@4111!!")  # invalid chars

    def test_clean_doc_id(self):
        assert CatalogParser.clean_doc_id("DAFIS.pdf") == "DAFIS"
        assert CatalogParser.clean_doc_id("M1.PDF") == "M1"
        assert CatalogParser.clean_doc_id("index.php?subfolder=EKMA4111/&doc=M02.pdf") == "M02"

    def test_parse_book_index_success(self):
        book = CatalogParser.parse_book_index(SAMPLE_CATALOG_HTML, "EKMA4111")
        assert book.code == "EKMA4111"
        assert book.title == "Pengantar Bisnis"
        assert len(book.sections) == 5

        # Check section mapping
        dafis = book.sections[0]
        assert dafis.doc_id == "DAFIS"
        assert dafis.title == "Daftar Isi"
        assert dafis.module_number is None

        m1 = book.sections[1]
        assert m1.doc_id == "M1"
        assert m1.module_number == 1
        assert "Pengantar Bisnis" in m1.title

        m2 = book.sections[2]
        assert m2.doc_id == "M2"
        assert m2.module_number == 2

        # Check module_sections property
        modules_only = book.module_sections
        assert len(modules_only) == 3
        assert [m.module_number for m in modules_only] == [1, 2, 3]

    def test_parse_book_index_not_found(self):
        with pytest.raises(BookNotFoundError):
            CatalogParser.parse_book_index(SAMPLE_NOT_FOUND_HTML, "KODE9999")

    def test_parse_book_index_empty(self):
        with pytest.raises(BookNotFoundError):
            CatalogParser.parse_book_index("", "EKMA4111")

    def test_filter_sections_numeric_list(self):
        book = CatalogParser.parse_book_index(SAMPLE_CATALOG_HTML, "EKMA4111")
        # Filter only module 1 and 3, including DAFIS
        filtered = book.filter_sections([1, 3], include_dafis=True)
        doc_ids = [s.doc_id for s in filtered]
        assert "DAFIS" in doc_ids
        assert "M1" in doc_ids
        assert "M3" in doc_ids
        assert "M2" not in doc_ids

    def test_filter_sections_string_range(self):
        book = CatalogParser.parse_book_index(SAMPLE_CATALOG_HTML, "EKMA4111")
        filtered = book.filter_sections("1-2", include_dafis=False)
        doc_ids = [s.doc_id for s in filtered]
        assert doc_ids == ["M1", "M2"]

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_book_success(self):
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_CATALOG_HTML)
        )

        manager = SessionManager()
        book = await CatalogParser.fetch_book(manager, "ekma4111")
        assert book.code == "EKMA4111"
        assert book.title == "Pengantar Bisnis"
        assert len(book.sections) == 5

    @pytest.mark.asyncio
    @respx.mock
    async def test_detect_section_pages(self):
        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_JSONP_PAGE1)
        )

        manager = SessionManager()
        section = BookSection(
            title="Modul 01",
            doc_id="M1",
            subfolder="EKMA4111",
            url="index.php?subfolder=EKMA4111/&doc=M1.pdf",
        )

        pages = await CatalogParser.detect_section_pages(manager, section)
        assert pages == 42
        assert section.total_pages == 42
