"""Run all pre-merge / pre-deploy checks; exit non-zero on any FAIL.

Usage:
  python .github/skills/kt-datacards/tools/check_all.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CHECKS = [
    "check_urls_main_branch.py",
    "check_hash_baseline.py",
    "check_timestamp_alignment.py",
    "check_structure_cards.py",
]


def main() -> int:
    tools_dir = Path(__file__).parent
    overall = 0
    for name in CHECKS:
        print(f"\n=== {name} ===")
        r = subprocess.run([sys.executable, str(tools_dir / name)])
        if r.returncode != 0:
            overall = 1
    print()
    if overall == 0:
        print("READY TO MERGE — all checks PASS")
    else:
        print("BLOCKED — at least one check failed")
    return overall


if __name__ == "__main__":
    sys.exit(main())
