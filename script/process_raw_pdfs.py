import fitz  # PyMuPDF
import re
from pathlib import Path
import shutil
import yaml


def load_team_mapping():
    """Load team name mapping from YAML file.
    Returns a dict where keys are variants and values are canonical names.
    Also returns a reverse lookup where both canonical and variants map to canonical.
    """
    mapping_file = Path('team-mapping.yaml')
    if mapping_file.exists():
        with open(mapping_file, 'r') as f:
            config = yaml.safe_load(f)
            raw_mapping = config.get('team_names', {})
            
            # Flip the mapping: left side (key) is canonical, right side (value) is variant
            # Create bidirectional lookup: both canonical and variant map to canonical
            flipped_mapping = {}
            for canonical, variant in raw_mapping.items():
                flipped_mapping[variant] = canonical  # variant -> canonical
                flipped_mapping[canonical] = canonical  # canonical -> canonical (identity)
            
            return flipped_mapping
    return {}


def clean_filename(text):
    """Clean text to create a valid filename."""
    if not text:
        return None
    
    text = text.lower().strip()
    text = re.sub(r'[\s_]+', '-', text)
    text = re.sub(r'[^a-z0-9-]', '', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    
    return text if text else None


def identify_pdf_type(pdf_path):
    """
    Identify the team name and PDF type from the PDF content.
    Returns (team_name, pdf_type) or (None, None) if not identifiable.
    """
    try:
        pdf = fitz.open(pdf_path)
        
        # Check first page
        page = pdf[0]
        text_dict = page.get_text("dict")
        
        # Collect all text with sizes
        text_by_size = []
        for block in text_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        size = span["size"]
                        if text and len(text) > 3:
                            text_by_size.append((size, text.upper()))
        
        # Sort by size (largest first)
        text_by_size.sort(reverse=True, key=lambda x: x[0])
        
        # Extract team name and type
        team_name = None
        pdf_type = None
        
        # Identify PDF type first from headers
        for size, text in text_by_size[:30]:
            text_lower = text.lower()
            
            if 'operatives' == text_lower.strip():
                pdf_type = 'operatives'
                break
            elif 'faction equipment' in text_lower:
                pdf_type = 'equipment'
                break
            elif 'strategy ploy' in text_lower or 'strategic ploy' in text_lower:
                pdf_type = 'strategy-ploy'
                break
            elif 'firefight ploy' in text_lower:
                pdf_type = 'firefight-ploy'
                break
            elif 'faction rule' in text_lower:
                pdf_type = 'faction-rules'
                break
        
        # For datacards, look at the bottom of the page first (comma-separated metadata)
        all_text = page.get_text()
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        
        # Check if this is a datacard only if type not already determined
        if not pdf_type:
            is_likely_datacard = False
            for line in lines[-10:]:
                if any(keyword in line.upper() for keyword in ['RULES CONTINUE', 'APL', 'WOUNDS', 'SAVE', 'MOVE']):
                    is_likely_datacard = True
                    break
        else:
            is_likely_datacard = False
        
        # If looks like a datacard, search for team name in metadata
        if is_likely_datacard:
            pdf_type = 'datacards'
            
            # Look for comma-separated line with faction info (usually has 3+ commas)
            # The metadata line is ALL CAPS and contains faction keywords
            faction_keywords = ['IMPERIUM', 'CHAOS', 'AELDARI', 'TYRANIDS', 'ORKS', 
                              'T\'AU', 'NECRONS', 'LEAGUES OF VOTANN', 'GENESTEALER']
            
            for line in lines[-15:]:
                # Check if line is ALL CAPS (metadata) vs mixed case (ability description)
                if line.isupper() and ',' in line and line.count(',') >= 2:
                    # Additional check: should contain a faction keyword
                    if any(keyword in line for keyword in faction_keywords):
                        # This is likely the metadata line (e.g., "HEARTHKYN SALVAGER , LEAGUES OF VOTANN, LEADER, THEYN")
                        parts = [p.strip() for p in line.split(',')]
                        first_part = parts[0]
                        
                        # Check if first part contains role/character keywords - if so, extract just the team name
                        role_keywords = ['LEADER', 'OPERATIVE', 'WARRIOR', 'SERGEANT', 'THEYN', 
                                        'NOB', 'BOSS', 'PRIEST', 'TECH-PRIEST', 'TECHNOARCHEOLOGIST',
                                        'ARCHAEOPTER', 'SERVITOR', 'IMMORTAL', 'WRAITH', 'CRYPTEK']
                        
                        # Split first part into words
                        words = first_part.split()
                        
                        # If last word(s) are role keywords, exclude them
                        team_words = []
                        for word in words:
                            # Stop adding words if we hit a role keyword
                            if any(role in word.upper() for role in role_keywords):
                                break
                            team_words.append(word)
                        
                        # If we have at least 1-2 words left, use as team name
                        if len(team_words) >= 1:
                            team_name = clean_filename(' '.join(team_words))
                        elif len(words) >= 2:  # Fallback: use first part as-is if no roles found
                            team_name = clean_filename(first_part)
                        
                        if team_name:
                            break
        
        # For non-datacards, look for team name in large text
        if not team_name:
            # First try: look for team names near headers (equipment, ploys, faction rules, operatives)
            if pdf_type in ['equipment', 'strategy-ploy', 'firefight-ploy', 'faction-rules', 'operatives']:
                # For these types, team name is often size 12-18 text near the header
                for size, text in text_by_size[:20]:
                    # For operatives, look for larger text (size 16-20) that represents team name
                    if pdf_type == 'operatives' and 16 <= size <= 20:
                        skip_terms = ['archetypes', 'operatives', 'faction rule', 'faction rules']
                        if not any(skip in text.lower() for skip in skip_terms):
                            # Remove "KILL TEAM" suffix if present
                            text_cleaned = text.upper().replace('KILL TEAM', '').strip()
                            team_name = clean_filename(text_cleaned)
                            break
                    # For faction-rules, look for smaller text (size 10-13) which is the team name
                    # The rule name is typically larger (size 14+)
                    elif pdf_type == 'faction-rules' and 10 <= size <= 13:
                        skip_terms = ['faction rule', 'faction rules']
                        if not any(skip in text.lower() for skip in skip_terms) and len(text.split()) <= 5:
                            team_name = clean_filename(text)
                            break
                    # For other types (equipment, ploys), look for size 10-14 text
                    elif pdf_type not in ['operatives', 'faction-rules'] and 10 <= size <= 14 and len(text.split()) <= 3:
                        # Skip generic terms
                        skip_terms = ['faction equipment', 'strategy ploy', 'firefight ploy', 
                                     'faction rule', 'universal equipment', 'marker', 'token']
                        if not any(skip in text.lower() for skip in skip_terms):
                            # This looks like a team name
                            team_name = clean_filename(text)
                            break
            
            # Second try: look for multi-word phrases with team keywords
            if not team_name:
                potential_team_names = []
                
                for size, text in text_by_size[:40]:
                    text_lower = text.lower()
                    
                    # Skip if it's too short or too long
                    if len(text) < 8 or len(text) > 50:
                        continue
                    
                    # Skip generic headers
                    skip_generic = ['faction equipment', 'strategy ploy', 'firefight ploy', 
                                   'faction rule', 'datacard', 'marker', 'token', 'guide',
                                   'name', 'wounds', 'save', 'move', 'universal equipment',
                                   'rules continue']
                    if any(skip in text_lower for skip in skip_generic):
                        continue
                    
                    # Count words (2-3 word phrases are usually team names)
                    word_count = len(text.split())
                    
                    # For large text (size > 11), it's likely a team name if it's 2-3 words
                    if size > 11 and 2 <= word_count <= 4:
                        # Check if it contains common team keywords
                        team_keywords = ['salvager', 'krew', 'battleclade', 'deathwatch', 
                                        'canoptek', 'circle', 'hearthkyn', 'wrecka', 'astartes',
                                        'veteran', 'necron', 'admech', 'mechanicus']
                        if any(keyword in text_lower for keyword in team_keywords):
                            potential_team_names.append((size, text))
                
                # Pick the largest team name candidate
                if potential_team_names:
                    potential_team_names.sort(reverse=True, key=lambda x: x[0])
                    team_name = clean_filename(potential_team_names[0][1])
        
        pdf.close()
        
        return team_name, pdf_type
    
    except Exception as e:
        print(f"Error identifying {pdf_path}: {e}")
        return None, None


def process_raw_pdfs(raw_folder="input", base_output_folder="processed"):
    """
    Process PDFs from input folder recursively, identify their type, rename and organize them.
    """
    raw_path = Path(raw_folder)
    
    if not raw_path.exists():
        print(f"Raw folder not found: {raw_folder}")
        return
    
    pdf_files = list(raw_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {raw_folder}")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s) to process\n")
    
    # Load team name mapping
    team_mapping = load_team_mapping()
    
    # Create archive folders
    archive_folder = Path('archive')
    archive_folder.mkdir(parents=True, exist_ok=True)
    archive_failed_folder = archive_folder / 'failed'
    archive_failed_folder.mkdir(parents=True, exist_ok=True)
    
    # Group files by team
    files_by_team = {}
    unidentified_files = []
    
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")
        
        team_name, pdf_type = identify_pdf_type(pdf_file)
        
        if team_name and pdf_type:
            # Apply team name mapping if exists
            canonical_team_name = team_mapping.get(team_name, team_name)
            if canonical_team_name != team_name:
                print(f"  → Identified as: {team_name} - {pdf_type} (mapped to: {canonical_team_name})")
                team_name = canonical_team_name
            else:
                print(f"  → Identified as: {team_name} - {pdf_type}")
            
            if team_name not in files_by_team:
                files_by_team[team_name] = []
            
            files_by_team[team_name].append((pdf_file, pdf_type))
        else:
            print(f"  ✗ Could not identify (team: {team_name}, type: {pdf_type})")
            unidentified_files.append(pdf_file)
    
    # Archive unidentified files first
    if unidentified_files:
        print(f"\n{'='*60}")
        print("Archiving unidentified files...")
        print(f"{'='*60}\n")
        
        for pdf_file in unidentified_files:
            # Keep GUID name and move to failed folder
            archive_path = archive_failed_folder / pdf_file.name
            shutil.copy2(str(pdf_file), str(archive_path))
            print(f"  ✓ {pdf_file.name} → archived to _archive/failed/")
    
    # Move and rename files
    print(f"\n{'='*60}")
    print("Moving and renaming files...")
    print(f"{'='*60}\n")
    
    for team_name, files in files_by_team.items():
        team_folder = Path(base_output_folder) / team_name
        team_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"Team: {team_name.upper()}")
        
        for pdf_file, pdf_type in files:
            # Extract GUID from original filename using regex
            import re
            guid_pattern = r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})'
            guid_matches = re.findall(guid_pattern, pdf_file.name, re.IGNORECASE)
            guid = guid_matches[-1] if guid_matches else pdf_file.stem
            
            new_filename = f"{team_name}-{pdf_type}.pdf"
            new_path = team_folder / new_filename
            
            # Archive with team subfolder and GUID as filename
            team_archive_folder = archive_folder / team_name
            team_archive_folder.mkdir(parents=True, exist_ok=True)
            archive_filename = f"{guid}.pdf"
            archive_path = team_archive_folder / archive_filename
            
            # Only archive if not already archived (avoid duplicates)
            if not archive_path.exists():
                shutil.copy2(str(pdf_file), str(archive_path))
            
            # Remove existing file if it exists (to allow overwrites)
            if new_path.exists():
                new_path.unlink()
                print(f"  ✓ {pdf_file.name} → {new_filename} (overwritten)")
            else:
                print(f"  ✓ {pdf_file.name} → {new_filename}")
            
            # Move and rename
            shutil.move(str(pdf_file), str(new_path))
        
        print()
    
    print(f"{'='*60}")
    print(f"Processing complete! Organized {len(pdf_files)} files into {len(files_by_team)} team(s)")
    print(f"Archived originals to: {archive_folder}")
    print(f"{'='*60}")


if __name__ == "__main__":
    process_raw_pdfs()
