"""Extract token names and types from PDF markertoken guides using PyMuPDF.

This script reads the faction-rules PDFs to extract token information with
proper marker/token classification, organized by team.
"""

import fitz  # PyMuPDF
import re
import yaml
from pathlib import Path
from typing import Dict, Set, Tuple


def find_faction_rules_pdf(team_dir: Path) -> Path:
    """Find the faction-rules PDF for a team."""
    # Look in processed directory first
    processed_pdf = Path("layers/kt-app/processed") / team_dir.name / f"{team_dir.name}-faction-rules.pdf"
    if processed_pdf.exists():
        return processed_pdf
    
    # Look in output_v2 directory
    for faction in ["imperium", "chaos", "xenos"]:
        output_pdf = Path("output_v2") / faction / team_dir.name / "faction-rules" / f"{team_dir.name}-faction-rules.pdf"
        if output_pdf.exists():
            return output_pdf
    
    return None


def find_marker_guide_page(pdf_path: Path) -> int:
    """Find the page number containing the MARKER/TOKEN GUIDE."""
    try:
        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            # Look for the marker/token guide header
            if re.search(r'MARKER[\s/]+TOKEN\s+GUIDE', text, re.IGNORECASE):
                return page_num
        return None
    except Exception as e:
        print(f"  Error reading PDF: {e}")
        return None


def extract_tokens_from_pdf_page(pdf_path: Path, page_num: int) -> list:
    """Extract token names and types from the marker/token guide page."""
    tokens = []
    
    try:
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        text = page.get_text()
        
        # Use the SAME extraction pattern that worked in the original script
        # This preserves the exact text without filtering keywords
        pattern = r'\b([A-Z][A-Za-z0-9\s\'-]+?)\s+(marker|token)\b'
        matches = re.findall(pattern, text, re.IGNORECASE)
        
        for name, token_type in matches:
            tokens.append({
                'name': name.strip(),
                'type': token_type.lower()
            })
        
    except Exception as e:
        print(f"  Error extracting tokens: {e}")
    
    return tokens


def get_all_teams_with_tokens() -> list:
    """Get all teams that have token bags in TTS output."""
    tts_objects_dir = Path("tts_objects")
    teams_with_tokens = []
    
    for team_dir in tts_objects_dir.iterdir():
        if not team_dir.is_dir():
            continue
        
        # Check if team has token bags
        has_tokenbag = list(team_dir.glob("*tokenbag.json"))
        has_cardbox_tokens = list(team_dir.glob("*Cards.json"))
        
        if has_tokenbag or has_cardbox_tokens:
            teams_with_tokens.append(team_dir.name)
    
    return sorted(teams_with_tokens)


def main():
    """Extract tokens from all teams' PDFs."""
    print("Finding teams with tokens...\n")
    
    teams = get_all_teams_with_tokens()
    print(f"Found {len(teams)} teams with tokens\n")
    print("="*60)
    
    teams_data = {}
    total_tokens = 0
    success_count = 0
    fail_count = 0
    
    for team_slug in teams:
        print(f"\n{team_slug}:")
        
        # Find the PDF
        team_dir = Path("tts_objects") / team_slug
        pdf_path = find_faction_rules_pdf(team_dir)
        
        if not pdf_path:
            print(f"  ✗ PDF not found")
            fail_count += 1
            continue
        
        print(f"  Found: {pdf_path}")
        
        # Find the marker guide page
        page_num = find_marker_guide_page(pdf_path)
        if page_num is None:
            print(f"  ✗ No marker/token guide page found")
            fail_count += 1
            continue
        
        print(f"  Marker guide on page {page_num + 1}")
        
        # Extract tokens
        tokens = extract_tokens_from_pdf_page(pdf_path, page_num)
        
        if tokens:
            teams_data[team_slug] = {'tokens': tokens}
            total_tokens += len(tokens)
            success_count += 1
            print(f"  ✓ Extracted {len(tokens)} tokens")
        else:
            print(f"  ⚠ No tokens extracted")
            fail_count += 1
    
    print("\n" + "="*60)
    print(f"Success: {success_count} teams, {total_tokens} tokens")
    print(f"Failed: {fail_count} teams")
    print("="*60)
    
    # Output as YAML
    yaml_output = yaml.dump({'teams': teams_data}, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Save to file
    output_path = Path("dev/extracted-tokens-pdf-reference.yaml")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(yaml_output)
    
    print(f"\nSaved to {output_path}")


if __name__ == '__main__':
    main()
