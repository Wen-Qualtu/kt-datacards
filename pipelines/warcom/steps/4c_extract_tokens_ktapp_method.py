"""
Step 4c: Extract Tokens Using kt-app Method

This script uses the kt-app TokenExtractor class directly on warcom PDFs
to extract and process tokens in one go, avoiding name mismatch issues.

Based on: script/tools/extract_tokens.py
Adapted for: warcom pipeline PDFs

Usage:
    python pipelines/warcom/steps/4c_extract_tokens_ktapp_method.py --team farstalker-kinband
    python pipelines/warcom/steps/4c_extract_tokens_ktapp_method.py --all
"""

import argparse
import sys
from pathlib import Path
import yaml

# Add script directory to path to import TokenExtractor
script_dir = Path(__file__).parents[3] / 'script'
sys.path.insert(0, str(script_dir))

from tools.extract_tokens import TokenExtractor


def load_team_config():
    """Load team configuration"""
    config_path = Path('config/team-config.yaml')
    with open(config_path) as f:
        return yaml.safe_load(f)


def extract_tokens_for_team(team_slug: str, base_dir: Path = None):
    """
    Extract tokens for a team using kt-app method.
    
    Args:
        team_slug: Team name (e.g., 'farstalker-kinband')
        base_dir: Base directory (default: current directory)
    """
    if base_dir is None:
        base_dir = Path.cwd()
    
    # Find the faction rules PDF (contains token guide)
    pdf_path = base_dir / 'layers' / 'warcom' / 'extracted' / team_slug / 'pdfs' / f'{team_slug}-faction-rules.pdf'
    
    if not pdf_path.exists():
        print(f"  ⚠ PDF not found: {pdf_path}")
        return False
    
    # Output directory (same as Step 4b for consistency)
    output_dir = base_dir / 'output' / team_slug / 'tokens'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load team config for token shapes
    config = load_team_config()
    teams = config.get('teams', {})
    team_data = teams.get(team_slug)
    
    if not team_data:
        print(f"  ⚠ Team '{team_slug}' not found in config")
        return False
    
    tokens_config = team_data.get('tokens', [])
    if not tokens_config:
        print(f"  ⚠ No tokens configured for '{team_slug}'")
        return False
    
    # Create TokenExtractor (kt-app class)
    extractor = TokenExtractor(
        output_base_dir=output_dir.parent.parent,  # Will create team/tokens subdirs
        name_match_max_distance=300.0
    )
    
    print(f"  Extracting tokens from: {pdf_path.name}")
    
    # Find marker guide pages in PDF
    marker_pages = extractor.find_marker_guide_pages(pdf_path)
    if not marker_pages:
        print(f"  ⚠ No marker/token guide pages found")
        return False
    
    print(f"  Found {len(marker_pages)} marker/token guide page(s)")
    
    all_extracted = []
    
    # Extract from each marker page
    for page_num in marker_pages:
        print(f"  Processing page {page_num + 1}...")
        
        # Use kt-app's extract_tokens_auto with PDF rendering
        extracted = extractor.extract_tokens_auto(
            pdf_page_info={
                'pdf_path': pdf_path,
                'page_num': page_num
            },
            output_dir=output_dir,
            debug=False,  # Set to True to see detection overlays
            skip_header_percent=15.0,
            extract_names=True
        )
        
        all_extracted.extend(extracted)
    
    # Report results
    print(f"  ✓ Extracted {len(all_extracted)} tokens")
    for token_info in all_extracted:
        name = token_info.get('name', 'unknown')
        shape = token_info.get('shape', 'unknown')
        filename = token_info.get('path', Path('')).name
        print(f"    - {name} ({shape}) → {filename}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Extract tokens using kt-app method (Step 4c)'
    )
    parser.add_argument('--team', type=str, help='Team slug to process')
    parser.add_argument('--all', action='store_true', help='Process all teams')
    parser.add_argument('--base-dir', type=Path, help='Base directory')
    args = parser.parse_args()
    
    base_dir = args.base_dir or Path.cwd()
    
    print("=" * 80)
    print("Step 4c: Extract Tokens Using kt-app Method")
    print("=" * 80)
    print("Using kt-app TokenExtractor directly on warcom PDFs")
    print("")
    
    if args.team:
        print(f"Processing team: {args.team}")
        success = extract_tokens_for_team(args.team, base_dir=base_dir)
        if not success:
            print(f"  ✗ Failed to extract tokens for {args.team}")
            return 1
    elif args.all:
        print("Processing all teams with token configs...")
        config = load_team_config()
        teams = config.get('teams', {})
        
        success_count = 0
        fail_count = 0
        
        for team_slug, team_data in sorted(teams.items()):
            if not team_data.get('tokens'):
                continue
            
            print(f"\nProcessing team: {team_slug}")
            if extract_tokens_for_team(team_slug, base_dir=base_dir):
                success_count += 1
            else:
                fail_count += 1
        
        print("")
        print(f"Teams processed: {success_count} succeeded, {fail_count} failed")
    else:
        parser.print_help()
        return 1
    
    print("")
    print("=" * 80)
    print("TOKEN EXTRACTION COMPLETE (kt-app method)")
    print("=" * 80)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
