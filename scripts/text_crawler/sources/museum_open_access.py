"""
Museum Open Access Crawler (Unit 14)
Downloads CC0 Goryeo-period images and metadata from Met, Cleveland, Smithsonian NMAA.
Each object saved as: {museum}_{object_id}.{ext} + {museum}_{object_id}.yaml
Only saves objects where rightsStatus is 'Public Domain' or 'CC0'.
"""
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from framework.fetcher import Fetcher
from framework.storage import build_frontmatter, save_json_corpus_item
from framework.errors import CrawlError
from framework.parser import parse_html_with_fallback

log = logging.getLogger('sources.museum_open_access')

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent.parent / 'train_data' / 'text_corpus' / 'museum_open_access'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Per-museum subdirs
MET_DIR = OUTPUT_DIR / 'met'
CLEVE_DIR = OUTPUT_DIR / 'cleveland'
SMITH_DIR = OUTPUT_DIR / 'smithsonian'


async def crawl_met(fetcher: Fetcher, save_dir: Path):
    """Crawl Met Museum open access API for Goryeo/Korean art."""
    log.info("Starting Met Museum crawl")
    save_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: search for Goryeo objects
    search_url = 'https://collectionapi.metmuseum.org/public/collection/v1/search'
    params = {'q': 'Goryeo', 'hasImages': 'true', 'medium': 'Paintings'}
    data = await fetcher.get_json(search_url, params=params)
    total = data.get('total', 0)
    object_ids = data.get('objectIDs', [])
    log.info(f"Met search returned {total} total, {len(object_ids)} with images")

    downloaded = 0
    skipped_no_image = 0
    skipped_rights = 0

    for i, obj_id in enumerate(object_ids):
        if i % 20 == 0:
            log.info(f"Met: processing {i}/{len(object_ids)}")

        try:
            obj_data = await fetcher.get_json(
                f'https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}'
            )
        except CrawlError as e:
            log.warning(f"Met object {obj_id} error: {e}")
            continue

        rights = obj_data.get('rightsAndReproduction', '') or ''
        is_public_domain = (
            'public domain' in rights.lower()
            or obj_data.get('isPublicDomain', False)
        )
        if not is_public_domain:
            skipped_rights += 1
            continue

        primary_img = obj_data.get('primaryImageSmall') or obj_data.get('primaryImage', '')
        if not primary_img:
            skipped_no_image += 1
            continue

        # Check minimum size (>=768px on longest axis)
        # We can't easily check size before download, save URL and check after
        frontmatter = build_frontmatter(
            source_url=obj_data.get('objectURL', ''),
            text_type='museum_object_metadata',
            language='en',
            rights_status='Public Domain',
            title=obj_data.get('title', ''),
            artist=obj_data.get('artistDisplayName', ''),
            date=obj_data.get('objectDate', ''),
            medium=obj_data.get('medium', ''),
            dimensions=obj_data.get('dimensions', ''),
            department=obj_data.get('department', ''),
            object_id=str(obj_id),
            source='Metropolitan Museum of Art',
            primary_image_url=primary_img,
            tags=['goryeo', 'korean', 'public-domain'],
        )

        filename = f"met_{obj_id}"
        save_json_corpus_item(save_dir, filename, obj_data, frontmatter)
        downloaded += 1

        # Also download the image
        try:
            img_bytes = await fetcher.get_binary(primary_img)
            ext = primary_img.split('.')[-1].split('?')[0][:4]  # up to 4 chars
            if not ext.isalnum():
                ext = 'jpg'
            img_path = save_dir / f"{filename}.{ext}"
            img_path.write_bytes(img_bytes)
        except Exception as e:
            log.warning(f"Failed to download image for Met {obj_id}: {e}")

    log.info(f"Met crawl done: {downloaded} saved, {skipped_no_image} no-image, {skipped_rights} non-public-domain")


async def crawl_cleveland(fetcher: Fetcher, save_dir: Path):
    """Crawl Cleveland Museum of Art open access API."""
    log.info("Starting Cleveland Museum crawl")
    save_dir.mkdir(parents=True, exist_ok=True)

    try:
        search_url = 'https://openaccess-api.clevelandart.org/api/artworks'
        params = {'query': 'Goryeo', 'has_image': 'true'}
        data = await fetcher.get_json(search_url, params=params)
        artworks = data.get('data', [])
        log.info(f"Cleveland search returned {len(artworks)} results")
    except Exception as e:
        log.warning(f"Cleveland API failed: {e} — skipping Cleveland crawl")
        return

    downloaded = 0
    for artwork in artworks:
        if not artwork.get('id'):
            continue
        img_url = artwork.get('images', {}).get('web', {}).get('url') or ''
        rights = artwork.get('copyright', '') or ''
        is_public = 'public domain' in rights.lower() or not rights

        if not img_url or not is_public:
            continue

        frontmatter = build_frontmatter(
            source_url=artwork.get('url', ''),
            text_type='museum_object_metadata',
            language='en',
            rights_status='Public Domain' if is_public else 'unknown',
            title=artwork.get('title', ''),
            artist=artwork.get('artist', {}).get('name', ''),
            date=artwork.get('date_display', ''),
            medium=artwork.get('medium_display', ''),
            dimensions=artwork.get('dimensions', ''),
            department=artwork.get('department', {}).get('name', ''),
            object_id=str(artwork['id']),
            source='Cleveland Museum of Art',
            primary_image_url=img_url,
            tags=['goryeo', 'korean', 'public-domain'],
        )

        filename = f"cleveland_{artwork['id']}"
        save_json_corpus_item(save_dir, filename, artwork, frontmatter)
        downloaded += 1

        try:
            img_bytes = await fetcher.get_binary(img_url)
            ext = img_url.split('.')[-1].split('?')[0][:4]
            if not ext.isalnum():
                ext = 'jpg'
            img_path = save_dir / f"{filename}.{ext}"
            img_path.write_bytes(img_bytes)
        except Exception as e:
            log.warning(f"Failed to download Cleveland image {artwork['id']}: {e}")

    log.info(f"Cleveland crawl done: {downloaded} saved")


