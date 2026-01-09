import fitz  # PyMuPDF
import os
import re
import shutil
from pathlib import Path


def clean_filename(text):
    """
    Clean text to create a valid filename.
    Converts to lowercase, replaces spaces with hyphens, removes special characters.
    """
    if not text:
        return None
    
    # Convert to lowercase and strip whitespace
    text = text.lower().strip()
    
    # Replace spaces and underscores with hyphens
    text = re.sub(r'[\s_]+', '-', text)
    
    # Remove any characters that aren't alphanumeric or hyphens
    text = re.sub(r'[^a-z0-9-]', '', text)
    
    # Remove multiple consecutive hyphens
    text = re.sub(r'-+', '-', text)
    
    # Remove leading/trailing hyphens
    text = text.strip('-')
    
    return text if text else None


def extract_card_name(page, is_datacard=False, team_name=None, pdf_base_name=None):
    """
    Try to extract the card name from the page text using font size.
    Returns the cleaned name or None if not found.
    
    Args:
        is_datacard: If True, looks for operative names in the header (largest text)
        team_name: The team name to skip when extracting card names
        pdf_base_name: The PDF base name to skip when extracting card names
    """
    try:
        # Use font size detection for all card types
        text_dict = page.get_text("dict")
        
        # Collect all text with their sizes
        text_candidates = []
        
        for block in text_dict["blocks"]:
            if block["type"] == 0:  # Text block
                for line in block["lines"]:
                    for span in line["spans"]:
                        text = span["text"].strip()
                        size = span["size"]
                        
                        if len(text) > 3:  # Skip very short text
                            text_candidates.append((text, size))
        
        if not text_candidates:
            return None
        
        # Sort by size (largest first)
        text_candidates.sort(key=lambda x: x[1], reverse=True)
        
        # Generic terms to skip
        skip_terms = [
            'rules continue', 'wounds', 'save', 'move', 'apl',
            'strategy ploy', 'strategic ploy', 'tactical ploy',
            'firefight ploy', 'firefight', 
            'faction equipment', 'equipment',
            'faction rules', 'datacard', 'datacards',
            'hit', 'dmg', 'name', 'atk'
        ]
        
        # For non-datacards, add team name to skip terms (datacards may have team prefix in operative names)
        if not is_datacard:
            if team_name:
                skip_terms.extend([team_name.lower(), team_name.replace('-', ' ').lower()])
            if pdf_base_name:
                skip_terms.extend([pdf_base_name.lower(), pdf_base_name.replace('-', ' ').lower()])
        
        # Look through largest text first
        for text, size in text_candidates[:20]:  # Check top 20 largest text
            text_lower = text.lower()
            
            # Skip if too short or too long
            if len(text) < 5 or len(text) > 50:
                continue
            
            # Team name filtering - only skip if text IS EXACTLY the team name
            text_normalized = text_lower.replace(' ', '').replace('-', '')
            if team_name:
                team_normalized = team_name.lower().replace(' ', '').replace('-', '')
                if text_normalized == team_normalized:
                    continue
            if pdf_base_name:
                pdf_normalized = pdf_base_name.lower().replace(' ', '').replace('-', '')
                if text_normalized == pdf_normalized:
                    continue
            
            # Skip generic headers
            if any(skip in text_lower for skip in skip_terms):
                continue
            
            # For datacards, we want the absolute largest (usually size 13+)
            # For other cards, we want large text (usually size 8-12)
            if is_datacard and size < 10:
                continue
            elif not is_datacard and size < 7:
                continue
            
            # Check if it looks like a proper card name
            # Should have reasonable uppercase ratio and not contain special chars that indicate rules text
            if ':' in text or '(' in text or ')' in text:
                continue
            
            cleaned = clean_filename(text)
            if cleaned and len(cleaned) > 4:
                return cleaned
        
        return None
    
    except Exception as e:
        print(f"    Warning: Could not extract text: {e}")
        return None


