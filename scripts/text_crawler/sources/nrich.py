"""
NRICH Portal Crawler (Unit 16)
Crawls NRICH (National Research Institute of Cultural Heritage) portal
for Goryeo-period excavation reports, site photos, and tomb furnishings.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.fetcher import Fetcher
from framework.parser import parse_html_with_fallback, extract_text
from framework.storage import build_frontmatter, save_text_corpus_item, save_json_corpus_item
from framework.errors import CrawlError
from framework.robots import RobotsChecker

log = logging.getLogger('sources.nrich')

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'train_data' / 'text_corpus' / 'nrich_reports'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# NRICH search terms from the plan
SEARCH_TERMS = [
    '고려시대 분묘유적 자료집',
    '고려시대 성곽유적 자료집',
    '고려시대 유물',
    '고려시대 고분',
    '고려 청자 출토',
]

NRICH_SEARCH_URL = 'https://portal.nrich.go.kr/eng/search/search.do'


async def crawl_nrich_page(fetcher: Fetcher, page_url: str, save_dir: Path) -> bool:
    """Crawl a single NRICH page."""
    try:
        response = await fetcher.get(page_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch NRICH page {page_url}: {e}")
        return False

    title = soup.find('title').get_text(strip=True) if soup.find('title') else page_url

    # Extract main content
    content_div = (
        soup.find('div', {'class': 'content'}) or
        soup.find('div', {'id': 'content'}) or
        soup.find('div', {'class': 'board-view'}) or
        soup
    )
    text = extract_text(content_div)

    if len(text.split()) < 100:
        log.info(f"Page too short, skipping: {page_url}")
        return False

    # Find image links
    img_urls = []
    for img in content_div.find_all('img'):
        src = img.get('src', '')
        if src.startswith('/') or src.startswith('http'):
            if not src.startswith('http'):
                src = 'https://portal.nrich.go.kr' + src
            img_urls.append(src)

    frontmatter = build_frontmatter(
        source_url=page_url,
        text_type='nrich_excavation_report',
        language='ko',
        rights_status='unknown',  # NRICH content may be KOGL, check per-item
        title=title,
        tags=['nrich', 'goryeo', 'excavation', 'tomb', 'heritage'],
        word_count=len(text.split()),
    )

    filename = f"nrich_{hash(page_url)}"
    save_text_corpus_item(save_dir, filename, text, frontmatter)

    # Download associated images
    for i, img_url in enumerate(img_urls[:10]):  # Limit to 10 images per page
        try:
            img_bytes = await fetcher.get_binary(img_url)
            ext = img_url.split('.')[-1].split('?')[0][:4]
            if not ext.isalnum():
                ext = 'jpg'
            img_path = save_dir / f"{filename}_img{i}.{ext}"
            img_path.write_bytes(img_bytes)
        except Exception as e:
            log.warning(f"Failed to download image {img_url}: {e}")

    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)  # 2 second delay for Korean sites
    robots = RobotsChecker(fetcher)

    # NRICH doesn't have a simple API - try to search
    # Search is form-based, so we construct URLs for known result patterns
    crawled = 0
    skipped = 0

    # Try to crawl the NRICH main search results for each term
    for term in SEARCH_TERMS:
        # NRICH search URL pattern
        search_url = f'https://portal.nrich.go.kr/eng/search/search.do?query={term.encode("euc-kr").hex()}&category=total'
        blocked, reason = await robots.can_fetch(search_url)
        if blocked:
            log.info(f"NRICH blocked: {reason}")
            continue

        try:
            response = await fetcher.get(search_url)
            soup = parse_html_with_fallback(response.content)

            # Find result links
            result_links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'detail' in href or 'view' in href or 'download' in href:
                    if not href.startswith('http'):
                        href = 'https://portal.nrich.go.kr' + href
                    result_links.append(href)

            log.info(f"NRICH term '{term}': found {len(result_links)} result links")
            for link in result_links[:20]:  # Limit to 20 per term
                if await crawl_nrich_page(fetcher, link, OUTPUT_DIR):
                    crawled += 1
                else:
                    skipped += 1

        except CrawlError as e:
            log.warning(f"NRICH search failed for '{term}': {e}")

    log.info(f"NRICH crawl done: {crawled} pages crawled, {skipped} skipped")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
