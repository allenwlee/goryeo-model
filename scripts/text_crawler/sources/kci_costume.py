"""
KCI Costume Paper Crawler (Unit 15)
Crawls KCI (Koreanstudies Information Service System) for open-access costume papers.
Note: KISS (kiss.kstudy.com) requires subscription and is excluded.
KCI (www.kci.go.kr) has some open-access articles.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.fetcher import Fetcher
from framework.parser import parse_html_with_fallback, extract_text
from framework.storage import build_frontmatter, save_text_corpus_item
from framework.errors import CrawlError, auth_error
from framework.robots import RobotsChecker

log = logging.getLogger('sources.kci_costume')

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'train_data' / 'text_corpus' / 'costume_papers'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# KCI costume search URLs
KCI_SEARCH_URLS = [
    'https://www.kci.go.kr/kciportal/ci/search/article/search.do',
]
# Search terms for costume papers
COSTUME_SEARCH_TERMS = ['고려 복식', '고려시대 의복', '한국 고대 복식', 'Goryeo costume', 'Korean costume history']


async def find_article_urls(fetcher: Fetcher, search_term: str) -> list[dict]:
    """Search KCI for costume articles and return article metadata."""
    # KCI uses a form-based search - try to construct a search URL
    # Note: KCI may require session/cookies for full search
    # This is a best-effort approach
    articles = []
    try:
        url = f'https://www.kci.go.kr/kciportal/ci/search/article/search.do?novelSearch=false&searchOption.all&primaryKeyWord={search_term.encode("euc-kr").hex()}'
        response = await fetcher.get(url)
        soup = parse_html_with_fallback(response.content)

        # Parse article links from results page
        for a in soup.find_all('a', href=True):
            href = a.get('href', '')
            if 'articleView' in href or 'articleDetail' in href:
                if not href.startswith('http'):
                    href = 'https://www.kci.go.kr' + href
                title_text = a.get_text(strip=True)
                articles.append({'url': href, 'title': title_text})
    except Exception as e:
        log.warning(f"KCI search failed for '{search_term}': {e}")

    return articles


async def download_article(fetcher: Fetcher, article_info: dict, save_dir: Path) -> bool:
    """Download and extract text from a KCI article page."""
    url = article_info['url']
    try:
        response = await fetcher.get(url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch KCI article {url}: {e}")
        return False

    # Check if article requires login
    login_needed = soup.find(string=lambda t: t and '로그인' in t) or soup.find(string=lambda t: t and 'login' in t.lower())
    if login_needed:
        log.info(f"KCI article requires login, skipping: {url}")
        return False

    title = article_info.get('title', '') or (soup.find('meta', {'name': 'citation_title'}) or {}).get('content', '')
    authors = (soup.find('meta', {'name': 'citation_author'}) or {}).get('content', '')
    abstract = (soup.find('meta', {'name': 'description'}) or {}).get('content', '')
    doi = (soup.find('meta', {'name': 'citation_doi'}) or {}).get('content', '')

    # Extract body text
    text = ''
    figure_captions = []
    body = soup.find('div', {'id': 'articleBody'}) or soup.find('div', {'class': 'article-body'}) or soup
    if body:
        text = extract_text(body)
        # Extract figure captions
        for fig in body.find_all(['span', 'p'], string=lambda t: t and ('Fig' in t or 'fig.' in t or '그림' in t)):
            figure_captions.append(fig.get_text(strip=True))

    if not text.strip():
        log.info(f"No text extracted from {url}")
        return False

    tags = ['costume', 'kci', 'korean', 'goryeo']
    full_text = f"# {title}\n\n## Abstract\n{abstract}\n\n## Body\n{text}"
    if figure_captions:
        full_text += "\n\n## Figure Captions\n" + '\n'.join(f"- {c}" for c in figure_captions)

    frontmatter = build_frontmatter(
        source_url=url,
        text_type='kci_costume_paper',
        language='ko',
        rights_status='open-access',
        title=title,
        authors=authors,
        doi=doi,
        abstract=abstract,
        tags=tags,
        word_count=len(text.split()),
    )

    filename = f"kci_{hash(url)}"
    save_text_corpus_item(save_dir, filename, full_text, frontmatter)
    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)
    robots = RobotsChecker(fetcher)

    all_articles = []
    for term in COSTUME_SEARCH_TERMS:
        articles = await find_article_urls(fetcher, term)
        all_articles.extend(articles)

    # Deduplicate
    seen = set()
    unique = []
    for a in all_articles:
        if a['url'] not in seen:
            seen.add(a['url'])
            unique.append(a)

    log.info(f"Found {len(unique)} unique KCI articles to process")

    downloaded = 0
    for article in unique:
        blocked, reason = await robots.can_fetch(article['url'])
        if blocked:
            log.info(f"Skipping blocked URL: {reason}")
            continue
        if await download_article(fetcher, article, OUTPUT_DIR):
            downloaded += 1

    log.info(f"KCI crawl done: {downloaded} articles downloaded")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
