"""
Step 7: Generate TTS Objects

Generates Tabletop Simulator (TTS) JSON save files from classified cards.
Uses the proven script/generators/tts_generator.py approach adapted for kt-app pipeline.

Prerequisites:
    Step 6: TTS assets (mesh/texture) must be generated

Input:
    layers/kt-app/classified/{team}/structure.json - Card organization
    output_v3/{team}/cards/{card_type}/*.png - Card images
    output_v3/{team}/tts/*.obj and *.jpg - 3D assets from step 6
    output_v3/{faction}/{team}/tts/token/{team}-tokens.json - Token bags (if exist)
    config/team-config.yaml - Team metadata
    
Output:
    tts_objects_v3/{team}/{Team Name} Cards.json - TTS card box save file
"""

import argparse
import json
import logging
from pathlib import Path
import sys

# Add generators to path
sys.path.insert(0, str(Path(__file__).parent))
from generators.tts_generator import TTSGenerator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def generate_urls_json_v3():
    """Generate datacards-urls.json format from v3 output structure"""
    output_v3 = PROJECT_ROOT / 'output_v3'
    branch = "refactor-kt-app-pipeline"
    base_url = f"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/{branch}/output_v3"
    
    # Load team config to get faction info
    import yaml
    team_config_path = PROJECT_ROOT / 'config' / 'team-config.yaml'
    team_to_faction = {}
    if team_config_path.exists():
        with open(team_config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
            for team_name, team_data in config.get('teams', {}).items():
                faction = team_data.get('faction', 'unknown')
                team_to_faction[team_name] = faction
    
    all_entries = []
    
    # Scan all team directories (flat structure in v3)
    for team_dir in sorted(output_v3.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team = team_dir.name
        faction = team_to_faction.get(team, 'unknown')
        cards_dir = team_dir / 'cards'
        cardbox_dir = team_dir / 'cardbox'
        
        if not cards_dir.exists():
            continue
        
        # Add cardbox assets (mesh and texture)
        if cardbox_dir.exists():
            for asset_file in cardbox_dir.glob('*'):
                if asset_file.suffix in ['.obj', '.jpg']:
                    asset_url = f"{base_url}/{team}/cardbox/{asset_file.name}"
                    all_entries.append({
                        'faction': faction,
                        'team': team,
                        'type': 'tts',
                        'name': asset_file.stem,
                        'url': asset_url
                    })
        
        # Scan card types
        for card_type_dir in sorted(cards_dir.iterdir()):
            if not card_type_dir.is_dir():
                continue
            
            card_type = card_type_dir.name
            
            # Convert v3 naming (underscores) to v2 naming (dashes)
            # Special mappings for v3 -> v2 compatibility
            type_mappings = {
                'operatives_selection': 'operative-selection',
                'faction_rules': 'faction-rules',
                'firefight_ploys': 'firefight-ploys',
                'strategy_ploys': 'strategy-ploys',
                'token_guide': 'token-guide'  # Include token guide as single card
            }
            card_type_v2 = type_mappings.get(card_type, card_type.replace('_', '-'))
            
            # Regular card type
            for card_file in sorted(card_type_dir.glob('*.png')):
                # Convert filename format from "{team}-{card}-front.png" to "{team}-{card}_front"
                name = card_file.stem
                if name.endswith('-front') or name.endswith('-back'):
                    # Replace final dash with underscore
                    name = name.rsplit('-', 1)
                    name = f"{name[0]}_{name[1]}"
                
                card_url = f"{base_url}/{team}/cards/{card_type}/{card_file.name}"
                all_entries.append({
                    'faction': faction,
                    'team': team,
                    'type': card_type_v2,
                    'name': name,
                    'url': card_url
                })
    
    return all_entries


def main():
    parser = argparse.ArgumentParser(description='Generate TTS objects from classified cards')
    parser.add_argument('--teams', nargs='+', help='Specific teams to process (default: all)')
    parser.add_argument('--log-level', default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    logging.getLogger().setLevel(getattr(logging, args.log_level))
    
    logger.info("=" * 60)
    logger.info("TTS Object Generation - KT-App Pipeline")
    logger.info("=" * 60)
    
    # Generate URLs JSON from v3 structure
    logger.info("Scanning output_v3 structure...")
    urls_data = generate_urls_json_v3()
    logger.info(f"Found {len(urls_data)} card/asset entries")
    
    # Write temporary URLs file for TTSGenerator to use
    temp_urls_file = PROJECT_ROOT / 'output_v3' / 'datacards-urls.json'
    temp_urls_file.parent.mkdir(parents=True, exist_ok=True)
    with open(temp_urls_file, 'w', encoding='utf-8') as f:
        json.dump(urls_data, f, indent=2, ensure_ascii=False)
    
    # Create TTS generator with v3 paths
    generator = TTSGenerator(
        output_v2_dir=PROJECT_ROOT / 'output_v3',  # Read from v3
        tts_output_dir=PROJECT_ROOT / 'tts_objects_v3',  # Write to v3
        config_dir=PROJECT_ROOT / 'config',
        team_filter=args.teams
    )
    
    # Generate TTS objects
    count = generator.generate_all_tts_objects()
    
    logger.info("=" * 60)
    logger.info("Generation Complete")
    logger.info("=" * 60)
    logger.info(f"Teams processed: {count}")
    logger.info(f"Output: {PROJECT_ROOT / 'tts_objects_v3'}")


if __name__ == '__main__':
    main()
