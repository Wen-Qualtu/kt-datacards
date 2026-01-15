"""
Token Extraction Script for Kill Team Datacards

Extracts individual token images from marker/token guide cards.
Uses PDF text extraction for accurate token names, falling back to OCR if needed.

Usage:
    python dev/extract_tokens.py --team farstalker-kinband
    python dev/extract_tokens.py --all
"""

import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import cv2
from typing import List, Tuple, Dict
import json
import pytesseract
import fitz  # PyMuPDF
import re


class TokenExtractor:
    """Extract individual tokens from marker/token guide images."""
    
    def __init__(self, output_base_dir: Path):
        self.output_base_dir = output_base_dir
        self.output_base_dir.mkdir(exist_ok=True, parents=True)
    
    def extract_text_from_pdf(self, pdf_path: Path, page_num: int = -1, target_image_path: Path = None) -> Dict[Tuple[int, int], str]:
        """
        Extract text with positions from a PDF page (marker guide page).
        
        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed), -1 for last page (marker guide is usually last)
            target_image_path: Path to the target JPG image for coordinate scaling
        
        Returns:
            Dict mapping (x, y) to text strings (scaled to match target image if provided)
        """
        text_positions = {}
        
        try:
            doc = fitz.open(pdf_path)
            
            # Marker guide is usually the last page
            if page_num == -1:
                page_num = len(doc) - 1
            
            if page_num >= len(doc) or page_num < 0:
                doc.close()
                return text_positions
            
            page = doc[page_num]
            
            # Get PDF page dimensions
            pdf_width = page.rect.width
            pdf_height = page.rect.height
            
            # Get target image dimensions for scaling
            scale_x = 1.0
            scale_y = 1.0
            if target_image_path and target_image_path.exists():
                img = cv2.imread(str(target_image_path))
                if img is not None:
                    img_height, img_width = img.shape[:2]
                    scale_x = img_width / pdf_width
                    scale_y = img_height / pdf_height
            
            # Extract text with positions
            text_data = page.get_text("words")  # Returns list of (x0, y0, x1, y1, "word", block_no, line_no, word_no)
            
            current_group = []
            current_pos = None
            
            for item in text_data:
                x0, y0, x1, y1, word, block_no, line_no, word_no = item
                
                # Calculate center position and scale to image coordinates
                center_x = int(((x0 + x1) / 2) * scale_x)
                center_y = int(((y0 + y1) / 2) * scale_y)
                
                # Clean up word
                word = re.sub(r'[^a-zA-Z0-9\s\'-]', '', word)
                if not word or word.lower() in ['marker', 'token', 'guide']:
                    continue
                
                # Group words that are close together (same line or multi-line stacked)
                if current_pos is None:
                    current_pos = (center_x, center_y)
                    current_group = [word]
                    last_x1 = x1  # Track the right edge of the last word
                    group_x_min = x0  # Track x range of current group
                    group_x_max = x1
                else:
                    prev_x, prev_y = current_pos
                    
                    # Calculate gap from previous word's right edge to this word's left edge
                    gap = abs(x0 - last_x1)
                    y_diff = abs(center_y - prev_y)
                    
                    # Check if x positions overlap with current group (for multi-line names)
                    x_overlap = (x0 <= group_x_max and x1 >= group_x_min)
                    
                    # Same line with small gap = same token name
                    same_line = y_diff < 15 * scale_y and gap < 10
                    
                    # Next line with overlapping x = continuation of multi-line token name
                    # Multi-line names have y_diff of ~11 PDF units (~45px)
                    next_line_continuation = (y_diff > 5 * scale_y and y_diff < 25 * scale_y and x_overlap)
                    
                    if same_line or next_line_continuation:
                        current_group.append(word)
                        current_pos = ((prev_x + center_x) // 2, (prev_y + center_y) // 2)
                        last_x1 = x1  # Update right edge
                        # Update group x range
                        group_x_min = min(group_x_min, x0)
                        group_x_max = max(group_x_max, x1)
                    else:
                        # Save previous group
                        if current_group:
                            text_positions[current_pos] = ' '.join(current_group)
                        current_pos = (center_x, center_y)
                        current_group = [word]
                        last_x1 = x1
                        group_x_min = x0
                        group_x_max = x1
            
            # Save last group
            if current_group and current_pos:
                text_positions[current_pos] = ' '.join(current_group)
            
            doc.close()
            
        except Exception as e:
            print(f"  ⚠ Could not extract text from PDF: {e}")
        
        return text_positions
    
    def find_faction_rules_pdf(self, team_name: str) -> Path | None:
        """Find the faction rules PDF for a team."""
        processed_dir = Path("processed") / team_name
        if processed_dir.exists():
            pdf_files = list(processed_dir.glob(f"{team_name}-faction-rules.pdf"))
            if pdf_files:
                return pdf_files[0]
        return None
    
    def _extract_team_from_path(self, image_path: Path) -> str:
        """Extract team name from image path."""
        parts = image_path.parts
        if 'output_v2' in parts:
            faction_idx = parts.index('output_v2') + 1
            if faction_idx + 1 < len(parts):
                return parts[faction_idx + 1]
        return None
    
    def find_marker_guide(self, team_name: str) -> Path | None:
        """Find the marker/token guide image for a team."""
        # Search in output_v2 structure
        search_paths = [
            Path("output_v2") / "chaos" / team_name / "faction-rules",
            Path("output_v2") / "imperium" / team_name / "faction-rules",
            Path("output_v2") / "xenos" / team_name / "faction-rules",
        ]
        
        for search_path in search_paths:
            if search_path.exists():
                # Look for marker/token guide files
                marker_files = list(search_path.glob("*markertoken-guide*_front.jpg")) + \
                              list(search_path.glob("*marker-token-guide*_front.jpg")) + \
                              list(search_path.glob("*token-guide*_front.jpg"))
                if marker_files:
                    return marker_files[0]
        
        return None
    
    def extract_token_names_from_image(self, image_path: Path) -> Dict[Tuple[int, int], str]:
        """
        Extract all text from the image with positions.
        
        Returns:
            Dict mapping (center_x, center_y) to text
        """
        img = cv2.imread(str(image_path))
        if img is None:
            return {}
        
        # Convert to PIL for pytesseract
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        # Get OCR data with bounding boxes
        ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
        
        token_names = {}
        current_text = []
        current_box = None
        
        # Group words into token names based on proximity
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i]) if ocr_data['conf'][i] != '-1' else 0
            
            if text and conf > 30:  # Only consider confident detections
                x = ocr_data['left'][i]
                y = ocr_data['top'][i]
                w = ocr_data['width'][i]
                h = ocr_data['height'][i]
                
                # Clean up text
                text = re.sub(r'[^a-zA-Z0-9\s\'-]', '', text)
                
                if text:
                    # Calculate center position
                    center_x = x + w // 2
                    center_y = y + h // 2
                    
                    # Store text with its position
                    if current_box is None:
                        current_box = (center_x, center_y)
                        current_text = [text]
                    else:
                        # If close to previous text horizontally AND vertically, group together
                        # Be stricter about vertical alignment to avoid grouping across rows
                        prev_x, prev_y = current_box
                        if abs(center_y - prev_y) < 25 and abs(center_x - prev_x) < 150:
                            current_text.append(text)
                            # Update position to average
                            current_box = ((prev_x + center_x) // 2, (prev_y + center_y) // 2)
                        else:
                            # Save previous group
                            if current_text:
                                full_text = ' '.join(current_text)
                                token_names[current_box] = full_text
                            # Start new group
                            current_box = (center_x, center_y)
                            current_text = [text]
        
        # Save last group
        if current_text and current_box:
            full_text = ' '.join(current_text)
            token_names[current_box] = full_text
        
        return token_names
    
    def match_token_to_name(self, token_bbox: Tuple[int, int, int, int], 
                           token_names: Dict[Tuple[int, int], str]) -> str:
        """
        Match a token bounding box to its name based on proximity.
        Text is typically to the right or below the token.
        
        Args:
            token_bbox: (x, y, width, height) of token
            token_names: Dict of (x, y) -> name from OCR
        
        Returns:
            Best matching token name or 'unknown'
        """
        if not token_names:
            return 'unknown'
        
        x, y, w, h = token_bbox
        token_center_x = x + w // 2
        token_center_y = y + h // 2
        token_right = x + w
        token_bottom = y + h
        
        # Find text to the right or below the token
        best_match = None
        best_distance = float('inf')
        
        for (name_x, name_y), name in token_names.items():
            # Check if text is to the right (within reasonable vertical range)
            is_to_right = (name_x > token_right and 
                          abs(name_y - token_center_y) < h * 0.8)
            
            # Check if text is below (within reasonable horizontal range)
            is_below = (name_y > token_bottom and 
                       abs(name_x - token_center_x) < w * 0.8)
            
            if is_to_right or is_below:
                # Calculate distance
                distance = ((name_x - token_center_x) ** 2 + (name_y - token_center_y) ** 2) ** 0.5
                
                # Prefer closer matches, but prioritize text to the right over text below
                if is_to_right:
                    distance *= 0.8  # Prefer right-side text
                
                if distance < best_distance:
                    best_match = name
                    best_distance = distance
        
        # Clean up the matched name
        if best_match:
            # Remove common words
            best_match = re.sub(r'\b(token|marker)\b', '', best_match, flags=re.IGNORECASE)
            best_match = ' '.join(best_match.split())  # Clean up extra spaces
            return best_match if best_match else 'unknown'
        
        return 'unknown'
    
    def extract_token_name_from_region(self, img: np.ndarray, bbox: Tuple[int, int, int, int], expand_percent: float = 10.0) -> str:
        """
        Extract text from a specific region (token bounding box) using OCR.
        
        Args:
            img: Full image (numpy array)
            bbox: (x, y, width, height) of the region to extract text from
            expand_percent: Percentage to expand the bounding box to catch nearby text
        
        Returns:
            Extracted text or 'unknown'
        """
        x, y, w, h = bbox
        
        # Expand bounding box to catch text that might be just outside
        expand_x = int(w * expand_percent / 100)
        expand_y = int(h * expand_percent / 100)
        
        x_expanded = max(0, x - expand_x)
        y_expanded = max(0, y - expand_y)
        w_expanded = min(img.shape[1] - x_expanded, w + 2 * expand_x)
        h_expanded = min(img.shape[0] - y_expanded, h + 2 * expand_y)
        
        # Extract region
        region = img[y_expanded:y_expanded+h_expanded, x_expanded:x_expanded+w_expanded]
        
        # Convert to PIL for pytesseract
        img_rgb = cv2.cvtColor(region, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(img_rgb)
        
        # Get OCR data
        ocr_data = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
        
        # Collect all confident text
        words = []
        for i in range(len(ocr_data['text'])):
            text = ocr_data['text'][i].strip()
            conf = int(ocr_data['conf'][i]) if ocr_data['conf'][i] != '-1' else 0
            
            if text and conf > 30:  # Only confident detections
                # Clean up text
                text = re.sub(r'[^a-zA-Z0-9\s\'-]', '', text)
                if text and text.lower() not in ['token', 'marker']:  # Filter early
                    words.append(text)
        
        if words:
            # Join all words with spaces
            full_text = ' '.join(words)
            # Remove common unwanted words
            full_text = re.sub(r'\b(token|marker)\b', '', full_text, flags=re.IGNORECASE)
            full_text = ' '.join(full_text.split())  # Clean up extra spaces
            return full_text if full_text else 'unknown'
        
        return 'unknown'
    
    def match_token_to_name(self, token_bbox: Tuple[int, int, int, int], 
                           token_names: Dict[Tuple[int, int], str]) -> str:
        """
        Match a token bounding box to its name based on proximity.
        
        Args:
            token_bbox: (x, y, width, height) of token
            token_names: Dict of (x, y) -> name from OCR
        
        Returns:
            Best matching token name or 'unknown'
        """
        if not token_names:
            return 'unknown'
        
        x, y, w, h = token_bbox
        token_center_x = x + w // 2
        token_center_y = y + h // 2
        
        # Find closest name
        best_match = None
        best_distance = float('inf')
        
        for (name_x, name_y), name in token_names.items():
            # Calculate distance
            distance = ((name_x - token_center_x) ** 2 + (name_y - token_center_y) ** 2) ** 0.5
            
            # Prioritize names that are close and below/beside the token
            # Token names are typically directly below or beside the token image
            if distance < best_distance and distance < 300:  # Within reasonable proximity
                best_match = name
                best_distance = distance
        
        return best_match if best_match else 'unknown'
    
    def extract_tokens_auto(self, 
                           image_path: Path, 
                           output_dir: Path,
                           debug: bool = False,
                           skip_header_percent: float = 15.0,
                           extract_names: bool = True) -> List[Dict]:
        """
        Automatically detect and extract tokens using computer vision.
        
        Args:
            image_path: Path to the marker guide image
            output_dir: Directory to save extracted tokens
            debug: If True, save debug images showing detection
            skip_header_percent: Percentage of image height to skip from top (header row)
            extract_names: If True, use OCR to extract token names
        
        Returns:
            List of dicts with 'path', 'name', 'shape' info
        """
        # Load image first (needed for global OCR)
        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Could not load image: {image_path}")
        
        # Try to extract token names from PDF first
        token_names_ocr = {}
        if extract_names:
            # Extract team name from image path to find PDF
            team_name = self._extract_team_from_path(image_path)
            pdf_path = self.find_faction_rules_pdf(team_name) if team_name else None
            
            if pdf_path and pdf_path.exists():
                print(f"  Extracting text from PDF: {pdf_path.name}")
                token_names_ocr = self.extract_text_from_pdf(pdf_path, target_image_path=image_path)
                print(f"  Found {len(token_names_ocr)} text labels from PDF")
            else:
                # Fallback to OCR on image
                print(f"  No PDF found, using OCR on image...")
                token_names_ocr = self.extract_token_names_from_image(image_path)
                print(f"  Found {len(token_names_ocr)} text regions from OCR")
        
        img_height, img_width = img.shape[:2]
        
        # Skip header row (top X% of image)
        skip_pixels = int(img_height * (skip_header_percent / 100))
        img_crop = img[skip_pixels:, :]
        
        gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold to get binary image
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter contours by area and aspect ratio
        min_area = 1000  # Minimum pixel area for a token
        max_aspect_ratio = 3.0  # Filter out very wide elements (like remaining headers)
        
        token_contours = []
        for c in contours:
            area = cv2.contourArea(c)
            if area < min_area:
                continue
            
            # Check aspect ratio to filter out header-like elements
            x, y, w, h = cv2.boundingRect(c)
            aspect_ratio = w / h if h > 0 else 0
            
            # Skip if too wide (likely a header or text row)
            if aspect_ratio > max_aspect_ratio:
                continue
                
            token_contours.append(c)
        
        # Sort contours by position (top to bottom, left to right)
        token_contours = sorted(token_contours, key=lambda c: (
            cv2.boundingRect(c)[1],  # y position
            cv2.boundingRect(c)[0]   # x position
        ))
        
        # Extract tokens
        extracted_tokens = []
        output_dir.mkdir(exist_ok=True, parents=True)
        
        if debug:
            debug_img = img.copy()
        
        for idx, contour in enumerate(token_contours):
            # Get bounding box (relative to cropped image)
            x, y, w, h = cv2.boundingRect(contour)
            
            # Adjust y coordinate to account for skipped header
            y_actual = y + skip_pixels
            
            # Match token to nearby text (to the right or below)
            token_name = 'unknown'
            if extract_names:
                token_name = self.match_token_to_name((x, y_actual, w, h), token_names_ocr)
            
            # Clean up name for filename
            if token_name and token_name != 'unknown':
                safe_name = re.sub(r'[^a-z0-9\-]', '-', token_name.lower())
                safe_name = re.sub(r'-+', '-', safe_name).strip('-')
            else:
                safe_name = f"token-{idx:02d}"
            
            # Add padding
            padding = 10
            x_pad = max(0, x - padding)
            y_pad = max(0, y_actual - padding)
            w_pad = min(img.shape[1] - x_pad, w + 2 * padding)
            h_pad = min(img.shape[0] - y_pad, h + 2 * padding)
            
            # Extract token from original image
            token_img = img[y_pad:y_pad+h_pad, x_pad:x_pad+w_pad]
            
            # Determine shape based on circularity
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
            aspect_ratio = w / h if h > 0 else 0
            
            if circularity >= 0.75 and 0.9 <= aspect_ratio <= 1.1:
                shape = "round"
            else:
                shape = "operative"
            
            # Save
            output_path = output_dir / f"{safe_name}.png"
            cv2.imwrite(str(output_path), token_img)
            
            token_info = {
                'path': output_path,
                'name': token_name,
                'safe_name': safe_name,
                'shape': shape,
                'dimensions': {'width': w, 'height': h},
                'circularity': round(circularity, 3)
            }
            extracted_tokens.append(token_info)
            
            if debug:
                cv2.rectangle(debug_img, (x, y_actual), (x+w, y_actual+h), (0, 255, 0), 2)
                label = f"{safe_name[:15]}" if token_name != 'unknown' else str(idx)
                cv2.putText(debug_img, label, (x, y_actual-5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            
            # Draw OCR text positions
            if token_names_ocr:
                for (text_x, text_y), text in token_names_ocr.items():
                    cv2.circle(debug_img, (text_x, text_y), 5, (255, 0, 0), -1)
                    cv2.putText(debug_img, text[:20], (text_x + 10, text_y), 
                              cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
            print(f"  ✓ Extracted: {token_name} ({shape}) -> {output_path.name}")
        
        if debug:
            # Draw line showing header skip region
            cv2.line(debug_img, (0, skip_pixels), (img_width, skip_pixels), (0, 0, 255), 2)
            cv2.putText(debug_img, "Header (ignored)", (10, skip_pixels - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            
            debug_path = output_dir / "_debug_detection.png"
            cv2.imwrite(str(debug_path), debug_img)
            print(f"  ℹ Debug image saved: {debug_path}")
        
        return extracted_tokens
    
    def _find_marker_guide_pdf(self, image_path: Path) -> Path:
        """
        Find the corresponding PDF file for a marker guide image.
        
        Args:
            image_path: Path to the marker guide JPG
        
        Returns:
            Path to the PDF file, or None if not found
        """
        # Image is in output_v2/{faction}/{team}/faction-rules/{team}-markertoken-guide_front.jpg
        # PDF should be in processed/{team}/{team}-faction-rules.pdf
        
        # Extract team name from path
        parts = image_path.parts
        if 'output_v2' in parts:
            faction_idx = parts.index('output_v2') + 1
            if faction_idx + 1 < len(parts):
                team = parts[faction_idx + 1]
                
                # Look for PDF in processed/{team}/
                pdf_path = Path('processed') / team / f"{team}-faction-rules.pdf"
                if pdf_path.exists():
                    return pdf_path
        
        return None
    
    def process_team(self, team_name: str, method: str = 'auto', debug: bool = False) -> bool:
        """
        Process a team's marker guide and extract all tokens.
        
        Args:
            team_name: Name of the team (e.g., 'farstalker-kinband')
            method: 'auto' for automatic detection
            debug: Save debug images showing detection
        
        Returns:
            True if successful, False otherwise
        """
        print(f"\n{'='*60}")
        print(f"Processing: {team_name}")
        print(f"{'='*60}")
        
        # Find marker guide
        marker_guide_path = self.find_marker_guide(team_name)
        if not marker_guide_path:
            print(f"  ✗ No marker/token guide found for {team_name}")
            return False
        
        print(f"  Found marker guide: {marker_guide_path}")
        
        # Create output directory
        output_dir = self.output_base_dir / team_name
        
        if method == 'auto':
            extracted = self.extract_tokens_auto(marker_guide_path, output_dir, debug=debug)
        else:
            print(f"  ✗ Manual extraction not implemented")
            return False
        
        print(f"  ✓ Extracted {len(extracted)} tokens")
        
        # Save metadata
        metadata = {
            'team': team_name,
            'source_image': str(marker_guide_path),
            'extraction_method': method,
            'tokens_extracted': len(extracted),
            'tokens': [
                {
                    'filename': t['path'].name,
                    'name': t['name'],
                    'shape': t['shape'],
                    'dimensions': t['dimensions']
                }
                for t in extracted
            ]
        }
        
        metadata_path = output_dir / 'extraction-metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"  ✓ Metadata saved: {metadata_path}")
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Extract tokens from marker/token guides')
    parser.add_argument('--team', type=str, help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--all', action='store_true', help='Process all teams')
    parser.add_argument('--method', choices=['auto'], default='auto',
                       help='Extraction method (default: auto)')
    parser.add_argument('--debug', action='store_true', help='Save debug images')
    parser.add_argument('--output-dir', type=str, default='dev/extracted-tokens',
                       help='Output directory for extracted tokens')
    
    args = parser.parse_args()
    
    if not args.team and not args.all:
        parser.error('Must specify --team or --all')
    
    # Setup
    output_base = Path(args.output_dir)
    extractor = TokenExtractor(output_base)
    
    if args.team:
        # Process single team
        success = extractor.process_team(args.team, method=args.method, debug=args.debug)
        if not success:
            exit(1)
    
    elif args.all:
        # Find all teams with marker guides
        print("Searching for teams with marker/token guides...")
        teams = []
        
        for faction_dir in Path("output_v2").iterdir():
            if faction_dir.is_dir():
                for team_dir in faction_dir.iterdir():
                    if team_dir.is_dir():
                        faction_rules = team_dir / "faction-rules"
                        if faction_rules.exists():
                            marker_files = list(faction_rules.glob("*markertoken-guide*_front.jpg"))
                            if marker_files:
                                teams.append(team_dir.name)
        
        print(f"Found {len(teams)} teams with marker guides")
        
        # Process each team
        success_count = 0
        for team in sorted(teams):
            if extractor.process_team(team, method=args.method, debug=args.debug):
                success_count += 1
        
        print(f"\n{'='*60}")
        print(f"Summary: {success_count}/{len(teams)} teams processed successfully")
        print(f"{'='*60}")
    
    print(f"\n✓ Token extraction complete!")
    print(f"  Output directory: {output_base.absolute()}")


if __name__ == '__main__':
    main()
