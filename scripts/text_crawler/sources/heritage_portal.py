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
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.fetcher import Fetcher
from framework.parser import parse_html_with_fallback, extract_text
from framework.storage import build_frontmatter, save_text_corpus_item, save_json_corpus_item
from framework.errors import CrawlError
from framework.robots import RobotsChecker

log = logging.getLogger('sources.heritage_portal')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'heritage_sites'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HERITAGE_BASE = 'https://www.heritage.go.kr'

# Goryeo-era shapes code + Korean search terms
SEARCH_TERMS = ['고려', '고려시대']
MAX_PAGES = 50  # pagination limit per term


def _build_search_url(term: str, page: int = 1) -> str:
    """Build search URL for a given term and page number."""
    encoded = quote(term)
    # shapes=50: 국보 유형 (National Treasure — highest-value Goryeo artifacts)
    return (
        f"{HERITAGE_BASE}/heri/unified/renewUnifiedList.do"
        f"?shapes=50&pageIndex={page}&region=1&query={encoded}&pageNo=1_1_1_1"
    )


def _extract_detail_links(soup) -> list[dict]:
    """Extract (href, ccbaCpno) pairs from search results.
    
    Each search result item has an <a href="/heri/cul/culSelectDetail.do?..."> button.
    We parse the ccbaCpno from the URL to build the content endpoint.
    """
    results = []
    seen = set()
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if 'culSelectDetail.do' not in href:
            continue
        href = href.replace('&amp;', '&').strip()
        href = re.sub(r'[\n\r\t]', '', href)
        # Extract ccbaCpno from query string
        cpno_match = re.search(r'ccbaCpno=(\d+)', href)
        if not cpno_match:
            continue
        ccba_cpno = cpno_match.group(1)
        if ccba_cpno in seen:
            continue
        seen.add(ccba_cpno)
        results.append({'href': href, 'ccba_cpno': ccba_cpno})
    return results


def _extract_title(soup) -> str:
    """Extract artifact title from detail page."""
    og_title = soup.find('meta', {'property': 'og:title'})
    if og_title:
        return og_title.get('content', '').strip()
    title = soup.find('title')
    return title.get_text(strip=True) if title else 'unknown'


def _extract_ccba_cpno(soup) -> str | None:
    """Extract ccbaCpno from hidden input on detail page."""
    inp = soup.find('input', {'name': 'ccbaCpno'})
    return inp.get('value', '') if inp else None


async def _fetch_content_html(fetcher: Fetcher, ccba_cpno: str) -> str | None:
    """Fetch the per-item content page that holds the actual description text.
    
    Content URL pattern: /DATA1/heritage/hub_img/html/cul_{ccbaCpno}.html
    """
    content_url = f"{HERITAGE_BASE}/DATA1/heritage/hub_img/html/cul_{ccba_cpno}.html"
    try:
        response = await fetcher.get(content_url)
        if response.status_code == 200:
            return response.text
    except CrawlError:
        pass
    return None


async def _fetch_detail_images(fetcher: Fetcher, detail_url: str, soup) -> list[str]:
    """Extract image URLs from the detail page."""
    img_urls = []
    seen = set()
    # Primary images: thumb URLs from the detail page
    for img in soup.find_all('img'):
        src = img.get('src', '')
        alt = img.get('alt', '')
        if 'thumb' in src and ('national_treasure' in src or 'unisearch' in src):
            if src not in seen:
                seen.add(src)
                full = src if src.startswith('http') else HERITAGE_BASE + src
                img_urls.append(full)
    return img_urls


def _extract_content_text(html_content: str) -> str:
    """Extract artifact description from the content HTML page."""
    if not html_content:
        return ''
    soup = parse_html_with_fallback(html_content.encode() if isinstance(html_content, str) else html_content)
    # The content div contains the actual description
    divs = soup.find_all('div')
    for d in divs:
        txt = d.get_text(strip=True)
        if len(txt) > 300:
            return txt
    # Fallback: extract all text
    return extract_text(soup)


def _extract_badge(soup) -> str | None:
    """Extract heritage designation badge (국보, 보물, etc.)."""
    for badge in soup.find_all(['span', 'strong', 'p', 'div'], class_=lambda c: c and 'badge' in str(c).lower()):
        txt = badge.get_text(strip=True)
        if txt:
            return txt
    return None


async def crawl_heritage_item(
    fetcher: Fetcher,
    item: dict,
    save_dir: Path,
) -> bool:
    """Crawl a single heritage item: fetch content page, download text + images."""
    ccba_cpno = item['ccba_cpno']
    detail_url = HERITAGE_BASE + item['href']

    try:
        # Fetch detail page to get page title and images
        detail_resp = await fetcher.get(detail_url)
        detail_soup = parse_html_with_fallback(detail_resp.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch detail page {detail_url}: {e}")
        return False

    title = _extract_title(detail_soup)
    badge = _extract_badge(detail_soup)

    # Fetch the dedicated content page (holds the actual description)
    content_html = await _fetch_content_html(fetcher, ccba_cpno)
    description = _extract_content_text(content_html or '')

    if not description or len(description) < 100:
        log.info(f"No content for ccbaCpno={ccba_cpno}, skipping")
        return False

    # Get images
    img_urls = await _fetch_detail_images(fetcher, detail_url, detail_soup)

    frontmatter = build_frontmatter(
        source_url=detail_url,
        text_type='heritage_artifact',
        language='ko',
        rights_status='unknown',
        title=title,
        badge=badge,
        description=description[:2000],
        tags=['heritage', 'goryeo', 'artifact', 'korean', 'national_treasure'],
        ccba_cpno=ccba_cpno,
    )

    filename = f"heritage_{ccba_cpno}"
    save_text_corpus_item(save_dir, filename, description, frontmatter)

    # Download images
    for i, img_url in enumerate(img_urls[:10]):
        try:
            img_bytes = await fetcher.get_binary(img_url)
            ext = img_url.split('.')[-1].split('?')[0][:4]
            if not ext.isalnum():
                ext = 'jpg'
            img_path = save_dir / f"{filename}_img{i}.{ext}"
            img_path.write_bytes(img_bytes)
            log.info(f"  Downloaded image {i}: {img_url.split('/')[-1][:40]}")
        except Exception as e:
            log.warning(f"  Failed to download {img_url}: {e}")

    log.info(f"Heritage item {ccba_cpno}: {title[:50]} ({len(description)} chars, {len(img_urls)} imgs)")
    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)

    crawled = 0
    skipped = 0

    for term in SEARCH_TERMS:
        log.info(f"Heritage search: '{term}'")
        seen_items = set()

        for page in range(1, MAX_PAGES + 1):
            search_url = _build_search_url(term, page)
            try:
                response = await fetcher.get(search_url)
                soup = parse_html_with_fallback(response.content)

                items = _extract_detail_links(soup)
                if not items:
                    break  # No more results on this page

                log.info(f"  Page {page}: found {len(items)} items (cumulative seen: {len(seen_items)})")

                for item in items:
                    ccba_cpno = item['ccba_cpno']
                    if ccba_cpno in seen_items:
                        continue
                    seen_items.add(ccba_cpno)

                    ok = await crawl_heritage_item(fetcher, item, OUTPUT_DIR)
                    if ok:
                        crawled += 1
                    else:
                        skipped += 1

            except CrawlError as e:
                log.warning(f"  Page {page} failed for '{term}': {e}")
                continue

    log.info(f"Heritage Portal crawl done: {crawled} items, {skipped} skipped")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
