"""Unit tests for authentication and session management in UT-RBV."""

import pytest
import respx
import httpx

from ut_rbv.core.auth import (
    solve_math_captcha,
    extract_captcha_question,
    CaptchaSolveError,
    InvalidCredentialsError,
    SessionExpiredError,
    UnreachableError,
)
from ut_rbv.core.session import SessionManager, DEFAULT_BASE_URL


SAMPLE_LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head><title>Ruang Baca Virtual</title></head>
<body>
    <div class="login-box">
        <h3>About RBV V.2</h3>
        <form method="post" action="index.php?modul=EKMA4111">
            <input type="hidden" name="_submit_check" value="1">
            <label>Username:</label>
            <input type="text" name="username">
            <label>Password:</label>
            <input type="password" name="password">
            <div class="captcha-row">
                Berapa hasil dari 7 + 8 =
                <input type="text" name="ccaptcha" size="3">
            </div>
            <input type="submit" name="submit" value="Submit">
        </form>
    </div>
</body>
</html>
"""

SAMPLE_SUCCESS_PAGE = """
<!DOCTYPE html>
<html>
<head><title>EKMA4111 - Pengantar Bisnis</title></head>
<body>
    <div class="reader-container">
        <h2>EKMA4111 Pengantar Bisnis</h2>
        <table>
            <tr><th><a href="index.php?subfolder=EKMA4111/&doc=DAFIS.pdf">Daftar Isi</a></th></tr>
            <tr><th><a href="index.php?subfolder=EKMA4111/&doc=M1.pdf">Modul 01</a></th></tr>
        </table>
    </div>
</body>
</html>
"""


class TestMathCaptchaSolver:
    """Test suite for math captcha detection and solving."""

    def test_addition(self):
        assert solve_math_captcha("Berapa hasil dari 3 + 9 =") == "12"
        assert solve_math_captcha("15 + 25") == "40"

    def test_subtraction(self):
        assert solve_math_captcha("Berapa hasil dari 20 - 7 =") == "13"
        assert solve_math_captcha("50 - 15") == "35"

    def test_multiplication(self):
        assert solve_math_captcha("Berapa hasil dari 4 x 6 =") == "24"
        assert solve_math_captcha("Berapa hasil dari 7 * 8 =") == "56"
        assert solve_math_captcha("3 × 9") == "27"

    def test_division(self):
        assert solve_math_captcha("Berapa hasil dari 18 / 3 =") == "6"
        assert solve_math_captcha("Berapa hasil dari 24 : 4 =") == "6"

    def test_extract_from_html(self):
        assert solve_math_captcha(SAMPLE_LOGIN_HTML) == "15"

    def test_invalid_captcha_format_raises_error(self):
        with pytest.raises(CaptchaSolveError):
            solve_math_captcha("Klik tombol di bawah ini tanpa angka")

    def test_division_by_zero_raises_error(self):
        with pytest.raises(CaptchaSolveError):
            solve_math_captcha("10 / 0")


class TestSessionManager:
    """Test suite for HTTP Session and Authentication workflows."""

    def test_set_session_cookie(self):
        manager = SessionManager()
        manager.set_session_cookie("PHPSESSID=my_secret_token_123;")
        assert manager.authenticated is True
        cookie_val = manager.client.cookies.get("PHPSESSID", domain="pustaka.ut.ac.id")
        assert cookie_val == "my_secret_token_123"

    def test_set_raw_cookie_value(self):
        manager = SessionManager()
        manager.set_session_cookie("raw_token_xyz987")
        assert manager.authenticated is True
        cookie_val = manager.client.cookies.get("PHPSESSID", domain="pustaka.ut.ac.id")
        assert cookie_val == "raw_token_xyz987"

    def test_set_multi_cookie_space_separated(self):
        manager = SessionManager()
        manager.set_session_cookie(
            "PHPSESSID=42s6cuke04v13vsadesnnvfr0a TS019a5912=0151f104f05b4637a95805424703ad87b73b1acd93c3b67b8ea831c26a9229a44f33aaf072b48286c906cf3920d2d576fbeb5380c0"
        )
        assert manager.authenticated is True
        assert manager.client.cookies.get("PHPSESSID", domain="pustaka.ut.ac.id") == "42s6cuke04v13vsadesnnvfr0a"
        assert manager.client.cookies.get("TS019a5912", domain="pustaka.ut.ac.id") == "0151f104f05b4637a95805424703ad87b73b1acd93c3b67b8ea831c26a9229a44f33aaf072b48286c906cf3920d2d576fbeb5380c0"

    @pytest.mark.asyncio
    @respx.mock
    async def test_login_success(self):
        manager = SessionManager()
        
        # 1. First probe request returns login form with captcha
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_LOGIN_HTML)
        )
        
        # 2. POST login request returns success page
        respx.post("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_SUCCESS_PAGE)
        )

        success = await manager.login_with_credentials("mahasiswa1", "pass123")
        assert success is True
        assert manager.authenticated is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_login_invalid_credentials(self):
        manager = SessionManager()

        # Probe returns form
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_LOGIN_HTML)
        )
        # Post returns form again (indicating failed auth)
        respx.post("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_LOGIN_HTML)
        )

        with pytest.raises(InvalidCredentialsError):
            await manager.login_with_credentials("wrong_user", "wrong_pass")
        
        assert manager.authenticated is False

    @pytest.mark.asyncio
    @respx.mock
    async def test_validate_session(self):
        manager = SessionManager()
        
        # Returns success content
        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_SUCCESS_PAGE)
        )

        valid = await manager.validate_session("EKMA4111")
        assert valid is True
        assert manager.authenticated is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_auto_reauth_on_session_expiry(self):
        manager = SessionManager()
        manager.username = "mahasiswa1"
        manager.password = "pass123"

        route = respx.get("https://pustaka.ut.ac.id/reader/data.php")
        # First call returns login form (session expired)
        # Second call returns valid data after reauth
        route.side_effect = [
            httpx.Response(200, text=SAMPLE_LOGIN_HTML),
            httpx.Response(200, text="OK_DATA"),
        ]

        respx.get("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_LOGIN_HTML)
        )
        respx.post("https://pustaka.ut.ac.id/reader/index.php").mock(
            return_value=httpx.Response(200, text=SAMPLE_SUCCESS_PAGE)
        )

        res = await manager.get("https://pustaka.ut.ac.id/reader/data.php")
        assert res.text == "OK_DATA"
