"""Hierarchical Table of Contents (TOC) and Bookmarks builder for PDF documents."""

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union
import pymupdf

from ut_rbv.core.catalog import Book, BookSection

logger = logging.getLogger(__name__)


@dataclass
class BookmarkItem:
    """Represents a single outline entry in a PDF document.

    Attributes:
        level: Hierarchy depth (1 = Module / Major section, 2 = Sub-section / KB).
        title: Title of the bookmark displayed in the PDF reader.
        page_number: 1-indexed target page number.
    """
    level: int
    title: str
    page_number: int

    def to_pymupdf(self) -> List[Union[int, str]]:
        """Convert to PyMuPDF TOC entry format: [level, title, page_number]."""
        return [self.level, self.title.strip(), max(1, int(self.page_number))]


# Regex patterns for detecting common UT BMP sub-sections
SUBSECTION_PATTERNS = [
    re.compile(r"^(kegiatan\s+belajar\s+\d+(?:\s*[:\-–]\s*[^\n\r]+)?)", re.IGNORECASE),
    re.compile(r"^(tes\s+formatif\s+\d*)", re.IGNORECASE),
    re.compile(r"^(rangkuman)", re.IGNORECASE),
    re.compile(r"^(kunci\s+jawaban\s+tes\s+formatif(?:\s+\d+)?)", re.IGNORECASE),
    re.compile(r"^(daftar\s+pustaka)", re.IGNORECASE),
    re.compile(r"^(glosarium)", re.IGNORECASE),
]


class TOCBuilder:
    """Constructs and applies hierarchical outlines (bookmarks) to PDF documents."""

    @staticmethod
    def extract_subsections_from_page_text(
        text_data: Union[Dict[str, Any], List[Dict[str, Any]]],
        absolute_page: int,
    ) -> List[BookmarkItem]:
        """Scan a page's text metadata for sub-sections (e.g. Kegiatan Belajar)."""
        if isinstance(text_data, list):
            text_data = text_data[0] if text_data else {}
        if not isinstance(text_data, dict):
            return []

        subsections: List[BookmarkItem] = []
        raw_items = text_data.get("text", [])
        seen_titles = set()

        for item in raw_items:
            line = str(item.get("text", "")).strip()
            if not line or len(line) < 4:
                continue

            for pattern in SUBSECTION_PATTERNS:
                match = pattern.search(line)
                if match:
                    found_title = match.group(1).strip()
                    # Clean repeated whitespace
                    clean_title = re.sub(r"\s+", " ", found_title)
                    norm_key = clean_title.lower()
                    if norm_key not in seen_titles:
                        seen_titles.add(norm_key)
                        subsections.append(
                            BookmarkItem(
                                level=2,
                                title=clean_title,
                                page_number=absolute_page,
                            )
                        )
                    break

        return subsections

    @classmethod
    def generate_toc(
        cls,
        sections: List[BookSection],
        section_page_counts: Dict[str, int],
        text_layers_by_section: Optional[Dict[str, Dict[int, Dict[str, Any]]]] = None,
        book_title: Optional[str] = None,
    ) -> List[BookmarkItem]:
        """Generate complete hierarchical TOC with accurate page offsets.

        Args:
            sections: List of BookSections in chronological order.
            section_page_counts: Mapping of doc_id to actual page count.
            text_layers_by_section: Optional nested mapping of [doc_id][page_num] -> text_data.
            book_title: Optional main book title for page 1 cover bookmark.

        Returns:
            List of BookmarkItem instances.
        """
        bookmarks: List[BookmarkItem] = []
        current_page_offset = 1  # 1-indexed

        # Optional Top-Level Cover Bookmark
        if book_title:
            bookmarks.append(
                BookmarkItem(
                    level=1,
                    title=f"Cover: {book_title}",
                    page_number=1,
                )
            )

        for sec in sections:
            page_count = section_page_counts.get(sec.doc_id, sec.total_pages)
            if page_count <= 0:
                continue

            section_start_page = current_page_offset

            # Level 1 Bookmark for the Module / Section
            section_display_title = sec.title
            if sec.module_number is not None and not section_display_title.lower().startswith("modul"):
                section_display_title = f"Modul {sec.module_number:02d}: {section_display_title}"

            bookmarks.append(
                BookmarkItem(
                    level=1,
                    title=section_display_title,
                    page_number=section_start_page,
                )
            )

            # Detect Level 2 sub-sections from text layer if provided
            if text_layers_by_section and sec.doc_id in text_layers_by_section:
                sec_texts = text_layers_by_section[sec.doc_id]
                for p_num in range(1, page_count + 1):
                    if p_num in sec_texts:
                        abs_page = section_start_page + (p_num - 1)
                        sub_items = cls.extract_subsections_from_page_text(sec_texts[p_num], abs_page)
                        bookmarks.extend(sub_items)

            current_page_offset += page_count

        return bookmarks

    @classmethod
    def apply_toc(
        cls,
        doc: pymupdf.Document,
        bookmarks: List[BookmarkItem],
    ) -> None:
        """Apply bookmarks list directly to PyMuPDF document outline."""
        if not bookmarks or len(doc) == 0:
            return

        max_page = len(doc)
        toc_matrix = []

        for b in bookmarks:
            # Constrain target page to document bounds
            clamped_page = min(max(1, b.page_number), max_page)
            toc_matrix.append([b.level, b.title, clamped_page])

        try:
            doc.set_toc(toc_matrix)
            logger.debug(f"Berhasil menyuntikkan {len(toc_matrix)} bookmark ke dokumen PDF.")
        except Exception as e:
            logger.warning(f"Gagal menyuntikkan TOC ke dokumen PDF: {e}")
