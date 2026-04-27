"""Extract token names from marker/token guide images using OCR.

This script uses OCR to read token names from the front image of markertoken guides.
"""

from PIL import Image
import pytesseract
import re
from pathlib import Path
import yaml


def extract_tokens_from_image(image_path: Path) -> list:
    """Extract token names from a marker/token guide image."""
    # Open image
    img = Image.open(image_path)
    
    # Perform OCR
    text = pytesseract.image_to_string(img)
    
    # First, join lines that might be split (but keep paragraph breaks)
    text_cleaned = re.sub(r'\n(?!\n)', ' ', text)
    text_cleaned = re.sub(r'\s+', ' ', text_cleaned)
    
    tokens = []
    seen = set()
    
    # Split by "token" and "marker" keywords to isolate names
    # This captures: "Name1 token Name2 marker" -> ["Name1", "token", "Name2", "marker", ...]
    parts = re.split(r'\s+(token|marker)\s+', text_cleaned, flags=re.IGNORECASE)
    
    # Process pairs: name followed by type
    for i in range(len(parts) - 1):
        if parts[i+1].lower() in ['token', 'marker']:
            # Get the name - it's in parts[i]
            name_part = parts[i].strip()
            
            # Skip if this is header text
            if not name_part or 'GUIDE' in name_part.upper() or 'CORSAIR' in name_part.upper():
                continue
            
            # Extract the last "phrase" (capitalized words, including apostrophes) from this part
            # Pattern: find sequences of capitalized words that may include apostrophes
            # Use a greedy pattern to capture multi-word names
            name_matches = re.findall(r"[A-Z][A-Za-z0-9']*(?:\s+(?:of\s+)?[A-Z][A-Za-z0-9']*)*", name_part)
            if name_matches:
                name = name_matches[-1].strip()  # Get the last match (closest to "token"/"marker")
                token_type = parts[i+1].lower()
                
                # Filter out very short or invalid names
                if len(name) > 2 and name.upper() not in ['TOKEN', 'MARKER', 'GUIDE', 'QO', 'A']:
                    name_lower = name.lower()
                    if name_lower not in seen:
                        seen.add(name_lower)
                        tokens.append({
                            'name': name,
                            'type': token_type
                        })
    
    return tokens


def find_all_markertoken_guides() -> list:
    """Find all markertoken-guide images across all teams."""
    output_v2_dir = Path("output_v2")
    
    # Search for all markertoken-guide_front.jpg files
    guide_files = []
    for faction_dir in output_v2_dir.iterdir():
        if faction_dir.is_dir():
            for team_dir in faction_dir.iterdir():
                if team_dir.is_dir():
                    faction_rules_dir = team_dir / "faction-rules"
                    if faction_rules_dir.exists():
                        guide_pattern = list(faction_rules_dir.glob("*-markertoken-guide_front.jpg"))
                        if guide_pattern:
                            team_slug = team_dir.name
                            guide_files.append((team_slug, guide_pattern[0]))
    
    return sorted(guide_files)


def main():
    """Extract tokens from all teams' marker guides."""
    print("Searching for markertoken-guide images...\n")
    
    guide_files = find_all_markertoken_guides()
    
    if not guide_files:
        print("No markertoken-guide images found!")
        return
    
    print(f"Found {len(guide_files)} markertoken-guide images\n")
    print("="*60)
    
    teams_data = {}
    total_tokens = 0
    
    for team_slug, image_path in guide_files:
        print(f"\n{team_slug}:")
        print(f"  {image_path}")
        
        tokens = extract_tokens_from_image(image_path)
        
        if tokens:
            teams_data[team_slug] = {'tokens': tokens}
            total_tokens += len(tokens)
            print(f"  ✓ Extracted {len(tokens)} tokens")
        else:
            print(f"  ⚠ No tokens extracted")
    
    print("\n" + "="*60)
    print(f"Total: {len(teams_data)} teams, {total_tokens} tokens")
    print("="*60)
    
    # Output as YAML
    yaml_output = yaml.dump({'teams': teams_data}, default_flow_style=False, allow_unicode=True, sort_keys=False)
    
    # Save to file
    output_path = Path("dev/extracted-tokens-ocr-reference.yaml")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(yaml_output)
    
    print(f"\nSaved to {output_path}")


if __name__ == '__main__':
    main()
