"""Unit tests for FastAPI Web Dashboard endpoints."""

import pytest
from fastapi.testclient import TestClient
import respx
import httpx
from pathlib import Path

from ut_rbv.web.app import app
from ut_rbv.utils.paths import get_output_dir

SAMPLE_CATALOG_HTML = """
<!DOCTYPE html>
<html>
<head><title>EKMA4111 - Pengantar Bisnis</title></head>
<body>
    <h2>EKMA4111 Pengantar Bisnis</h2>
    <table>
        <tr><th><a href="index.php?subfolder=EKMA4111/&doc=DAFIS.pdf">Daftar Isi</a></th></tr>
        <tr><th><a href="index.php?subfolder=EKMA4111/&doc=M1.pdf">Modul 01</a></th></tr>
    </table>
</body>
</html>
"""

SAMPLE_JSONP = '([{"number": 1, "pages": 12, "height": 800, "width": 600, "text": []}])'


class TestWebDashboard:
    """Test suite for FastAPI endpoints."""

    @pytest.fixture
    def client(self):
        return TestClient(app)

    def test_serve_dashboard_html(self, client):
        response = client.get("/")
        assert response.status_code == 200
        assert "UT-RBV Downloader" in response.text
        assert "Periksa Buku" in response.text

    def test_api_inspect_invalid_code(self, client):
        response = client.post("/api/inspect", json={"code": "bad!code"})
        assert response.status_code == 400
        assert "Kode mata kuliah tidak valid" in response.json()["detail"]

    @respx.mock
    def test_api_inspect_success(self, client):
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_CATALOG_HTML)
        )
        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_JSONP)
        )

        response = client.post("/api/inspect", json={"code": "EKMA4111"})
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == "EKMA4111"
        assert data["title"] == "Pengantar Bisnis"
        assert len(data["sections"]) == 2
        assert data["sections"][0]["doc_id"] == "DAFIS"
        assert data["sections"][1]["doc_id"] == "M1"
        assert data["sections"][1]["total_pages"] == 12

    def test_api_download_and_progress(self, client):
        # 1. Start download task
        payload = {
            "code": "EKMA4111",
            "doc_ids": ["M1"],
            "merge": True,
            "compress": "medium",
        }
        res = client.post("/api/download", json=payload)
        assert res.status_code == 200
        task_id = res.json()["task_id"]
        assert task_id is not None

        # 2. Check task progress
        prog_res = client.get(f"/api/progress/{task_id}")
        assert prog_res.status_code == 200
        state = prog_res.json()
        assert state["task_id"] == task_id
        assert state["status"] in ("running", "completed", "failed")

    def test_api_files_not_found(self, client):
        res = client.get("/api/files/non_existent_book.pdf")
        assert res.status_code == 404

    def test_api_files_success(self, client, tmp_path, monkeypatch):
        # Create a mock output file
        out_dir = tmp_path / "downloads"
        out_dir.mkdir(parents=True, exist_ok=True)
        pdf_file = out_dir / "EKMA4111 - Pengantar Bisnis.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 mock pdf content")

        # Point get_output_dir to out_dir
        monkeypatch.setattr("ut_rbv.web.app.get_output_dir", lambda: out_dir)

        res = client.get(f"/api/files/{pdf_file.name}")
        assert res.status_code == 200
        assert res.content == b"%PDF-1.4 mock pdf content"
        assert "application/pdf" in res.headers["content-type"]
