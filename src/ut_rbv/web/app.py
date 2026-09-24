"""FastAPI backend application for UT-RBV Local Web Dashboard."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ut_rbv import __version__
from ut_rbv.core.auth import InvalidCredentialsError, SessionExpiredError
from ut_rbv.core.catalog import CatalogParser, Book, BookSection, BookNotFoundError
from ut_rbv.core.downloader import PageDownloader
from ut_rbv.core.session import SessionManager
from ut_rbv.pdf.builder import PDFBuilder
from ut_rbv.utils.paths import get_output_dir

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent
TEMPLATES_DIR = WEB_DIR / "templates"
STATIC_DIR = WEB_DIR / "static"

app = FastAPI(
    title="UT-RBV Downloader Web Dashboard",
    version=__version__,
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# In-memory task progress tracker
tasks_state: Dict[str, Dict[str, Any]] = {}


class InspectRequest(BaseModel):
    code: str
    cookie: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


class DownloadRequest(BaseModel):
    code: str
    doc_ids: List[str]
    merge: bool = True
    compress: str = "medium"
    cookie: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None


@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    """Serve main HTML dashboard."""
    index_file = TEMPLATES_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Template index.html tidak ditemukan.")
    return FileResponse(index_file)


@app.post("/api/inspect")
async def inspect_book(req: InspectRequest):
    """Inspect course book structure and total pages."""
    try:
        norm_code = CatalogParser.validate_code(req.code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    async with SessionManager() as session:
        if req.cookie:
            session.set_session_cookie(req.cookie)
        elif req.username and req.password:
            try:
                await session.login_with_credentials(req.username, req.password, probe_code=norm_code)
            except InvalidCredentialsError as e:
                raise HTTPException(status_code=401, detail=str(e))
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Gagal login ke RBV: {e}")

        try:
            book = await CatalogParser.fetch_book(session, norm_code)
        except BookNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except SessionExpiredError:
            raise HTTPException(
                status_code=401,
                detail=f"Server UT mewajibkan login untuk mengakses buku '{norm_code}'. Silakan buka menu 'Pengaturan Autentikasi' dan masukkan Cookie Sesi (PHPSESSID) atau NIM & Password Anda.",
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Gagal mengambil katalog: {e}")

        # Detect pages for each section
        for sec in book.sections:
            if sec.total_pages <= 0:
                sec.total_pages = await CatalogParser.detect_section_pages(session, sec)

        return {
            "code": book.code,
            "title": book.title,
            "total_pages": book.total_pages,
            "sections": [
                {
                    "doc_id": s.doc_id,
                    "title": s.title,
                    "total_pages": s.total_pages,
                    "module_number": s.module_number,
                }
                for s in book.sections
            ],
        }


async def _run_download_task(task_id: str, req: DownloadRequest):
    """Background task executing the complete download and PDF assembly pipeline."""
    state = tasks_state[task_id]
    output_dir = get_output_dir()

    try:
        norm_code = CatalogParser.validate_code(req.code)
        state["latest_log"] = f"Menghubungkan ke portal RBV untuk buku {norm_code}..."

        async with SessionManager() as session:
            if req.cookie:
                session.set_session_cookie(req.cookie)
            elif req.username and req.password:
                await session.login_with_credentials(req.username, req.password, probe_code=norm_code)

            book = await CatalogParser.fetch_book(session, norm_code)
            # Filter sections to only selected doc_ids
            selected_set = set(req.doc_ids)
            target_sections = [s for s in book.sections if s.doc_id in selected_set]

            for sec in target_sections:
                if sec.total_pages <= 0:
                    sec.total_pages = await CatalogParser.detect_section_pages(session, sec)

            total_pages = sum(s.total_pages for s in target_sections if s.total_pages > 0)
            state["total_pages"] = max(1, total_pages)
            state["current_stage"] = "Mengunduh Halaman Modul..."

            downloader = PageDownloader(session=session, max_concurrency=2)
            all_downloads: Dict[str, List] = {}
            completed_count = 0

            for sec in target_sections:
                state["latest_log"] = f"Mengunduh {sec.title} ({sec.doc_id})..."
                pages = await downloader.download_section(sec, fetch_text=True)
                all_downloads[sec.doc_id] = pages
                completed_count += len(pages)
                state["completed_pages"] = completed_count
                state["percentage"] = min(90, (completed_count / max(1, total_pages)) * 90)

            # PDF Assembly
            state["current_stage"] = "Menyusun Dokumen PDF..."
            state["latest_log"] = "Menggabungkan citra dan lapisan teks searchable ke PDF..."
            state["percentage"] = 92

            generated_files = []

            if req.merge:
                merged_name = f"{book.code} - {book.title}.pdf"
                out_file = output_dir / merged_name
                PDFBuilder.build_merged_book_pdf(
                    book=book,
                    download_results=all_downloads,
                    output_file=out_file,
                    compress_level=req.compress,
                )
                generated_files.append({"filename": merged_name, "path": str(out_file)})
            else:
                for sec in target_sections:
                    sec_pages = all_downloads.get(sec.doc_id, [])
                    if not sec_pages:
                        continue
                    sec_name = f"{book.code}_{sec.doc_id}.pdf"
                    out_file = output_dir / sec_name
                    PDFBuilder.build_section_pdf(
                        section=sec,
                        page_results=sec_pages,
                        output_file=out_file,
                        compress_level=req.compress,
                        book_title=book.title,
                    )
                    generated_files.append({"filename": sec_name, "path": str(out_file)})

            state["status"] = "completed"
            state["current_stage"] = "Selesai!"
            state["percentage"] = 100
            state["generated_files"] = generated_files
            state["latest_log"] = f"Berhasil membuat {len(generated_files)} file PDF!"

    except Exception as e:
        logger.exception("Kesalahan dalam background download task:")
        state["status"] = "failed"
        state["error_message"] = str(e)
        state["latest_log"] = f"Gagal: {e}"


@app.post("/api/download")
async def start_download(req: DownloadRequest, background_tasks: BackgroundTasks):
    """Start asynchronous book download task."""
    task_id = str(uuid.uuid4())
    tasks_state[task_id] = {
        "task_id": task_id,
        "status": "running",
        "current_stage": "Menyiapkan Antrean...",
        "percentage": 0,
        "completed_pages": 0,
        "total_pages": 0,
        "latest_log": "Tugas unduhan telah dijadwalkan.",
        "generated_files": [],
        "error_message": None,
    }

    background_tasks.add_task(_run_download_task, task_id, req)
    return {"task_id": task_id}


@app.get("/api/progress/{task_id}")
async def get_progress(task_id: str):
    """Get real-time progress status of a download task."""
    if task_id not in tasks_state:
        raise HTTPException(status_code=404, detail="Task ID tidak ditemukan.")
    return tasks_state[task_id]


@app.get("/api/files/{filename}")
async def get_generated_file(filename: str):
    """Download a compiled PDF file from the output directory."""
    # Sanitize filename to prevent directory traversal
    clean_name = Path(filename).name
    file_path = get_output_dir() / clean_name

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File PDF tidak ditemukan.")

    return FileResponse(
        file_path,
        media_type="application/pdf",
        filename=clean_name,
    )
