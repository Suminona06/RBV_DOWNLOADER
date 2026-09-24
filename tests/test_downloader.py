"""Unit tests for asynchronous page downloader, disk caching, and retry mechanisms."""

import pytest
import respx
import httpx
import shutil
from pathlib import Path

from ut_rbv.core.catalog import Book, BookSection
from ut_rbv.core.downloader import PageDownloader, PageDownloadResult
from ut_rbv.core.session import SessionManager
from ut_rbv.utils.paths import get_page_cache_paths, get_book_cache_dir, get_cache_root

# Valid minimal JPEG magic bytes
DUMMY_JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00" + b"\x00" * 600
DUMMY_JSONP = '([{"number": 1, "pages": 5, "height": 1000, "width": 800, "fonts": [], "text": [{"text": "Hello World", "top": 50, "left": 100, "width": 200, "height": 20}]}])'


@pytest.fixture
def temp_cache_dir(tmp_path, monkeypatch):
    """Fixture providing an isolated temporary cache directory."""
    test_cache = tmp_path / "test_cache"
    test_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("UT_RBV_CACHE_DIR", str(test_cache))
    return test_cache


class TestPathHelpers:
    """Test suite for path and cache directory generation."""

    def test_paths_generation(self, temp_cache_dir):
        book_dir = get_book_cache_dir("EKMA4111")
        assert book_dir.exists()
        assert book_dir.name == "EKMA4111"

        img_path, json_path = get_page_cache_paths("EKMA4111", "M1", 5)
        assert img_path.name == "M1_005.jpg"
        assert json_path.name == "M1_005.json"


class TestPageDownloader:
    """Test suite for PageDownloader concurrency, caching, and retry logic."""

    @pytest.mark.asyncio
    async def test_download_page_cache_hit(self, temp_cache_dir):
        manager = SessionManager()
        downloader = PageDownloader(session=manager, enable_jitter=False)

        section = BookSection(
            title="Modul 01",
            doc_id="M1",
            subfolder="EKMA4111",
            url="index.php?subfolder=EKMA4111/&doc=M1.pdf",
            total_pages=5,
        )

        # Pre-create cached files
        img_path, json_path = get_page_cache_paths(section.subfolder, section.doc_id, 1)
        img_path.write_bytes(DUMMY_JPEG)
        json_path.write_text('{"pages": 5}', encoding="utf-8")

        # Execute download (should hit cache without network requests)
        result = await downloader.download_page(section, 1, fetch_text=True)

        assert result.from_cache is True
        assert result.success is True
        assert result.image_path == img_path
        assert result.json_path == json_path

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_page_network_fetch_success(self, temp_cache_dir):
        manager = SessionManager()
        downloader = PageDownloader(session=manager, enable_jitter=False)

        # Mock image and jsonp endpoints
        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            side_effect=lambda request: httpx.Response(
                200,
                content=DUMMY_JPEG if request.url.params.get("format") == "jpg" else DUMMY_JSONP.encode("utf-8")
            )
        )

        section = BookSection(
            title="Modul 01",
            doc_id="M1",
            subfolder="EKMA4111",
            url="index.php?subfolder=EKMA4111/&doc=M1.pdf",
            total_pages=3,
        )

        result = await downloader.download_page(section, 2, fetch_text=True)

        assert result.from_cache is False
        assert result.success is True
        assert result.image_path.exists()
        assert result.image_path.stat().st_size > 0
        assert result.json_path is not None
        assert result.json_path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_page_retry_on_server_error(self, temp_cache_dir):
        manager = SessionManager()
        downloader = PageDownloader(session=manager, max_retries=3, backoff_base=0.01, enable_jitter=False)

        route = respx.get("https://pustaka.ut.ac.id/reader/services/view.php")
        # 1st attempt: 500 Server Error
        # 2nd attempt: 200 OK
        route.side_effect = [
            httpx.Response(500, text="Internal Server Error"),
            httpx.Response(200, content=DUMMY_JPEG),
            httpx.Response(200, text=DUMMY_JSONP),
        ]

        section = BookSection(
            title="Modul 01",
            doc_id="M1",
            subfolder="EKMA4111",
            url="index.php",
            total_pages=1,
        )

        result = await downloader.download_page(section, 1, fetch_text=True)
        assert result.success is True
        assert result.image_path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_page_permanent_failure_recorded(self, temp_cache_dir):
        manager = SessionManager()
        downloader = PageDownloader(session=manager, max_retries=2, backoff_base=0.01, enable_jitter=False)

        # Mock continuous 500 error
        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            return_value=httpx.Response(500, text="Down")
        )

        section = BookSection(
            title="Modul 01",
            doc_id="M1",
            subfolder="EKMA4111",
            url="index.php",
            total_pages=1,
        )

        result = await downloader.download_page(section, 1, fetch_text=False)
        assert result.success is False
        assert len(downloader.failed_pages) == 1
        assert downloader.failed_pages[0][0] == "M1"
        assert downloader.failed_pages[0][1] == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_section_concurrency(self, temp_cache_dir):
        manager = SessionManager()
        downloader = PageDownloader(session=manager, max_concurrency=2, enable_jitter=False)

        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            return_value=httpx.Response(200, content=DUMMY_JPEG)
        )

        section = BookSection(
            title="Modul 01",
            doc_id="M1",
            subfolder="EKMA4111",
            url="index.php",
            total_pages=3,
        )

        progress_calls = []

        def on_prog(res, done, total):
            progress_calls.append((done, total))

        results = await downloader.download_section(section, start_page=1, end_page=3, fetch_text=False, on_progress=on_prog)

        assert len(results) == 3
        assert [r.page_num for r in results] == [1, 2, 3]
        assert len(progress_calls) == 3
        assert progress_calls[-1] == (3, 3)

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_book_orchestrator(self, temp_cache_dir):
        manager = SessionManager()
        downloader = PageDownloader(session=manager, enable_jitter=False)

        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            return_value=httpx.Response(200, content=DUMMY_JPEG)
        )

        s1 = BookSection(title="Daftar Isi", doc_id="DAFIS", subfolder="EKMA4111", url="", total_pages=2)
        s2 = BookSection(title="Modul 01", doc_id="M1", subfolder="EKMA4111", url="", total_pages=2, module_number=1)
        book = Book(code="EKMA4111", title="Pengantar Bisnis", sections=[s1, s2])

        all_results = await downloader.download_book(book, fetch_text=False)

        assert "DAFIS" in all_results
        assert "M1" in all_results
        assert len(all_results["DAFIS"]) == 2
        assert len(all_results["M1"]) == 2
