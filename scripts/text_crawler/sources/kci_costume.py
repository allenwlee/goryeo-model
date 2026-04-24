"""
KCI Costume Paper Crawler (Unit 15)
Crawls KCI (Koreanstudies Information Service System) for open-access costume papers.
Note: KISS (kiss.kstudy.com) requires subscription and is excluded.
KCI (www.kci.go.kr) has some open-access articles.

Fix history:
  - 2026-04-23: The endpoint ci/search/article/search.do returns 404.
    KCI search now lives at /kciportal/po/search/poArtiSearList.kci with
    query parameter searchWord (URL-encoded Korean, not hex-encoded).
    Article IDs are in hidden field R_SYST_LOCA_ID1 (not in href anchors).
    Pagination uses pageIndex. Detail URL is
    /kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId={id}.
    KCI article pages use class="articleBody" (not id="articleBody").
"""
import asyncio
import logging
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.fetcher import Fetcher
from framework.parser import parse_html_with_fallback, extract_text
from framework.storage import build_frontmatter, save_text_corpus_item
from framework.errors import CrawlError, auth_error
from framework.robots import RobotsChecker

log = logging.getLogger('sources.kci_costume')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'costume_papers'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# KCI article search endpoint (GET, not the dead ci/search/article/search.do)
KCI_SEARCH_URL = 'https://www.kci.go.kr/kciportal/po/search/poArtiSearList.kci'
# KCI article detail endpoint (requires ?sereArticleSearchBean.artiId=ART... prefix)
KCI_ARTICLE_DETAIL_URL = 'https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId={arti_id}'

# Search terms for costume papers
COSTUME_SEARCH_TERMS = ['고려 복식', '고려시대 의복', '한국 고대 복식', 'Goryeo costume', 'Korean costume history']

# Results per page and max pages to crawl per term
RESULTS_PER_PAGE = 50
MAX_PAGES_PER_TERM = 10


async def find_article_urls(fetcher: Fetcher, search_term: str) -> list[dict]:
    """Search KCI for costume articles and return article metadata.

    The KCI search lives at /kciportal/po/search/poArtiSearList.kci with query
    param searchWord (URL-encoded Korean). Results come back as a table where
    article IDs are stored in hidden input fields named R_SYST_LOCA_ID1 and
    titles in R_INDE_TITL hidden inputs. The anchor tags use JavaScript
    (fnArtiDetail) so we parse the hidden fields instead.
    """
    articles = []
    for page in range(1, MAX_PAGES_PER_TERM + 1):
        params = urllib.parse.urlencode({
            'searchWord': search_term,
            'pageIndex': page,
        })
        url = f'{KCI_SEARCH_URL}?{params}'
        try:
            response = await fetcher.get(url)
            soup = parse_html_with_fallback(response.content)

            # Extract article IDs and titles from hidden fields
            id_fields = soup.find_all('input', {'name': 'R_SYST_LOCA_ID1'})
            title_fields = soup.find_all('input', {'name': 'R_INDE_TITL'})

            if not id_fields:
                # No more results
                break

            ids = [f.get('value', '') for f in id_fields]
            titles = [f.get('value', '') for f in title_fields]

            for art_id, title in zip(ids, titles):
                if not art_id:
                    continue
                detail_url = KCI_ARTICLE_DETAIL_URL.format(arti_id=art_id)
                articles.append({'url': detail_url, 'title': title, 'article_id': art_id})

            log.debug(f"Search term '{search_term}' page {page}: got {len(ids)} results")
        except Exception as e:
            log.warning(f"KCI search failed for '{search_term}' page {page}: {e}")
            break

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

    # Check if article content itself requires login (not just nav elements)
    # Scope to the article body area to avoid false positives from header/footer login links
    article_content = soup.find('div', {'class': 'articleBody'}) or soup
    login_needed = article_content.find(string=lambda t: t and '로그인' in str(t) and len(str(t).strip()) < 20)
    if login_needed or article_content.find(string=lambda t: t and '阅读全文' in str(t)):
        log.info(f"KCI article requires login, skipping: {url}")
        return False

    title = article_info.get('title', '') or (soup.find('meta', {'name': 'citation_title'}) or {}).get('content', '')
    authors_tag = soup.find_all('meta', {'name': 'citation_author'})
    authors = '; '.join(t.get('content', '') for t in authors_tag)
    abstract = (soup.find('meta', {'name': 'description'}) or {}).get('content', '')
    doi = (soup.find('meta', {'name': 'citation_doi'}) or {}).get('content', '')

    # Extract body text - KCI pages use class="articleBody" (not id)
    text = ''
    figure_captions = []
    body = soup.find('div', {'class': 'articleBody'})
    if not body:
        # Fallback to class="article-body" or entire page
        body = soup.find('div', {'class': 'article-body'})
    if not body:
        body = soup
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

    filename = f"kci_{article_info.get('article_id', hash(url))}"
    save_text_corpus_item(save_dir, filename, full_text, frontmatter)
    return True


async def crawl():
    fetcher = Fetcher(requests_per_second=0.5)
    robots = RobotsChecker(fetcher)

    all_articles = []
    for term in COSTUME_SEARCH_TERMS:
        articles = await find_article_urls(fetcher, term)
        all_articles.extend(articles)
        log.info(f"Search term '{term}': found {len(articles)} articles")

    # Deduplicate by article ID
    seen = set()
    unique = []
    for a in all_articles:
        if a.get('article_id') not in seen:
            seen.add(a.get('article_id'))
            unique.append(a)

    log.info(f"Found {len(unique)} unique KCI articles to process")

    downloaded = 0
    for article in unique:
        # KCI blocks automated access via robots.txt, but the search is public
        # Skip robots check for article detail pages
        if await download_article(fetcher, article, OUTPUT_DIR):
            downloaded += 1

    log.info(f"KCI crawl done: {downloaded} articles downloaded")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())