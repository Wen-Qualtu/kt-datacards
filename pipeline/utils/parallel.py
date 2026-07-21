"""Run a per-item worker across teams/files, serially or on a thread pool.

Teams (and the per-PDF work inside the front-end) are independent, so the
per-item loop of a step can fan out across workers. A **thread** pool is used
rather than processes: the heavy lifting lives in PyMuPDF / OpenCV / Pillow,
which release the GIL during native work, so threads give real speedup without
process-pickling. ``jobs <= 1`` runs inline (no pool) — preserving order and
keeping single-worker runs easy to debug.

Each step keeps its own per-item ``try/except`` and returns a small result/stat,
so one failing item never aborts the batch and the step aggregates results
serially after the map (no shared-counter mutation across threads).
"""
from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, List, TypeVar

T = TypeVar("T")
R = TypeVar("R")


def resolve_jobs(jobs: int) -> int:
    """Clamp a requested worker count to a sane range (>=1, <= cpu count)."""
    if jobs is None or jobs <= 1:
        return 1
    return min(jobs, (os.cpu_count() or 1))


def map_items(worker: Callable[[T], R], items: Iterable[T], jobs: int = 1) -> List[R]:
    """Apply ``worker`` to each item, returning results in input order.

    ``jobs <= 1`` (or a single item) runs inline; otherwise a thread pool of
    ``jobs`` workers is used. Workers must not rely on shared mutable state —
    have them return a result and aggregate afterwards.
    """
    items = list(items)
    jobs = resolve_jobs(jobs)
    if jobs <= 1 or len(items) <= 1:
        return [worker(it) for it in items]
    with ThreadPoolExecutor(max_workers=jobs) as pool:
        return list(pool.map(worker, items))
