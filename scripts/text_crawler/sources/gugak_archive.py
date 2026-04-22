"""
Gugak Archive Crawler (Unit 17)
Extracts court music metadata and descriptions from the Gugak Archive (gugak.go.kr).
Note: Full video requires login/request - crawler extracts metadata and text descriptions only.
Actual audio/video files are manual retrieval (per Deferred to Implementation).
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.fetcher import Fetcher
from framework.parser import parse_html_with_fallback, extract_text
from framework.storage import build_frontmatter, save_text_corpus_item
from framework.errors import CrawlError
from framework.robots import RobotsChecker

log = logging.getLogger('sources.gugak_archive')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'gugak_audio'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GUGAK_BASE = 'https://www.gugak.go.kr'
SEARCH_TERMS = ['고려', '궁중', '의식', '공연']


async def crawl_gugak_page(fetcher: Fetcher, page_url: str, save_dir: Path) -> bool:
    """Crawl a single Gugak archive page."""
    try:
        response = await fetcher.get(page_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch Gugak page {page_url}: {e}")
        return False

    title = (
        soup.find('meta', {'property': 'og:title'}) or
        soup.find('title')
    )
    title = title.get('content', title.get_text(strip=True)) if title else page_url

    desc = soup.find('meta', {'property': 'og:description'})
    description = desc.get('content', '') if desc else ''
    if not description:
        content_div = soup.find('div', class_='cont') or soup.find('div', id='content') or soup
        description = extract_text(content_div)

    # Check KOGL status
    kogol_text = ''
    for tag in soup.find_all(string=lambda t: t and 'KOGL' in t.upper()):
        kogol_text += tag.strip() + ' '

    frontmatter = build_frontmatter(
        source_url=page_url,
        text_type='gugak_archive_metadata',
        language='ko',
        rights_status='KOGL' if kogol_text else 'unknown',
        title=title,
        description=description[:2000],
        tags=['gugak', 'court-music', 'korean', 'ceremonial'],
        kogol_text=kogol_text.strip(),
        note='Full video requires login/request. Crawler extracts metadata only.',
    )

    filename = f"gugak_{hash(page_url)}"
    save_text_corpus_item(save_dir, filename, description, frontmatter)
    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)
    robots = RobotsChecker(fetcher)

    crawled = 0
    for term in SEARCH_TERMS:
        search_url = f'{GUGAK_BASE}/search/search.do?keyword={term}'
        blocked, reason = await robots.can_fetch(search_url)
        if blocked:
            log.info(f"Gugak blocked: {reason}")
            continue

        try:
            response = await fetcher.get(search_url)
            soup = parse_html_with_fallback(response.content)

            links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'archive' in href or 'music' in href or 'perform' in href:
                    if not href.startswith('http'):
                        href = GUGAK_BASE + href
                    links.append(href)

            log.info(f"Gugak '{term}': found {len(links)} links")
            for link in links[:20]:
                if await crawl_gugak_page(fetcher, link, OUTPUT_DIR):
                    crawled += 1

        except CrawlError as e:
            log.warning(f"Gugak search failed for '{term}': {e}")

    log.info(f"Gugak Archive crawl done: {crawled} pages")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
