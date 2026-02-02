"""
PDF Processing Pipeline

Orchestrates the multi-step process of:
1. Scraping Kill Team PDFs from Warhammer Community
2. Extracting datacards from PDFs
3. Classifying and organizing cards by type
4. Extracting tokens from token guide cards
5. (Future) Processing tokens (background removal, etc.)

Usage:
    python pipelines/warcom/pdf_process_pipeline.py --all
    python pipelines/warcom/pdf_process_pipeline.py --step 1
    python pipelines/warcom/pdf_process_pipeline.py --step 3 --teams battleclade
"""

import argparse
from pathlib import Path
import sys
import logging
import importlib.util

logger = logging.getLogger(__name__)


def load_step(step_number: int):
    """Dynamically load a pipeline step module."""
    step_file = Path(__file__).parent / 'steps' / f'{step_number}_*.py'
    
    # Find matching step file
    step_files = list(Path(__file__).parent.glob(f'steps/{step_number}_*.py'))
    
    if not step_files:
        raise FileNotFoundError(f"Step {step_number} not found in steps/ directory")
    
    step_path = step_files[0]
    
    # Load module dynamically
    spec = importlib.util.spec_from_file_location(f"step_{step_number}", step_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    
    return module


def run_step_1(args, successful_teams=None):
    """Step 1: Scrape Warhammer Community Kill Team downloads"""
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE STEP 1: Scrape Kill Team PDFs")
    logger.info("=" * 70 + "\n")
    
    step1 = load_step(1)
    
    # Get workspace root (2 levels up from this script)
    workspace_root = Path(__file__).parent.parent.parent
    
    result = step1.run(
        output_dir=args.output or workspace_root / 'layers/warcom/staging',
        url=args.url or 'https://www.warhammer-community.com/en-gb/downloads/kill-team/',
        delay=args.delay
    )
    
    # Step 1 doesn't filter by teams - all PDFs downloaded
    # Successful teams will be determined in step 2
    result['successful_teams'] = None  # Indicates step 1 doesn't track individual teams
    return result


def run_step_2(args, successful_teams=None):
    """Step 2: Extract cards from PDFs"""
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE STEP 2: Extract Cards from PDFs")
    logger.info("=" * 70 + "\n")
    
    step2 = load_step(2)
    
    # Get workspace root (2 levels up from this script)
    workspace_root = Path(__file__).parent.parent.parent
    
    result = step2.run(
        input_dir=args.input or workspace_root / 'layers/warcom/staging',
        output_dir=args.cards_output or workspace_root / 'layers/warcom/extracted',
        templates_file=args.templates or workspace_root / 'config/pipelines/warcom/card_templates.json',
        dpi=args.dpi,
        max_workers=args.workers
    )
    
    # Step 2 archives successful teams - track them
    # Successful teams are those moved to layers/archive/{team}/
    archive_dir = Path('layers/archive')
    if archive_dir.exists():
        result['successful_teams'] = [d.name for d in archive_dir.iterdir() if d.is_dir()]
    else:
        result['successful_teams'] = []
    
    return result


def run_step_3(args, successful_teams=None):
    """Step 3: Classify and organize cards by type"""
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE STEP 3: Classify and Organize Cards")
    logger.info("=" * 70 + "\n")
    
    step3 = load_step(3)
    
    # Get workspace root (2 levels up from this script)
    workspace_root = Path(__file__).parent.parent.parent
    
    # If we have successful teams from previous step, pass them to step 3
    result = step3.run(
        extracted_dir=args.extracted or workspace_root / 'layers/warcom/extracted',
        archive_dir=args.archive or workspace_root / 'layers/archive',
        output_dir=args.output_classified or workspace_root / 'output',
        config_path=args.config,
        teams=successful_teams or args.teams,  # Use successful teams from step 2 if available
        workers=args.workers
    )
    
    # Track successful teams from step 3 if provided
    if 'successful_teams' not in result:
        result['successful_teams'] = successful_teams
    
    return result


def run_step_4(args, successful_teams=None):
    """Step 4: Extract tokens from token guide cards"""
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE STEP 4: Extract Tokens from Token Guide Cards")
    logger.info("=" * 70 + "\n")
    
    step4 = load_step(4)
    
    # Get workspace root (2 levels up from this script)
    workspace_root = Path(__file__).parent.parent.parent
    
    result = step4.run(
        extracted_dir=args.extracted or workspace_root / 'layers/warcom/extracted',
        archive_dir=args.archive or workspace_root / 'layers/archive',
        output_dir=args.tokens_output or workspace_root / 'layers/warcom/extracted',
        teams=successful_teams or args.teams,  # Use successful teams from previous steps
        workers=args.workers,
        debug=args.debug
    )
    
    # Track successful teams from step 4 if provided
    if 'successful_teams' not in result:
        result['successful_teams'] = successful_teams
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Kill Team PDF Processing Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Pipeline control
    parser.add_argument('--all', action='store_true',
                       help='Run all pipeline steps')
    parser.add_argument('--step', type=int,
                       help='Run a specific step (1, 2, 3, etc.)')
    
    # Step 1 arguments
    parser.add_argument('--url', type=str,
                       help='Kill Team downloads page URL (Step 1)')
    parser.add_argument('--output', type=Path,
                       help='Output directory for PDFs (Step 1, default: input/)')
    parser.add_argument('--delay', type=float, default=1.0,
                       help='Delay between PDF downloads in seconds (Step 1)')
    
    # Step 2 arguments
    parser.add_argument('--input', type=Path,
                       help='Input directory with PDFs (Step 2, default: layers/warcom/staging)')
    parser.add_argument('--cards-output', type=Path,
                       help='Output directory for extracted cards (Step 2, default: layers/warcom/extracted)')
    parser.add_argument('--templates', type=Path,
                       help='Templates file (Step 2, default: config/pipelines/warcom/card_templates.json)')
    parser.add_argument('--dpi', type=int, default=150,
                       help='DPI for card extraction (Step 2)')
    parser.add_argument('--workers', type=int, default=None,
                       help='Max concurrent workers (Steps 2, 3, default: auto)')
    
    # Step 3 arguments
    parser.add_argument('--extracted', type=Path,
                       help='Directory with extracted cards (Steps 3, 4, default: layers/warcom/extracted)')
    parser.add_argument('--archive', type=Path,
                       help='Archive directory with PDFs (Steps 3, 4, default: layers/archive)')
    parser.add_argument('--output-classified', type=Path,
                       help='Output directory for classified cards (Step 3, default: output)')
    parser.add_argument('--config', type=str,
                       help='Team config file (Step 3, default: config/team-config.yaml)')
    parser.add_argument('--teams', nargs='+',
                       help='Specific teams to process (Steps 3, 4, default: all)')
    
    # Step 4 arguments
    parser.add_argument('--tokens-output', type=Path,
                       help='Output directory for extracted tokens (Step 4, default: layers/warcom/extracted)')
    parser.add_argument('--debug', action='store_true',
                       help='Save debug images (Step 4)')
    
    # Logging configuration
    parser.add_argument('--log-level', type=str, default='INFO',
                       choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    # Determine which steps to run
    if args.all:
        steps_to_run = [1, 2, 3, 4]  # Will expand as more steps are added
    elif args.step:
        steps_to_run = [args.step]
    else:
        parser.print_help()
        logger.error("\nError: Must specify --all or --step <number>")
        sys.exit(1)
    
    # Configure logging
    log_level = getattr(logging, args.log_level.upper() if hasattr(args, 'log_level') and args.log_level else 'INFO')
    logging.basicConfig(level=log_level, format='%(levelname)s: %(message)s')
    
    # Run the pipeline
    logger.info("=" * 70)
    logger.info("KILL TEAM PDF PROCESSING PIPELINE")
    logger.info("=" * 70)
    
    results = {}
    failures = []  # Track failures across all steps
    successful_teams = None  # Pass successful teams between steps
    
    for step_num in steps_to_run:
        if step_num == 1:
            result = run_step_1(args, successful_teams)
            results[1] = result
            successful_teams = result.get('successful_teams')
            
            # Step 1 downloads PDFs - only fail if nothing was downloaded
            if result.get('downloaded', 0) == 0 and result.get('skipped', 0) == 0:
                failures.append({
                    'step': 1,
                    'reason': 'No PDFs downloaded or found',
                    'details': result
                })
                logger.warning(f"\nStep {step_num} failed: No PDFs downloaded")
            else:
                logger.info(f"\nStep {step_num} completed: {result.get('downloaded', 0)} downloaded, {result.get('skipped', 0)} skipped")
                
        elif step_num == 2:
            result = run_step_2(args, successful_teams)
            results[2] = result
            successful_teams = result.get('successful_teams')
            
            # Step 2 extracts cards - continue if any teams succeeded
            if result.get('files_processed', 0) == 0:
                failures.append({
                    'step': 2,
                    'reason': 'No files processed',
                    'details': result
                })
                logger.warning(f"\nStep {step_num} failed: No teams processed successfully")
            else:
                logger.info(f"\nStep {step_num} completed: {result.get('files_processed', 0)} teams processed, {result.get('failed', 0)} failed")
                if result.get('failed', 0) > 0:
                    failures.append({
                        'step': 2,
                        'reason': f"{result.get('failed')} teams failed extraction",
                        'details': result
                    })
                    
        elif step_num == 3:
            result = run_step_3(args, successful_teams)
            results[3] = result
            successful_teams = result.get('successful_teams')
            
            if result.get('status') != 'success':
                failures.append({
                    'step': 3,
                    'reason': 'Classification failed',
                    'details': result
                })
                logger.warning(f"\nStep {step_num} had issues")
            else:
                logger.info(f"\nStep {step_num} completed successfully")
                
        elif step_num == 4:
            result = run_step_4(args, successful_teams)
            results[4] = result
            successful_teams = result.get('successful_teams')
            
            if result.get('status') != 'success':
                failures.append({
                    'step': 4,
                    'reason': 'Token extraction failed',
                    'details': result
                })
                logger.warning(f"\nStep {step_num} had issues")
            else:
                logger.info(f"\nStep {step_num} completed successfully")
        else:
            logger.error(f"\nStep {step_num} not yet implemented")
            failures.append({
                'step': step_num,
                'reason': 'Step not implemented',
                'details': {}
            })
    
    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)
    
    # Show summary results for each step (not detailed internals)
    for step_num, result in results.items():
        logger.info(f"\nStep {step_num}:")
        # Only show key summary stats, not the entire results dict
        if 'status' in result:
            logger.info(f"  status: {result['status']}")
        if 'teams_processed' in result:
            logger.info(f"  teams processed: {result['teams_processed']}")
        if 'total_cards_classified' in result:
            logger.info(f"  cards classified: {result['total_cards_classified']}")
        if 'failed' in result and result['failed'] > 0:
            logger.error(f"  failed: {result['failed']}")
        if 'skipped' in result and result['skipped'] > 0:
            logger.warning(f"  skipped: {result['skipped']}")
    
    # Show comprehensive failure summary
    if failures:
        logger.info("\n" + "=" * 70)
        logger.info("FAILURE SUMMARY")
        logger.info("=" * 70)
        for failure in failures:
            logger.error(f"\nStep {failure['step']}: {failure['reason']}")
            if 'failed' in failure['details']:
                logger.error(f"  Failed count: {failure['details']['failed']}")
        
        # Exit with error if ALL steps failed or no teams succeeded
        if len(results) == 0 or all(r.get('files_processed', r.get('downloaded', 1)) == 0 for r in results.values()):
            logger.error("\nPipeline failed: No successful processing")
            sys.exit(1)
        else:
            logger.warning("\nPipeline completed with some failures")
    else:
        logger.info("\n✓ All steps completed successfully!")


if __name__ == '__main__':
    main()
