"""
Warcom PDF Processing Pipeline orchestrator.

Steps:
  1   Scrape Kill Team PDFs from warhammer-community.com
  2a  Extract icons & artwork from PDFs
  2b  Extract cards from PDFs
  3   Classify and organize cards
  4   Process tokens with template cutout
  4a  Generate team dice textures
  5   Generate TTS objects

Usage:
    python pipelines/warcom/pdf_process_pipeline.py --all
    python pipelines/warcom/pdf_process_pipeline.py --step 2b
    python pipelines/warcom/pdf_process_pipeline.py --step 3 --teams battleclade kommandos
    python pipelines/warcom/pdf_process_pipeline.py --from 2a       # run 2a onward
    python pipelines/warcom/pdf_process_pipeline.py --skip-download # --all minus step 1
"""

import argparse
import importlib.util
import logging
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


ALL_STEPS: List[str] = ['1', '2a', '2b', '3', '4', '4a', '5']

WORKSPACE_ROOT = Path(__file__).parent.parent.parent


def load_step(step_id: str):
    """Dynamically load a pipeline step module by id ('1', '2a', '4a', ...)."""
    steps_dir = Path(__file__).parent / 'steps'
    matches = list(steps_dir.glob(f'{step_id}_*.py'))
    if not matches:
        raise FileNotFoundError(f"Step '{step_id}' not found in {steps_dir}")
    step_path = matches[0]

    module_name = f"warcom_step_{step_id}"
    spec = importlib.util.spec_from_file_location(module_name, step_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _banner(title: str) -> None:
    logger.info("\n" + "=" * 70)
    logger.info(title)
    logger.info("=" * 70 + "\n")


def run_step_1(args) -> dict:
    _banner("STEP 1: Scrape Kill Team PDFs")
    mod = load_step('1')
    return mod.run(
        output_dir=args.output or WORKSPACE_ROOT / 'layers/warcom/staging',
        url=args.url or 'https://www.warhammer-community.com/en-gb/downloads/kill-team/',
        delay=args.delay,
    )


def run_step_2a(args) -> dict:
    _banner("STEP 2a: Extract Icons & Artwork from PDFs")
    mod = load_step('2a')
    return mod.run(
        input_dir=args.input or WORKSPACE_ROOT / 'layers/warcom/staging',
        output_dir=args.cards_output or WORKSPACE_ROOT / 'layers/warcom/extracted',
        max_workers=args.workers or 4,
    )


def run_step_2b(args) -> dict:
    _banner("STEP 2b: Extract Cards from PDFs")
    mod = load_step('2b')
    return mod.run(
        input_dir=args.input or WORKSPACE_ROOT / 'layers/warcom/staging',
        output_dir=args.cards_output or WORKSPACE_ROOT / 'layers/warcom/extracted',
        templates_file=args.templates or WORKSPACE_ROOT / 'config/pipelines/warcom/card_templates.json',
        dpi=args.dpi,
        max_workers=args.workers,
    )


def run_step_3(args, successful_teams: Optional[List[str]] = None) -> dict:
    _banner("STEP 3: Classify and Organize Cards")
    mod = load_step('3')
    return mod.run(
        extracted_dir=str(args.extracted or WORKSPACE_ROOT / 'layers/warcom/extracted'),
        archive_dir=str(args.archive or WORKSPACE_ROOT / 'layers/archive'),
        output_dir=str(args.output_classified or WORKSPACE_ROOT / 'output'),
        config_path=args.config,
        teams=args.teams or successful_teams,
        workers=args.workers or 1,
    )


def run_step_4(args, successful_teams: Optional[List[str]] = None) -> dict:
    _banner("STEP 4: Process Tokens with Template Cutout")
    mod = load_step('4')
    return mod.run(
        extracted_dir=args.extracted or WORKSPACE_ROOT / 'layers/warcom/extracted',
        output_dir=args.tokens_output or WORKSPACE_ROOT / 'output',
        teams=args.teams or successful_teams,
        workers=args.workers,
        debug=args.debug,
    )


def run_step_4a(args) -> dict:
    _banner("STEP 4a: Generate Team Dice Textures")
    mod = load_step('4a')
    return mod.run(
        extracted_dir=args.extracted or WORKSPACE_ROOT / 'layers/warcom/extracted',
        output_dir=args.tokens_output or WORKSPACE_ROOT / 'output',
    )


def run_step_5(args) -> dict:
    _banner("STEP 5: Generate TTS Objects")
    mod = load_step('5')
    return mod.run(
        output_dir=args.tokens_output or WORKSPACE_ROOT / 'output',
        teams=args.teams,
        force=args.force,
        branch=args.branch,
    )


STEP_DISPATCH = {
    '1':  lambda args, st: run_step_1(args),
    '2a': lambda args, st: run_step_2a(args),
    '2b': lambda args, st: run_step_2b(args),
    '3':  lambda args, st: run_step_3(args, st),
    '4':  lambda args, st: run_step_4(args, st),
    '4a': lambda args, st: run_step_4a(args),
    '5':  lambda args, st: run_step_5(args),
}


def _track_successful_teams(step_id: str, result: dict, current: Optional[List[str]]) -> Optional[List[str]]:
    """After 2b, derive successful teams from layers/archive content."""
    if step_id == '2b':
        archive_dir = WORKSPACE_ROOT / 'layers/archive'
        if archive_dir.exists():
            return sorted(d.name for d in archive_dir.iterdir() if d.is_dir())
    return current


def main():
    parser = argparse.ArgumentParser(
        description='Kill Team Warcom PDF Processing Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Pipeline control
    parser.add_argument('--all', action='store_true', help='Run all pipeline steps')
    parser.add_argument('--step', type=str, choices=ALL_STEPS,
                        help='Run a single step (e.g. 1, 2a, 2b, 3, 4, 4a, 5)')
    parser.add_argument('--from', dest='from_step', type=str, choices=ALL_STEPS,
                        help='Run from this step onward (inclusive)')
    parser.add_argument('--skip-download', action='store_true',
                        help='With --all or --from 1, skip the warhammer-community.com scrape')

    # Step 1 args
    parser.add_argument('--url', type=str, help='Kill Team downloads page URL (step 1)')
    parser.add_argument('--output', type=Path,
                        help='Output dir for downloaded PDFs (step 1, default: layers/warcom/staging)')
    parser.add_argument('--delay', type=float, default=1.0,
                        help='Delay between downloads in seconds (step 1)')

    # Step 2 args
    parser.add_argument('--input', type=Path,
                        help='Input dir with PDFs (steps 2a/2b, default: layers/warcom/staging)')
    parser.add_argument('--cards-output', type=Path,
                        help='Output dir for extracted cards (steps 2a/2b, default: layers/warcom/extracted)')
    parser.add_argument('--templates', type=Path,
                        help='Templates file (step 2b, default: config/pipelines/warcom/card_templates.json)')
    parser.add_argument('--dpi', type=int, default=150, help='DPI for card extraction (step 2b)')
    parser.add_argument('--workers', type=int, default=None,
                        help='Max concurrent workers (steps 2a/2b/3/4)')

    # Steps 3, 4 args
    parser.add_argument('--extracted', type=Path,
                        help='Dir with extracted cards (steps 3/4/4a, default: layers/warcom/extracted)')
    parser.add_argument('--archive', type=Path,
                        help='Archive dir with processed PDFs (step 3, default: layers/archive)')
    parser.add_argument('--output-classified', type=Path,
                        help='Output dir for classified cards (step 3, default: output)')
    parser.add_argument('--config', type=str,
                        help='Team config file (step 3, default: config/team-config.yaml)')
    parser.add_argument('--teams', nargs='+',
                        help='Specific teams to process (steps 3/4/5, default: all)')

    # Steps 4/4a/5 args
    parser.add_argument('--tokens-output', type=Path,
                        help='Output dir for tokens / dice / tts (steps 4/4a/5, default: output)')
    parser.add_argument('--debug', action='store_true', help='Save debug images (step 4)')

    # Step 5 args
    parser.add_argument('--force', action='store_true',
                        help='Force TTS regeneration even if unchanged (step 5)')
    parser.add_argument('--branch', default='main',
                        help='Git branch for GitHub raw URLs (step 5, default: main)')

    # Logging
    parser.add_argument('--log-level', type=str, default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'])

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level), format='%(levelname)s: %(message)s')

    # Decide steps to run
    if args.all:
        steps_to_run = list(ALL_STEPS)
    elif args.from_step:
        idx = ALL_STEPS.index(args.from_step)
        steps_to_run = ALL_STEPS[idx:]
    elif args.step:
        steps_to_run = [args.step]
    else:
        parser.print_help()
        logger.error("\nError: Must specify --all, --step <id>, or --from <id>")
        sys.exit(1)

    if args.skip_download and '1' in steps_to_run:
        steps_to_run = [s for s in steps_to_run if s != '1']
        logger.info("Skipping step 1 (--skip-download)")

    logger.info("=" * 70)
    logger.info("KILL TEAM WARCOM PIPELINE")
    logger.info("=" * 70)
    logger.info(f"Steps to run: {', '.join(steps_to_run)}")

    results: dict = {}
    failures: List[dict] = []
    successful_teams: Optional[List[str]] = None

    for step_id in steps_to_run:
        try:
            result = STEP_DISPATCH[step_id](args, successful_teams)
        except Exception as e:
            logger.exception(f"Step {step_id} crashed: {e}")
            failures.append({'step': step_id, 'reason': str(e), 'details': {}})
            # Stop early if a foundational step crashed
            if step_id in ('1', '2a', '2b'):
                logger.error(f"Aborting pipeline after fatal step {step_id} failure")
                break
            continue

        results[step_id] = result or {}
        successful_teams = _track_successful_teams(step_id, result or {}, successful_teams)

        # Per-step pass/fail summary
        status = (result or {}).get('status')
        if status and status not in ('success',):
            failures.append({'step': step_id, 'reason': f"status={status}", 'details': result})
            logger.warning(f"\nStep {step_id} completed with status={status}")
        else:
            logger.info(f"\nStep {step_id} completed")

    # Final summary
    logger.info("\n" + "=" * 70)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 70)
    for step_id, result in results.items():
        logger.info(f"\nStep {step_id}:")
        for key in ('status', 'teams_processed', 'teams_updated', 'processed', 'files_processed',
                    'total_cards', 'total_cards_classified', 'icons', 'artwork',
                    'downloaded', 'skipped', 'failed'):
            if key in result and result[key] not in (None, 0):
                logger.info(f"  {key}: {result[key]}")

    if failures:
        logger.info("\n" + "=" * 70)
        logger.info("FAILURES")
        logger.info("=" * 70)
        for f in failures:
            logger.error(f"Step {f['step']}: {f['reason']}")
        sys.exit(2)

    logger.info("\nAll requested steps finished.")


if __name__ == '__main__':
    main()
