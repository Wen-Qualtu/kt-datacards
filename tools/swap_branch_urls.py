#!/usr/bin/env python3
"""
Swap the branch name in all TTS object URLs for acceptance testing.

Replaces the branch segment in raw.githubusercontent.com URLs across all
output/{team}/tts_objects/ and tts_objects/{team}/ JSON files.

Running the pipeline again will overwrite these files back to the correct
branch (main), so this is safe to run freely for testing.

Usage:
    python tools/swap_branch_urls.py feature/add-dice-v2    # point to branch
    python tools/swap_branch_urls.py main                   # restore to main
    python tools/swap_branch_urls.py main --dry-run         # preview changes
"""

import argparse
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Matches the branch segment in any raw.githubusercontent.com URL, anchored to a
# known top-level path so branch names containing slashes (e.g. feature/foo) work:
#   https://raw.githubusercontent.com/{owner}/{repo}/{branch}/output/...
# Non-greedy match on the branch segment so the FIRST occurrence of a known
# top-level dir wins — this also self-heals double-path URLs like
# .../feature/add-dice-v2/add-dice-v2/output/... back to .../feature/add-dice-v2/output/...
BRANCH_RE = re.compile(
    r'(https://raw\.githubusercontent\.com/[^/]+/[^/]+)/(.+?)/(output|output_v2|config|tts_objects)/'
)


def swap_urls(target_branch: str, dry_run: bool = False) -> int:
    files = (
        list((PROJECT_ROOT / "output").glob("*/tts_objects/**/*.json"))
        + list((PROJECT_ROOT / "tts_objects").glob("**/*.json"))
    )

    modified = 0
    for path in sorted(files):
        original = path.read_text(encoding="utf-8")
        updated = BRANCH_RE.sub(rf"\1/{target_branch}/\3/", original)
        if updated == original:
            continue
        if not dry_run:
            path.write_text(updated, encoding="utf-8")
        rel = path.relative_to(PROJECT_ROOT)
        print(f"  {'(dry) ' if dry_run else ''}Updated: {rel}")
        modified += 1

    action = "Would update" if dry_run else "Updated"
    print(f"\n{action} {modified} file(s) -> branch: {target_branch}")
    return modified


def main():
    parser = argparse.ArgumentParser(
        description="Swap branch name in TTS object URLs"
    )
    parser.add_argument("branch", help="Target branch (e.g. main, feature/add-dice-v2)")
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would change without writing files"
    )
    args = parser.parse_args()
    swap_urls(args.branch, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
