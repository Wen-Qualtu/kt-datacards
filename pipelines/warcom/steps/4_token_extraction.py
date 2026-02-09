"""
Step 3: Token Extraction from Token Guide Cards

Extracts individual token images from marker/token guide cards in the warcom extracted cards.
Uses the same computer vision logic as the kt-app pipeline to detect token contours and extract
names from PDFs.

Input:  layers/warcom/extracted/{team}/cards/*.png
Output: layers/warcom/extracted/{team}/tokens/*.png
        layers/warcom/extracted/{team}/tokens/extraction-metadata.json
"""

import argparse
import json
import logging
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add tools directory to path to reuse TokenExtractor
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / 'tools'))
from extract_tokens import TokenExtractor


logger = logging.getLogger(__name__)


def find_token_guide_cards(team_dir: Path) -> List[Path]:
    """
    Find token guide cards in the extracted cards directory.
    
    Token guide cards typically have names like:
    - *token-guide*.png
    - *marker*guide*.png
    
    Args:
        team_dir: Path to team's cards directory (layers/warcom/extracted/{team}/cards/)
    
    Returns:
        List of paths to token guide card images
    """
    cards_dir = team_dir / 'cards'
    if not cards_dir.exists():
        return []
    
    token_guides = []
    
    # Look for token guide patterns
    patterns = [
        '*token-guide*.png',
        '*token*guide*.png',
        '*marker*guide*.png',
        '*markertoken*.png'
    ]
    
    for pattern in patterns:
        for card in cards_dir.glob(pattern):
            if card not in token_guides:
                token_guides.append(card)
    
    return sorted(token_guides)


def find_team_pdf(team_name: str, archive_dir: Path) -> Optional[Path]:
    """
    Find the archived PDF for a team.
    
    Args:
        team_name: Team slug
        archive_dir: Base archive directory (layers/archive/)
    
    Returns:
        Path to PDF or None if not found
    """
    team_archive = archive_dir / team_name / 'warcom'
    if not team_archive.exists():
        return None
    
    # Find the first PDF in the archive
    pdfs = list(team_archive.glob('*.pdf'))
    if pdfs:
        return pdfs[0]
    
    return None


def extract_tokens_for_team(
    team_name: str,
    extracted_dir: Path,
    archive_dir: Path,
    output_dir: Path,
    debug: bool = False
) -> Dict:
    """
    Extract tokens for a single team.
    
    Args:
        team_name: Team slug
        extracted_dir: Base extracted directory (layers/warcom/extracted/)
        archive_dir: Base archive directory (layers/archive/)
        output_dir: Base output directory for tokens (layers/warcom/extracted/)
        debug: If True, save debug images
    
    Returns:
        Dict with extraction statistics
    """
    team_dir = extracted_dir / team_name
    tokens_output = output_dir / team_name / 'tokens'

    existing_tokens = sorted(tokens_output.glob('*.png')) if tokens_output.exists() else []
    if existing_tokens:
        return {
            'team': team_name,
            'status': 'success',
            'tokens_extracted': len(existing_tokens),
            'output_dir': str(tokens_output),
            'reason': 'tokens already extracted'
        }

    # Find token guide cards
    token_guide_cards = find_token_guide_cards(team_dir)
    
    if not token_guide_cards:
        return {
            'team': team_name,
            'status': 'skipped',
            'reason': 'No token guide cards found',
            'tokens_extracted': 0
        }
    
    # Find archived PDF
    pdf_path = find_team_pdf(team_name, archive_dir)
    if not pdf_path:
        return {
            'team': team_name,
            'status': 'failed',
            'reason': 'No archived PDF found',
            'tokens_extracted': 0
        }
    
    # Setup output directory
    tokens_output.mkdir(parents=True, exist_ok=True)
    
    # Initialize extractor
    extractor = TokenExtractor(output_base_dir=tokens_output.parent)
    
    all_tokens = []
    
    logger.info("=" * 60)
    logger.info("Processing: %s", team_name)
    logger.info("=" * 60)
    logger.info("  Token guide cards: %d", len(token_guide_cards))
    logger.info("  PDF: %s", pdf_path.name)
    
    # Process each token guide card
    for card_idx, card_path in enumerate(token_guide_cards, 1):
        logger.info("  Processing card %d/%d: %s", card_idx, len(token_guide_cards), card_path.name)
        
        try:
            # We need to find which PDF page this card came from
            # For now, we'll use the card image directly and try to match it to a PDF page
            # The TokenExtractor can work with just the image
            
            # Extract tokens using the auto method
            extracted = extractor.extract_tokens_auto(
                image_path=card_path,
                pdf_page_info=None,  # Will try to match image to PDF
                output_dir=tokens_output,
                debug=debug,
                skip_header_percent=15.0,
                extract_names=True
            )
            
            if extracted:
                all_tokens.extend(extracted)
                logger.info("    ✓ Extracted %d tokens", len(extracted))
            else:
                logger.warning("    ⚠ No tokens extracted")
                
        except Exception as e:
            logger.error("    ✗ Error extracting tokens: %s", e)
            if debug:
                import traceback
                traceback.print_exc()
            continue
    
    # Create extraction metadata
    metadata = {
        'team': team_name,
        'source_pdf': str(pdf_path),
        'source_cards': [str(c) for c in token_guide_cards],
        'extraction_method': 'auto',
        'tokens_extracted': len(all_tokens),
        'tokens': all_tokens
    }
    
    metadata_file = tokens_output / 'extraction-metadata.json'
    with open(metadata_file, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2)
    
    logger.info("✓ Total tokens extracted: %d", len(all_tokens))
    logger.info("  Saved to: %s", tokens_output)
    
    return {
        'team': team_name,
        'status': 'success',
        'tokens_extracted': len(all_tokens),
        'output_dir': str(tokens_output)
    }


