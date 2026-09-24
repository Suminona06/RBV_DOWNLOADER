"""Authentication and Captcha solving utilities for UT-RBV."""

import re
from typing import Optional
from bs4 import BeautifulSoup


class UTRBVError(Exception):
    """Base exception for all UT-RBV errors."""
    pass


class AuthError(UTRBVError):
    """Base exception for authentication errors."""
    pass


class InvalidCredentialsError(AuthError):
    """Raised when username or password is incorrect."""
    pass


class CaptchaSolveError(AuthError):
    """Raised when math captcha cannot be detected or solved."""
    pass


class SessionExpiredError(AuthError):
    """Raised when session cookie or token has expired."""
    pass


class UnreachableError(UTRBVError):
    """Raised when the UT RBV server cannot be reached."""
    pass


def extract_captcha_question(html_or_text: str) -> str:
    """Extract math question text from RBV login form HTML or raw text."""
    if "<" in html_or_text and ">" in html_or_text:
        soup = BeautifulSoup(html_or_text, "html.parser")
        input_tag = soup.find("input", {"name": "ccaptcha"})
        if input_tag:
            # Check previous text/sibling
            prev_node = input_tag.find_previous(string=True)
            if prev_node and any(c.isdigit() for c in prev_node):
                return prev_node.strip()
            # If not in immediate previous node, check parent text
            parent = input_tag.parent
            if parent:
                parent_text = parent.get_text().strip()
                if any(c.isdigit() for c in parent_text):
                    return parent_text

    # Fallback to regex search across raw string
    match = re.search(r"(?:berapa\s+hasil\s+dari\s+)?(\d+\s*[\+\-\*\/\:x×]\s*\d+)", html_or_text, re.IGNORECASE)
    if match:
        return match.group(1)

    raise CaptchaSolveError("Tidak dapat menemukan teks pertanyaan captcha matematika dalam halaman.")


def solve_math_captcha(html_or_text: str) -> str:
    """Solve math captcha from RBV login form.

    Supports operations: addition (+), subtraction (-), multiplication (*, x, ×),
    and division (/, :).

    Examples:
        >>> solve_math_captcha("Berapa hasil dari 3 + 9 =")
        "12"
        >>> solve_math_captcha("Berapa hasil dari 20 - 7 =")
        "13"
        >>> solve_math_captcha("Berapa hasil dari 4 x 6 =")
        "24"
        >>> solve_math_captcha("Berapa hasil dari 18 / 3 =")
        "6"
    """
    question_text = extract_captcha_question(html_or_text)

    # Search for pattern: number operator number
    # Standardize operators
    clean_text = question_text.replace("×", "*").replace(":", "/").strip()
    match = re.search(r"(\d+)\s*([\+\-\*\/xX])\s*(\d+)", clean_text)
    if not match:
        raise CaptchaSolveError(f"Format persamaan matematika tidak dikenali: '{question_text}'")

    num1_str, op, num2_str = match.groups()
    num1 = int(num1_str)
    num2 = int(num2_str)

    op_lower = op.lower()
    if op_lower == "+":
        result = num1 + num2
    elif op_lower == "-":
        result = num1 - num2
    elif op_lower in ("*", "x"):
        result = num1 * num2
    elif op_lower == "/":
        if num2 == 0:
            raise CaptchaSolveError("Pembagian dengan nol pada captcha matematika.")
        result = num1 // num2
    else:
        raise CaptchaSolveError(f"Operator matematika tidak didukung: '{op}'")

    return str(result)
