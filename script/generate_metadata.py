"""Generate output metadata YAML file"""
import sys
from pathlib import Path
import logging

# Add script directory to path
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir / 'src'))

from generators.metadata_generator import OutputMetadataGenerator


def main():
    """Main entry point"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Set paths relative to project root
    project_root = Path(__file__).parent.parent
    output_dir = project_root / 'output'
    config_dir = project_root / 'config'
    output_file = project_root / 'output-metadata.yaml'
    
    # Generate metadata
    generator = OutputMetadataGenerator(
        output_dir=output_dir,
        config_dir=config_dir
    )
    generator.generate_and_save(output_path=output_file)


if __name__ == '__main__':
    main()
