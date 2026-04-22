"""
Save crawled content to train_data/text_corpus/{source}/ with YAML frontmatter.
Mirrors the YAML frontmatter pattern used in cross-post for structured content.
"""
import json
from pathlib import Path
from typing import Optional

import yaml


def build_frontmatter(
    source_url: str,
    text_type: str,
    language: str = 'ko',
    rights_status: str = 'unknown',
    *,
    title: Optional[str] = None,
    date_crawled: Optional[str] = None,
    tags: Optional[list[str]] = None,
    kogol_status: Optional[int] = None,
    **extra,
) -> dict:
    """Build a YAML frontmatter dict for a crawled item."""
    fm = {
        'source_url': source_url,
        'text_type': text_type,
        'language': language,
        'rights_status': rights_status,
    }
    if title:
        fm['title'] = title
    if date_crawled:
        fm['date_crawled'] = date_crawled
    else:
        from datetime import datetime
        fm['date_crawled'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
    if tags:
        fm['tags'] = tags
    if kogol_status is not None:
        fm['kogol_status'] = kogol_status
    fm.update(extra)
    return fm


def save_text_corpus_item(
    output_dir: Path,
    filename: str,
    content: str,
    frontmatter: dict,
    extension: str = 'txt',
) -> Path:
    """
    Save a text corpus item with YAML frontmatter.
    Format:
        ---
        [yaml frontmatter]
        ---
        [content]
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{filename}.{extension}"

    frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('---\n')
        f.write(frontmatter_yaml)
        f.write('---\n')
        f.write(content)

    return filepath


def save_json_corpus_item(
    output_dir: Path,
    filename: str,
    data: dict,
    frontmatter: dict,
) -> Path:
    """Save a JSON corpus item with YAML frontmatter as comment block."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / f"{filename}.json"

    frontmatter_yaml = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('# ---\n')
        f.write('# ' + '\n# '.join(frontmatter_yaml.strip().split('\n')))
        f.write('\n# ---\n')
        json_data = json.dumps(data, ensure_ascii=False, indent=2)
        f.write(json_data)

    return filepath


def load_corpus_item(filepath: Path) -> tuple[dict, str]:
    """Load a corpus item, returning (frontmatter_dict, content)."""
    content = filepath.read_text(encoding='utf-8')
    parts = content.split('---', 2)
    if len(parts) < 3:
        return {}, content
    frontmatter = yaml.safe_load(parts[1].strip())
    body = parts[2].strip()
    return frontmatter or {}, body