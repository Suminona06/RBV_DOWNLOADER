"""Path and directory management for UT-RBV cache and outputs."""

import os
from pathlib import Path
from typing import Optional


def get_cache_root() -> Path:
    """Get root cache directory adhering to XDG standard or environment variable."""
    env_cache = os.environ.get("UT_RBV_CACHE_DIR") or os.environ.get("READER_RBV_HOME")
    if env_cache:
        path = Path(env_cache)
    else:
        xdg_cache = os.environ.get("XDG_CACHE_HOME")
        if xdg_cache:
            path = Path(xdg_cache) / "ut-rbv"
        else:
            path = Path.home() / ".cache" / "ut-rbv"

    path.mkdir(parents=True, exist_ok=True)
    return path


def get_book_cache_dir(book_code: str) -> Path:
    """Get cache directory for a specific course book."""
    path = get_cache_root() / book_code.strip().upper()
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_output_dir(custom_path: Optional[str] = None) -> Path:
    """Get destination directory for compiled PDF files."""
    if custom_path:
        path = Path(custom_path)
    else:
        path = Path.cwd() / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_page_cache_paths(book_code: str, doc_id: str, page_num: int) -> tuple[Path, Path]:
    """Get standardized cache file paths for an image and its json text layer."""
    book_dir = get_book_cache_dir(book_code)
    clean_doc = doc_id.strip()
    img_path = book_dir / f"{clean_doc}_{page_num:03d}.jpg"
    json_path = book_dir / f"{clean_doc}_{page_num:03d}.json"
    return img_path, json_path
