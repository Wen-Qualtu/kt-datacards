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
import logging
from typing import Callable, Optional

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

    for key, module, scope in _select_steps(args):
        module_name = _resolve_module(key, module, scope, args.source)
        run = _runner(module_name)
        print(f"==> {key} ({module_name})")
        kwargs = {"teams": teams, "force": args.force}
        if scope in ("track", "source"):
            kwargs["source"] = args.source
        run(**kwargs)


if __name__ == "__main__":
    main()
