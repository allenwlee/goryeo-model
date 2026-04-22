"""
BeautifulSoup wrapper with Korean encoding detection and fallback chain.
Tries utf-8 -> euc-kr -> cp949 -> iso-8859-1 in order.
"""
from typing import Optional

from bs4 import BeautifulSoup, UnicodeDammit

# Encodings to try, in order of preference
ENCODING_FALLBACK_CHAIN = ['utf-8', 'euc-kr', 'cp949', 'iso-8859-1']


def detect_encoding(html_bytes: bytes) -> str:
    """
    Use UnicodeDammit to detect the encoding of HTML bytes.
    Falls back through the chain if detection fails.
    """
    dammit = UnicodeDammit(html_bytes, smart_lines_to_fix=True)
    detected = dammit.original_encoding
    if detected:
        return detected
    # Fallback chain
    for enc in ENCODING_FALLBACK_CHAIN:
        try:
            html_bytes.decode(enc)
            return enc
        except (UnicodeDecodeError, LookupError):
            continue
    return 'utf-8'  # Last resort


def parse_html(html_bytes: bytes, encoding: Optional[str] = None) -> BeautifulSoup:
    """
    Parse HTML bytes using BeautifulSoup.
    If encoding is None, auto-detect using UnicodeDammit + fallback chain.
    """
    if encoding is None:
        encoding = detect_encoding(html_bytes)
    return BeautifulSoup(html_bytes, 'lxml', from_encoding=encoding)


def parse_html_with_fallback(html_bytes: bytes) -> BeautifulSoup:
    """
    Try to parse with detected encoding; if that fails, try the fallback chain.
    Returns the first successful parse.
    """
    # Try detected encoding first
    enc = detect_encoding(html_bytes)
    try:
        return BeautifulSoup(html_bytes, 'lxml', from_encoding=enc)
    except (UnicodeDecodeError, LookupError):
        pass

    for enc in ENCODING_FALLBACK_CHAIN:
        try:
            return BeautifulSoup(html_bytes, 'lxml', from_encoding=enc)
        except (UnicodeDecodeError, LookupError):
            continue

    # Absolute last resort: decode with errors='replace' and parse as utf-8
    return BeautifulSoup(html_bytes.decode('utf-8', errors='replace'), 'lxml')


def extract_text(soup: BeautifulSoup, strip: bool = True) -> str:
    """Extract visible text from a BeautifulSoup tree."""
    text = soup.get_text(separator=' ', strip=strip)
    return ' '.join(text.split())  # Normalize whitespace


def find_all_links(soup: BeautifulSoup) -> list[str]:
    """Return all href values from anchor tags."""
    return [a.get('href', '') for a in soup.find_all('a') if a.get('href')]