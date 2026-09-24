"""PDF Assembly Engine: stitches page assets, text layers, TOC, and metadata."""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import pymupdf
from PIL import Image

from ut_rbv.core.catalog import Book, BookSection
from ut_rbv.core.downloader import PageDownloadResult
from ut_rbv.pdf.bookmarks import TOCBuilder
from ut_rbv.pdf.optimizer import PDFOptimizer
from ut_rbv.pdf.text_layer import inject_text_layer

logger = logging.getLogger(__name__)


class PDFBuilder:
    """Assembles downloaded page images and text layers into professional PDF files."""

    @staticmethod
    def set_document_metadata(
        doc: pymupdf.Document,
        book_code: str,
        title: str,
        section_title: Optional[str] = None,
    ) -> None:
        """Embed standardized metadata into the PDF document."""
        full_title = f"{book_code} - {title}"
        if section_title:
            full_title += f" ({section_title})"

        metadata = {
            "title": full_title,
            "author": "Universitas Terbuka",
            "subject": f"Buku Materi Pokok (BMP) UT - {book_code}",
            "keywords": "UT, BMP, Ruang Baca Virtual, Modul Kuliah, Universitas Terbuka",
            "creator": "UT-RBV Downloader v1.0",
            "producer": "PyMuPDF PDF Engine",
        }
        doc.set_metadata(metadata)

    @classmethod
    def build_section_pdf(
        cls,
        section: BookSection,
        page_results: List[PageDownloadResult],
        output_file: Path,
        compress_level: str = "medium",
        book_title: Optional[str] = None,
    ) -> Path:
        """Compile a single section/module into an independent PDF."""
        doc = pymupdf.open()
        cls.set_document_metadata(
            doc,
            book_code=section.subfolder,
            title=book_title or section.title,
            section_title=section.title,
        )

        output_file.parent.mkdir(parents=True, exist_ok=True)
        sorted_pages = sorted(page_results, key=lambda p: p.page_num)

        # Collect text layer data for TOC detection
        text_layers: Dict[int, dict] = {}

        for p_res in sorted_pages:
            if not p_res.image_path.exists() or p_res.image_path.stat().st_size == 0:
                continue

            img_bytes = p_res.image_path.read_bytes()
            if compress_level == "high":
                img_bytes = PDFOptimizer.optimize_image_bytes(img_bytes, compress_level="high")

            # Determine image dimensions
            with Image.open(p_res.image_path) as img:
                w, h = img.size

            page = doc.new_page(width=float(w), height=float(h))
            page.insert_image(page.rect, stream=img_bytes)

            # Inject searchable text layer if available
            if p_res.json_path and p_res.json_path.exists():
                try:
                    raw_data = json.loads(p_res.json_path.read_text(encoding="utf-8"))
                    text_layers[p_res.page_num] = raw_data
                    inject_text_layer(page, raw_data, img_width=w, img_height=h)
                except Exception as e:
                    logger.debug(f"Gagal injeksi teks hal {p_res.page_num}: {e}")

        # Construct single section TOC
        toc = TOCBuilder.generate_toc(
            sections=[section],
            section_page_counts={section.doc_id: len(doc)},
            text_layers_by_section={section.doc_id: text_layers},
            book_title=None,
        )
        TOCBuilder.apply_toc(doc, toc)

        # Save with stream deflation and garbage collection
        doc.save(str(output_file), garbage=3, deflate=True)
        doc.close()
        logger.info(f"Berhasil membuat PDF modul: {output_file} ({len(sorted_pages)} halaman)")
        return output_file

    @classmethod
    def build_merged_book_pdf(
        cls,
        book: Book,
        download_results: Dict[str, List[PageDownloadResult]],
        output_file: Path,
        compress_level: str = "medium",
    ) -> Path:
        """Compile all downloaded sections into a single consolidated PDF with full TOC."""
        doc = pymupdf.open()
        cls.set_document_metadata(doc, book_code=book.code, title=book.title)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        actual_page_counts: Dict[str, int] = {}
        all_text_layers: Dict[str, Dict[int, dict]] = {}

        # Ensure ordered iteration based on book.sections
        target_sections = [s for s in book.sections if s.doc_id in download_results]

        for sec in target_sections:
            pages = sorted(download_results[sec.doc_id], key=lambda p: p.page_num)
            sec_page_count = 0
            sec_texts: Dict[int, dict] = {}

            for p_res in pages:
                if not p_res.image_path.exists() or p_res.image_path.stat().st_size == 0:
                    continue

                img_bytes = p_res.image_path.read_bytes()
                if compress_level == "high":
                    img_bytes = PDFOptimizer.optimize_image_bytes(img_bytes, compress_level="high")

                with Image.open(p_res.image_path) as img:
                    w, h = img.size

                page = doc.new_page(width=float(w), height=float(h))
                page.insert_image(page.rect, stream=img_bytes)
                sec_page_count += 1

                # Inject text layer
                if p_res.json_path and p_res.json_path.exists():
                    try:
                        raw_data = json.loads(p_res.json_path.read_text(encoding="utf-8"))
                        sec_texts[p_res.page_num] = raw_data
                        inject_text_layer(page, raw_data, img_width=w, img_height=h)
                    except Exception as e:
                        logger.debug(f"Gagal injeksi teks {sec.doc_id} hal {p_res.page_num}: {e}")

            actual_page_counts[sec.doc_id] = sec_page_count
            all_text_layers[sec.doc_id] = sec_texts

        # Generate and apply full book TOC
        full_toc = TOCBuilder.generate_toc(
            sections=target_sections,
            section_page_counts=actual_page_counts,
            text_layers_by_section=all_text_layers,
            book_title=f"{book.code} {book.title}",
        )
        TOCBuilder.apply_toc(doc, full_toc)

        # Save with deflation and object deduplication
        total_pages = len(doc)
        doc.save(str(output_file), garbage=3, deflate=True)
        doc.close()
        logger.info(f"Berhasil membuat Merged PDF: {output_file} ({total_pages} total halaman)")
        return output_file
