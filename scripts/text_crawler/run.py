#!/usr/bin/env python3
"""
Text Corpus Crawler Orchestrator.
Loads the task queue, runs tasks in priority order, logs progress, and resumes on interruption.
"""
import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from framework.fetcher import Fetcher
from framework.robots import RobotsChecker

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger('crawler')


# Task queue: (task_id, source_name, module_path, priority)
TASKS = [
    (1, 'museum_open_access', 'sources.museum_open_access', 1),
    (2, 'jkaa',              'sources.jkaa',               2),
    (3, 'nmk',               'sources.nmk',                3),
    (4, 'nrich',             'sources.nrich',               4),
    (5, 'heritage_portal',   'sources.heritage_portal',     5),
    (6, 'aks_vocabulary',    'sources.aks_vocabulary',      6),
    (7, 'goryeodogyeong',    'sources.goryeodogyeong_text', 7),
    (8, 'kci_costume',       'sources.kci_costume',         8),
    (9, 'gugak_archive',     'sources.gugak_archive',       9),
    (10,'nikh_db',           'sources.nikh_db',            10),
]


class CrawlerState:
    """Persistent state for resumable crawling."""
    def __init__(self, state_file: Path):
        self.state_file = state_file
        self.completed: set[str] = set()
        self.skipped: set[str] = set()
        self.failed: dict[str, str] = {}
        self.load()

    def load(self):
        if self.state_file.exists():
            data = json.loads(self.state_file.read_text())
            self.completed = set(data.get('completed', []))
            self.skipped = set(data.get('skipped', []))
            self.failed = data.get('failed', {})

    def save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps({
            'completed': list(self.completed),
            'skipped': list(self.skipped),
            'failed': self.failed,
            'saved_at': datetime.utcnow().isoformat(),
        }, indent=2))

    def mark_completed(self, task_id: str):
        self.completed.add(task_id)
        self.save()

    def mark_skipped(self, task_id: str):
        self.skipped.add(task_id)
        self.save()

    def mark_failed(self, task_id: str, reason: str):
        self.failed[task_id] = reason
        self.save()


async def run_task(task_id: str, source_name: str, module_path: str, dry_run: bool = False):
    """Run a single source crawler task."""
    log.info(f"Running task {task_id}: {source_name}")
    try:
        # Dynamic import of the source module
        from importlib import import_module
        module = import_module(module_path)
        if dry_run:
            log.info(f"[DRY RUN] Would run {source_name}")
            return True
        await module.crawl()
        log.info(f"Task {task_id} ({source_name}) completed successfully")
        return True
    except ImportError as e:
        log.warning(f"Task {task_id} ({source_name}): module not found ({e}) — skipping")
        return None
    except Exception as e:
        log.error(f"Task {task_id} ({source_name}) failed: {e}")
        return False


async def run_all(dry_run: bool = False, resume: bool = True):
    """Run all tasks in priority order."""
    from framework.errors import CrawlError

    state_file = Path(__file__).parent.parent / 'crawler_state.json'
    state = CrawlerState(state_file) if resume else CrawlerState.__new__(CrawlerState)

    fetcher = Fetcher()
    robots_checker = RobotsChecker(fetcher)

    results = []
    for task_id, source_name, module_path, priority in TASKS:
        task_key = f"task_{task_id}_{source_name}"

        if resume and task_key in state.completed:
            log.info(f"Skipping completed task {task_id} ({source_name})")
            results.append((task_id, source_name, 'completed'))
            continue

        result = await run_task(task_id, source_name, module_path, dry_run)
        if result is True:
            state.mark_completed(task_key)
            results.append((task_id, source_name, 'success'))
        elif result is None:
            state.mark_skipped(task_key)
            results.append((task_id, source_name, 'skipped'))
        else:
            state.mark_failed(task_key, 'unknown_error')
            results.append((task_id, source_name, 'failed'))

    return results


def main():
    parser = argparse.ArgumentParser(description='Text Corpus Crawler')
    parser.add_argument('--dry-run', action='store_true', help='List tasks without running')
    parser.add_argument('--no-resume', action='store_true', help='Ignore saved state, run all tasks')
    args = parser.parse_args()

    log.info(f"Starting crawler at {datetime.utcnow().isoformat()}")
    results = asyncio.run(run_all(dry_run=args.dry_run, resume=not args.no_resume))

    log.info("=== Crawler Summary ===")
    for task_id, source_name, status in results:
        log.info(f"  Task {task_id} ({source_name}): {status}")

    log.info(f"Finished at {datetime.utcnow().isoformat()}")


if __name__ == '__main__':
    main()
