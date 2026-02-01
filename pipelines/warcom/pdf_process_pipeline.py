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
import importlib.util


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


def run_step_1(args):
    """Step 1: Scrape Warhammer Community Kill Team downloads"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 1: Scrape Kill Team PDFs")
    print("=" * 70 + "\n")
    
    step1 = load_step(1)
    
    # Get workspace root (2 levels up from this script)
    workspace_root = Path(__file__).parent.parent.parent
    
    result = step1.run(
        output_dir=args.output or workspace_root / 'layers/warcom/staging',
        url=args.url or 'https://www.warhammer-community.com/en-gb/downloads/kill-team/',
        delay=args.delay
    )
    
    return result


def run_step_2(args):
    """Step 2: Extract cards from PDFs"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 2: Extract Cards from PDFs")
    print("=" * 70 + "\n")
    
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
    
    return result


def run_step_3(args):
    """Step 3: Classify and organize cards by type"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 3: Classify and Organize Cards")
    print("=" * 70 + "\n")
    
    step3 = load_step(3)
    
    # Get workspace root (2 levels up from this script)
    workspace_root = Path(__file__).parent.parent.parent
    
    result = step3.run(
        extracted_dir=args.extracted or workspace_root / 'layers/warcom/extracted',
        archive_dir=args.archive or workspace_root / 'layers/archive',
        output_dir=args.output_classified or workspace_root / 'output',
        config_path=args.config,
        teams=args.teams,
        workers=args.workers
    )
    
    return result


def run_step_4(args):
    """Step 4: Extract tokens from token guide cards"""
    print("\n" + "=" * 70)
    print("PIPELINE STEP 4: Extract Tokens from Token Guide Cards")
    print("=" * 70 + "\n")
    
    step4 = load_step(4)
    
    # Get workspace root (2 levels up from this script)
    workspace_root = Path(__file__).parent.parent.parent
    
    result = step4.run(
        extracted_dir=args.extracted or workspace_root / 'layers/warcom/extracted',
        archive_dir=args.archive or workspace_root / 'layers/archive',
        output_dir=args.tokens_output or workspace_root / 'layers/warcom/extracted',
        teams=args.teams,
        workers=args.workers,
        debug=args.debug
    )
    
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
    
    args = parser.parse_args()
    
    # Determine which steps to run
    if args.all:
        steps_to_run = [1, 2, 3, 4]  # Will expand as more steps are added
    elif args.step:
        steps_to_run = [args.step]
    else:
        parser.print_help()
        print("\nError: Must specify --all or --step <number>")
        sys.exit(1)
    
    # Run the pipeline
    print("=" * 70)
    print("KILL TEAM PDF PROCESSING PIPELINE")
    print("=" * 70)
    
    results = {}
    
    for step_num in steps_to_run:
        if step_num == 1:
            result = run_step_1(args)
            results[1] = result
            
            if not result['success']:
                print(f"\nStep {step_num} failed, stopping pipeline")
                sys.exit(1)
        elif step_num == 2:
            result = run_step_2(args)
            results[2] = result
            
            if not result['success']:
                print(f"\nStep {step_num} failed, stopping pipeline")
                sys.exit(1)
        elif step_num == 3:
            result = run_step_3(args)
            results[3] = result
            
            if result.get('status') != 'success':
                print(f"\nStep {step_num} failed, stopping pipeline")
                sys.exit(1)
        elif step_num == 4:
            result = run_step_4(args)
            results[4] = result
            
            if result.get('status') != 'success':
                print(f"\nStep {step_num} failed, stopping pipeline")
                sys.exit(1)
        else:
            print(f"\nStep {step_num} not yet implemented")
            sys.exit(1)
    
    # Summary
    print("\n" + "=" * 70)
    print("PIPELINE COMPLETE")
    print("=" * 70)
    
    for step_num, result in results.items():
        print(f"\nStep {step_num}:")
        for key, value in result.items():
            print(f"  {key}: {value}")


if __name__ == '__main__':
    main()
