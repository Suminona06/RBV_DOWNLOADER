"""Session management, HTTP client, and authentication workflow for UT-RBV."""

import logging
from typing import Optional, Dict, Any
import httpx

from ut_rbv.core.auth import (
    solve_math_captcha,
    InvalidCredentialsError,
    SessionExpiredError,
    UnreachableError,
    CaptchaSolveError,
)

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
}

DEFAULT_BASE_URL = "https://pustaka.ut.ac.id/reader/"


class SessionManager:
    """Manages HTTP communication, cookies, and authentication for UT-RBV."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ):
        self.base_url = base_url.rstrip("/") + "/"
        self.headers = {**DEFAULT_HEADERS, **(headers or {})}
        self.client = httpx.AsyncClient(
            headers=self.headers,
            timeout=timeout,
            follow_redirects=True,
        )
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.authenticated: bool = False

    def set_session_cookie(self, cookie_input: str) -> None:
        """Set session cookie from string (e.g. 'PHPSESSID=abcdef12345' or raw token)."""
        cookie_str = cookie_input.strip()
        cookie_name = "PHPSESSID"
        cookie_value = cookie_str

        if "=" in cookie_str:
            parts = cookie_str.split("=", 1)
            cookie_name = parts[0].strip()
            cookie_value = parts[1].strip().strip(";")

        # Set cookie for pustaka.ut.ac.id domain
        self.client.cookies.set(cookie_name, cookie_value, domain="pustaka.ut.ac.id")
        self.client.cookies.set(cookie_name, cookie_value, domain="www.pustaka.ut.ac.id")
        self.authenticated = True
        logger.info(f"Session cookie '{cookie_name}' berhasil diterapkan.")

    async def login_with_credentials(
        self,
        username: str,
        password: str,
        probe_code: str = "EKMA4111",
    ) -> bool:
        """Perform login using username, password, and automatic math captcha solving."""
        self.username = username
        self.password = password

        probe_url = f"{self.base_url}index.php"
        params = {"modul": probe_code}

        try:
            res = await self.client.get(probe_url, params=params)
        except httpx.RequestError as e:
            raise UnreachableError(f"Gagal menghubungi server UT RBV: {e}") from e

        # If already logged in (no login form present)
        if not self._is_login_form_present(res.text):
            self.authenticated = True
            logger.info("Sudah dalam status terautentikasi.")
            return True

        # Solve captcha
        try:
            captcha_ans = solve_math_captcha(res.text)
            logger.debug(f"Captcha matematika terpecahkan: {captcha_ans}")
        except CaptchaSolveError as e:
            raise CaptchaSolveError(f"Gagal memecahkan captcha saat login: {e}") from e

        # Prepare login POST payload
        payload = {
            "_submit_check": "1",
            "username": username,
            "password": password,
            "ccaptcha": captcha_ans,
            "submit": "Submit",
        }

        post_headers = {
            "Referer": str(res.url),
            "Origin": "https://pustaka.ut.ac.id",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        try:
            login_res = await self.client.post(
                probe_url,
                params=params,
                data=payload,
                headers=post_headers,
            )
        except httpx.RequestError as e:
            raise UnreachableError(f"Gagal mengirim request login: {e}") from e

        if self._is_login_form_present(login_res.text):
            self.authenticated = False
            raise InvalidCredentialsError("Username, Password salah, atau Captcha ditolak oleh server UT.")

        self.authenticated = True
        logger.info(f"Berhasil login sebagai pengguna: {username}")
        return True

    def _is_login_form_present(self, html_text: str) -> bool:
        """Check whether the HTML response is a login form."""
        if not html_text:
            return False
        # RBV shows "About RBV V.2" or input with name="ccaptcha" / name="password"
        if "about rbv" in html_text.lower():
            return True
        has_captcha_input = 'name="ccaptcha"' in html_text or "ccaptcha" in html_text or "captcha" in html_text.lower()
        has_password_input = 'name="password"' in html_text or 'type="password"' in html_text
        return has_captcha_input and has_password_input

    async def validate_session(self, probe_code: str = "EKMA4111") -> bool:
        """Validate if current session can access reader contents."""
        url = f"{self.base_url}index.php"
        params = {"modul": probe_code}

        try:
            res = await self.client.get(url, params=params)
            if res.is_success and not self._is_login_form_present(res.text):
                self.authenticated = True
                return True
        except httpx.RequestError:
            pass

        self.authenticated = False
        return False

    async def get(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        auto_reauth: bool = True,
        **kwargs,
    ) -> httpx.Response:
        """Send authenticated GET request with auto re-auth on session expiry."""
        req_headers = {**self.headers, **(headers or {})}
        try:
            res = await self.client.get(url, params=params, headers=req_headers, **kwargs)
        except httpx.RequestError as e:
            raise UnreachableError(f"Koneksi gagal: {e}") from e

        if self._is_login_form_present(res.text):
            if auto_reauth and self.username and self.password:
                logger.warning("Sesi kedaluwarsa, mencoba re-autentikasi otomatis...")
                await self.login_with_credentials(self.username, self.password)
                return await self.client.get(url, params=params, headers=req_headers, **kwargs)
            else:
                self.authenticated = False
                raise SessionExpiredError("Sesi telah kedaluwarsa atau belum terautentikasi.")

        return res

    async def close(self) -> None:
        """Close underlying httpx client."""
        await self.client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
