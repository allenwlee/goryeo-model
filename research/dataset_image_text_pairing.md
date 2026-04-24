# Goryeo Costume Dataset — Image-Text Pairing

## Problem

The text corpus crawlers (heritage_portal, nrich, museum_open_access, etc.) save image files and text files using a shared ID prefix per artifact/item. Example:

```
heritage_sites/heritage_1113701110000.txt          ← artifact description
heritage_sites/heritage_1113701110000_img0.jpg    ← photo 1
heritage_sites/heritage_1113701110000_img1.jpg    ← photo 2

nrich_reports/nrich_713438.pdf                    ← excavation report (no images)
nrich_reports/nrich_713438_meta.json              ← metadata
```

The filename convention groups paired files, but a model cannot infer relationships from filenames alone. The training dataloader must resolve the grouping programmatically.

---

## Pairing Convention

Each source crawler uses the following naming convention:

| Source | ID field | Text file | Images |
|--------|----------|-----------|--------|
| heritage_portal | `ccbaCpno` | `heritage_{ccbaCpno}.txt` | `heritage_{ccbaCpno}_img{N}.jpg` |
| nrich | `file_idx` | `nrich_{file_idx}.pdf` | `nrich_{file_idx}_img{N}.jpg` |
| museum_open_access/met | `object_id` | `met_{object_id}.json` | — (API returns structured data) |
| museum_open_access/cleveland | `id` | `cleveland_{id}.json` | — |
| museum_open_access/smithsonian | `object_id` | `smithsonian_{object_id}.json` | — |
| jkaa | article hash | `jkaa_{hash}.txt/.pdf` | — |
| kci_costume | article ID | `kci_{id}.txt` | — |

The text file always contains a frontmatter block with a `ccba_cpno` / `file_idx` / `object_id` field. Images omit the field but share the same base ID.

---

## Pre-training Data Pipeline

### Step 1: Generate metadata index

A script walks the output directories and produces a `metadata.jsonl` index:

```python
import json, os
from pathlib import Path

def build_index(base_dir: Path) -> list[dict]:
    index = []
    for txt_path in base_dir.glob("**/*.txt"):
        # Strip extension to get base ID
        base = txt_path.stem  # e.g. "heritage_1113701110000"

        # Find images with same base prefix
        img_dir = txt_path.parent
        id_prefix = base  # e.g. "heritage_1113701110000"
        images = sorted([
            f.name for f in img_dir.iterdir()
            if f.name.startswith(id_prefix + "_img") and f.suffix in (".jpg", ".jpeg", ".png", ".JPG")
        ])

        # Load frontmatter for metadata
        frontmatter = {}
        text_content = ""
        # parse frontmatter from txt file...

        entry = {
            "id": base,
            "text_file": txt_path.name,
            "images": images,
            "source": img_dir.name,
            **frontmatter
        }
        index.append(entry)
    return index
```

### Step 2: Convert to model training format

**Vision-Language (LLaVA-style) — image + caption → generation:**
```json
{
  "id": "heritage_1113701110000",
  "image": ["heritage_1113701110000_img0.jpg", "heritage_1113701110000_img1.jpg"],
  "conversations": [
    {"from": "human", "value": "<image>\n다음은 국가유산 [국보 安珦 肖像]의 설명이다. 이미지를 참고하여 설명해줘."},
    {"from": "gpt", "value": "국가유산 설명...고려 중기 문신인 회헌 안향..."}
  ]
}
```

**Text-only fine-tuning (LLM corpus) — document-level:**
```json
{"id": "heritage_1113701110000", "text": " 국가유산 설명...고려 중기..."}
```

### Step 3: Dataloader resolves pairs at runtime

```python
def get_training_sample(entry: dict, image_dir: Path):
    images = []
    for img_name in entry["images"]:
        img_path = image_dir / img_name
        img_tensor = load_and_preprocess(img_path)  # CLIP/ViT encoder
        images.append(img_tensor)

    if entry["images"]:
        # Vision-language: image(s) → text generation
        return {"images": images, "text": entry["conversations"]}
    else:
        # Text-only: next-token prediction on document
        return {"text": entry["text"]}
```

The model never sees filenames directly — it only sees image tensors + tokenized text. The filename convention is solely for the pre-processing indexer to discover and group paired files.

---

## Directory Layout

```
train_data/text_corpus/
  heritage_sites/
    heritage_{id}.txt         ← frontmatter + description (Korean + EN/ZH/JP)
    heritage_{id}_img0.jpg
    heritage_{id}_img1.jpg
    ...
  nrich_reports/
    nrich_{id}.pdf            ← binary PDF (no text extraction needed)
    nrich_{id}_meta.json
  museum_open_access/
    met/{met_id}.json        ← structured JSON with description + image URLs
    smithsonian/{id}.json
    cleveland/{id}.json
  jkaa_articles/
    jkaa_{hash}.txt
    jkaa_{hash}.pdf
  kci_costume/
    kci_{id}.txt
```

The metadata index at `metadata.jsonl` is the single source of truth for pairing, generated once after all crawls complete.
