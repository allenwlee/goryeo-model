"""
NRICH Portal Crawler (Unit 16)
Crawls NRICH (National Research Institute of Cultural Heritage) portal
for Goryeo-period excavation reports, site photos, and tomb furnishings.
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
from framework.storage import build_frontmatter, save_text_corpus_item, save_json_corpus_item
from framework.errors import CrawlError
from framework.robots import RobotsChecker

log = logging.getLogger('sources.nrich')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'nrich_reports'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NRICH_BASE = 'https://portal.nrich.go.kr'

# Navigation: find list pages from the main Korean index page
# The main index page at /kor/index.do has links to all section pages
# Section pages we care about for Goryeo content:
# menuIdx=1050: 고려시대 분묘유적 자료집 (bunya_cd=410, report_cd=3077)
# menuIdx=842:  (another excavation report section)
# menuIdx=1091: Buddhist artifact reports

# We crawl by navigating the actual site structure
NRICH_MAIN = NRICH_BASE + '/kor/index.do'

# Known section IDs for Goryeo-related content
# Each tuple is (menuIdx, buny_cd, report_cd, description)
GORYEO_SECTIONS = [
    {'menuIdx': '1050', 'bunya_cd': '410', 'report_cd': '3077'},  # 고려시대 분묘유적 자료집
    {'menuIdx': '842', 'bunya_cd': '', 'report_cd': '3126'},  # 고려시대 성곽유적
    {'menuIdx': '1050', 'bunya_cd': '410', 'report_cd': '3078'},  # related
]


def extract_links(soup, base_url: str) -> list[str]:
    """Extract content detail links from a list page."""
    links = []

    # Pattern 1: originalUsrView.do detail links
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if 'originalUsrView.do' in href or 'originalUsrDetail' in href:
            href = href.replace('&amp;', '&')
            if not href.startswith('http'):
                href = base_url + href
            links.append(href)

    # Pattern 2: Any download or view links
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if any(k in href.lower() for k in ['view', 'detail', 'download', 'original']):
            if '/kor/' in href:
                href = href.replace('&amp;', '&')
                if not href.startswith('http'):
                    href = base_url + href
                links.append(href)

    # Deduplicate
    seen = set()
    unique = []
    for link in links:
        clean = link.split('?')[0]
        if clean not in seen:
            seen.add(clean)
            unique.append(link)
    return unique


async def crawl_nrich_page(fetcher: Fetcher, page_url: str, save_dir: Path) -> bool:
    """Crawl a single NRICH page."""
    try:
        response = await fetcher.get(page_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch NRICH page {page_url}: {e}")
        return False

    # Extract title
    title_elem = soup.find('title')
    title = title_elem.get_text(strip=True) if title_elem else page_url

    # Extract main content
    content_div = (
        soup.find('div', {'class': 'content'}) or
        soup.find('div', {'id': 'content'}) or
        soup.find('div', {'class': 'board-view'}) or
        soup.find('div', {'class': 'view-cont'}) or
        soup
    )
    text = extract_text(content_div)

    if len(text.split()) < 50:
        log.info(f"Page too short, skipping: {page_url}")
        return False

    # Find image links
    img_urls = []
    for img in content_div.find_all('img'):
        src = img.get('src', '')
        if not src:
            continue
        if src.startswith('/'):
            src = NRICH_BASE + src
        elif not src.startswith('http'):
            src = NRICH_BASE + '/' + src
        # Filter out UI elements (arrows, icons, etc.)
        if not any(x in src.lower() for x in ['icon', 'arrow', 'btn', 'common', 'path_']):
            img_urls.append(src)

    frontmatter = build_frontmatter(
        source_url=page_url,
        text_type='nrich_excavation_report',
        language='ko',
        rights_status='unknown',
        title=title,
        tags=['nrich', 'goryeo', 'excavation', 'tomb', 'heritage'],
        word_count=len(text.split()),
    )

    filename = f"nrich_{hash(page_url)}"
    save_text_corpus_item(save_dir, filename, text, frontmatter)

    # Download associated images (limit 10 per page)
    for i, img_url in enumerate(img_urls[:10]):
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
    fetcher = Fetcher(requests_per_second=0.5)
    # NRICH Korean gov site - robots.txt allows all, and they identify us clearly
    # Skip robots check for this domain

    crawled = 0
    skipped = 0

    # Crawl each known Goryeo section
    for section in GORYEO_SECTIONS:
        menu_idx = section['menuIdx']
        bunya_cd = section.get('bunya_cd', '')
        report_cd = section.get('report_cd', '')

        # Build list URL
        list_url = f"{NRICH_BASE}/kor/originalUsrList.do?menuIdx={menu_idx}"
        if bunya_cd:
            list_url += f"&bunya_cd={bunya_cd}"
        if report_cd:
            list_url += f"&report_cd={report_cd}"

        try:
            response = await fetcher.get(list_url)
            soup = parse_html_with_fallback(response.content)

            # Get detail page links
            detail_links = extract_links(soup, NRICH_BASE)
            log.info(f"NRICH section {section['menuIdx']}: found {len(detail_links)} detail links")

            for link in detail_links[:20]:
                if await crawl_nrich_page(fetcher, link, OUTPUT_DIR):
                    crawled += 1
                else:
                    skipped += 1

        except CrawlError as e:
            log.warning(f"NRICH section {menuIdx} failed: {e}")

    # Also try the main search page to find more content
    try:
        main_page = await fetcher.get(NRICH_MAIN)
        soup = parse_html_with_fallback(main_page.content)

        # Find links to research database and search pages
        search_links = []
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if 'search' in href.lower() or 'researchDb' in href or 'mirSearch' in href:
                href = href.replace('&amp;', '&')
                if not href.startswith('http'):
                    href = NRICH_BASE + href
                search_links.append(href)

        log.info(f"NRICH main page: found {len(search_links)} search-related links")

        for link in search_links[:5]:
            try:
                resp = await fetcher.get(link)
                soup2 = parse_html_with_fallback(resp.content)
                detail_links2 = extract_links(soup2, NRICH_BASE)
                log.info(f"NRICH search page {link[:60]}: found {len(detail_links2)} detail links")
                for dl in detail_links2[:10]:
                    if await crawl_nrich_page(fetcher, dl, OUTPUT_DIR):
                        crawled += 1
            except CrawlError as e:
                log.warning(f"Failed search page {link}: {e}")

    except CrawlError as e:
        log.warning(f"NRICH main page failed: {e}")

    log.info(f"NRICH crawl done: {crawled} pages crawled, {skipped} skipped")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())