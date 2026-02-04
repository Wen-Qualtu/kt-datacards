"""
Test script for icon extraction from PDFs.

Tests:
1. Extract team icon from page 1 (for card backsides) - both portrait and landscape areas
2. Identify and extract team icon from "KILL TEAM" page (for token bag)
"""
import cv2
import fitz  # PyMuPDF
import numpy as np
from pathlib import Path


def find_kill_team_page(pdf_path: Path) -> int:
    """
    Find the page with large "KILL TEAM" text (operatives list page).
    
    This page has:
    - Team name followed by "KILL TEAM" in large text
    - Dark background
    - Operative list
    
    Args:
        pdf_path: Path to team PDF
    
    Returns:
        Page number (0-indexed) or -1 if not found
    """
    try:
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            
            # Get text with font information
            text_dict = page.get_text("dict")
            
            # Look for large text containing "KILL TEAM"
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:  # Text block
                    for line in block.get("lines", []):
                        # Check if line has large font size (typically > 20)
                        for span in line.get("spans", []):
                            text = span.get("text", "").upper()
                            size = span.get("size", 0)
                            
                            # Look for "KILL TEAM" in large text (size > 20)
                            if "KILL TEAM" in text and size > 20:
                                print(f"  Found 'KILL TEAM' on page {page_num + 1} (size: {size:.1f})")
                                print(f"    Text: {text[:100]}...")
                                doc.close()
                                return page_num
        
        doc.close()
        print("  'KILL TEAM' page not found")
        return -1
        
    except Exception as e:
        print(f"  ERROR: {e}")
        return -1


def extract_page1_icons(pdf_path: Path, output_dir: Path, team_name: str):
    """
    Extract team icons from page 1 for card backsides.
    
    Extracts:
    - Portrait icon area (green box in screenshot)
    - Landscape icon area (blue box in screenshot)
    
    Args:
        pdf_path: Path to team PDF
        output_dir: Directory to save extracted icons
        team_name: Team slug name
    """
    try:
        doc = fitz.open(pdf_path)
        if len(doc) == 0:
            print("  ERROR: PDF has no pages")
            return
        
        page = doc[0]
        
        # Render page at high DPI for visualization
        mat = fitz.Matrix(2.0, 2.0)  # 144 DPI
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        page_width = pix.width
        page_height = pix.height
        
        print(f"  Page 1 dimensions: {page_width}x{page_height}")
        
        # Define extraction areas (as percentage of page dimensions)
        # Portrait icon (top-left, roughly square)
        portrait_x1 = int(page_width * 0.05)
        portrait_y1 = int(page_height * 0.05)
        portrait_x2 = int(page_width * 0.25)
        portrait_y2 = int(page_height * 0.25)
        
        # Landscape icon (top-left, wider)
        landscape_x1 = int(page_width * 0.05)
        landscape_y1 = int(page_height * 0.05)
        landscape_x2 = int(page_width * 0.30)
        landscape_y2 = int(page_height * 0.20)
        
        # Draw boxes on visualization
        vis_img = img.copy()
        cv2.rectangle(vis_img, (portrait_x1, portrait_y1), (portrait_x2, portrait_y2), (0, 255, 0), 3)  # Green
        cv2.rectangle(vis_img, (landscape_x1, landscape_y1), (landscape_x2, landscape_y2), (255, 0, 0), 3)  # Blue
        
        # Add labels
        cv2.putText(vis_img, "Portrait", (portrait_x1, portrait_y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 2)
        cv2.putText(vis_img, "Landscape", (landscape_x1, landscape_y2 + 40), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 0, 0), 2)
        
        # Save visualization
        vis_path = output_dir / f"{team_name}_page1_visualization.png"
        cv2.imwrite(str(vis_path), vis_img)
        print(f"  ✓ Saved visualization: {vis_path.name}")
        
        # Extract and save portrait icon
        portrait_icon = img[portrait_y1:portrait_y2, portrait_x1:portrait_x2]
        portrait_path = output_dir / f"{team_name}_icon_portrait.jpg"
        cv2.imwrite(str(portrait_path), portrait_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"  ✓ Extracted portrait icon: {portrait_icon.shape[1]}x{portrait_icon.shape[0]} -> {portrait_path.name}")
        
        # Extract and save landscape icon
        landscape_icon = img[landscape_y1:landscape_y2, landscape_x1:landscape_x2]
        landscape_path = output_dir / f"{team_name}_icon_landscape.jpg"
        cv2.imwrite(str(landscape_path), landscape_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"  ✓ Extracted landscape icon: {landscape_icon.shape[1]}x{landscape_icon.shape[0]} -> {landscape_path.name}")
        
        doc.close()
        
    except Exception as e:
        print(f"  ERROR: {e}")


