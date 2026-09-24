"""Unit and integration tests for the CLI interface."""

import pytest
from click.testing import CliRunner
import respx
import httpx
from pathlib import Path

from ut_rbv.cli import main
from PIL import Image
import io

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

_buf = io.BytesIO()
Image.new("RGB", (100, 100), color="white").save(_buf, format="JPEG")
DUMMY_JPEG = _buf.getvalue()

DUMMY_JSONP = '([{"number": 1, "pages": 1, "height": 800, "width": 600, "text": [{"text": "Hello UT", "top": 50, "left": 50, "width": 100, "height": 20}]}])'


class TestCLI:
    """Test suite for Click CLI commands and workflows."""

    def test_cli_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "UT-RBV Downloader v" in result.output

    def test_cli_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "download" in result.output
        assert "inspect" in result.output

    def test_cli_download_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["download", "--help"])
        assert result.exit_code == 0
        assert "--modules" in result.output
        assert "--cookie" in result.output
        assert "--output" in result.output
        assert "--compress" in result.output

    def test_cli_inspect_invalid_code(self):
        runner = CliRunner()
        result = runner.invoke(main, ["inspect", "bad!code"])
        assert result.exit_code != 0
        assert "Kode mata kuliah tidak valid" in result.output

    @respx.mock
    def test_cli_inspect_success(self):
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_CATALOG_HTML)
        )
        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            return_value=httpx.Response(200, text=DUMMY_JSONP)
        )

        runner = CliRunner()
        result = runner.invoke(main, ["inspect", "EKMA4111"])
        assert result.exit_code == 0
        assert "EKMA4111" in result.output
        assert "Pengantar Bisnis" in result.output
        assert "DAFIS" in result.output
        assert "Modul 01" in result.output

    @respx.mock
    def test_cli_download_e2e(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UT_RBV_CACHE_DIR", str(tmp_path / "cache"))
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_CATALOG_HTML)
        )
        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            side_effect=lambda req: httpx.Response(
                200,
                content=DUMMY_JPEG if req.url.params.get("format") == "jpg" else DUMMY_JSONP.encode("utf-8")
            )
        )

        out_dir = tmp_path / "downloads"
        runner = CliRunner()
        result = runner.invoke(main, [
            "download",
            "EKMA4111",
            "--output", str(out_dir),
            "--merge",
        ])

        assert result.exit_code == 0
        assert "Selesai!" in result.output

        # Verify output PDF file exists
        pdf_files = list(out_dir.glob("*.pdf"))
        assert len(pdf_files) == 1
        assert "EKMA4111" in pdf_files[0].name

    @respx.mock
    def test_cli_download_no_merge(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UT_RBV_CACHE_DIR", str(tmp_path / "cache"))
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_CATALOG_HTML)
        )
        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            side_effect=lambda req: httpx.Response(
                200,
                content=DUMMY_JPEG if req.url.params.get("format") == "jpg" else DUMMY_JSONP.encode("utf-8")
            )
        )

        out_dir = tmp_path / "downloads_split"
        runner = CliRunner()
        result = runner.invoke(main, [
            "download",
            "EKMA4111",
            "--output", str(out_dir),
            "--split",
            "--modules", "M1",
        ])

        assert result.exit_code == 0
        assert "Selesai!" in result.output
        pdf_files = list(out_dir.glob("*.pdf"))
        assert len(pdf_files) >= 1

    @respx.mock
    def test_cli_download_with_cookie(self, tmp_path, monkeypatch):
        monkeypatch.setenv("UT_RBV_CACHE_DIR", str(tmp_path / "cache"))
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_CATALOG_HTML)
        )
        respx.get("https://pustaka.ut.ac.id/reader/services/view.php").mock(
            return_value=httpx.Response(200, content=DUMMY_JPEG)
        )

        out_dir = tmp_path / "downloads_cookie"
        runner = CliRunner()
        result = runner.invoke(main, [
            "download",
            "EKMA4111",
            "--cookie", "PHPSESSID=mock12345",
            "--output", str(out_dir),
            "--modules", "M1",
        ])
        assert result.exit_code == 0

    @respx.mock
    def test_cli_download_no_sections_found(self, tmp_path):
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text="<html><body>No modules</body></html>")
        )

        runner = CliRunner()
        result = runner.invoke(main, [
            "download",
            "EKMA4111",
            "--modules", "M99",
        ])
        assert result.exit_code != 0
        assert "Gagal menemukan daftar modul" in result.output

    def test_cli_web_command(self, monkeypatch):
        ran = {}

        def mock_run(app_instance, host, port, log_level):
            ran["host"] = host
            ran["port"] = port
            ran["log_level"] = log_level

        monkeypatch.setattr("uvicorn.run", mock_run)

        runner = CliRunner()
        result = runner.invoke(main, ["web", "--port", "9090", "--no-browser"])
        assert result.exit_code == 0
        assert ran["port"] == 9090


