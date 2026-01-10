#!/usr/bin/env python3
"""
Add backside images to cards
Compatible with script/add_default_backsides.py
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
    logger = setup_logger(name='add_backsides', level='INFO')
    
    logger.info("Adding backside images")
    
    pipeline = DatacardPipeline()
    count = pipeline.add_backsides()
    
    logger.info(f"Added {count} backside(s)")
    
    logger.info("Done!")


if __name__ == '__main__':
    main()
