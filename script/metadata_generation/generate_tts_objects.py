"""
Generate Tabletop Simulator saved object files from datacards-urls.json

This script creates TTS Custom_Model_Bag objects containing cards organized by type.
Each type (datacards, equipment, etc.) becomes a separate deck or card.

Can be run standalone or as part of the pipeline.
"""

from pathlib import Path
import sys

# Add the script directory to the path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from src.generators.tts_generator import TTSGenerator


def main():
    """Generate TTS objects for all teams"""
    workspace_dir = Path(__file__).parent.parent
    
    generator = TTSGenerator(
        output_v2_dir=workspace_dir / 'output_v2',
        tts_output_dir=workspace_dir / 'tts_objects',
        config_dir=workspace_dir / 'config'
    )
    
    count = generator.generate_all_tts_objects()
    print(f"\n✓ Generated {count} TTS object(s)")


if __name__ == "__main__":
    main()

