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
        print(f"✓ Output folder cleaned\n")
    
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
            
            # Create subfolder for this PDF type
            pdf_output_path = output_path / folder_name
            pdf_output_path.mkdir(parents=True, exist_ok=True)
            
            # Check if this is a datacard or faction-rules PDF
            is_datacard = 'datacard' in base_name.lower()
            is_faction_rules = 'faction-rule' in base_name.lower()
            
            # Track used filenames to avoid duplicates
            used_names = set()
            
            # For datacards, track consecutive pages with same operative name for front/back
            if is_datacard:
                # First pass: extract all operative names to detect front/back pairs
                operative_pages = []
                for page_num in range(len(pdf_document)):
                    page = pdf_document[page_num]
                    card_name = extract_card_name(page, is_datacard=True, team_name=team_name, pdf_base_name=base_name)
                    operative_pages.append((page_num, card_name))
                
                # Detect which operatives have front/back by finding consecutive same names
                operative_counts = {}
                for page_num, card_name in operative_pages:
                    if card_name:
                        operative_counts[card_name] = operative_counts.get(card_name, 0) + 1
            
            # For faction rules, track which pages are faction rule pages vs marker guide
            faction_rule_counter = 0
            
            # Extract each page
            for page_num in range(len(pdf_document)):
                # Get the page
                page = pdf_document[page_num]
                
                # Special handling for faction rules
                if is_faction_rules:
                    # Check if this is the marker/token guide page
                    text = page.get_text().upper()
                    if 'MARKER' in text and 'TOKEN' in text and 'GUIDE' in text:
                        output_filename = "markertoken-guide.jpg"
                    else:
                        # It's a faction rule page, number them sequentially
                        faction_rule_counter += 1
                        output_filename = f"faction-rule-{faction_rule_counter}.jpg"
                else:
                    # Try to extract card name from text
                    card_name = extract_card_name(page, is_datacard=is_datacard, team_name=team_name, pdf_base_name=base_name)
                    
                    # Create output filename
                    if card_name:
                        # For datacards, always add front/back suffix for consistency
                        if is_datacard:
                            # Check if this is first or second occurrence
                            occurrence = sum(1 for p, n in operative_pages[:page_num + 1] if n == card_name)
                            if occurrence == 1:
                                output_filename = f"{card_name}_front.jpg"
                            elif occurrence == 2:
                                output_filename = f"{card_name}_back.jpg"
                            else:
                                output_filename = f"{card_name}_{occurrence}.jpg"
                        else:
                            output_filename = f"{card_name}.jpg"
                        
                        # Check for duplicates (shouldn't happen with front/back logic, but just in case)
                        if output_filename in used_names:
                            output_filename = f"{base_name}-{page_num + 1}.jpg"
                        used_names.add(output_filename)
                    else:
                        # No card name extracted - this indicates a problem
                        print(f"    ⚠ Warning: Could not extract card name for page {page_num + 1}")
                        output_filename = f"{base_name}-{page_num + 1}.jpg"
                
                output_file = pdf_output_path / output_filename
                
                # Set the resolution (zoom factor)
                zoom = dpi / 72  # 72 is the default DPI
                mat = fitz.Matrix(zoom, zoom)
                
                # Render page to pixmap
                pix = page.get_pixmap(matrix=mat)
                
                # Save as JPG
                try:
                    pix.save(output_file)
                    print(f"  ✓ Saved: {folder_name}/{output_filename}")
                    total_pages += 1
                except Exception as save_error:
                    # If filename too long or has issues, try with fallback name
                    output_filename = f"{base_name}-{page_num + 1}.jpg"
                    output_file = pdf_output_path / output_filename
                    pix.save(output_file)
                    print(f"  ✓ Saved: {folder_name}/{output_filename} (fallback)")
                    total_pages += 1
            
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
