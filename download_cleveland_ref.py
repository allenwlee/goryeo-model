#!/usr/bin/env python3
"""Download Goryeo reference images from Cleveland Museum of Art CC0 collection."""
import json
import urllib.request
import os

# Cleveland Museum of Art has a simple open access API
# https://openaccess.clevelandart.org/

def search_cleveland(query, outdir, max_images=5):
    """Search Cleveland's open access API."""
    # Their API format
    url = f"https://openaccess.clevelandart.org/api/ artworks?search[term][q]={query}&search[term][is_public_domain]=true&fields=id,accession_number,title,creation_date,artist_name,culture,images,classification&per_page={max_images}"
    print(f"Searching Cleveland: {query}")
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            data = json.loads(resp.read())
            print(f"  Found: {data.get('info', {}).get('total', 0) if isinstance(data, dict) else 'N/A'}")
            if isinstance(data, dict) and 'data' in data:
                count = 0
                for item in data['data'][:max_images]:
                    title = item.get('title', 'Unknown')
                    culture = item.get('culture', '')
                    date = item.get('creation_date', '')
                    img_url = None
                    if item.get('images'):
                        img_url = item['images'].get('full') or item['images'].get('thumb')
                    print(f"  [{item['id']}] {title}, {culture}, {date}")
                    if img_url:
                        outpath = f"{outdir}/cleveland_{item['id']}.jpg"
                        print(f"  Downloading: {img_url}")
                        try:
                            urllib.request.urlretrieve(img_url, outpath)
                            size = os.path.getsize(outpath)
                            print(f"  Saved: {outpath} ({size} bytes)")
                            count += 1
                        except Exception as e:
                            print(f"  Download error: {e}")
                return count
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 0

outdir = "/Users/allenwlee/goryeo-model/reference_images"
os.makedirs(outdir, exist_ok=True)

# Search for Goryeo / Korean art
queries = ["Korean Goryeo", "Korean Buddhist", "Koryo celadon", "Korean painting"]
for q in queries:
    print(f"\n{'='*50}")
    search_cleveland(q.replace(' ', '+'), outdir, max_images=3)