def extract_token_bag_icon(pdf_path: Path, output_dir: Path, team_name: str):
    """
    Extract team icon from "KILL TEAM" operatives page for token bag.
    
    Args:
        pdf_path: Path to team PDF
        output_dir: Directory to save extracted icon
        team_name: Team slug name
    """
    try:
        # Find the correct page
        page_num = find_kill_team_page(pdf_path)
        
        if page_num == -1:
            print("  Cannot extract token bag icon - page not found")
            return
        
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        
        # Render page at high DPI for visualization
        mat = fitz.Matrix(2.0, 2.0)  # 144 DPI
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        
        page_width = pix.width
        page_height = pix.height
        
        print(f"  Page {page_num + 1} dimensions: {page_width}x{page_height}")
        
        # Define extraction area for token bag icon
        # Icon is typically in left margin, centered vertically in a box
        icon_x1 = int(page_width * 0.05)
        icon_y1 = int(page_height * 0.25)
        icon_x2 = int(page_width * 0.25)
        icon_y2 = int(page_height * 0.55)
        
        # Draw box on visualization
        vis_img = img.copy()
        cv2.rectangle(vis_img, (icon_x1, icon_y1), (icon_x2, icon_y2), (0, 255, 0), 3)  # Green
        
        # Add label
        cv2.putText(vis_img, "Token Bag Icon", (icon_x1, icon_y1 - 10), 
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 255, 0), 2)
        
        # Add corner dots
        cv2.circle(vis_img, (icon_x1, icon_y1), 10, (255, 0, 0), -1)  # Top-left
        cv2.circle(vis_img, (icon_x2, icon_y1), 10, (255, 0, 0), -1)  # Top-right
        cv2.circle(vis_img, (icon_x1, icon_y2), 10, (255, 0, 0), -1)  # Bottom-left
        cv2.circle(vis_img, (icon_x2, icon_y2), 10, (255, 0, 0), -1)  # Bottom-right
        
        # Save visualization
        vis_path = output_dir / f"{team_name}_page{page_num + 1}_token_visualization.png"
        cv2.imwrite(str(vis_path), vis_img)
        print(f"  ✓ Saved visualization: {vis_path.name}")
        
        # Extract and save token bag icon
        token_icon = img[icon_y1:icon_y2, icon_x1:icon_x2]
        token_path = output_dir / f"{team_name}_icon_token_bag.jpg"
        cv2.imwrite(str(token_path), token_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"  ✓ Extracted token bag icon: {token_icon.shape[1]}x{token_icon.shape[0]} -> {token_path.name}")
        
        doc.close()
        
    except Exception as e:
        print(f"  ERROR: {e}")


if __name__ == '__main__':
    # Test teams - expanded list to verify page detection
    test_teams = [
        ('angels-of-death', Path('layers/archive/angels-of-death/warcom')),
        ('elucidian-starstriders', Path('layers/archive/elucidian-starstriders/warcom')),
        ('hunter-clade', Path('layers/archive/hunter-clade/warcom')),
        ('pathfinders', Path('layers/archive/pathfinders/warcom')),
        ('warpcoven', Path('layers/archive/warpcoven/warcom')),
        ('kommandos', Path('layers/archive/kommandos/warcom')),
    ]
    
    output_dir = Path('dev')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 60)
    print("Icon Extraction Test - Page Detection")
    print("=" * 60)
    
    for team_name, team_dir in test_teams:
        print(f"\n{team_name}:")
        
        # Find PDF
        pdfs = list(team_dir.glob('*.pdf'))
        if not pdfs:
            print(f"  ERROR: No PDF found in {team_dir}")
            continue
        
        pdf_path = pdfs[0]
        print(f"  PDF: {pdf_path.name}")
        
        try:
            doc = fitz.open(pdf_path)
            
            # Save clean page 1
            print("\n  Saving page 1 (clean):")
            page = doc[0]
            mat = fitz.Matrix(2.0, 2.0)  # 144 DPI
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            page1_path = output_dir / f"{team_name}_page1_clean.png"
            cv2.imwrite(str(page1_path), img)
            print(f"  ✓ Saved: {page1_path.name} ({img.shape[1]}x{img.shape[0]})")
            
            # Find and save KILL TEAM page
            print("\n  Finding KILL TEAM page:")
            page_num = find_kill_team_page(pdf_path)
            
            if page_num != -1:
                page = doc[page_num]
                mat = fitz.Matrix(2.0, 2.0)  # 144 DPI
                pix = page.get_pixmap(matrix=mat)
                img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
                
                token_page_path = output_dir / f"{team_name}_page{page_num + 1}_clean.png"
                cv2.imwrite(str(token_page_path), img)
                print(f"  ✓ Saved: {token_page_path.name} ({img.shape[1]}x{img.shape[0]})")
            
            doc.close()
            
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print("\n" + "=" * 60)
    print("All clean page images saved to dev/ folder")
    print("=" * 60)
