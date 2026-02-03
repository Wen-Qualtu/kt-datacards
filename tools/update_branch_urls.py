"""
Update GitHub raw URLs to use a specific branch (for testing).

This script updates GitHub raw URLs in project files to use a specific branch
instead of a source branch (default: 'main'), allowing us to test changes before
merging.
"""

import argparse
from pathlib import Path
import re
from typing import Iterable


def _iter_project_files(root: Path) -> Iterable[Path]:
    skip_dirs = {
        ".git",
        ".venv",
        "node_modules",
    }
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_dirs for part in path.parts):
            continue
        yield path


def update_github_urls(*, target_branch: str, source_branch: str = "main"):
    """Update all GitHub URLs to use the target branch across the project."""

    base = r"https://(?:raw\.githubusercontent\.com|github\.com)/Wen-Qualtu/kt-datacards/"
    pattern = rf"({base})(blob/)?({re.escape(source_branch)}|main)/"

    root = Path.cwd()
    updated_count = 0
    files_touched = 0

    for file_path in _iter_project_files(root):
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            # Skip non-text or unreadable files.
            continue

        new_content, count = re.subn(
            pattern,
            rf"\1\2{target_branch}/",
            content,
        )
        if count == 0:
            continue

        file_path.write_text(new_content, encoding="utf-8")
        print(f"✓ {file_path}: updated {count} URL(s)")
        updated_count += count
        files_touched += 1

    print(f"\n✓ Total: {updated_count} URLs updated across {files_touched} file(s) to use branch '{target_branch}'")


def main():
    parser = argparse.ArgumentParser(
        description='Update GitHub URLs to use a specific branch'
    )
    parser.add_argument(
        'target_branch',
        type=str,
        help='Branch name to use in URLs (e.g., restructure-tts-objects)'
    )
    parser.add_argument(
        '--source-branch',
        default='main',
        help='Current branch in URLs to replace (default: main)'
    )

    args = parser.parse_args()
    update_github_urls(target_branch=args.target_branch, source_branch=args.source_branch)


if __name__ == '__main__':
    main()
