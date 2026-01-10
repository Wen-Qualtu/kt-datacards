#!/usr/bin/env python3
"""
Process raw PDFs: identify and organize
Compatible with script/process_raw_pdfs.py
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
    logger = setup_logger(name='process_pdfs', level='INFO')
    
    logger.info("Processing raw PDFs")
    
    pipeline = DatacardPipeline()
    processed = pipeline.process_raw_pdfs()
    
    logger.info(f"Processed {len(processed)} PDF(s)")
    
    for pdf_path, team, card_type in processed:
        logger.info(f"  {team.name}: {card_type.value}")
    
    logger.info("Done!")


if __name__ == '__main__':
    main()
