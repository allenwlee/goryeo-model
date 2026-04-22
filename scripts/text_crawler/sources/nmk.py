"""
NMK (National Museum of Korea) Collection DB Crawler (Unit 16)
Crawls NMK collection database for Goryeo-period objects.
Tags each item with KOGL status. Prioritizes Type 1 (CC0-equivalent).
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

log = logging.getLogger('sources.nmk')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'nmk_objects'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# NMK collection search URLs
NMK_BASE = 'https://www.museum.go.kr'
SEARCH_TERMS = ['고려', '수월관음', '관복', '고려 청자', '고려 불화']


async def crawl_nmk_page(fetcher: Fetcher, page_url: str, save_dir: Path) -> bool:
    """Crawl a single NMK collection object page."""
    try:
        response = await fetcher.get(page_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch NMK page {page_url}: {e}")
        return False

    # Extract metadata
    title = (
        soup.find('meta', {'property': 'og:title'}) or
        soup.find('title')
    )
    title = title.get('content', title.get_text(strip=True)) if title else page_url

    # Extract description
    desc = soup.find('meta', {'property': 'og:description'})
    description = desc.get('content', '') if desc else ''
    if not description:
        content_div = soup.find('div', {'class': 'cont'}) or soup.find('div', {'id': 'content'}) or soup
        description = extract_text(content_div)

    # Extract KOGL status
    kogol_status = None
    kogol_text = ''
    for tag in soup.find_all(string=lambda t: t and 'KOGL' in t.upper()):
        kogol_text += tag.strip() + ' '
    for badge in soup.find_all(['span', 'div'], class_=lambda c: c and 'kogl' in c.lower()):
        kogol_text += badge.get_text(strip=True) + ' '

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
            img_url = NMK_BASE + img_url

    # Determine subdir based on KOGL status
    subdir = save_dir / 'train_eligible' if kogol_status == 1 else save_dir / 'reference_only'

    frontmatter = build_frontmatter(
        source_url=page_url,
        text_type='nmk_collection_object',
        language='ko',
        rights_status='KOGL Type ' + str(kogol_status) if kogol_status else 'unknown',
        kogol_status=kogol_status,
        title=title,
        description=description[:2000],
        tags=['nmk', 'goryeo', 'museum', 'korean', 'kogl'],
        kogol_text=kogol_text.strip(),
    )

    filename = f"nmk_{hash(page_url)}"
    save_text_corpus_item(subdir, filename, description, frontmatter)

    if img_url:
        try:
            img_bytes = await fetcher.get_binary(img_url)
            ext = img_url.split('.')[-1].split('?')[0][:4]
            if not ext.isalnum():
                ext = 'jpg'
            img_path = subdir / f"{filename}.{ext}"
            img_path.write_bytes(img_bytes)
        except Exception as e:
            log.warning(f"Failed to download NMK image: {e}")

    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)
    robots = RobotsChecker(fetcher)

    crawled = 0
    for term in SEARCH_TERMS:
        # NMK ENG search
        search_url = f'{NMK_BASE}/ENG/contents/E0402000000.do?searchKeyword={term}'
        blocked, reason = await robots.can_fetch(search_url)
        if blocked:
            log.info(f"NMK blocked: {reason}")
            continue

        try:
            response = await fetcher.get(search_url)
            soup = parse_html_with_fallback(response.content)

            # Find object detail links
            links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'detail' in href or 'object' in href:
                    if not href.startswith('http'):
                        href = NMK_BASE + href
                    links.append(href)

            log.info(f"NMK term '{term}': found {len(links)} links")
            for link in links[:30]:
                if await crawl_nmk_page(fetcher, link, OUTPUT_DIR):
                    crawled += 1

        except CrawlError as e:
            log.warning(f"NMK search failed for '{term}': {e}")

    log.info(f"NMK crawl done: {crawled} objects")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
