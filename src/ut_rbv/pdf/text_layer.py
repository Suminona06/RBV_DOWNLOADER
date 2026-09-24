"""Searchable transparent text layer parser and injector for PDF pages."""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import pymupdf

logger = logging.getLogger(__name__)


def clean_jsonp_text(raw_text: str) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    """Clean and parse JSON/JSONP string into python dictionary or list."""
    trimmed = raw_text.strip()
    if not trimmed:
        raise ValueError("Payload JSONP kosong.")

    # Remove outer parenthesis e.g. ([{...}]) or ( {...} )
    if trimmed.startswith("(") and trimmed.endswith(")"):
        trimmed = trimmed[1:-1].strip()

    # Remove callback function wrapper e.g. callback_func({...});
    callback_match = re.match(r"^[a-zA-Z_$][a-zA-Z0-9_$]*\s*\((.*)\)\s*;?$", trimmed, re.DOTALL)
    if callback_match:
        trimmed = callback_match.group(1).strip()

    # Re-check parenthesis if nested
    if trimmed.startswith("(") and trimmed.endswith(")"):
        trimmed = trimmed[1:-1].strip()

    return json.loads(trimmed)


def parse_page_text_data(json_input: Union[Dict[str, Any], List[Dict[str, Any]], str, Path]) -> Optional[Dict[str, Any]]:
    """Load and normalize page text metadata into a single dictionary."""
    if isinstance(json_input, Path):
        if json_input.is_file():
            content = json_input.read_text(encoding="utf-8").strip()
            data = clean_jsonp_text(content)
        else:
            return None
    elif isinstance(json_input, str):
        trimmed = json_input.strip()
        # If it looks like a path (short, no newlines, no json brackets)
        if len(trimmed) < 260 and "\n" not in trimmed and not trimmed.startswith(("{", "[", "(")):
            p = Path(trimmed)
            if p.is_file():
                content = p.read_text(encoding="utf-8").strip()
                data = clean_jsonp_text(content)
            else:
                return None
        else:
            data = clean_jsonp_text(trimmed)
    else:
        data = json_input

    if isinstance(data, list):
        if not data:
            return None
        return data[0]
    elif isinstance(data, dict):
        return data
    return None


def inject_text_layer(
    page: pymupdf.Page,
    json_input: Union[Dict[str, Any], List[Dict[str, Any]], str, Path],
    img_width: Optional[float] = None,
    img_height: Optional[float] = None,
) -> bool:
    """Inject invisible searchable text onto a PyMuPDF Page.

    Uses PDF standard render_mode=3 (invisible text) positioned according to
    RBV's coordinate metadata, allowing full text search and copy-paste.

    Args:
        page: PyMuPDF Page object to modify.
        json_input: JSON dict, path, or string from RBV services/view.php.
        img_width: Optional original image width for coordinate scaling.
        img_height: Optional original image height for coordinate scaling.

    Returns:
        True if text was injected, False if skipped or no text present.
    """
    try:
        page_data = parse_page_text_data(json_input)
    except Exception as e:
        logger.warning(f"Gagal mem-parse data JSONP text layer: {e}")
        return False

    if not page_data:
        return False

    raw_items = page_data.get("text", [])
    if not raw_items:
        return False

    # Determine original source coordinate bounds
    src_width = float(img_width or page_data.get("width") or page.rect.width)
    src_height = float(img_height or page_data.get("height") or page.rect.height)

    if src_width <= 0 or src_height <= 0:
        return False

    # Coordinate scaling factor to target PDF page
    scale_x = page.rect.width / src_width
    scale_y = page.rect.height / src_height

    # Sort text items to preserve natural reading order (top-to-bottom, left-to-right)
    # Using small y-bucket tolerance of 4 pixels
    def sort_key(item: Dict[str, Any]) -> tuple:
        top = float(item.get("top", 0))
        left = float(item.get("left", 0))
        bucket = round(top / 4.0)
        return (bucket, left)

    sorted_items = sorted(raw_items, key=sort_key)
    injected_count = 0

    for item in sorted_items:
        text_content = str(item.get("text", "")).strip()
        if not text_content:
            continue

        left = float(item.get("left", 0)) * scale_x
        top = float(item.get("top", 0)) * scale_y
        w = float(item.get("width", 0)) * scale_x
        h = float(item.get("height", 12)) * scale_y

        fontsize = max(6.0, h * 0.85)

        # Baseline alignment for insert_text
        baseline_y = top + h * 0.8
        point = pymupdf.Point(left, baseline_y)

        try:
            page.insert_text(
                point,
                text_content,
                fontsize=fontsize,
                render_mode=3,  # 3 = invisible text
            )
            injected_count += 1
        except Exception as e:
            logger.debug(f"Gagal menyisipkan teks '{text_content}': {e}")

    return injected_count > 0
