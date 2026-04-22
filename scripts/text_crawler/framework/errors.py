"""
CrawlError: Structured error type for the text crawler.
Mirrors the PublishError pattern from cross-post/src/shared/errors.ts
"""
from typing import Literal, Optional, TypeAlias

CrawlErrorCode: TypeAlias = Literal[
    'network', 'parse', 'auth', 'rate_limited',
    'robots_blocked', 'not_found', 'unknown'
]


class CrawlError(Exception):
    code: str
    message: str
    retryable: bool
    details: dict

    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        details: Optional[dict] = None,
    ):
        self.code = code
        self.message = message
        self.retryable = retryable
        self.details = details or {}

    def __repr__(self):
        return f"CrawlError({self.code!r}, {self.message!r}, retryable={self.retryable})"

    def to_dict(self) -> dict:
        return {
            'code': self.code,
            'message': self.message,
            'retryable': self.retryable,
            'details': self.details,
        }


def network_error(url: str, reason: str, *, details: Optional[dict] = None) -> CrawlError:
    return CrawlError(
        'network',
        f"Network failure fetching {url}: {reason}",
        retryable=True,
        details={'url': url, 'reason': reason, **(details or {})},
    )


def parse_error(url: str, reason: str, *, details: Optional[dict] = None) -> CrawlError:
    return CrawlError(
        'parse',
        f"Parse error for {url}: {reason}",
        retryable=False,
        details={'url': url, 'reason': reason, **(details or {})},
    )


def auth_error(url: str, reason: str = 'login_required') -> CrawlError:
    return CrawlError(
        'auth',
        f"Authentication required for {url}",
        retryable=False,
        details={'url': url, 'reason': reason},
    )


def rate_limited_error(url: str, retry_after: Optional[int] = None) -> CrawlError:
    return CrawlError(
        'rate_limited',
        f"Rate limited at {url}" + (f", retry after {retry_after}s" if retry_after else ''),
        retryable=True,
        details={'url': url, 'retry_after': retry_after},
    )


def robots_blocked_error(url: str, source: str = 'robots.txt') -> CrawlError:
    return CrawlError(
        'robots_blocked',
        f"Crawling {url} blocked by {source}",
        retryable=False,
        details={'url': url, 'source': source},
    )


def not_found_error(url: str) -> CrawlError:
    return CrawlError(
        'not_found',
        f"Resource not found at {url}",
        retryable=False,
        details={'url': url},
    )