"""
Generate Tabletop Simulator saved object files from datacards-urls.json

This script creates TTS Custom_Model_Bag objects containing cards organized by type.
Each type (datacards, equipment, etc.) becomes a separate deck or card.

Can be run standalone or as part of the pipeline.

Usage:
    python script/generate_tts_objects.py                    # Generate all teams
    python script/generate_tts_objects.py murderwings        # Generate only murderwings
    python script/generate_tts_objects.py murderwings celestian-insidiant  # Generate multiple teams
"""

from pathlib import Path
import sys
import argparse

# Add the script directory to the path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from src.generators.tts_generator import TTSGenerator


def main():
    """Generate TTS objects for all teams or specified teams"""
    parser = argparse.ArgumentParser(
        description='Generate TTS objects for Kill Team datacards',
        epilog='Examples:\n'
               '  python script/generate_tts_objects.py\n'
               '  python script/generate_tts_objects.py murderwings\n'
               '  python script/generate_tts_objects.py murderwings celestian-insidiant',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        'teams',
        nargs='*',
        help='Team names to regenerate (if omitted, regenerate all teams)'
    )
    
    args = parser.parse_args()
    
    workspace_dir = Path(__file__).parent.parent
    
    # Convert team filter to None if empty list
    team_filter = args.teams if args.teams else None
    
    if team_filter:
        print(f"Regenerating TTS objects for: {', '.join(team_filter)}")
    else:
        print("Regenerating TTS objects for all teams")
    
    generator = TTSGenerator(
        output_v2_dir=workspace_dir / 'output_v2',
        tts_output_dir=workspace_dir / 'tts_objects',
        config_dir=workspace_dir / 'config',
        team_filter=team_filter
    )
    
    count = generator.generate_all_tts_objects()
    print(f"\nGenerated {count} TTS object(s)")


if __name__ == "__main__":
    main()


