"""
Step 4a: Extract and Organize Cards

**SIMPLE EXECUTOR - NO CLASSIFICATION LOGIC**

Reads card_index.json and organizes cards into output folders.
All intelligence (type, name, relationships) comes from the index.

Input:  metadata/{team}/card_index.json (from step 3)
        layers/warcom/extracted/{team}/cards/*.png (source files)
Output: output/{team}/cards/{type}/*.png

Algorithm:
1. Read card_index.json
2. For each card in index:
   - Get type from card_index (no detection)
   - Get name from card_index (no extraction)
   - Copy to output/{team}/cards/{type}/{name}.png
   - Apply backside if needed
3. Done - NO decisions made here

"""

import argparse
import json
import logging
import shutil
from pathlib import Path
from typing import Dict, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)


def extract_cards_for_team(team_name: str, base_dir: Path = None) -> Dict:
    """
    Organize cards for a team using the index.
    
    Args:
        team_name: Team name
        base_dir: Base directory (default: current directory)
    
    Returns:
        Stats dict with counts
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    # Read card index
    index_path = base_dir / 'metadata' / team_name / 'card_index.json'
    if not index_path.exists():
        logger.error(f"Card index not found: {index_path}")
        logger.error("Run step 3 (index_cards) first")
        return None
    
    with open(index_path, 'r', encoding='utf-8') as f:
        index = json.load(f)
    
    # TODO: Implement card organization
    # For each card in index:
    #   - Get source PNG from card['source_png']
    #   - Get card type from card['type']
    #   - Get card name from card['name'] (or operative['name'])
    #   - Copy to output/{team}/cards/{type}/{formatted_name}.png
    #   - If card has backside, apply it
    
    logger.warning(f"TODO: Implement card extraction for {team_name}")
    logger.info(f"  Card index has {len(index.get('operatives', []))} operatives")
    
    return {'processed': 0, 'skipped': 1}


def main():
    parser = argparse.ArgumentParser(
        description='Extract and organize cards (Step 4a - Simple Executor)'
    )
    parser.add_argument('--team', type=str, help='Team name to process')
    parser.add_argument('--base-dir', type=Path, help='Base directory')
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("Step 4a: Extract and Organize Cards")
    logger.info("=" * 80)
    logger.info("NOTE: This step reads card_index.json and copies files")
    logger.info("      NO classification logic here - that's in step 3")
    logger.info("")
    
    if args.team:
        result = extract_cards_for_team(
            args.team,
            base_dir=args.base_dir
        )
    else:
        logger.info("Processing all teams...")
        # TODO: Process all teams with card_index.json
        logger.warning("TODO: Implement batch processing")
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("CARD EXTRACTION COMPLETE")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
