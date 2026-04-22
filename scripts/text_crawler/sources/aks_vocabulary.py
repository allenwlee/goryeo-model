"""
AKS EncyKorea + KOSTMA Terminology Crawler (Unit 17)
Extracts controlled Korean costume vocabulary from AKS EncyKorea.
Outputs structured YAML per term: {term_ko, term_en, definition, related_terms, visual_notes, period_of_validity}
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

log = logging.getLogger('sources.aks_vocabulary')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'aks_vocabulary'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

AKS_ENCYKOREA_BASE = 'https://encykorea.aks.ac.kr'
# Key costume terms from the plan
COSTUME_TERMS = [
    '백관복', '제복', '품대', '각대', '의물', '팔관회', '연등회',
    '고려 복식', '고려 머리모양', '관모', '나전', '고려 목판',
    '고려 청자', '고려 불화', '팔관회', '관복', 'norigae',
    '치마', '저고리', '웃통', '경번갑',
]


async def crawl_term(fetcher: Fetcher, term: str, save_dir: Path) -> bool:
    """Crawl a single AKS EncyKorea term page."""
    # EncyKorea uses a search-based URL structure
    encoded = term.encode('utf-8').hex()
    page_url = f'{AKS_ENCYKOREA_BASE}/Search/Detail/{encoded}'

    try:
        response = await fetcher.get(page_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch AKS term '{term}': {e}")
        return False

    # Extract title (Korean)
    title_ko = term

    # Extract English name (if present)
    term_en = ''
    en_elem = soup.find('span', class_='en') or soup.find('em', class_='en')
    if en_elem:
        term_en = en_elem.get_text(strip=True)

    # Extract definition
    def_section = (
        soup.find('div', class_='definition') or
        soup.find('div', class_='desc') or
        soup.find('div', class_='content') or
        soup
    )
    definition = extract_text(def_section)

    # Extract related terms
    related = []
    for a in soup.find_all('a', href=True):
        href = a.get('href', '')
        if 'Search' in href or 'Term' in href:
            related.append(a.get_text(strip=True))
    related = list(set(related))[:10]

    # Extract period of validity
    period = ''
    for tag in soup.find_all(string=lambda t: t and ('시기' in t or '시대' in t or 'period' in t.lower())):
        period += tag.strip() + ' '

    if not definition.strip():
        log.info(f"No content for term '{term}', skipping")
        return False

    # Build YAML frontmatter
    frontmatter = build_frontmatter(
        source_url=page_url,
        text_type='aks_vocabulary_entry',
        language='ko',
        rights_status='open-access',
        title=title_ko,
        tags=['vocabulary', 'costume', 'korean', 'encykorea'],
        term_ko=title_ko,
        term_en=term_en or None,
        definition=definition[:1000],
        related_terms=related,
        period_of_validity=period.strip() or None,
        visual_notes='',
    )

    filename = f"aks_{hash(term)}"
    save_text_corpus_item(save_dir, filename, definition, frontmatter)
    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)
    robots = RobotsChecker(fetcher)

    extracted = 0
    for term in COSTUME_TERMS:
        blocked, reason = await robots.can_fetch(f'{AKS_ENCYKOREA_BASE}/Search')
        if blocked:
            log.info(f"AKS EncyKorea blocked: {reason}")
            break

        if await crawl_term(fetcher, term, OUTPUT_DIR):
            extracted += 1

    log.info(f"AKS vocabulary crawl done: {extracted} terms extracted")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
