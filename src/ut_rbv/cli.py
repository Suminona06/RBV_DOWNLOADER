"""Interactive Command Line Interface for UT-RBV Downloader."""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional
import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import (
    Progress,
    SpinnerColumn,
    BarColumn,
    TextColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)

from ut_rbv import __version__
from ut_rbv.core.auth import (
    AuthError,
    InvalidCredentialsError,
    SessionExpiredError,
    UnreachableError,
)
from ut_rbv.core.catalog import CatalogParser, BookNotFoundError
from ut_rbv.core.downloader import PageDownloader
from ut_rbv.core.session import SessionManager
from ut_rbv.pdf.builder import PDFBuilder
from ut_rbv.utils.paths import get_output_dir

console = Console()


def print_banner():
    """Print welcoming CLI banner with branding."""
    banner_text = (
        f"[bold cyan]UT-RBV Downloader[/bold cyan] [dim]v{__version__}[/dim]\n"
        "[italic white]Alat Pengunduh E-Book Ruang Baca Virtual Universitas Terbuka ke PDF[/italic white]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


@click.group()
@click.version_option(version=__version__, message="UT-RBV Downloader v%(version)s")
def main():
    """UT-RBV Downloader - Unduh E-Book BMP Universitas Terbuka ke PDF."""
    pass


@main.command()
@click.argument("code")
@click.option("-m", "--modules", help="Pilih modul spesifik (cth: 1,2,3 atau 1-4)")
@click.option("-o", "--output", default=None, help="Direktori penyimpanan file PDF (default: ./downloads)")
@click.option("-c", "--cookie", help="Session cookie PHPSESSID (untuk akun SSO ecampus)")
@click.option("-u", "--username", envvar="UT_USERNAME", help="Username akun RBV / Tuton")
@click.option("-p", "--password", envvar="UT_PASSWORD", help="Password akun RBV / Tuton")
@click.option("--merge/--split", default=True, help="Gabung menjadi satu PDF (default) atau pisah per bab")
@click.option(
    "--compress",
    type=click.Choice(["none", "medium", "high"], case_sensitive=False),
    default="medium",
    help="Tingkat kompresi citra JPEG (default: medium)",
)
@click.option("--workers", default=4, type=int, help="Batas unduhan paralel/concurrency (default: 4)")
@click.option("--no-text", is_flag=True, default=False, help="Jangan unduh layer teks searchable")
@click.option("-v", "--verbose", is_flag=True, default=False, help="Tampilkan log rincian debug")
def download(
    code: str,
    modules: Optional[str],
    output: Optional[str],
    cookie: Optional[str],
    username: Optional[str],
    password: Optional[str],
    merge: bool,
    compress: str,
    workers: int,
    no_text: bool,
    verbose: bool,
):
    """Unduh Buku Materi Pokok (BMP) berdasarkan kode mata kuliah."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")

    print_banner()

    try:
        norm_code = CatalogParser.validate_code(code)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    output_dir = get_output_dir(output)

    async def run_pipeline():
        async with SessionManager() as session:
            # 1. Setup Authentication
            if cookie:
                session.set_session_cookie(cookie)
                console.print("[dim]✓ Menggunakan session cookie yang disediakan.[/dim]")
            elif username and password:
                with console.status("[yellow]Melakukan login ke portal RBV...[/yellow]"):
                    try:
                        await session.login_with_credentials(username, password, probe_code=norm_code)
                        console.print(f"[bold green]✓ Berhasil login sebagai:[/bold green] {username}")
                    except Exception as e:
                        console.print(f"[bold red]Gagal login:[/bold red] {e}")
                        sys.exit(1)
            else:
                # Cek apakah sesi publik / tanpa login diizinkan untuk probe
                is_valid = await session.validate_session(norm_code)
                if not is_valid:
                    console.print(
                        "[bold yellow]Peringatan:[/bold yellow] Sesi belum login. "
                        "Gunakan opsi [bold]-c / --cookie[/bold] atau [bold]-u / -p[/bold] jika modul memerlukan autentikasi."
                    )

            # 2. Inspect Book Catalog
            with console.status(f"[cyan]Mengambil metadata buku {norm_code}...[/cyan]"):
                try:
                    book = await CatalogParser.fetch_book(session, norm_code)
                except BookNotFoundError as e:
                    console.print(f"[bold red]Buku Tidak Ditemukan:[/bold red] {e}")
                    sys.exit(1)
                except Exception as e:
                    console.print(f"[bold red]Gagal membaca katalog:[/bold red] {e}")
                    if verbose:
                        console.print_exception()
                    sys.exit(1)

            # Filter sections if requested
            target_sections = book.filter_sections(modules)
            if not target_sections:
                console.print(f"[bold red]Tidak ada modul yang cocok dengan filter:[/bold red] {modules}")
                sys.exit(1)

            # Display book summary table
            table = Table(title=f"Buku Materi Pokok: {book.code} - {book.title}", border_style="cyan")
            table.add_column("No", justify="right", style="cyan")
            table.add_column("Doc ID", style="magenta")
            table.add_column("Judul Bagian / Modul", style="white")

            for i, sec in enumerate(target_sections, start=1):
                table.add_row(str(i), sec.doc_id, sec.title)

            console.print(table)

            # 3. Detect page counts
            with console.status("[cyan]Mendeteksi jumlah halaman setiap modul...[/cyan]"):
                for sec in target_sections:
                    if sec.total_pages <= 0:
                        sec.total_pages = await CatalogParser.detect_section_pages(session, sec)

            total_pages_est = sum(sec.total_pages for sec in target_sections if sec.total_pages > 0)
            console.print(f"[bold green]Total Estimasi Halaman:[/bold green] {total_pages_est or 'Tidak diketahui'}")

            # 4. Download Pages
            downloader = PageDownloader(
                session=session,
                max_concurrency=workers,
            )

            console.print("\n[bold]Memulai proses pengunduhan aset halaman...[/bold]")
            all_downloads = {}

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(bar_width=40),
                TaskProgressColumn(),
                TextColumn("({task.completed}/{task.total} hlm)"),
                TimeRemainingColumn(),
                console=console,
            ) as progress:
                overall_task = progress.add_task(
                    "Total Unduhan",
                    total=max(1, total_pages_est),
                )

                def on_page_progress(page_res, done, total):
                    progress.update(overall_task, completed=done, total=max(done, total))

                all_downloads = await downloader.download_book(
                    book=book,
                    target_modules=modules,
                    fetch_text=not no_text,
                    on_page_progress=on_page_progress,
                )

            # 5. PDF Assembly Pipeline
            console.print("\n[bold yellow]Menyusun dokumen PDF & mengoptimalkan kompresi...[/bold yellow]")

            with console.status("[yellow]Merakit PDF...[/yellow]"):
                if merge:
                    out_name = f"{book.code} - {book.title}.pdf"
                    final_file = output_dir / out_name
                    PDFBuilder.build_merged_book_pdf(
                        book=book,
                        download_results=all_downloads,
                        output_file=final_file,
                        compress_level=compress,
                    )
                    console.print(f"\n[bold green]✓ Berhasil membuat PDF Buku:[/bold green] [underline]{final_file}[/underline]")
                else:
                    for sec in target_sections:
                        sec_pages = all_downloads.get(sec.doc_id, [])
                        if not sec_pages:
                            continue
                        out_name = f"{book.code}_{sec.doc_id}.pdf"
                        final_file = output_dir / out_name
                        PDFBuilder.build_section_pdf(
                            section=sec,
                            page_results=sec_pages,
                            output_file=final_file,
                            compress_level=compress,
                            book_title=book.title,
                        )
                        console.print(f"[bold green]✓ Modul tersimpan:[/bold green] {final_file}")

            console.print("\n[bold cyan]Selesai![/bold cyan] Semua dokumen telah siap untuk dibaca secara offline.")

    try:
        asyncio.run(run_pipeline())
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Pengunduhan dibatalkan oleh pengguna.[/bold yellow]")
        sys.exit(130)


@main.command()
@click.argument("code")
def inspect(code: str):
    """Lihat struktur modul dan daftar bab buku tanpa mengunduh."""
    print_banner()

    try:
        norm_code = CatalogParser.validate_code(code)
    except ValueError as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        sys.exit(1)

    async def run_inspect():
        async with SessionManager() as session:
            with console.status(f"[cyan]Mengambil struktur buku {norm_code}...[/cyan]"):
                try:
                    book = await CatalogParser.fetch_book(session, norm_code)
                except Exception as e:
                    console.print(f"[bold red]Gagal mengambil data buku:[/bold red] {e}")
                    sys.exit(1)

                for sec in book.sections:
                    sec.total_pages = await CatalogParser.detect_section_pages(session, sec)

            table = Table(title=f"Detail Buku: {book.code} - {book.title}", border_style="cyan")
            table.add_column("No", justify="right", style="cyan")
            table.add_column("Doc ID", style="magenta")
            table.add_column("Judul Modul / Bagian", style="white")
            table.add_column("Jumlah Halaman", justify="right", style="green")

            for i, sec in enumerate(book.sections, start=1):
                page_str = str(sec.total_pages) if sec.total_pages > 0 else "-"
                table.add_row(str(i), sec.doc_id, sec.title, page_str)

            console.print(table)
            console.print(f"[bold green]Total Halaman Keseluruhan:[/bold green] {book.total_pages}")

    asyncio.run(run_inspect())


@main.command()
@click.option("--host", default="127.0.0.1", help="Host interface (default: 127.0.0.1)")
@click.option("--port", default=8000, type=int, help="Port server lokal (default: 8000)")
@click.option("--no-browser", is_flag=True, default=False, help="Jangan buka browser secara otomatis")
def web(host: str, port: int, no_browser: bool):
    """Jalankan antarmuka grafis Web Dashboard lokal."""
    print_banner()
    import uvicorn
    import webbrowser
    from ut_rbv.web.app import app

    url = f"http://{host}:{port}"
    console.print(f"[bold green]✓ Web Dashboard aktif di:[/bold green] [underline cyan]{url}[/underline cyan]")
    console.print("[dim]Tekan Ctrl + C di terminal ini untuk mematikan server.[/dim]\n")

    if not no_browser and host in ("127.0.0.1", "localhost"):
        try:
            webbrowser.open(url)
        except Exception:
            pass

    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
