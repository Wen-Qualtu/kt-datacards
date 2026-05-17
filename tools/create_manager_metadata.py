#!/usr/bin/env python3
"""
Create output_v2/tts-manager.json with the Manager bag URL and file timestamp.
Run this manually after updating dev/examples/KT Display Manager.json.
"""

import json
from pathlib import Path
from datetime import datetime

MANAGER_URL = "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/main/dev/examples/KT Display Manager.json"


def create_manager_metadata():
    manager_path = Path("dev/examples/KT Display Manager.json")
    output_file = Path("output_v2/tts-manager.json")

    if not manager_path.exists():
        print(f"Manager bag not found: {manager_path}")
        return False

    timestamp = datetime.fromtimestamp(manager_path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")

    metadata = {
        "url": MANAGER_URL,
        "last_modified": timestamp,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)

    print(f"Wrote {output_file}")
    print(f"  url: {metadata['url']}")
    print(f"  last_modified: {metadata['last_modified']}")
    return True


if __name__ == "__main__":
    create_manager_metadata()
