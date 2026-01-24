#!/usr/bin/env python3
"""
Generate URLs CSV for TTS access
Compatible with script/generate_urls.py
"""
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / 'script'))

import os
os.chdir(project_root)

from src.pipeline import DatacardPipeline
from src.utils.logger import setup_logger


def main():
    """Main entry point"""
    logger = setup_logger(name='generate_urls', level='INFO')
    
    logger.info("Generating URLs CSV")
    
    pipeline = DatacardPipeline()
    count = pipeline.generate_urls()
    
    logger.info(f"Generated {count} URL(s)")
    
    logger.info("Done!")


if __name__ == '__main__':
    main()
