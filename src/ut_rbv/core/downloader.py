"""Asynchronous page asset downloader with caching, rate limiting, and retries."""

import asyncio
import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple, Dict, Any
import httpx

from ut_rbv.core.auth import UTRBVError, UnreachableError
from ut_rbv.core.catalog import Book, BookSection, CatalogParser
from ut_rbv.core.session import SessionManager
from ut_rbv.utils.paths import get_page_cache_paths, get_book_cache_dir

logger = logging.getLogger(__name__)


class DownloadError(UTRBVError):
    """Raised when page download fails permanently after retries."""
    pass


@dataclass
class PageDownloadResult:
    """Result of a single page download."""
    doc_id: str
    page_num: int
    image_path: Path
    json_path: Optional[Path] = None
    from_cache: bool = False
    success: bool = True
    error_message: Optional[str] = None


class PageDownloader:
    """Handles asynchronous downloading of book pages with rate limits and caching."""

    def __init__(
        self,
        session: SessionManager,
        max_concurrency: int = 4,
        max_retries: int = 5,
        backoff_base: float = 0.5,
        enable_jitter: bool = True,
    ):
        self.session = session
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.enable_jitter = enable_jitter
        self.failed_pages: List[Tuple[str, int, str]] = []

    async def _apply_jitter(self, min_ms: float = 0.6, max_ms: float = 1.5):
        """Add realistic human delay between network requests to be gentle on UT servers and avoid WAF bans."""
        if self.enable_jitter:
            delay = random.uniform(min_ms, max_ms)
            await asyncio.sleep(delay)

    async def download_page(
        self,
        section: BookSection,
        page_num: int,
        fetch_text: bool = True,
    ) -> PageDownloadResult:
        """Download a single page image and optional text layer, with disk cache support."""
        img_path, json_path = get_page_cache_paths(section.subfolder, section.doc_id, page_num)

        # 1. Check disk cache hit
        img_cached = img_path.exists() and img_path.stat().st_size > 0
        json_cached = not fetch_text or (json_path.exists() and json_path.stat().st_size > 0)

        if img_cached and json_cached:
            logger.debug(f"Cache hit: {section.doc_id} hal {page_num}")
            return PageDownloadResult(
                doc_id=section.doc_id,
                page_num=page_num,
                image_path=img_path,
                json_path=json_path if json_path.exists() else None,
                from_cache=True,
                success=True,
            )

        # 2. Network download with concurrency control and retries
        async with self.semaphore:
            img_success = img_cached
            last_err = None

            # Download Image
            if not img_cached:
                img_url = f"{self.session.base_url}services/view.php"
                img_params = {
                    "doc": section.doc_id,
                    "format": "jpg",
                    "subfolder": f"{section.subfolder}/",
                    "page": page_num,
                }
                img_headers = {
                    "Referer": f"{self.session.base_url}index.php?subfolder={section.subfolder}/&doc={section.doc_id}.pdf",
                    "Sec-Fetch-Dest": "image",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "same-origin",
                    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                }

                for attempt in range(1, self.max_retries + 1):
                    await self._apply_jitter()
                    try:
                        res = await self.session.get(img_url, params=img_params, headers=img_headers)
                        # Check if response is valid image or HTML error
                        if res.is_success and res.content.startswith(b"\xff\xd8") or b"JFIF" in res.content[:20] or b"Exif" in res.content[:20] or len(res.content) > 500:
                            # Valid JPEG content
                            img_path.write_bytes(res.content)
                            img_success = True
                            break
                        elif res.status_code in (429, 500, 502, 503, 504):
                            raise httpx.HTTPStatusError(f"HTTP {res.status_code}", request=res.request, response=res)
                        else:
                            last_err = f"Respon bukan citra valid (status {res.status_code}, len={len(res.content)})"
                    except Exception as e:
                        last_err = str(e)
                        if attempt < self.max_retries:
                            backoff = self.backoff_base * (2 ** (attempt - 1)) + random.uniform(0.1, 0.3)
                            logger.warning(f"Retry {attempt}/{self.max_retries} hal {page_num} [{section.doc_id}]: {e} (jeda {backoff:.2f}s)")
                            await asyncio.sleep(backoff)

            if not img_success:
                self.failed_pages.append((section.doc_id, page_num, str(last_err)))
                return PageDownloadResult(
                    doc_id=section.doc_id,
                    page_num=page_num,
                    image_path=img_path,
                    json_path=None,
                    from_cache=False,
                    success=False,
                    error_message=last_err,
                )

            # Download JSONP Text Layer (optional)
            saved_json_path = None
            if fetch_text and not json_cached:
                json_url = f"{self.session.base_url}services/view.php"
                json_params = {
                    "doc": section.doc_id,
                    "format": "jsonp",
                    "subfolder": f"{section.subfolder}/",
                    "page": page_num,
                }
                json_headers = {
                    "Referer": f"{self.session.base_url}index.php?subfolder={section.subfolder}/&doc={section.doc_id}.pdf",
                    "Sec-Fetch-Dest": "script",
                    "Sec-Fetch-Mode": "no-cors",
                    "Sec-Fetch-Site": "same-origin",
                    "Accept": "*/*",
                }
                try:
                    await self._apply_jitter(0.2, 0.5)
                    jres = await self.session.get(json_url, params=json_params, headers=json_headers)
                    if jres.is_success and jres.text.strip():
                        raw_text = jres.text.strip().rstrip(";")
                        if "(" in raw_text and raw_text.endswith(")"):
                            raw_text = raw_text[raw_text.find("(") + 1 : raw_text.rfind(")")].strip()
                        # Validate json parseable
                        parsed = json.loads(raw_text)
                        json_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
                        saved_json_path = json_path
                except Exception as e:
                    logger.debug(f"JSONP layer tidak tersedia untuk {section.doc_id} hal {page_num}: {e}")

            elif json_path.exists():
                saved_json_path = json_path

            return PageDownloadResult(
                doc_id=section.doc_id,
                page_num=page_num,
                image_path=img_path,
                json_path=saved_json_path,
                from_cache=False,
                success=True,
            )

    async def download_section(
        self,
        section: BookSection,
        start_page: int = 1,
        end_page: Optional[int] = None,
        fetch_text: bool = True,
        on_progress: Optional[Callable[[PageDownloadResult, int, int], None]] = None,
    ) -> List[PageDownloadResult]:
        """Download all pages in a given section concurrently."""
        if end_page is None:
            if section.total_pages <= 0:
                # Probing total pages
                section.total_pages = await CatalogParser.detect_section_pages(self.session, section)
            end_page = max(1, section.total_pages)

        total_pages = end_page - start_page + 1
        logger.info(f"Mengunduh {section.title} ({section.doc_id}): hal {start_page} s/d {end_page} ({total_pages} hal)")

        tasks = []
        for page_num in range(start_page, end_page + 1):
            tasks.append(self.download_page(section, page_num, fetch_text=fetch_text))

        results: List[PageDownloadResult] = []
        completed_count = 0

        for coro in asyncio.as_completed(tasks):
            res = await coro
            completed_count += 1
            results.append(res)
            if on_progress:
                on_progress(res, completed_count, total_pages)

        # Sort results by page_num ascending
        results.sort(key=lambda r: r.page_num)
        return results

    async def download_book(
        self,
        book: Book,
        target_modules: Optional[Any] = None,
        fetch_text: bool = True,
        on_section_start: Optional[Callable[[BookSection, int, int], None]] = None,
        on_page_progress: Optional[Callable[[PageDownloadResult, int, int], None]] = None,
    ) -> Dict[str, List[PageDownloadResult]]:
        """Download full course book or filtered modules."""
        target_sections = book.filter_sections(target_modules)
        total_sections = len(target_sections)
        all_results: Dict[str, List[PageDownloadResult]] = {}

        total_book_pages = sum(s.total_pages for s in target_sections if s.total_pages > 0)
        overall_completed_pages = 0

        for idx, section in enumerate(target_sections, start=1):
            if on_section_start:
                on_section_start(section, idx, total_sections)

            def wrapped_progress(page_res: PageDownloadResult, sec_done: int, sec_total: int):
                nonlocal overall_completed_pages
                overall_completed_pages += 1
                if on_page_progress:
                    on_page_progress(page_res, overall_completed_pages, max(overall_completed_pages, total_book_pages))

            sec_results = await self.download_section(
                section=section,
                fetch_text=fetch_text,
                on_progress=wrapped_progress,
            )
            all_results[section.doc_id] = sec_results

        return all_results
