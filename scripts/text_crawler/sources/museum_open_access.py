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
        params = {'q': 'Goryeo', 'has_image': 'true'}
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


# Smithsonian S3 bulk data base URL (no auth required)
# Data is line-delimited JSON organized by unit code (museum/department).
# Relevant units for Asian/Korean art:
#   FSG  = Freer/Sackler Galleries (now NMAA - National Museum of Asian Art)
#   FSA  = National Museum of Asian Art Archives
# Each unit has 256 index files (~256 records each).
SMITHSONIAN_S3_BASE = 'https://smithsonian-open-access.s3-us-west-2.amazonaws.com/metadata/edan'
SMITHSONIAN_UNIT_INDEX = f'{SMITHSONIAN_S3_BASE}/index.txt'

# Smithsonian API endpoint (requires free API key from https://api.data.gov/signup/)
SMITHSONIAN_API_BASE = 'https://api.si.edu/openaccess/api/v1.0/search'


async def _search_smithsonian_s3(fetcher: Fetcher, unit_code: str, keyword: str, limit: int = 30) -> list[dict]:
    """Search Smithsonian bulk S3 data for records matching keyword.

    Downloads only the per-unit index file (list of shard URLs), then scans
    shards in order until ``limit`` matching records are found.
    Requires no API key. Yields raw record dicts.

    Args:
        fetcher:   Shared async fetcher with rate-limiting.
        unit_code: Smithsonian unit code (e.g. 'fsg', 'fsa', 'chndm').
        keyword:   Search term (case-insensitive).
        limit:     Maximum number of matching records to return.
    """
    import json
    import httpx

    index_url = f'{SMITHSONIAN_S3_BASE}/{unit_code.lower()}/index.txt'
    shard_urls: list[str] = []
    async with httpx.AsyncClient(timeout=30.0, headers={'User-Agent': fetcher.user_agent}) as client:
        resp = await client.get(index_url)
        if resp.status_code == 404:
            log.warning(f"Smithsonian S3: unit code '{unit_code}' not found at {index_url}")
            return []
        resp.raise_for_status()
        shard_urls = [line.strip() for line in resp.text.splitlines() if line.strip()]

    records = []
    kw_lower = keyword.lower()

    for shard_url in shard_urls:
        try:
            async with httpx.AsyncClient(timeout=60.0, headers={'User-Agent': fetcher.user_agent}) as client:
                resp = await client.get(shard_url)
                if resp.status_code >= 400:
                    log.warning(f"Smithsonian S3 shard error {resp.status_code}: {shard_url}")
                    continue
                resp.raise_for_status()

            for line in resp.text.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                rec_type = record.get('type', '')
                if rec_type not in ('edanmdm',):
                    continue

                content = record.get('content', {})
                descriptive = content.get('descriptiveNonRepeating', {})

                # Check rights - only CC0 or public domain
                online_media = descriptive.get('online_media', {})
                media_list = online_media.get('media', []) if isinstance(online_media, dict) else []

                img_url = ''
                rights = ''
                for m in media_list:
                    if m.get('type') == 'Images':
                        usage = m.get('usage', {})
                        access = (usage.get('access', '') or '') if isinstance(usage, dict) else ''
                        if access not in ('CC0', 'Public Domain'):
                            continue
                        img_url = m.get('content', '') or ''
                        rights = access
                        break

                if not img_url:
                    continue

                # Check title/content for keyword
                title_obj = descriptive.get('title', {})
                title_text = (title_obj.get('content', '') or '') if isinstance(title_obj, dict) else str(title_obj or '')

                freetext = content.get('freetext', {})
                search_text = (
                    title_text + ' ' +
                    ' '.join(f.get('content', '') for f in freetext.get('notes', [])) + ' ' +
                    ' '.join(f.get('content', '') for f in freetext.get('topic', [])) + ' ' +
                    ' '.join(f.get('content', '') for f in freetext.get('culture', [])) + ' ' +
                    ' '.join(f.get('content', '') for f in freetext.get('objectType', []))
                ).lower()

                if kw_lower not in search_text:
                    continue

                records.append(record)
                if len(records) >= limit:
                    return records

        except Exception as e:
            log.warning(f"Smithsonian S3 shard read error: {e}")
            continue

    return records


