"""Catalog and book module structure parser for UT-RBV."""

import re
import json
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Union
from bs4 import BeautifulSoup

from ut_rbv.core.auth import UTRBVError, UnreachableError
from ut_rbv.core.session import SessionManager

logger = logging.getLogger(__name__)


class BookNotFoundError(UTRBVError):
    """Raised when the specified course book code is not found on UT RBV."""
    pass


class CatalogParseError(UTRBVError):
    """Raised when book structure or sections cannot be parsed."""
    pass


@dataclass
class BookSection:
    """Represents a section or module of a course book (e.g. DAFIS, Modul 1)."""
    title: str
    doc_id: str
    subfolder: str
    url: str
    total_pages: int = 0
    module_number: Optional[int] = None

    def __post_init__(self):
        # Auto-detect numeric module number from doc_id or title
        # e.g. M1 -> 1, Modul 02 -> 2
        if self.module_number is None:
            match = re.search(r"[mM](\d+)", self.doc_id)
            if match:
                self.module_number = int(match.group(1))
            else:
                title_match = re.search(r"(?:modul|bab)\s*0*(\d+)", self.title, re.IGNORECASE)
                if title_match:
                    self.module_number = int(title_match.group(1))


@dataclass
class Book:
    """Represents a full course book on UT RBV."""
    code: str
    title: str
    sections: List[BookSection] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        """Calculate total pages across all sections."""
        return sum(s.total_pages for s in self.sections)

    @property
    def module_sections(self) -> List[BookSection]:
        """Return only module sections (excluding DAFIS, cover, lampiran)."""
        return [s for s in self.sections if s.module_number is not None]

    def filter_sections(
        self,
        target_modules: Optional[Union[List[int], str]] = None,
        include_dafis: bool = True,
    ) -> List[BookSection]:
        """Filter book sections based on module numbers or comma-separated string.

        Args:
            target_modules: e.g. [1, 2, 3] or "1,2,3" or "1-4"
            include_dafis: Whether to include Daftar Isi (DAFIS) if present

        Returns:
            Filtered list of BookSection
        """
        if not target_modules:
            return list(self.sections)

        # Parse target module numbers if string
        allowed_nums = set()
        if isinstance(target_modules, str):
            for part in target_modules.split(","):
                part = part.strip()
                if "-" in part:
                    start_str, end_str = part.split("-", 1)
                    allowed_nums.update(range(int(start_str), int(end_str) + 1))
                elif part.isdigit():
                    allowed_nums.add(int(part))
        else:
            allowed_nums = set(target_modules)

        filtered = []
        for sec in self.sections:
            if sec.module_number is not None and sec.module_number in allowed_nums:
                filtered.append(sec)
            elif include_dafis and "dafis" in sec.doc_id.lower():
                filtered.append(sec)

        return filtered


