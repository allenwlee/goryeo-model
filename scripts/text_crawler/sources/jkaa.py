"""
JKAA Article Crawler (Unit 15)
Downloads open-access JKAA articles on Goryeo costume as PDFs.
Extracts text with pdfplumber, preserving figure captions.
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
from framework.robots import RobotsChecker, is_blocked

log = logging.getLogger('sources.jkaa')

OUTPUT_DIR = Path(__file__).parent.parent.parent / 'train_data' / 'text_corpus' / 'jkaa_articles'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Known JKAA costume article URLs from research report
JKAA_ARTICLE_URLS = [
    'https://www.ijkaa.org/v.14/0/73/29',   # costume article vol.14
    # Add more URLs as discovered - crawl the index to find them
]


async def find_article_urls(fetcher: Fetcher) -> list[str]:
    """Crawl JKAA index page to find all costume/Goryeo article URLs."""
    index_url = 'https://www.ijkaa.org/'
    try:
        response = await fetcher.get(index_url)
        soup = parse_html_with_fallback(response.content)
        # Find all article links with costume/korean keywords
        urls = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            text = a.get_text(strip=True).lower()
            if any(kw in text for kw in ['costume', 'goryeo', 'korean', 'clothing', 'dress']):
                if href.startswith('http'):
                    urls.append(href)
        return list(set(urls))
    except CrawlError as e:
        log.warning(f"Failed to crawl JKAA index: {e}")
        return JKAA_ARTICLE_URLS  # Fall back to known URLs


async def download_pdf(fetcher: Fetcher, article_url: str, save_dir: Path) -> bool:
    """Download PDF from an article page and extract text."""
    try:
        response = await fetcher.get(article_url)
        soup = parse_html_with_fallback(response.content)
    except CrawlError as e:
        log.warning(f"Failed to fetch article page {article_url}: {e}")
        return False

    # Find PDF link
    pdf_links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.endswith('.pdf'):
            if not href.startswith('http'):
                href = 'https://www.ijkaa.org' + href
            pdf_links.append(href)

    if not pdf_links:
        log.info(f"No PDF link found on {article_url}")
        # Save the page text itself as fallback
        text = extract_text(soup)
        title = soup.title.get_text(strip=True) if soup.title else article_url
        frontmatter = build_frontmatter(
            source_url=article_url,
            text_type='jkaa_article',
            language='en',
            rights_status='open-access',
            title=title,
            tags=['jkaa', 'costume', 'goryeo'],
        )
        save_text_corpus_item(save_dir, f"jkaa_{hash(article_url)}", text[:5000], frontmatter)
        return True

    for pdf_url in pdf_links:
        try:
            pdf_bytes = await fetcher.get_binary(pdf_url)
        except CrawlError as e:
            log.warning(f"Failed to download PDF {pdf_url}: {e}")
            continue

        # Extract text from PDF
        try:
            import pdfplumber
        except ImportError:
            log.error("pdfplumber not installed, cannot extract PDF text")
            return False

        article_title = soup.title.get_text(strip=True) if soup.title else article_url

        # Save PDF
        pdf_filename = f"jkaa_{hash(pdf_url)}.pdf"
        pdf_path = save_dir / pdf_filename
        pdf_path.write_bytes(pdf_bytes)

        # Extract text
        try:
            extracted_text = ''
            figure_captions = []
            with pdfplumber.open(pdf_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text() or ''
                    extracted_text += page_text + '\n\n'
                    # Extract figure captions
                    captions = page.extract_texts_by_layout()  # rough layout-based extraction
                    figure_captions.extend([c.strip() for c in captions if 'fig' in c.lower() or 'plate' in c.lower()])

            if not extracted_text.strip():
                log.warning(f"PDF {pdf_url} appears to be scanned images, no extractable text")
                frontmatter = build_frontmatter(
                    source_url=pdf_url,
                    text_type='jkaa_article_pdf_scan',
                    language='en',
                    rights_status='open-access',
                    title=article_title,
                    tags=['jkaa', 'costume', 'goryeo', 'scanned-images'],
                    note='PDF contains scanned images, text not extractable',
                )
                save_text_corpus_item(save_dir, f"jkaa_scan_{hash(pdf_url)}", article_title, frontmatter)
                return True

            # Format: main text + separated figure captions
            full_text = f"# {article_title}\n\n## Body\n{extracted_text}"
            if figure_captions:
                full_text += f"\n\n## Figure Captions\n" + '\n'.join(f"- {c}" for c in figure_captions)

            frontmatter = build_frontmatter(
                source_url=pdf_url,
                text_type='jkaa_article',
                language='en',
                rights_status='open-access',
                title=article_title,
                tags=['jkaa', 'costume', 'goryeo'],
                word_count=len(extracted_text.split()),
            )
            txt_filename = f"jkaa_{hash(pdf_url)}"
            save_text_corpus_item(save_dir, txt_filename, full_text, frontmatter)
            log.info(f"Extracted {len(extracted_text.split())} words from {pdf_url}")
            return True

        except Exception as e:
            log.warning(f"Failed to extract text from PDF {pdf_url}: {e}")
            return False

    return False


async def crawl():
    """Crawl JKAA for costume articles."""
    fetcher = Fetcher(requests_per_second=0.5)  # Slow, academic site
    robots = RobotsChecker(fetcher)

    article_urls = await find_article_urls(fetcher)
    log.info(f"Found {len(article_urls)} JKAA article URLs to process")

    downloaded = 0
    for url in article_urls:
        # Check robots
        blocked, reason = await robots.can_fetch(url)
        if blocked:
            log.info(f"Skipping blocked URL {url}: {reason}")
            continue

        result = await download_pdf(fetcher, url, OUTPUT_DIR)
        if result:
            downloaded += 1

    log.info(f"JKAA crawl done: {downloaded} articles downloaded")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())
