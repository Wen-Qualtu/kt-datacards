import fitz  # PyMuPDF
import re
from pathlib import Path
import shutil


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
        
        # Look through the text to find team name and type
        for size, text in text_by_size[:30]:  # Check top 30 largest text
            text_lower = text.lower()
            
            # Identify PDF type from headers
            if 'faction equipment' in text_lower:
                pdf_type = 'equipment'
            elif 'strategy ploy' in text_lower or 'strategic ploy' in text_lower:
                pdf_type = 'strategy-ploy'
            elif 'firefight ploy' in text_lower:
                pdf_type = 'firefight-ploy'
            elif 'faction rule' in text_lower:
                pdf_type = 'faction-rules'
            elif 'datacard' in text_lower:
                pdf_type = 'datacards'
            
            # Extract team name (usually a large text that's not a generic header)
            if not team_name and len(text) > 5 and len(text) < 30:
                skip_generic = ['faction equipment', 'strategy ploy', 'firefight ploy', 
                               'faction rule', 'datacard', 'marker', 'token', 'guide',
                               'name', 'wounds', 'save', 'move']
                if not any(skip in text_lower for skip in skip_generic):
                    # Check if it looks like a team name
                    if size > 10 or (size > 8 and pdf_type):  # Large text is likely team name
                        team_name = clean_filename(text)
        
        # For datacards, check bottom of page for team name (small text)
        if pdf_type == 'datacards' and not team_name:
            # Get all text and look at the bottom section
            all_text = page.get_text()
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            
            # Check last 20 lines for team name
            for line in lines[-20:]:
                line_lower = line.lower()
                if len(line) > 5 and len(line) < 30:
                    # Common keywords that appear with team name in datacards
                    if any(keyword in line_lower for keyword in ['deathwatch', 'salvagers', 'wrecka', 'battleclade']):
                        team_name = clean_filename(line.split(',')[0].strip())  # Take first part before comma
                        break
        
        pdf.close()
        
        return team_name, pdf_type
    
    except Exception as e:
        print(f"Error identifying {pdf_path}: {e}")
        return None, None


def process_raw_pdfs(raw_folder="input/_raw", base_output_folder="input"):
    """
    Process PDFs from raw folder, identify their type, rename and organize them.
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
    
    # Group files by team
    files_by_team = {}
    
    for pdf_file in pdf_files:
        print(f"Processing: {pdf_file.name}")
        
        team_name, pdf_type = identify_pdf_type(pdf_file)
        
        if team_name and pdf_type:
            print(f"  → Identified as: {team_name} - {pdf_type}")
            
            if team_name not in files_by_team:
                files_by_team[team_name] = []
            
            files_by_team[team_name].append((pdf_file, pdf_type))
        else:
            print(f"  ✗ Could not identify (team: {team_name}, type: {pdf_type})")
    
    # Move and rename files
    print(f"\n{'='*60}")
    print("Moving and renaming files...")
    print(f"{'='*60}\n")
    
    for team_name, files in files_by_team.items():
        team_folder = Path(base_output_folder) / team_name
        team_folder.mkdir(parents=True, exist_ok=True)
        
        print(f"Team: {team_name.upper()}")
        
        for pdf_file, pdf_type in files:
            new_filename = f"{team_name}-{pdf_type}.pdf"
            new_path = team_folder / new_filename
            
            # Move and rename
            shutil.move(str(pdf_file), str(new_path))
            print(f"  ✓ {pdf_file.name} → {new_filename}")
        
        print()
    
    print(f"{'='*60}")
    print(f"Processing complete! Organized {len(pdf_files)} files into {len(files_by_team)} team(s)")
    print(f"{'='*60}")


if __name__ == "__main__":
    process_raw_pdfs()
