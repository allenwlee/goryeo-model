"""
Heritage Portal Crawler (Unit 16)
Crawls Heritage Portal (heritage.go.kr) for Goryeo-period site photos and descriptions.
Tags each item with KOGL status.
"""
import asyncio
import logging
import re
import sys
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.fetcher import Fetcher
from framework.parser import parse_html_with_fallback, extract_text
from framework.storage import build_frontmatter, save_text_corpus_item
from framework.errors import CrawlError
from framework.robots import RobotsChecker

log = logging.getLogger('sources.heritage_portal')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'heritage_sites'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HERITAGE_BASE = 'https://www.heritage.go.kr'
SEARCH_URL = HERITAGE_BASE + '/heri/unified/renewUnifiedList.do'
SEARCH_TERMS = ['고려', 'Goryeo', '고려시대']


def extract_item_links(soup) -> list[str]:
    """Extract valid HTTP(S) detail page links from a heritage search results page."""
    links = []

    # Method 1: Extract from goTopPage JS calls - URLs are in the SECOND argument
    # goTopPage('pageId', '/heri/path/to.do?params', 'handler')
    for match in re.finditer(r"goTopPage\s*\(\s*'[^']+'\s*,\s*'([^']+\.do[^']*)'", soup.text):
        href = match.group(1)
        href = href.replace('&amp;', '&')
        # Only include if it looks like a real path (not javascript expression)
        if href.startswith('/heri/') and '.do' in href:
            if not href.startswith('http'):
                href = HERITAGE_BASE + href
            links.append(href)

    # Method 2: Direct <a href> links - only include valid HTTP paths, NOT javascript:
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        # Skip javascript:, void, and any non-http(s) schemes
        if any(href.startswith(s) for s in ['javascript:', 'void:', '#', 'mailto:', 'tel:']):
            continue
        # Only include if it's a real path
        if href.startswith('/heri/') and '.do' in href:
            href = href.replace('&amp;', '&')
            if not href.startswith('http'):
                href = HERITAGE_BASE + href
            links.append(href)

    # Deduplicate
    seen = set()
    unique = []
    for link in links:
        clean = link.split(';')[0].split('?')[0].split('#')[0]
        if clean not in seen:
            seen.add(clean)
            unique.append(link)
    return unique


async def crawl_heritage_page(fetcher: Fetcher, page_url: str, save_dir: Path) -> bool:
    """Crawl a single heritage page."""
    try:
        response = await fetcher.get(page_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch heritage page {page_url}: {e}")
        return False

    # Extract title
    title_elem = soup.find('meta', {'property': 'og:title'}) or soup.find('title')
    title = title_elem.get('content', title_elem.get_text(strip=True)) if title_elem else page_url

    # Extract main description
    desc = soup.find('meta', {'property': 'og:description'})
    description = desc.get('content', '') if desc else ''
    if not description:
        content_div = soup.find('div', {'class': 'cont'}) or soup.find('div', {'id': 'content'}) or soup
        description = extract_text(content_div)[:5000]

    # Extract KOGL status
    kogl_text = ''
    for tag in soup.find_all(string=lambda t: t and 'KOGL' in t.upper()):
        kogl_text += tag.strip() + ' '
    for badge in soup.find_all(['span', 'div', 'p'], class_=lambda c: c and 'kogl' in c.lower()):
        kogl_text += badge.get_text(strip=True) + ' '

    kogl_status = None
    if 'KOGL 1' in kogl_text.upper() or 'CC0' in kogl_text:
        kogl_status = 1
    elif 'KOGL 2' in kogl_text.upper():
        kogl_status = 2
    elif 'KOGL 3' in kogl_text.upper():
        kogl_status = 3
    elif 'KOGL 4' in kogl_text.upper():
        kogl_status = 4

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
        rights_status='KOGL' if kogl_status else 'unknown',
        kogl_status=kogl_status,
        title=title,
        description=description[:500],
        tags=['heritage', 'goryeo', 'site', 'korean'],
        kogl_text=kogl_text.strip(),
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

    crawled = 0
    for term in SEARCH_TERMS:
        encoded_term = quote(term)
        search_url = f"{SEARCH_URL}?shapes=0&pageIndex=1&region=1&query={encoded_term}&pageNo=1_1_1_1"

        try:
            response = await fetcher.get(search_url)
            soup = parse_html_with_fallback(response.content)

            links = extract_item_links(soup)
            log.info(f"Heritage '{term}': found {len(links)} item links")

            for link in links[:30]:
                if await crawl_heritage_page(fetcher, link, OUTPUT_DIR):
                    crawled += 1

        except CrawlError as e:
            log.warning(f"Heritage search failed for '{term}': {e}")

    log.info(f"Heritage Portal crawl done: {crawled} pages")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())