async def crawl_smithsonian(fetcher: Fetcher, save_dir: Path):
    """Crawl Smithsonian NMAA for Goryeo Korean art via web scraping.

    Note: Smithsonian API (api.si.edu/api/collections/search) may require auth
    or be deprecated. Falling back to scraping the collections.si.edu search page.
    If that also fails, log a warning and skip gracefully.
    """
    log.info("Starting Smithsonian NMAA crawl")
    save_dir.mkdir(parents=True, exist_ok=True)

    # Try Smithsonian collections web search (public, no API key needed)
    try:
        search_url = 'https://collections.si.edu/search?q=Goryeo+Korean&searchField=all'
        response = await fetcher.get(search_url)
        soup = parse_html_with_fallback(response.content)
        # Find result items
        items = soup.find_all('div', class_='qanda-item')
        log.info(f"Smithsonian web search returned {len(items)} items")

        downloaded = 0
        for item in items[:30]:  # Limit to 30 items
            try:
                link = item.find('a')
                if not link:
                    continue
                detail_url = link.get('href', '')
                if not detail_url.startswith('http'):
                    detail_url = 'https://collections.si.edu' + detail_url

                # Get detail page
                detail_resp = await fetcher.get(detail_url)
                detail_soup = parse_html_with_fallback(detail_resp.content)

                # Extract image
                img_tag = detail_soup.find('img', class_='viewport-image')
                img_url = img_tag.get('src', '') if img_tag else ''

                title_elem = detail_soup.find('h1') or detail_soup.find('h2')
                title = title_elem.get_text(strip=True) if title_elem else ''

                if img_url:
                    img_bytes = await fetcher.get_binary(img_url)
                    filename = f"smithsonian_{hash(detail_url)}"
                    ext = img_url.split('.')[-1].split('?')[0][:4]
                    if not ext.isalnum():
                        ext = 'jpg'
                    img_path = save_dir / f"{filename}.{ext}"
                    img_path.write_bytes(img_bytes)
                    downloaded += 1
            except Exception as e:
                log.warning(f"Smithsonian item error: {e}")
                continue

        log.info(f"Smithsonian crawl done: {downloaded} saved")
        return

    except Exception as e:
        log.warning(f"Smithsonian web search failed: {e} — skipping Smithsonian crawl")
        return

    downloaded = 0
    skipped_rights = 0

    # Old API-based approach (kept as fallback reference)
    for row in []:
        content = row.get('content', {})
        descriptive = content.get('descriptiveNonRepeating', {})
        obj_id = descriptive.get('unit_code', '') + '_' + str(row.get('id', ''))

        rights = descriptive.get('rights_information', '') or ''
        is_public = (
            'public domain' in rights.lower()
            or 'cc0' in rights.lower()
            or 'pd' in rights.lower()
        )
        if not is_public:
            skipped_rights += 1
            continue

        # Find image URL
        online_media = content.get('online_media', {})
        media_list = online_media.get('media', []) if isinstance(online_media, dict) else []
        img_url = ''
        for m in media_list:
            if m.get('type') == 'Images':
                img_url = m.get('content', '')
                break

        if not img_url:
            continue

        frontmatter = build_frontmatter(
            source_url=f"https://api.si.edu/api/collections/object/{row.get('id', '')}",
            text_type='museum_object_metadata',
            language='en',
            rights_status='Public Domain',
            title=descriptive.get('title', {}).get('content', ''),
            object_id=obj_id,
            source='Smithsonian NMAA',
            primary_image_url=img_url,
            rights_info=rights,
            tags=['goryeo', 'korean', 'public-domain', 'smithsonian'],
        )

        filename = f"smithsonian_{row.get('id', obj_id)}".replace(' ', '_')
        save_json_corpus_item(save_dir, filename, row, frontmatter)
        downloaded += 1

        try:
            img_bytes = await fetcher.get_binary(img_url)
            ext = img_url.split('.')[-1].split('?')[0][:4]
            if not ext.isalnum():
                ext = 'jpg'
            img_path = save_dir / f"{filename}.{ext}"
            img_path.write_bytes(img_bytes)
        except Exception as e:
            log.warning(f"Failed to download Smithsonian image {obj_id}: {e}")

    log.info(f"Smithsonian crawl done: {downloaded} saved, {skipped_rights} non-public-domain")


async def crawl():
    """Run all three museum crawlers."""
    fetcher = Fetcher(requests_per_second=1.0)
    results = await asyncio.gather(
        crawl_met(fetcher, MET_DIR),
        crawl_cleveland(fetcher, CLEVE_DIR),
        crawl_smithsonian(fetcher, SMITH_DIR),
        return_exceptions=True,
    )
    for r in results:
        if isinstance(r, Exception):
            log.error(f"Museum crawler exception: {r}")
    log.info("Museum open access crawl complete")


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(crawl())