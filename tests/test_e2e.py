"""End-to-End (E2E) integration test suite for UT-RBV Downloader.

Simulates the entire workflow in an isolated hermetic environment using mock fixtures:
1. Captcha-solving authentication & session handling.
2. Catalog parsing for course structure and page detection.
3. Resilient asynchronous page downloading (including 429 backoff & expired session re-auth).
4. PDF assembly with invisible searchable text injection and hierarchical bookmarks.
5. PyMuPDF integrity verification of the resulting document.
"""

import io
import pytest
import respx
import httpx
import pymupdf
from pathlib import Path
from PIL import Image

from ut_rbv.core.auth import solve_math_captcha, extract_captcha_question
from ut_rbv.core.session import SessionManager
from ut_rbv.core.catalog import CatalogParser, Book, BookSection
from ut_rbv.core.downloader import PageDownloader
from ut_rbv.pdf.builder import PDFBuilder
from ut_rbv.pdf.optimizer import PDFOptimizer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def login_html():
    return (FIXTURES_DIR / "rbv_login_form.html").read_text(encoding="utf-8")


@pytest.fixture
def catalog_html():
    return (FIXTURES_DIR / "rbv_module_index.html").read_text(encoding="utf-8")


@pytest.fixture
def sample_jsonp():
    return (FIXTURES_DIR / "sample_page.jsonp").read_text(encoding="utf-8")


@pytest.fixture
def sample_jpeg_bytes():
    return (FIXTURES_DIR / "sample_page.jpg").read_bytes()


