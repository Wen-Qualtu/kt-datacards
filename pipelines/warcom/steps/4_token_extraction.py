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
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add kt-app tools to path to reuse TokenExtractor
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'kt-app' / 'tools'))
from extract_tokens import TokenExtractor


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
    tokens_output = output_dir / team_name / 'tokens'
    tokens_output.mkdir(parents=True, exist_ok=True)
    
    # Initialize extractor
    extractor = TokenExtractor(output_base_dir=tokens_output.parent)
    
    all_tokens = []
    
    print(f"\n{'='*60}")
    print(f"Processing: {team_name}")
    print(f"{'='*60}")
    print(f"  Token guide cards: {len(token_guide_cards)}")
    print(f"  PDF: {pdf_path.name}")
    
    # Process each token guide card
    for card_idx, card_path in enumerate(token_guide_cards, 1):
        print(f"\n  Processing card {card_idx}/{len(token_guide_cards)}: {card_path.name}")
        
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
                print(f"    ✓ Extracted {len(extracted)} tokens")
            else:
                print(f"    ⚠ No tokens extracted")
                
        except Exception as e:
            print(f"    ✗ Error extracting tokens: {e}")
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
    
    print(f"\n✓ Total tokens extracted: {len(all_tokens)}")
    print(f"  Saved to: {tokens_output}")
    
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
        print(f"✗ Extracted directory not found: {extracted_path}")
        return {'status': 'failed', 'reason': 'extracted directory not found'}
    
    if not archive_path.exists():
        print(f"✗ Archive directory not found: {archive_path}")
        return {'status': 'failed', 'reason': 'archive directory not found'}
    
    # Find teams to process
    if teams:
        team_dirs = [extracted_path / team for team in teams if (extracted_path / team).exists()]
    else:
        team_dirs = [d for d in extracted_path.iterdir() if d.is_dir()]
    
    if not team_dirs:
        print(f"✗ No teams found in {extracted_path}")
        return {'status': 'failed', 'reason': 'no teams found'}
    
    print(f"\n{'='*60}")
    print(f"Token Extraction (Step 3)")
    print(f"{'='*60}")
    print(f"Extracted dir: {extracted_path}")
    print(f"Archive dir: {archive_path}")
    print(f"Output dir: {output_path}")
    print(f"Teams: {len(team_dirs)}")
    print(f"Workers: {workers}")
    print(f"{'='*60}")
    
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
                    print(f"\n✗ Error processing {team_name}: {e}")
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
    
    print(f"\n{'='*60}")
    print(f"Token Extraction Complete")
    print(f"{'='*60}")
    print(f"  Teams processed: {len(results)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")
    print(f"  Skipped: {len(skipped)}")
    print(f"  Total tokens: {total_tokens}")
    
    if failed:
        print(f"\nFailed teams:")
        for r in failed:
            print(f"  - {r['team']}: {r.get('reason', 'unknown error')}")
    
    if skipped:
        print(f"\nSkipped teams:")
        for r in skipped:
            print(f"  - {r['team']}: {r.get('reason', 'unknown reason')}")
    
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
    
    args = parser.parse_args()
    
    result = run(
        extracted_dir=args.extracted_dir,
        archive_dir=args.archive_dir,
        output_dir=args.output_dir,
        teams=args.teams,
        workers=args.workers,
        debug=args.debug
    )
    
    sys.exit(0 if result.get('status') == 'success' else 1)
