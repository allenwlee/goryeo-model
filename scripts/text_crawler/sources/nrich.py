"""
NRICH Portal Crawler (Unit 16)
Crawls NRICH (National Research Institute of Cultural Heritage) portal
for Goryeo-period excavation reports, site photos, and tomb furnishings.

Updated 2026-04-23: Files download via fnSatisfaction2 onclick handler:
  1. Parse fnSatisfaction2('/kor/includeFileDownLoad.do', file_idx, menuidx, '')
  2. GET https://portal.nrich.go.kr/kor/includeFileDownLoad.do?file_idx=...&menuidx=...
  3. Server returns application/octet-stream PDF
  No satisfaction popup / form POST required.
"""
import asyncio
import logging
import re
import sys
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.fetcher import Fetcher
from framework.parser import parse_html_with_fallback
from framework.storage import build_frontmatter, save_json_corpus_item
from framework.errors import CrawlError

log = logging.getLogger('sources.nrich')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'nrich_reports'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NRICH_BASE = 'https://portal.nrich.go.kr'

# Known section IDs for Goryeo-related content
GORYEO_SECTIONS = [
    {'menuIdx': '1050', 'bunya_cd': '410', 'report_cd': '3077'},  # 고려시대 분묘유적 자료집
    {'menuIdx': '842',  'bunya_cd': '', 'report_cd': '3126'},  # 고려시대 성곽유적
    {'menuIdx': '1050', 'bunya_cd': '410', 'report_cd': '3078'},  # related
]


def extract_file_downloads(soup) -> list[dict]:
    """Extract file download info from fnSatisfaction2 onclick handlers.
    
    Returns list of dicts with keys: download_path, file_idx, menuidx
    """
    results = []
    seen = set()
    for match in re.finditer(
        r"fnSatisfaction2\s*\(\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]*)['\"]\s*\)",
        str(soup)
    ):
        download_path = match.group(1)
        file_idx = match.group(2)
        menuidx = match.group(3)
        key = (download_path, file_idx, menuidx)
        if key not in seen:
            seen.add(key)
            results.append({
                'download_path': download_path,
                'file_idx': file_idx,
                'menuidx': menuidx,
            })
    return results


async def download_nrich_file(fetcher: Fetcher, info: dict, save_dir: Path) -> bool:
    """Download a single NRICH PDF file."""
    download_path = info['download_path']
    file_idx = info['file_idx']
    menuidx = info['menuidx']

    file_url = f'{NRICH_BASE}{download_path}?file_idx={file_idx}&menuidx={menuidx}'

    try:
        response = await fetcher.get(file_url)
        if response.status_code != 200:
            log.warning(f'NRICH file {file_idx}: HTTP {response.status_code}')
            return False

        ct = response.headers.get('content-type', '')
        content = response.content

        if len(content) < 1024:
            log.warning(f'NRICH file {file_idx}: too small ({len(content)} bytes), skipping')
            return False

        cd = response.headers.get('content-disposition', '')
        if 'filename=' in cd:
            filename = unquote(cd.split('filename=')[1].strip('"\r\n '))
        else:
            ext = 'pdf' if b'%PDF' in content[:4] else 'bin'
            filename = f'nrich_{file_idx}.{ext}'

        filepath = save_dir / filename
        filepath.write_bytes(content)

        frontmatter = build_frontmatter(
            source_url=file_url,
            text_type='nrich_pdf',
            language='ko',
            rights_status='unknown',
            title=filename,
            tags=['nrich', 'goryeo', 'excavation', 'tomb', 'heritage'],
            word_count=-1,
        )
        metadata_name = f'nrich_{file_idx}_meta'
        save_json_corpus_item(save_dir, metadata_name, {
            'file_idx': file_idx,
            'menuidx': menuidx,
            'filename': filename,
            'file_size': len(content),
            'content_type': ct,
        }, frontmatter)

        log.info(f'NRICH: downloaded {filename} ({len(content)} bytes)')
        return True

    except CrawlError as e:
        log.warning(f'NRICH file {file_idx} download failed: {e}')
        return False


async def crawl_article_page(fetcher: Fetcher, page_url: str, save_dir: Path) -> bool:
    """Parse an NRICH article page and download all attached files."""
    try:
        response = await fetcher.get(page_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f'Failed to fetch NRICH page {page_url}: {e}')
        return False

    file_infos = extract_file_downloads(soup)
    if not file_infos:
        log.info(f'No download links on page: {page_url}')
        return False

    for info in file_infos:
        await download_nrich_file(fetcher, info, save_dir)

    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)

    crawled = 0
    skipped = 0

    for section in GORYEO_SECTIONS:
        menu_idx = section['menuIdx']
        bunya_cd = section.get('bunya_cd', '')
        report_cd = section.get('report_cd', '')

        list_url = f'{NRICH_BASE}/kor/originalUsrList.do?menuIdx={menu_idx}'
        if bunya_cd:
            list_url += f'&bunya_cd={bunya_cd}'
        if report_cd:
            list_url += f'&report_cd={report_cd}'

        try:
            response = await fetcher.get(list_url)
            soup = parse_html_with_fallback(response.content)

            detail_links = []
            for a in soup.find_all('a', href=True):
                href = a.get('href', '')
                if 'originalUsrView.do' in href or 'originalUsrDetail' in href:
                    href = href.replace('&amp;', '&')
                    if not href.startswith('http'):
                        href = NRICH_BASE + href
                    detail_links.append(href.strip())

            log.info(f'NRICH section {menu_idx}: found {len(detail_links)} detail links')

            for link in detail_links[:20]:
                if await crawl_article_page(fetcher, link, OUTPUT_DIR):
                    crawled += 1
                else:
                    skipped += 1

        except CrawlError as e:
            log.warning(f'NRICH section {menu_idx} failed: {e}')

    log.info(f'NRICH crawl done: {crawled} pages crawled, {skipped} skipped')


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