class TestEndToEndPipeline:
    """Comprehensive E2E integration test suite."""

    @respx.mock
    @pytest.mark.asyncio
    async def test_full_pipeline_hermetic_mock(
        self,
        tmp_path,
        login_html,
        catalog_html,
        sample_jsonp,
        sample_jpeg_bytes,
        monkeypatch,
    ):
        """Test complete workflow from login to verified final PDF output."""
        cache_dir = tmp_path / "cache"
        output_dir = tmp_path / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("UT_RBV_CACHE_DIR", str(cache_dir))

        # 1. Mock Login Endpoints
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=login_html)
        )
        respx.post("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(
                302,
                headers={
                    "Location": "https://pustaka.ut.ac.id/reader/index.php?subfolder=EKMA4111/",
                    "Set-Cookie": "PHPSESSID=mock_session_e2e_valid; path=/",
                },
                text="Redirecting to reader...",
            )
        )

        # 2. Mock Catalog & Page Endpoints
        # Once authenticated, GET index.php?subfolder=EKMA4111/ returns catalog_html
        def handle_index(req):
            if "subfolder" in req.url.params or "modul" in req.url.params:
                return httpx.Response(200, text=catalog_html)
            return httpx.Response(200, text=login_html)

        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(side_effect=handle_index)

        # Mock view.php for total page probe, images, and text JSONP
        def handle_view(req):
            fmt = req.url.params.get("format")
            if fmt == "jpg":
                return httpx.Response(200, content=sample_jpeg_bytes)
            # JSONP text
            return httpx.Response(200, text=sample_jsonp)

        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(side_effect=handle_view)

        # --- STEP 1: Authenticate ---
        async with SessionManager() as session:
            auth_ok = await session.login_with_credentials("012345678", "secretpass", probe_code="EKMA4111")
            assert auth_ok is True
            assert session.authenticated is True

            # --- STEP 2: Parse Catalog ---
            book = await CatalogParser.fetch_book(session, "EKMA4111")
            assert book.code == "EKMA4111"
            assert "Pengantar Bisnis" in book.title
            assert len(book.sections) == 3
            assert book.sections[0].doc_id == "M1"
            assert book.sections[1].doc_id == "M2"
            assert book.sections[2].doc_id == "M3"

            # Set test page counts for sections
            for sec in book.sections:
                sec.total_pages = 2

            # --- STEP 3: Async Downloader ---
            downloader = PageDownloader(session=session, max_concurrency=2)
            download_results = {}
            for sec in book.sections[:2]:  # Download M1 and M2
                results = await downloader.download_section(sec, fetch_text=True)
                assert len(results) == 2
                assert all(r.image_path.exists() for r in results)
                assert all(r.json_path and r.json_path.exists() for r in results)
                download_results[sec.doc_id] = results

        # --- STEP 4: Build Single Section PDF ---
        m1_pdf = output_dir / "EKMA4111_M1.pdf"
        PDFBuilder.build_section_pdf(
            section=book.sections[0],
            page_results=download_results["M1"],
            output_file=m1_pdf,
            book_title=book.title,
            compress_level="medium",
        )
        assert m1_pdf.exists()

        # Verify Single Section PDF with PyMuPDF
        doc_m1 = pymupdf.open(str(m1_pdf))
        assert len(doc_m1) == 2
        assert "EKMA4111" in doc_m1.metadata["title"]
        # Searchable text layer verification
        page0_text = doc_m1[0].get_text()
        assert "MODUL 1" in page0_text
        assert "Konsep Dasar Bisnis" in page0_text
        assert len(doc_m1[0].search_for("Bisnis")) > 0
        doc_m1.close()

        # --- STEP 5: Build Merged Book PDF ---
        merged_pdf = output_dir / "EKMA4111 - Pengantar Bisnis.pdf"
        PDFBuilder.build_merged_book_pdf(
            book=book,
            download_results=download_results,
            output_file=merged_pdf,
            compress_level="medium",
        )
        assert merged_pdf.exists()

        # Verify Merged PDF with PyMuPDF
        doc_merged = pymupdf.open(str(merged_pdf))
        assert len(doc_merged) == 4  # 2 pages M1 + 2 pages M2
        assert doc_merged.metadata["author"] == "Universitas Terbuka"

        # Verify TOC / Bookmarks hierarchy
        toc = doc_merged.get_toc()
        assert len(toc) >= 2
        titles = [item[1] for item in toc]
        assert any("Modul 01" in t or "Modul 1" in t or "MODUL" in t.upper() for t in titles)
        assert any("Kegiatan Belajar" in t for t in titles)

        # Verify text search across pages
        found_in_doc = False
        for p in doc_merged:
            if "Konsep Dasar Bisnis" in p.get_text():
                found_in_doc = True
                break
        assert found_in_doc is True

        doc_merged.close()

    @respx.mock
    @pytest.mark.asyncio
    async def test_resilient_downloader_with_429_backoff(self, tmp_path, sample_jpeg_bytes, monkeypatch):
        """Simulate HTTP 429 Too Many Requests and ensure exponential backoff succeeds."""
        cache_dir = tmp_path / "cache_429"
        monkeypatch.setenv("UT_RBV_CACHE_DIR", str(cache_dir))

        attempts = 0

        def rate_limited_view(req):
            nonlocal attempts
            attempts += 1
            if attempts <= 2:
                # First 2 attempts return 429
                return httpx.Response(429, headers={"Retry-After": "0.01"})
            # Subsequent attempt succeeds
            return httpx.Response(200, content=sample_jpeg_bytes)

        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            side_effect=rate_limited_view
        )

        async with SessionManager() as session:
            downloader = PageDownloader(session=session, max_retries=4, backoff_base=0.01)
            section = BookSection(title="Modul 1", doc_id="M1", subfolder="EKMA4111", url="", total_pages=1)
            results = await downloader.download_section(section, fetch_text=False)

            assert len(results) == 1
            assert results[0].image_path.exists()
            assert attempts >= 3  # Confirms retries happened

    @respx.mock
    @pytest.mark.asyncio
    async def test_session_expiration_and_reauth(
        self,
        tmp_path,
        login_html,
        catalog_html,
        monkeypatch,
    ):
        """Simulate session expiration returning 'About RBV V.2' and verify automatic re-login."""
        cache_dir = tmp_path / "cache_reauth"
        monkeypatch.setenv("UT_RBV_CACHE_DIR", str(cache_dir))

        calls = 0

        def handle_reader_index(req):
            nonlocal calls
            calls += 1
            if calls <= 2:
                # 1st: initial request shows login form; 2nd: probe in login_with_credentials shows login form
                return httpx.Response(200, text=login_html)
            # 3rd & onwards: successful reader content
            return httpx.Response(200, text=catalog_html)

        respx.route(method="GET", url__regex=r"https://pustaka\.ut\.ac\.id/reader/index\.php").mock(
            side_effect=handle_reader_index
        )
        respx.route(method="POST", url__regex=r"https://pustaka\.ut\.ac\.id/reader/index\.php").mock(
            return_value=httpx.Response(
                302,
                headers={
                    "Location": "https://pustaka.ut.ac.id/reader/index.php?subfolder=EKMA4111/",
                    "Set-Cookie": "PHPSESSID=mock_reauth_new_session; path=/",
                },
                text="Redirecting to reader...",
            )
        )

        async with SessionManager() as session:
            session.username = "012345678"
            session.password = "secretpass"

            # Auto re-auth during GET request
            res = await session.get("https://pustaka.ut.ac.id/reader/index.php?subfolder=EKMA4111/")
            assert res.status_code == 200
            assert "Pengantar Bisnis" in res.text
            assert session.authenticated is True

