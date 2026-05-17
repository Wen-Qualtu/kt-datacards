#!/usr/bin/env python3
"""
Copy team box JSON files to a TTS Saves folder for in-game testing.

Copies output/{team}/tts_objects/{Team Name} Box.json for every team
that has a box JSON. Existing files at the destination are overwritten.

Usage:
    python tools/copy_tts_objects.py "C:/path/to/TTS/Saves/folder"
    python tools/copy_tts_objects.py "C:/path/to/folder" --dry-run
"""

import argparse
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def copy_boxes(dest: Path, dry_run: bool = False) -> int:
    dest.mkdir(parents=True, exist_ok=True)
    copied = 0

    for box_json in sorted((PROJECT_ROOT / "output").glob("*/tts_objects/*.json")):
        if not box_json.name.endswith(" Box.json"):
            continue
        target = dest / box_json.name
        if not dry_run:
            shutil.copy2(box_json, target)
        print(f"  {'(dry) ' if dry_run else ''}{'would copy' if dry_run else 'copied'}: {box_json.name}")
        copied += 1

    action = "Would copy" if dry_run else "Copied"
    print(f"\n{action} {copied} box(es) -> {dest}")
    return copied


def main():
    parser = argparse.ArgumentParser(description="Copy TTS box JSONs to a Saves folder")
    parser.add_argument("dest", help="Destination folder path")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be copied without writing")
    args = parser.parse_args()

    dest = Path(args.dest)
    copy_boxes(dest, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
