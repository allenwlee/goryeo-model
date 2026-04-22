"""
Heritage Portal Crawler (Unit 16)
Crawls Heritage Portal (heritage.go.kr) for Goryeo-period site photos and descriptions.
Tags each item with KOGL status.
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

log = logging.getLogger('sources.heritage_portal')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'heritage_sites'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Heritage Portal base URL and period filter
HERITAGE_BASE = 'https://www.heritage.go.kr'
SEARCH_TERMS = ['고려', 'Goryeo', '고려시대']


async def crawl_heritage_page(fetcher: Fetcher, page_url: str, save_dir: Path) -> bool:
    """Crawl a single heritage page."""
    try:
        response = await fetcher.get(page_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch heritage page {page_url}: {e}")
        return False

    # Extract title
    title = (
        soup.find('meta', {'property': 'og:title'}) or
        soup.find('title')
    )
    title = title.get('content', title.get_text(strip=True)) if title else page_url

    # Extract main description
    desc = soup.find('meta', {'property': 'og:description'})
    description = desc.get('content', '') if desc else ''
    if not description:
        content_div = soup.find('div', {'class': 'cont'}) or soup.find('div', {'id': 'content'}) or soup
        description = extract_text(content_div)[:5000]

    # Extract KOGL status (usually in a badge or text)
    kogol_status = None
    kogol_text = ''
    for tag in soup.find_all(string=lambda t: t and 'KOGL' in t.upper()):
        kogol_text += tag.strip() + ' '
    for badge in soup.find_all(['span', 'div', 'p'], class_=lambda c: c and 'kogl' in c.lower()):
        kogol_text += badge.get_text(strip=True) + ' '

    # Determine KOGL type from text
    if 'KOGL 1' in kogol_text.upper() or 'CC0' in kogol_text:
        kogol_status = 1
    elif 'KOGL 2' in kogol_text.upper():
        kogol_status = 2
    elif 'KOGL 3' in kogol_text.upper():
        kogol_status = 3
    elif 'KOGL 4' in kogol_text.upper():
        kogol_status = 4

    # Extract image
    img_url = ''
    og_img = soup.find('meta', {'property': 'og:image'})
    if og_img:
        img_url = og_img.get('content', '')
        if img_url and not img_url.startswith('http'):
            img_url = HERITAGE_BASE + img_url

    frontmatter = build_frontmatter(
        source_url=page_url,
        text_type='heritage_site_photo',
        language='ko',
        rights_status='KOGL' if kogol_status else 'unknown',
        kogol_status=kogol_status,
        title=title,
        description=description[:500],
        tags=['heritage', 'goryeo', 'site', 'korean'],
        kogol_text=kogol_text.strip(),
    )

    filename = f"heritage_{hash(page_url)}"
    save_text_corpus_item(save_dir, filename, description, frontmatter)

    # Download image
    if img_url:
        try:
            img_bytes = await fetcher.get_binary(img_url)
            ext = img_url.split('.')[-1].split('?')[0][:4]
            if not ext.isalnum():
                ext = 'jpg'
            img_path = save_dir / f"{filename}.{ext}"
            img_path.write_bytes(img_bytes)
        except Exception as e:
            log.warning(f"Failed to download heritage image: {e}")

    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)
    robots = RobotsChecker(fetcher)

    crawled = 0
    for term in SEARCH_TERMS:
        search_url = f'{HERITAGE_BASE}/search/search.do?query={term}&category=total'
        blocked, reason = await robots.can_fetch(search_url)
        if blocked:
            log.info(f"Heritage Portal blocked: {reason}")
            continue

        try:
            response = await fetcher.get(search_url)
            soup = parse_html_with_fallback(response.content)

            # Find result links
            links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'info' in href or 'heritage' in href or 'detail' in href:
                    if not href.startswith('http'):
                        href = HERITAGE_BASE + href
                    links.append(href)

            log.info(f"Heritage '{term}': found {len(links)} links")
            for link in links[:30]:
                if await crawl_heritage_page(fetcher, link, OUTPUT_DIR):
                    crawled += 1

        except CrawlError as e:
            log.warning(f"Heritage search failed for '{term}': {e}")

    log.info(f"Heritage Portal crawl done: {crawled} pages")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
