"""
httpx-based async HTTP client with rate limiting, retry, and timeout.
Configurable requests-per-second. Raises CrawlError on non-200 responses.
"""
import asyncio
import time
from typing import Optional

import httpx

from .errors import CrawlError, network_error, rate_limited_error


class Fetcher:
    def __init__(
        self,
        requests_per_second: float = 1.0,
        timeout: float = 30.0,
        max_retries: int = 3,
        user_agent: str = 'GoryeoCostumeCrawler/1.0 (personal research; contact: fuchitalee)',
    ):
        self.requests_per_second = requests_per_second
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self._last_request_time: float = 0.0
        self._lock = asyncio.Lock()

    def _min_interval(self) -> float:
        return 1.0 / self.requests_per_second if self.requests_per_second > 0 else 0.0

    async def _throttle(self):
        async with self._lock:
            elapsed = time.monotonic() - self._last_request_time
            interval = self._min_interval()
            if elapsed < interval:
                await asyncio.sleep(interval - elapsed)
            self._last_request_time = time.monotonic()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        await self._throttle()
        for attempt in range(self.max_retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    headers={'User-Agent': self.user_agent},
                    follow_redirects=True,
                    **kwargs,
                ) as client:
                    response = await client.get(url)
                    if response.status_code == 429:
                        retry_after = response.headers.get('Retry-After')
                        wait = int(retry_after) if retry_after and retry_after.isdigit() else 60
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(wait)
                            continue
                        raise rate_limited_error(url, retry_after=wait)
                    if response.status_code == 404:
                        raise CrawlError('not_found', f"Not found: {url}", retryable=False, details={'url': url})
                    if response.status_code >= 400:
                        raise CrawlError(
                            'network',
                            f"HTTP {response.status_code} for {url}",
                            retryable=False,
                            details={'url': url, 'status_code': response.status_code},
                        )
                    return response
            except httpx.Timeout as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise network_error(url, f"timeout after {self.max_retries} retries", details={'timeout': self.timeout})
            except httpx.RequestError as e:
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    continue
                raise network_error(url, str(e))
        raise network_error(url, f"max retries ({self.max_retries}) exceeded")

    async def get_binary(self, url: str, **kwargs) -> bytes:
        response = await self.get(url, **kwargs)
        return response.content

    async def get_json(self, url: str, **kwargs) -> dict:
        response = await self.get(url, **kwargs)
        return response.json()