def extract_pdf_pages_to_jpg(input_folder, output_folder, dpi=300, clean_output=True):
    """
    Extract each page from PDFs in input_folder and save as JPG in output_folder.
    Creates subfolders based on PDF names and tries to extract card names.
    
    Args:
        input_folder: Path to folder containing PDF files
        output_folder: Path to folder where JPG files will be saved
        dpi: Resolution for the output images (default: 300)
        clean_output: Whether to clean the output folder before extraction (default: True)
    """
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    
    # Get team name from the folder structure
    team_name = input_path.name
    
    # Clean output folder if requested
    if clean_output and output_path.exists():
        print(f"Cleaning output folder: {output_folder}")
        shutil.rmtree(output_path)
        print(f"OK Output folder cleaned\n")
    
    # Get all PDF files in the input folder
    pdf_files = list(input_path.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {input_folder}")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s)")
    
    total_pages = 0
    
    for pdf_file in pdf_files:
        print(f"\nProcessing: {pdf_file.name}")
        
        try:
            # Open the PDF
            pdf_document = fitz.open(pdf_file)
            
            # Get the base name without extension and clean it for folder name
            base_name = pdf_file.stem
            
            # Remove team name prefix from base_name if present
            # e.g., "hearthkyn-salvager-datacards" -> "datacards"
            if base_name.startswith(team_name + '-'):
                base_name = base_name[len(team_name) + 1:]
            
            # Convert singular to plural for folder names (e.g., strategy-ploy -> strategy-ploys)
            folder_name = base_name.replace('-', ' ').strip()
            if not folder_name.endswith('s') and folder_name.split()[-1] not in ['rules', 'equipment']:
                # Make plural (simple approach)
                # For words ending in 'y' preceded by a consonant, replace with 'ies'
                # For words ending in 'y' preceded by a vowel (like 'ploy'), just add 's'
                if folder_name.endswith('y') and len(folder_name) > 1 and folder_name[-2] not in 'aeiou':
                    folder_name = folder_name[:-1] + 'ies'
                else:
                    folder_name += 's'
            folder_name = folder_name.replace(' ', '-')
            
            # Create subfolder for this PDF type (without team name prefix)
            pdf_output_path = output_path / folder_name
            pdf_output_path.mkdir(parents=True, exist_ok=True)
            
            # Check if this is a datacard or faction-rules PDF
            is_datacard = 'datacard' in base_name.lower()
            is_faction_rules = 'faction-rule' in base_name.lower()
            
            # Track used filenames to avoid duplicates
            used_names = set()
            
            # First pass: analyze all pages to detect front/back relationships
            card_pages = []
            skip_next_page = False
            
            for page_num in range(len(pdf_document)):
                if skip_next_page:
                    skip_next_page = False
                    continue
                
                page = pdf_document[page_num]
                text = page.get_text().upper()
                
                # Check if this page continues on the other side
                has_continuation = 'CONTINUES ON OTHER SIDE' in text or 'CONTINUES ON THE OTHER SIDE' in text or 'RULES CONTINUE ON OTHER SIDE' in text
                
                # Extract card name
                card_name = None
                
                if is_faction_rules:
                    # Special handling for faction rules
                    if 'MARKER' in text and 'TOKEN' in text and 'GUIDE' in text:
                        card_name = "markertoken-guide"
                    else:
                        # Try to extract the faction rule name (usually size 14 text)
                        text_dict = page.get_text("dict")
                        text_by_size = []
                        for block in text_dict["blocks"]:
                            if block["type"] == 0:
                                for line in block["lines"]:
                                    for span in line["spans"]:
                                        t = span["text"].strip()
                                        size = span["size"]
                                        if t and len(t) > 3:
                                            text_by_size.append((size, t.upper()))
                        text_by_size.sort(reverse=True, key=lambda x: x[0])
                        
                        # Look for the rule name (typically size 14, after "FACTION RULE" header)
                        for size, t in text_by_size[:15]:
                            if 13 <= size <= 15 and t not in ['FACTION RULE', 'FACTION RULES', team_name.upper().replace('-', ' ')]:
                                # Skip if it's too short or contains generic words
                                if len(t) >= 4 and 'RULE' not in t:
                                    card_name = clean_filename(t)
                                    break
                else:
                    card_name = extract_card_name(page, is_datacard=is_datacard, team_name=team_name, pdf_base_name=base_name)
                
                # Determine if this card has a back side
                has_back = False
                if has_continuation and page_num + 1 < len(pdf_document):
                    has_back = True
                    skip_next_page = True  # Skip the next page in this loop as it's the back
                elif is_datacard:
                    # For datacards, check if next page has same name
                    if page_num + 1 < len(pdf_document):
                        next_page = pdf_document[page_num + 1]
                        next_card_name = extract_card_name(next_page, is_datacard=True, team_name=team_name, pdf_base_name=base_name)
                        if next_card_name == card_name:
                            has_back = True
                            skip_next_page = True
                
                card_pages.append({
                    'page_num': page_num,
                    'card_name': card_name,
                    'has_back': has_back
                })
            
            # For faction rules, track which pages are faction rule pages vs marker guide
            faction_rule_counter = 0
            
            # Second pass: extract pages with proper naming
            page_index = 0
            while page_index < len(card_pages):
                card_info = card_pages[page_index]
                page_num = card_info['page_num']
                card_name = card_info['card_name']
                has_back = card_info['has_back']
                
                # Get the page
                page = pdf_document[page_num]
                
                # Generate filename
                if is_faction_rules and not card_name:
                    # It's a faction rule page without a name, number them sequentially
                    faction_rule_counter += 1
                    base_filename = f"faction-rule-{faction_rule_counter}"
                    
                    if has_back:
                        output_filename_front = f"{base_filename}_front.jpg"
                        output_filename_back = f"{base_filename}_back.jpg"
                    else:
                        output_filename_front = f"{base_filename}_front.jpg"
                        output_filename_back = None
                elif card_name:
                    base_filename = card_name
                    
                    if has_back:
                        output_filename_front = f"{base_filename}_front.jpg"
                        output_filename_back = f"{base_filename}_back.jpg"
                    else:
                        output_filename_front = f"{base_filename}_front.jpg"
                        output_filename_back = None
                else:
                    # No card name extracted - this indicates a problem
                    print(f"    ⚠ Warning: Could not extract card name for page {page_num + 1}")
                    output_filename_front = f"{base_name}-{page_num + 1}.jpg"
                    output_filename_back = None
                
                # Save front page
                output_file = pdf_output_path / output_filename_front
                zoom = dpi / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                
                # Save as JPG
                try:
                    pix.save(output_file)
                    print(f"  OK Saved: {folder_name}/{output_filename_front}")
                    total_pages += 1
                except Exception as save_error:
                    # If filename too long or has issues, try with fallback name
                    output_filename_front = f"{base_name}-{page_num + 1}.jpg"
                    output_file = pdf_output_path / output_filename_front
                    pix.save(output_file)
                    print(f"  OK Saved: {folder_name}/{output_filename_front} (fallback)")
                    total_pages += 1
                
                # Save back page if it exists
                if output_filename_back and has_back:
                    back_page_num = page_num + 1
                    if back_page_num < len(pdf_document):
                        back_page = pdf_document[back_page_num]
                        back_pix = back_page.get_pixmap(matrix=mat)
                        back_output_file = pdf_output_path / output_filename_back
                        
                        try:
                            back_pix.save(back_output_file)
                            print(f"  OK Saved: {folder_name}/{output_filename_back}")
                            total_pages += 1
                        except Exception as save_error:
                            # If filename too long or has issues, try with fallback name
                            output_filename_back = f"{base_name}-{back_page_num + 1}.jpg"
                            back_output_file = pdf_output_path / output_filename_back
                            back_pix.save(back_output_file)
                            print(f"  OK Saved: {folder_name}/{output_filename_back} (fallback)")
                            total_pages += 1
                
                page_index += 1
            
            # Close the PDF
            pdf_document.close()
            
        except Exception as e:
            print(f"  ✗ Error processing {pdf_file.name}: {e}")
    
    print(f"\n{'='*50}")
    print(f"Extraction complete! {total_pages} pages saved to {output_folder}")
    print(f"{'='*50}")


if __name__ == "__main__":
    # Process all team folders in the input directory
    input_base = Path("input")
    output_base = Path("output")
    
    # Get all team folders (subdirectories in input/) - skip _raw folder
    team_folders = [d for d in input_base.iterdir() if d.is_dir() and d.name != '_raw']
    
    if not team_folders:
        print("No team folders found in input/")
    else:
        print(f"Found {len(team_folders)} team folder(s): {', '.join([d.name for d in team_folders])}\n")
        
        for team_folder in team_folders:
            team_name = team_folder.name
            input_folder = input_base / team_name
            output_folder = output_base / team_name
            
            print(f"{'='*60}")
            print(f"Processing team: {team_name.upper()}")
            print(f"{'='*60}\n")
            
            # Extract pages for this team
            extract_pdf_pages_to_jpg(str(input_folder), str(output_folder))
