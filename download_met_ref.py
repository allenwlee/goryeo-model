#!/usr/bin/env python3
"""Download Goryeo reference images from Met Open Access."""
import json
import urllib.request
import os

def search_and_download(query, outdir, max_images=3):
    """Search Met API and download first results."""
    api_url = f"https://collectionapi.metmuseum.org/public/collection/v1/search?q={query}&hasImages=true"
    print(f"Searching: {query}")
    try:
        with urllib.request.urlopen(api_url, timeout=15) as resp:
            data = json.loads(resp.read())
            print(f"  Found {data.get('total', 0)} results")
            count = 0
            for obj_id in data.get('objectIDs', [])[:max_images]:
                obj_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}"
                try:
                    with urllib.request.urlopen(obj_url, timeout=15) as oresp:
                        obj = json.loads(oresp.read())
                        # Check if it's Korean/Goryeo
                        title = obj.get('title', '')
                        period = obj.get('period', '')
                        culture = obj.get('culture', '')
                        is_korean = any(x in (period + culture + title).lower() for x in ['korean', 'goryeo', 'korea'])
                        img_url = obj.get('primaryImageSmall')
                        rights = obj.get('rightsAndReproduction', '')

                        print(f"  [{obj_id}] {title}")
                        print(f"       period: {period}, culture: {culture}")
                        print(f"       rights: {rights[:50] if rights else 'N/A'}...")

                        # Download if it's Korean and has image
                        if is_korean and img_url and ('CC0' in rights or 'public domain' in rights.lower() or rights == ''):
                            outpath = f"{outdir}/met_{obj_id}.jpg"
                            print(f"  Downloading: {img_url}")
                            urllib.request.urlretrieve(img_url, outpath)
                            print(f"  Saved: {outpath} ({os.path.getsize(outpath)} bytes)")
                            count += 1
                            if count >= max_images:
                                break
                except Exception as e:
                    print(f"  Error fetching object {obj_id}: {e}")
            return count
    except Exception as e:
        print(f"Search error: {e}")
        return 0

outdir = "/Users/admin/goryeo-model/reference_images"
os.makedirs(outdir, exist_ok=True)

# Search for various Goryeo-related terms
for query in ["Goryeo", "Korean Buddhist painting", "Korean celadon", "Avalokitesvara"]:
    print(f"\n{'='*50}")
    count = search_and_download(query.replace(' ', '+'), outdir, max_images=5)
    if count > 0:
        print(f"Downloaded {count} images for '{query}'")