class CatalogParser:
    """Parses book catalog metadata, module tables, and section pages."""

    @staticmethod
    def validate_code(code: str) -> str:
        """Validate and normalize UT course code (e.g. 'ekma4111' -> 'EKMA4111')."""
        normalized = code.strip().upper()
        if not re.match(r"^[A-Z0-9_\-]{4,12}$", normalized):
            raise ValueError(f"Kode mata kuliah tidak valid: '{code}'. Contoh: EKMA4111, MKDU4110")
        return normalized

    @classmethod
    def clean_doc_id(cls, raw_doc: str) -> str:
        """Clean doc param from URL to get internal doc_id (e.g. 'DAFIS.pdf' -> 'DAFIS')."""
        # If full URL: index.php?subfolder=EKMA4111/&doc=M1.pdf
        if "doc=" in raw_doc:
            raw_doc = raw_doc.split("doc=")[-1].split("&")[0]
        cleaned = re.sub(r"\.pdf$", "", raw_doc, flags=re.IGNORECASE)
        return cleaned.strip("/").strip()

    @classmethod
    def parse_book_index(cls, html_text: str, code: str) -> Book:
        """Parse HTML page of book index into a Book object."""
        if not html_text or not html_text.strip():
            raise BookNotFoundError(f"Data buku kosong untuk kode: {code}")

        soup = BeautifulSoup(html_text, "html.parser")

        # 1. Detect Book Title
        title = ""
        # Check h2 or h1
        for heading in soup.find_all(["h2", "h1", "h3"]):
            text = heading.get_text().strip()
            if text and "about rbv" not in text.lower():
                title = text
                break

        if not title and soup.title:
            title = soup.title.get_text().strip()

        # If title still starts with code, strip the redundant prefix or format cleanly
        if not title:
            title = code

        # Clean title (e.g. "EKMA4111 Pengantar Bisnis" -> "Pengantar Bisnis")
        clean_title = re.sub(rf"^{code}\s*[-–:]*\s*", "", title, flags=re.IGNORECASE).strip()
        if not clean_title:
            clean_title = title

        # 2. Extract sections from table headers <th> or links <a>
        sections: List[BookSection] = []
        seen_docs = set()

        for th in soup.find_all(["th", "td", "li"]):
            link = th.find("a")
            if not link or not link.get("href"):
                continue

            href = link["href"]
            if "doc=" not in href:
                continue

            doc_id = cls.clean_doc_id(href)
            if not doc_id or doc_id in seen_docs:
                continue

            display_title = link.get_text().strip()
            if not display_title:
                display_title = doc_id

            seen_docs.add(doc_id)
            section = BookSection(
                title=display_title,
                doc_id=doc_id,
                subfolder=code,
                url=href,
            )
            sections.append(section)

        if not sections:
            # Check if there is an error message or not found message
            if "tidak ditemukan" in html_text.lower() or "not found" in html_text.lower():
                raise BookNotFoundError(f"Buku dengan kode '{code}' tidak ditemukan di sistem RBV UT.")
            raise CatalogParseError(f"Gagal menemukan daftar modul/section pada buku '{code}'.")

        return Book(code=code, title=clean_title, sections=sections)

    @classmethod
    async def fetch_book(cls, session: SessionManager, code: str) -> Book:
        """Fetch book index page from RBV and parse metadata and sections."""
        norm_code = cls.validate_code(code)
        url = f"{session.base_url}index.php"
        params = {"modul": norm_code}

        try:
            res = await session.get(url, params=params)
        except Exception as e:
            raise UnreachableError(f"Gagal mengakses buku {norm_code}: {e}") from e

        if not res.is_success:
            raise BookNotFoundError(f"Server mengembalikan status {res.status_code} untuk modul {norm_code}")

        book = cls.parse_book_index(res.text, norm_code)
        return book

    @classmethod
    async def detect_section_pages(cls, session: SessionManager, section: BookSection) -> int:
        """Detect the total number of pages for a given section using the JSONP service."""
        url = f"{session.base_url}services/view.php"
        params = {
            "doc": section.doc_id,
            "format": "jsonp",
            "subfolder": f"{section.subfolder}/",
            "page": 1,
        }
        headers = {
            "Referer": f"{session.base_url}index.php?modul={section.subfolder}",
        }

        try:
            res = await session.get(url, params=params, headers=headers)
            if not res.is_success or not res.text.strip():
                return 0

            raw_text = res.text.strip().rstrip(";")
            if "(" in raw_text and raw_text.endswith(")"):
                raw_text = raw_text[raw_text.find("(") + 1 : raw_text.rfind(")")].strip()

            data = json.loads(raw_text)
            if isinstance(data, list) and data:
                total = data[0].get("pages", 0)
            elif isinstance(data, dict):
                total = data.get("pages", 0)
            else:
                total = 0

            section.total_pages = total
            return total
        except Exception as e:
            logger.warning(f"Tidak dapat mendeteksi total halaman untuk {section.doc_id}: {e}")
            return 0