def run(
    extracted_dir: str = 'layers/warcom/extracted',
    archive_dir: str = 'layers/archive',
    output_dir: str = 'layers/warcom/extracted',
    teams: Optional[List[str]] = None,
    workers: int = 1,
    debug: bool = False
) -> Dict:
    """
    Extract tokens from token guide cards for all teams.
    
    Args:
        extracted_dir: Directory with extracted cards (layers/warcom/extracted/)
        archive_dir: Directory with archived PDFs (layers/archive/)
        output_dir: Base output directory (layers/warcom/extracted/)
        teams: Optional list of specific teams to process
        workers: Number of concurrent workers (default: 1, sequential)
        debug: Save debug images
    
    Returns:
        Dict with extraction statistics
    """
    extracted_path = Path(extracted_dir)
    archive_path = Path(archive_dir)
    output_path = Path(output_dir)
    
    if not extracted_path.exists():
        logger.error("Extracted directory not found: %s", extracted_path)
        return {'status': 'failed', 'reason': 'extracted directory not found'}
    
    if not archive_path.exists():
        logger.error("Archive directory not found: %s", archive_path)
        return {'status': 'failed', 'reason': 'archive directory not found'}
    
    # Find teams to process
    if teams:
        team_dirs = [extracted_path / team for team in teams if (extracted_path / team).exists()]
    else:
        team_dirs = [d for d in extracted_path.iterdir() if d.is_dir()]
    
    if not team_dirs:
        logger.error("No teams found in %s", extracted_path)
        return {'status': 'failed', 'reason': 'no teams found'}
    
    logger.info("=" * 60)
    logger.info("Token Extraction (Step 4)")
    logger.info("=" * 60)
    logger.info("Extracted dir: %s", extracted_path)
    logger.info("Archive dir: %s", archive_path)
    logger.info("Output dir: %s", output_path)
    logger.info("Teams: %d", len(team_dirs))
    logger.info("Workers: %s", workers)
    logger.info("=" * 60)
    
    results = []
    
    if workers == 1:
        # Sequential processing
        for team_dir in team_dirs:
            result = extract_tokens_for_team(
                team_dir.name,
                extracted_path,
                archive_path,
                output_path,
                debug=debug
            )
            results.append(result)
    else:
        # Concurrent processing
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    extract_tokens_for_team,
                    team_dir.name,
                    extracted_path,
                    archive_path,
                    output_path,
                    debug
                ): team_dir.name
                for team_dir in team_dirs
            }
            
            for future in as_completed(futures):
                team_name = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error("Error processing %s: %s", team_name, e)
                    results.append({
                        'team': team_name,
                        'status': 'failed',
                        'reason': str(e),
                        'tokens_extracted': 0
                    })
    
    # Summary
    successful = [r for r in results if r.get('status') == 'success']
    failed = [r for r in results if r.get('status') == 'failed']
    skipped = [r for r in results if r.get('status') == 'skipped']
    total_tokens = sum(r.get('tokens_extracted', 0) for r in results)
    
    logger.info("=" * 60)
    logger.info("Token Extraction Complete")
    logger.info("=" * 60)
    logger.info("  Teams processed: %d", len(results))
    logger.info("  Successful: %d", len(successful))
    logger.info("  Failed: %d", len(failed))
    logger.info("  Skipped: %d", len(skipped))
    logger.info("  Total tokens: %d", total_tokens)
    
    if failed:
        logger.error("Failed teams:")
        for r in failed:
            logger.error("  - %s: %s", r['team'], r.get('reason', 'unknown error'))
    
    if skipped:
        logger.warning("Skipped teams:")
        for r in skipped:
            logger.warning("  - %s: %s", r['team'], r.get('reason', 'unknown reason'))
    
    return {
        'status': 'success',
        'teams_processed': len(results),
        'successful': len(successful),
        'failed': len(failed),
        'skipped': len(skipped),
        'total_tokens_extracted': total_tokens,
        'results': results
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Step 3: Extract tokens from token guide cards')
    parser.add_argument('--extracted-dir', default='layers/warcom/extracted',
                        help='Directory with extracted cards (default: layers/warcom/extracted)')
    parser.add_argument('--archive-dir', default='layers/archive',
                        help='Directory with archived PDFs (default: layers/archive)')
    parser.add_argument('--output-dir', default='layers/warcom/extracted',
                        help='Base output directory (default: layers/warcom/extracted)')
    parser.add_argument('--teams', nargs='+',
                        help='Specific teams to process (default: all)')
    parser.add_argument('--workers', type=int, default=1,
                        help='Number of concurrent workers (default: 1)')
    parser.add_argument('--debug', action='store_true',
                        help='Save debug images')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Logging level (default: INFO)')
    
    args = parser.parse_args()
    
    logging.basicConfig(level=getattr(logging, args.log_level), format='%(levelname)s: %(message)s')

    result = run(
        extracted_dir=args.extracted_dir,
        archive_dir=args.archive_dir,
        output_dir=args.output_dir,
        teams=args.teams,
        workers=args.workers,
        debug=args.debug
    )
    
    sys.exit(0 if result.get('status') == 'success' else 1)
