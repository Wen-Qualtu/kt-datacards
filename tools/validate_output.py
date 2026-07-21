#!/usr/bin/env python3
"""Validate ``new_implementation/output`` against the repo-root ``output/`` folder.

The goal is a new-pipeline output tree that is *identical in naming and content*
to the production ``output/`` tree. Files are compared by relative path plus a
SHA-256 content hash.

Naming decisions that intentionally diverged between the two pipelines are
reconciled with ``PATH_MAPPINGS`` (regex rewrites applied to the NEW relative
path to produce the ROOT path we expect it to match). Files whose content is
expected to differ by design (e.g. TTS JSON with embedded URLs / timestamps)
can be excluded from the hash check with ``IGNORE_PATTERNS``.

Both tables start EMPTY on purpose: the first pass hard-flags every difference
so we can evaluate each one and decide whether it is a mapping, an ignore, or a
real bug. Add entries as decisions are made.

Usage (from new_implementation/):
    python -m tools.validate_output                 # all teams
    python -m tools.validate_output --team kasrkin  # one team
    python -m tools.validate_output --json report.json
    python -m tools.validate_output --quiet         # summary only
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

HERE = Path(__file__).resolve()
NEW_IMPL = HERE.parents[1]
REPO_ROOT = HERE.parents[2]
NEW_OUTPUT = NEW_IMPL / "output"
ROOT_OUTPUT = REPO_ROOT / "output"

# --------------------------------------------------------------------------- #
# Reconciliation tables — grow these as naming decisions are confirmed.
# --------------------------------------------------------------------------- #

# Each entry is (compiled_regex, replacement) applied IN ORDER to a NEW relative
# path (posix-style, forward slashes) to produce the ROOT relative path it should
# line up with. Example (do NOT enable until confirmed):
#   (re.compile(r"/cards/faction-rules/"), "/cards/faction_rules/"),
PATH_MAPPINGS: list[tuple[re.Pattern[str], str]] = [
]

# Glob-style patterns (fnmatch, against the ROOT-normalized relative path) whose
# files exist in both trees but whose CONTENT is allowed to differ. They are
# reported separately as "content-exempt" instead of failing the run.
IGNORE_PATTERNS: list[str] = [
]

# JSON normalization (on by default; disable with --raw). Two sources of
# unavoidable, meaningless noise are neutralized before hashing JSON so that the
# residual diffs are REAL content differences:
#   1. deploy path segment  .../new_implementation/output/...  ->  .../output/...
#      (the new pipeline serves from a sandbox sub-path; converges once deployed)
#   2. ?v=<epoch> cache-buster on asset URLs (a "last generated" timestamp)
# Key ordering / whitespace is also canonicalized (json round-trip, sorted keys).
_URL_PREFIX_RE = re.compile(r"/new_implementation/output/")
_CACHE_BUST_RE = re.compile(r"\?v=\d+")

# JSON keys whose VALUES are generation timestamps (pure noise): null them out
# recursively so only real content differences remain.
_NOISE_KEYS = {"generated_at"}


def normalize_json_text(text: str) -> str:
    text = _URL_PREFIX_RE.sub("/output/", text)
    text = _CACHE_BUST_RE.sub("", text)
    return text


def _scrub_noise_keys(obj):
    """Recursively null the values of timestamp/noise keys in a parsed JSON object."""
    if isinstance(obj, dict):
        return {k: (None if k in _NOISE_KEYS else _scrub_noise_keys(v)) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_scrub_noise_keys(v) for v in obj]
    return obj


# --------------------------------------------------------------------------- #

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def content_hash(rel: str, path: Path, normalize: bool) -> str:
    """Hash a file's content. For ``.json`` (when ``normalize``) neutralize deploy
    path + cache-bust noise and canonicalize key order so only real diffs remain."""
    if normalize and rel.lower().endswith(".json"):
        try:
            obj = json.loads(normalize_json_text(path.read_text(encoding="utf-8")))
            canon = json.dumps(_scrub_noise_keys(obj), sort_keys=True, ensure_ascii=False)
            return hashlib.sha256(canon.encode("utf-8")).hexdigest()
        except (ValueError, OSError):
            pass  # fall back to raw bytes on unparseable/unreadable JSON
    return sha256(path)


def rel_files(root: Path) -> dict[str, Path]:
    """Map posix relative path -> absolute Path for every file under ``root``."""
    out: dict[str, Path] = {}
    if not root.exists():
        return out
    for p in root.rglob("*"):
        if p.is_file():
            out[p.relative_to(root).as_posix()] = p
    return out


def apply_mappings(rel: str) -> str:
    for pattern, repl in PATH_MAPPINGS:
        rel = pattern.sub(repl, rel)
    return rel


def is_ignored(rel: str) -> bool:
    from fnmatch import fnmatch
    return any(fnmatch(rel, pat) for pat in IGNORE_PATTERNS)


@dataclass
class Report:
    only_in_new: list[str] = field(default_factory=list)      # mapped path missing in root
    only_in_root: list[str] = field(default_factory=list)     # root path with no new source
    hash_mismatch: list[str] = field(default_factory=list)    # present both, content differs
    content_exempt: list[str] = field(default_factory=list)   # differ but IGNORE_PATTERNS
    matched: int = 0

    @property
    def has_diffs(self) -> bool:
        return bool(self.only_in_new or self.only_in_root or self.hash_mismatch)

    def to_dict(self) -> dict:
        return {
            "matched": self.matched,
            "only_in_new": self.only_in_new,
            "only_in_root": self.only_in_root,
            "hash_mismatch": self.hash_mismatch,
            "content_exempt": self.content_exempt,
        }


def compare(teams: Iterable[str] | None, normalize: bool = True) -> Report:
    rep = Report()

    new_files = rel_files(NEW_OUTPUT)
    root_files = rel_files(ROOT_OUTPUT)

    if teams:
        wanted = set(teams)
        new_files = {k: v for k, v in new_files.items() if k.split("/", 1)[0] in wanted}
        root_files = {k: v for k, v in root_files.items() if k.split("/", 1)[0] in wanted}

    # Map every NEW path into ROOT space; detect collisions defensively.
    mapped: dict[str, Path] = {}
    for rel, path in new_files.items():
        target = apply_mappings(rel)
        mapped[target] = path

    matched_targets: set[str] = set()

    for target in sorted(mapped):
        new_path = mapped[target]
        root_path = root_files.get(target)
        if root_path is None:
            rep.only_in_new.append(target)
            continue
        matched_targets.add(target)
        if content_hash(target, new_path, normalize) == content_hash(target, root_path, normalize):
            rep.matched += 1
        elif is_ignored(target):
            rep.content_exempt.append(target)
        else:
            rep.hash_mismatch.append(target)

    for rel in sorted(root_files):
        if rel not in matched_targets and rel not in mapped:
            rep.only_in_root.append(rel)

    return rep


def print_report(rep: Report, quiet: bool) -> None:
    def section(title: str, items: list[str]) -> None:
        print(f"\n{title}: {len(items)}")
        if not quiet:
            for it in items:
                print(f"  {it}")

    print("=" * 70)
    print("OUTPUT VALIDATION  (new_implementation/output  vs  output/)")
    print(f"  new : {NEW_OUTPUT}")
    print(f"  root: {ROOT_OUTPUT}")
    print("=" * 70)
    print(f"matched (identical hash): {rep.matched}")

    section("ONLY IN NEW  (no matching root file)", rep.only_in_new)
    section("ONLY IN ROOT (new pipeline did not produce)", rep.only_in_root)
    section("HASH MISMATCH (present both, content differs)", rep.hash_mismatch)
    if rep.content_exempt:
        section("CONTENT-EXEMPT (differ but ignored by rule)", rep.content_exempt)

    print("\n" + "-" * 70)
    verdict = "DIFFERENCES FOUND" if rep.has_diffs else "IDENTICAL"
    print(f"RESULT: {verdict}")
    print("-" * 70)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--team", action="append", dest="teams",
                    help="limit to team slug (repeatable)")
    ap.add_argument("--json", metavar="FILE", help="write full report as JSON")
    ap.add_argument("--quiet", action="store_true", help="summary counts only")
    ap.add_argument("--raw", action="store_true",
                    help="disable JSON URL/timestamp normalization (compare raw bytes)")
    args = ap.parse_args(argv)

    rep = compare(args.teams, normalize=not args.raw)
    print_report(rep, args.quiet)

    if args.json:
        Path(args.json).write_text(json.dumps(rep.to_dict(), indent=2), encoding="utf-8")
        print(f"\nJSON report -> {args.json}")

    return 1 if rep.has_diffs else 0


if __name__ == "__main__":
    raise SystemExit(main())
