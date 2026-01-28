#!/usr/bin/env python3
"""
Main entry point for datacard processing pipeline
"""
import sys
import argparse
from pathlib import Path
import os

# Add script directory to path and change to project root
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(script_dir))
os.chdir(project_root)

from src.pipeline import DatacardPipeline
from src.utils.logger import setup_logger


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Kill Team Datacard Processing Pipeline'
    )
    
    parser.add_argument(
        '--step',
        choices=['process', 'extract', 'backsides', 'urls', 'tokens', 'all'],
        default='all',
        help='Pipeline step to run (default: all)'
    )
    
    parser.add_argument(
        '--teams',
        nargs='+',
        help='Filter by team names (e.g., --teams kasrkin blooded)'
    )

    parser.add_argument(
        '--force-overwrite-ready-tokens',
        action='store_true',
        help='Overwrite token JSON for tokens_ready teams (use for one-time migrations)'
    )
    
    parser.add_argument(
        '--dpi',
        type=int,
        default=300,
        help='Image resolution (default: 300)'
    )
    
    parser.add_argument(
        '--log-file',
        type=Path,
        help='Log to file'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Verbose logging'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = 'DEBUG' if args.verbose else 'INFO'
    logger = setup_logger(
        name='datacard_pipeline',
        level=log_level,
        log_file=args.log_file
    )
    
    # Create pipeline
    pipeline = DatacardPipeline(dpi=args.dpi)
    
    # Run requested step
    try:
        if args.step == 'all':
            logger.info("Running full pipeline")
            stats = pipeline.run_full_pipeline()
            
        elif args.step == 'process':
            logger.info("Processing raw PDFs")
            processed = pipeline.process_raw_pdfs()
            logger.info(f"Processed {len(processed)} PDF(s)")
            
        elif args.step == 'extract':
            logger.info("Extracting images")
            datacards = pipeline.extract_images(team_filter=args.teams)
            logger.info(f"Extracted {len(datacards)} card(s)")
            
        elif args.step == 'backsides':
            logger.info("Adding backsides")
            count = pipeline.add_backsides(team_filter=args.teams)
            logger.info(f"Added {count} backside(s)")
            
        elif args.step == 'urls':
            logger.info("Generating URLs")
            count = pipeline.generate_urls()
            logger.info(f"Generated {count} URL(s)")

        elif args.step == 'tokens':
            logger.info("Packaging tokens and embedding ready teams")
            from src.processors.token_integration import TokenIntegrator

            project_root = Path(__file__).parent.parent
            integrator = TokenIntegrator(
                project_root=project_root,
                config_path=project_root / 'config' / 'team-config.yaml',
                extracted_tokens_dir=project_root / 'processed' / 'extracted-tokens',
                output_v2_dir=project_root / 'output_v2',
                tts_objects_dir=project_root / 'tts_objects',
                tts_token_json_dir=project_root / 'tts_objects',
            )
            token_stats = integrator.embed_ready_tokens(
                team_filter=args.teams,
                force_overwrite_ready=args.force_overwrite_ready_tokens,
            )
            logger.info(
                "Tokens: packaged=%s ready=%s embedded=%s skipped_missing=%s",
                token_stats.get('packaged', 0),
                token_stats.get('ready', 0),
                token_stats.get('embedded', 0),
                token_stats.get('skipped_missing', 0),
            )
        
        logger.info("Done!")
        return 0
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == '__main__':
    sys.exit(main())
