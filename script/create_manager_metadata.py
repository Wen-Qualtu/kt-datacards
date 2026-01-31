"""
Add Manager bag to GitHub so it can self-update.
Creates a metadata file with the Manager bag URL and timestamp.
"""

import json
from pathlib import Path
from datetime import datetime


def create_manager_metadata():
    """Create metadata for the Manager bag self-update."""
    manager_path = Path("dev/examples/KT Display Manager.json")
    output_dir = Path("output_v2")
    output_file = output_dir / "tts-manager.json"
    
    if not manager_path.exists():
        print(f"❌ Manager bag not found at: {manager_path}")
        return False
    
    # Get timestamp from file modification time
    timestamp = datetime.fromtimestamp(manager_path.stat().st_mtime).strftime("%Y-%m-%dT%H:%M:%S")
    
    # Create metadata
    metadata = {
        "url": "https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/fix/correct-celestians/dev/examples/KT Display Manager.json",
        "last_modified": timestamp
    }
    
    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save metadata
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✓ Created {output_file}")
    print(f"  URL: {metadata['url']}")
    print(f"  Last modified: {metadata['last_modified']}")
    
    return True


if __name__ == '__main__':
    print("Creating Manager bag metadata...\n")
    create_manager_metadata()
