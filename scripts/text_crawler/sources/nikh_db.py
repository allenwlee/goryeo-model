"""
NIKH DB Crawler (Unit 17)
Crawls NIKH (National Institute of Korean History) DB for chronology entries
and court ritual references relevant to Goryeo costume research.
db.history.go.kr - search reign-year entries for Goryeo period.
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

log = logging.getLogger('sources.nikh_db')

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'train_data' / 'text_corpus' / 'nikh_db'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

NIKH_BASE = 'https://db.history.go.kr'
# Key Goryeo reigns: Gojong year 5 (1218 CE) = critical post-1218 boundary
GORYEO_REIGNS = [
    ('太祖', '1', '918'),
    ('太宗', '5', '918'),  # will search years 1-16
    ('世宗', '9', '1418'),
    ('成宗', '5', '1465'),
    # For Goryeo: starting king and year range
    ('高宗', '1', '1213'),   # Goryeo King Gojong
    ('高宗', '5', '1217'),   # Gojong year 5 = 1218 CE post-Yuan boundary
]


async def crawl_nikh_entries(fetcher: Fetcher, king: str, year: str, start_year: str, save_dir: Path) -> int:
    """Crawl NIKH DB for a specific reign-year entry."""
    # NIKH URL pattern: /item/{king}_{year}
    search_url = f'{NIKH_BASE}/search/search.do?num=10&pageSize=10&sort= profess+king+year_start+year_end&king={king}&year_start={year}&year_end={year}'

    try:
        blocked, reason = await RobotsChecker(fetcher).can_fetch(NIKH_BASE)
        if blocked:
            log.info(f"NIKH blocked: {reason}")
            return 0
    except Exception:
        pass

    try:
        response = await fetcher.get(search_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to search NIKH for {king} year {year}: {e}")
        return 0

    # Extract entries
    entries = []
    for item in soup.find_all('div', class_='result-item') or soup.find_all('li', class_='result'):
        title = item.find('a')
        if title:
            href = title.get('href', '')
            if not href.startswith('http'):
                href = NIKH_BASE + href
            text = item.get_text(strip=True)
            entries.append({'url': href, 'title': title.get_text(strip=True), 'text': text})

    if not entries:
        # Try direct URL pattern
        direct_url = f'{NIKH_BASE}/item/{king}_{year}'
        try:
            response = await fetcher.get(direct_url)
            soup = parse_html_with_fallback(response.content)
            content = extract_text(soup)
            if len(content.split()) > 50:
                frontmatter = build_frontmatter(
                    source_url=direct_url,
                    text_type='nikh_chronology_entry',
                    language='ko',
                    rights_status='open-access',
                    title=f'{king} {year}년',
                    king=king,
                    year=year,
                    tags=['nikh', 'chronology', 'goryeo', 'court-ritual'],
                )
                filename = f"nikh_{king}_{year}"
                save_text_corpus_item(save_dir, filename, content, frontmatter)
                return 1
        except CrawlError:
            pass

    for entry in entries[:5]:  # Limit per search
        try:
            response = await fetcher.get(entry['url'])
            soup = parse_html_with_fallback(response.content)
            content = extract_text(soup)

            if len(content.split()) < 50:
                continue

            frontmatter = build_frontmatter(
                source_url=entry['url'],
                text_type='nikh_chronology_entry',
                language='ko',
                rights_status='open-access',
                title=entry['title'],
                king=king,
                year=year,
                tags=['nikh', 'chronology', 'goryeo', 'court-ritual'],
            )
            filename = f"nikh_{hash(entry['url'])}"
            save_text_corpus_item(save_dir, filename, content, frontmatter)
        except Exception as e:
            log.warning(f"Failed to process NIKH entry: {e}")

    return len(entries)


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)

    total = 0
    # Search key years
    for king, year, _ in GORYEO_REIGNS:
        count = await crawl_nikh_entries(fetcher, king, year, year, OUTPUT_DIR)
        total += count

    log.info(f"NIKH crawl done: {total} entries")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
