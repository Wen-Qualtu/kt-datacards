#!/usr/bin/env python3
"""
Extract card images from processed PDFs
Compatible with script/extract_pages.py
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
    logger = setup_logger(name='extract_images', level='INFO')
    
    logger.info("Extracting card images")
    
    pipeline = DatacardPipeline()
    datacards = pipeline.extract_images()
    
    logger.info(f"Extracted {len(datacards)} card(s)")
    
    logger.info("Done!")


if __name__ == '__main__':
    main()
