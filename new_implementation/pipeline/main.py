"""Integrated datacard pipeline — orchestrator.

One pipeline with a ``--source kt-app|warcom`` track selector. The source only
changes the extraction front-end (front_end → artwork → structure → classified);
from ``content_analysis`` onward the steps are source-agnostic and operate on the
shared layers.

Usage (run from ``new_implementation/``)::

    python -m pipeline.main --list
    python -m pipeline.main --source kt-app --teams kasrkin
    python -m pipeline.main --source warcom --step integrate_classified --teams kasrkin
    python -m pipeline.main --source kt-app --from build_structure --to content_analysis --teams kasrkin

Each step module exposes ``run(teams, source=None, force=False)``.
"""
from __future__ import annotations

import argparse
import importlib
import inspect
import logging
import sys
from typing import Callable, Optional

from .utils import paths
from .utils.parallel import map_items

# Ported steps print status with Unicode glyphs (checkmarks etc.); force UTF-8 on
# stdout/stderr so they don't crash on a Windows cp1252 console.
for _stream in (sys.stdout, sys.stderr):
    _reconfigure = getattr(_stream, "reconfigure", None)
    if _reconfigure is not None:
        try:
            _reconfigure(encoding="utf-8")
        except Exception:
            pass

# Ordered pipeline. (key, module, scope)
#   scope:
#     "track"  -> front-end; resolved to a track module by --source
#     "source" -> shared code but needs the raw/track input (gets --source)
#     "shared" -> operates on shared layers only (source-agnostic)
STEP_ORDER: list[tuple[str, Optional[str], str]] = [
    ("front_end",            None,                    "track"),
    ("extract_artwork",      "extract_artwork",       "source"),
    ("build_structure",      "build_structure",       "source"),
    ("integrate_classified", "integrate_classified",  "source"),
    ("content_analysis",     "content_analysis",      "shared"),
    ("extract_backsides",    "extract_backsides",     "shared"),
    ("extract_tokens",       "extract_tokens",        "shared"),
    ("generate_dice",        "generate_dice",         "shared"),
    ("generate_box_texture", "generate_box_texture",  "shared"),
    ("generate_card_images", "generate_card_images",  "shared"),
    ("extract_stats",        "extract_stats",         "shared"),
    ("generate_tts",         "generate_tts",          "shared"),
]

# Track-specific front-end modules, chosen by --source.
TRACK_FRONT_END = {
    "kt-app": "track_kt_app",
    "warcom": "track_warcom",
}

STEP_KEYS = [k for k, _, _ in STEP_ORDER]

# Steps that must run over ALL teams in one call — either they consume the shared
# inbox/scrape (the team set isn't known per-team) or they emit a global artifact.
# Everything else is per-team and runs team-major (one whole-chain worker per team,
# many teams in parallel) when --jobs > 1.
#   front_end       -> shared inbox/scrape; parallelizes internally via --jobs
#   extract_artwork -> global "best source per team" scan over the raw inbox
#   generate_tts    -> writes the global team-urls.json summary + object-urls
SERIAL_STEPS = {"front_end", "extract_artwork", "generate_tts"}


def _discover_teams(source: Optional[str]) -> list[str]:
    """Teams that actually have data — the pool for team-major execution.

    Discovered lazily (after the front-end has produced per-team layers): from the
    track's extracted dir when a source is set, else from the shared integration dir.
    """
    base = paths.extracted_dir(source) if source else paths.INTEGRATION
    if not base.exists():
        return []
    return sorted(d.name for d in base.iterdir() if d.is_dir())


def _resolve_module(key: str, module: Optional[str], scope: str, source: Optional[str]) -> str:
    if scope == "track":
        if source not in TRACK_FRONT_END:
            raise SystemExit(f"--source is required for the front-end step (one of {list(TRACK_FRONT_END)})")
        return TRACK_FRONT_END[source]
    return module  # type: ignore[return-value]


def _runner(module_name: str) -> Callable:
    mod = importlib.import_module(f"pipeline.steps.{module_name}")
    if not hasattr(mod, "run"):
        raise SystemExit(f"step '{module_name}' has no run() function")
    return mod.run


def _run_step(key, module, scope, teams, source, force, jobs) -> None:
    """Invoke one step's run(), passing source/jobs only when it accepts them."""
    module_name = _resolve_module(key, module, scope, source)
    run = _runner(module_name)
    kwargs = {"teams": teams, "force": force}
    if scope in ("track", "source"):
        kwargs["source"] = source
    if "jobs" in inspect.signature(run).parameters:
        kwargs["jobs"] = jobs
    run(**kwargs)


def _select_steps(args) -> list[tuple[str, Optional[str], str]]:
    if args.step:
        return [s for s in STEP_ORDER if s[0] == args.step]
    start = STEP_KEYS.index(args.from_) if args.from_ else 0
    end = STEP_KEYS.index(args.to) if args.to else len(STEP_KEYS) - 1
    return STEP_ORDER[start:end + 1]


def main() -> None:
    p = argparse.ArgumentParser(description="Integrated datacard pipeline")
    p.add_argument("--source", choices=list(TRACK_FRONT_END), help="track for the extraction front-end")
    p.add_argument("--teams", help="comma-separated team slugs (default: all)")
    p.add_argument("--step", choices=STEP_KEYS, help="run a single step")
    p.add_argument("--from", dest="from_", choices=STEP_KEYS, help="start step (inclusive)")
    p.add_argument("--to", choices=STEP_KEYS, help="end step (inclusive)")
    p.add_argument("--force", action="store_true", help="ignore caches / re-run")
    p.add_argument("--jobs", type=int, default=10,
                   help="parallel team workers (default: 10; 1 = fully serial)")
    p.add_argument("--list", action="store_true", help="list steps and exit")
    args = p.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.list:
        for i, (key, module, scope) in enumerate(STEP_ORDER, 1):
            mod = "/".join(TRACK_FRONT_END.values()) if scope == "track" else module
            print(f"{i:2d}. {key:22s} [{scope:6s}] -> {mod}")
        return

    teams = [t.strip() for t in args.teams.split(",")] if args.teams else None
    selected = _select_steps(args)
    jobs = max(1, args.jobs)

    if jobs <= 1:
        # Fully serial: each step runs once over all teams.
        for key, module, scope in selected:
            print(f"==> {key} ({_resolve_module(key, module, scope, args.source)})")
            _run_step(key, module, scope, teams, args.source, args.force, jobs=1)
        return

    # Team-major: walk the selected steps; run consecutive per-team steps as a
    # whole-chain worker per team (many teams in parallel), while serial steps
    # (shared input / global finalize) run once over all teams.
    i = 0
    while i < len(selected):
        key, module, scope = selected[i]
        if key in SERIAL_STEPS:
            print(f"==> {key} ({_resolve_module(key, module, scope, args.source)}) [serial, jobs={jobs}]")
            _run_step(key, module, scope, teams, args.source, args.force, jobs=jobs)
            i += 1
            continue

        batch = []
        while i < len(selected) and selected[i][0] not in SERIAL_STEPS:
            batch.append(selected[i])
            i += 1

        pool = teams or _discover_teams(args.source)
        batch_keys = " -> ".join(k for k, _, _ in batch)
        print(f"==> team-major [{batch_keys}] x{len(pool)} teams, {jobs} workers")

        def team_worker(team, _batch=batch):
            for k, m, sc in _batch:
                _run_step(k, m, sc, [team], args.source, args.force, jobs=1)

        map_items(team_worker, pool, jobs=jobs)


if __name__ == "__main__":
    main()