async def crawl_smithsonian(
    fetcher: Fetcher,
    save_dir: Path,
    *,
    smithsonian_api_key: str | None = None,
):
    """Crawl Smithsonian NMAA for Goryeo Korean art.

    Supports two data sources (in priority order):
    1. **Official API** (``smithsonian_api_key`` provided):
       Uses ``https://api.si.edu/openaccess/api/v1.0/search`` with the
       registered API key. Requires free registration at https://api.data.gov/signup/
    2. **S3 bulk data** (no auth needed):
       Scans publicly accessible line-delimited JSON on AWS S3 at
       ``s3://smithsonian-open-access/metadata/edan/``. Filters by
       unit code FSG (Freer/Sackler/NMAA) and keyword 'Goryeo'.

    Args:
        fetcher:             Shared async fetcher with rate-limiting.
        save_dir:            Directory to save results.
        smithsonian_api_key: Optional API key for the official API.
                             If not provided, falls back to S3 bulk data.
    """
    log.info("Starting Smithsonian NMAA crawl")
    log.info(f"  API key provided: {bool(smithsonian_api_key)}")
    save_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    records: list[dict] = []

    if smithsonian_api_key:
        # ---- Method 1: Official API ----
        log.info("Smithsonian: using official API (api.si.edu)")
        try:
            data = await fetcher.get_json(SMITHSONIAN_API_BASE, params={
                'q': 'Goryeo',
                'start': 0,
                'rows': 50,
                'sort': 'relevancy',
                'type': 'edanmdm',
                'row_group': 'objects',
                'api_key': smithsonian_api_key,
            })
            rows = data.get('response', {}).get('rows', [])
            log.info(f"Smithsonian API returned {len(rows)} rows")
            if rows:
                records = rows
        except CrawlError as e:
            log.warning(f"Smithsonian API crawl failed: {e} - falling back to S3 bulk data")
        except KeyError as e:
            log.warning(f"Smithsonian API unexpected response format: {e} - falling back to S3 bulk data")
        except Exception as e:
            log.warning(f"Smithsonian API error: {e} - falling back to S3 bulk data")

    if not records:
        if smithsonian_api_key:
            log.info("Smithsonian: API returned no results - trying S3 bulk data")
        else:
            log.info("Smithsonian: no API key provided - using S3 bulk data")
        records = await _search_smithsonian_s3(fetcher, 'fsg', 'Goryeo', limit=30)

    log.info(f"Smithsonian: processing {len(records)} candidate records")

    for record in records:
        try:
            content = record.get('content', {})
            descriptive = content.get('descriptiveNonRepeating', {})
            rec_type = record.get('type', '')
            unit_code = descriptive.get('unit_code', '') or record.get('unitCode', '') or ''
            rec_id = str(record.get('id', ''))

            obj_id = f"{unit_code}_{rec_id}" if rec_id else unit_code

            title_obj = descriptive.get('title', {})
            title = (title_obj.get('content', '') or '') if isinstance(title_obj, dict) else str(title_obj or '')

            online_media = descriptive.get('online_media', {})
            media_list = online_media.get('media', []) if isinstance(online_media, dict) else []
            img_url = ''
            rights = ''
            for m in media_list:
                if m.get('type') == 'Images':
                    usage = m.get('usage', {})
                    access = (usage.get('access', '') or '') if isinstance(usage, dict) else ''
                    if access in ('CC0', 'Public Domain'):
                        img_url = m.get('content', '') or ''
                        rights = access
                        break

            if not img_url:
                continue

            guid = descriptive.get('guid', '') or record.get('guid', '') or ''
            source_url = guid if guid.startswith('http') else f'https://n2t.net/ark:/{rec_id}'

            frontmatter = build_frontmatter(
                source_url=source_url,
                text_type='museum_object_metadata',
                language='en',
                rights_status=rights if rights else 'CC0',
                title=title,
                object_id=obj_id,
                source='Smithsonian NMAA',
                primary_image_url=img_url,
                record_type=rec_type,
                tags=['goryeo', 'korean', 'public-domain', 'smithsonian'],
            )

            filename = f"smithsonian_{obj_id}".replace(' ', '_')
            save_json_corpus_item(save_dir, filename, record, frontmatter)
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

        except Exception as e:
            log.warning(f"Smithsonian record processing error: {e}")
            continue

    log.info(f"Smithsonian crawl done: {downloaded} saved")


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