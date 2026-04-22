"""
robots.txt checker with blocklist for sites that must not be crawled
regardless of robots.txt status. Used to enforce compliance.
"""
import asyncio
from urllib.parse import urlparse

import httpx

# Sites that are always blocked regardless of robots.txt
ALWAYS_BLOCKED = {
    'vod.kbs.co.kr': 'KBS VOD terms prohibit AI learning',
    'www.kbs.co.kr': 'KBS VOD terms prohibit AI learning',
    'kbs.co.kr': 'KBS VOD terms prohibit AI learning',
    'dbpia.co.kr': 'DBpia terms prohibit unauthorized copying',
    'www.dbpia.co.kr': 'DBpia terms prohibit unauthorized copying',
    'kiss.kstudy.com': 'KISS terms prohibit unauthorized copying',
    'kiss.kstudy.co.kr': 'KISS terms prohibit unauthorized copying',
    'namu.wiki': 'namu.wiki robots.txt disallows all crawlers; requires JS rendering',
    'www.namu.wiki': 'namu.wiki robots.txt disallows all crawlers',
}

# Korean government sites that request self-identification
KOREAN_GOV_SITES = {
    'heritage.go.kr',
    'www.heritage.go.kr',
    'nrich.go.kr',
    'portal.nrich.go.kr',
    'museum.go.kr',
    'www.museum.go.kr',
}


def is_blocked(url: str) -> tuple[bool, str]:
    """
    Check if a URL is on the always-blocked list.
    Returns (is_blocked, reason).
    """
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if host in ALWAYS_BLOCKED:
        return True, ALWAYS_BLOCKED[host]
    return False, ''


def is_korean_gov_site(url: str) -> bool:
    """Check if URL is a Korean government heritage site."""
    parsed = urlparse(url)
    return parsed.netloc.lower() in KOREAN_GOV_SITES


class RobotsChecker:
    def __init__(self, fetcher, cache_ttl: int = 3600):
        self.fetcher = fetcher
        self.cache_ttl = cache_ttl
        self._cache: dict[str, tuple[bool, float]] = {}

    async def can_fetch(self, url: str) -> tuple[bool, str]:
        """
        Check robots.txt for a URL.
        Returns (allowed, reason).
        Reason is empty if allowed, or the specific disallow message.
        """
        blocked, reason = is_blocked(url)
        if blocked:
            return False, reason

        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        # Check cache
        now = asyncio.get_event_loop().time()
        if robots_url in self._cache:
            allowed, cached_at = self._cache[robots_url]
            if now - cached_at < self.cache_ttl:
                return allowed, '' if allowed else 'robots.txt'

        try:
            response = await self.fetcher.get(robots_url)
            text = response.text
        except Exception:
            # If we can't fetch robots.txt, be conservative and skip
            return False, f"Could not fetch robots.txt for {parsed.netloc}"

        allowed = self._parse_robots_txt(text, parsed.path)
        self._cache[robots_url] = (allowed, now)
        return allowed, '' if allowed else 'robots.txt disallows'

    def _parse_robots_txt(self, robots_txt: str, path: str) -> bool:
        """
        Simple robots.txt parser. Returns True if fetch is allowed.
        Only handles User-agent: * rules for now.
        """
        lines = robots_txt.split('\n')
        allow_rules: list[str] = []
        disallow_rules: list[str] = []

        current_user_agent = None
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if line.lower().startswith('user-agent:'):
                ua = line.split(':', 1)[1].strip()
                current_user_agent = ua.lower()
            elif line.lower().startswith('disallow:'):
                path_rule = line.split(':', 1)[1].strip()
                if current_user_agent == '*' or current_user_agent is None:
                    disallow_rules.append(path_rule)
            elif line.lower().startswith('allow:'):
                path_rule = line.split(':', 1)[1].strip()
                if current_user_agent == '*' or current_user_agent is None:
                    allow_rules.append(path_rule)

        # Check rules in order - first matching rule wins
        check_path = path
        for rule in disallow_rules:
            if self._path_matches(check_path, rule):
                # Check if there's an allow override
                overridden = any(
                    self._path_matches(check_path, ar) for ar in allow_rules
                )
                if not overridden:
                    return False
        return True

    def _path_matches(self, path: str, rule: str) -> bool:
        """Check if a path matches a robots.txt rule."""
        if rule == '' or rule == '/':
            return False  # Empty disallow = allow
        if rule.endswith('$'):
            return path == rule[:-1]
        return path.startswith(rule) if path.startswith(rule) else False