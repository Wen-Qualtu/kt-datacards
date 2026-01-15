"""
Improved Token Extraction Script for Kill Team Datacards

Extracts individual token images directly from PDF marker/token guide pages.
Applies transparency during extraction for optimal quality.

Key improvements:
- Extracts directly from PDF (no JPG intermediate)
- Applies transparency immediately
- Single-pass processing

Usage:
    python dev/extract_tokens_v2.py --team farstalker-kinband
    python dev/extract_tokens_v2.py --team farstalker-kinband --no-transparency
"""

import argparse
from pathlib import Path
from PIL import Image
import numpy as np
import cv2
from typing import List, Tuple, Dict
import json
import fitz  # PyMuPDF
import re


class TokenExtractorV2:
    """Extract individual tokens directly from PDF with transparency."""
    
    def __init__(self, output_base_dir: Path):
        self.output_base_dir = output_base_dir
        self.output_base_dir.mkdir(exist_ok=True, parents=True)
    
    def find_faction_rules_pdf(self, team_name: str) -> Path | None:
        """Find the faction rules PDF for a team."""
        processed_dir = Path("processed") / team_name
        if processed_dir.exists():
            pdf_files = list(processed_dir.glob(f"{team_name}-faction-rules.pdf"))
            if pdf_files:
                return pdf_files[0]
        return None
    
    def extract_text_from_pdf_page(self, doc: fitz.Document, page_num: int, 
                                   scale_x: float = 1.0, scale_y: float = 1.0) -> Dict[Tuple[int, int], str]:
        """
        Extract text positions from a PDF page.
        
        Args:
            doc: Open PyMuPDF document
            page_num: Page number to extract from
            scale_x, scale_y: Scaling factors for coordinates
        
        Returns:
            Dict mapping (x, y) to text strings
        """
        text_positions = {}
        
        try:
            page = doc[page_num]
            text_data = page.get_text("words")
            
            current_group = []
            current_pos = None
            last_x1 = None
            group_x_min = None
            group_x_max = None
            
            for item in text_data:
                x0, y0, x1, y1, word, block_no, line_no, word_no = item
                
                # Calculate center position and scale
                center_x = int(((x0 + x1) / 2) * scale_x)
                center_y = int(((y0 + y1) / 2) * scale_y)
                
                # Clean up word
                word = re.sub(r'[^a-zA-Z0-9\s\'-]', '', word)
                if not word or word.lower() in ['marker', 'token', 'guide']:
                    continue
                
                # Group words that are close together
                if current_pos is None:
                    current_pos = (center_x, center_y)
                    current_group = [word]
                    last_x1 = x1
                    group_x_min = x0
                    group_x_max = x1
                else:
                    prev_x, prev_y = current_pos
                    gap = abs(x0 - last_x1)
                    y_diff = abs(center_y - prev_y)
                    x_overlap = (x0 <= group_x_max and x1 >= group_x_min)
                    
                    same_line = y_diff < 15 * scale_y and gap < 10
                    next_line_continuation = (y_diff > 5 * scale_y and y_diff < 25 * scale_y and x_overlap)
                    
                    if same_line or next_line_continuation:
                        current_group.append(word)
                        current_pos = ((prev_x + center_x) // 2, (prev_y + center_y) // 2)
                        last_x1 = x1
                        group_x_min = min(group_x_min, x0)
                        group_x_max = max(group_x_max, x1)
                    else:
                        if current_group:
                            text_positions[current_pos] = ' '.join(current_group)
                        current_pos = (center_x, center_y)
                        current_group = [word]
                        last_x1 = x1
                        group_x_min = x0
                        group_x_max = x1
            
            if current_group and current_pos:
                text_positions[current_pos] = ' '.join(current_group)
        
        except Exception as e:
            print(f"  ⚠ Could not extract text: {e}")
        
        return text_positions
    
    def render_pdf_page_to_image(self, pdf_path: Path, page_num: int = -1, dpi: int = 300) -> np.ndarray:
        """
        Render a PDF page directly to a high-resolution image.
        
        Args:
            pdf_path: Path to PDF file
            page_num: Page number (-1 for last page)
            dpi: Resolution for rendering
        
        Returns:
            Image as numpy array (RGB)
        """
        doc = fitz.open(pdf_path)
        
        if page_num == -1:
            page_num = len(doc) - 1
        
        page = doc[page_num]
        
        # Render at high resolution
        # DPI / 72 = zoom factor (PDF uses 72 DPI)
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        
        # Convert to numpy array
        img = np.frombuffer(pix.samples, dtype=np.uint8)
        img = img.reshape(pix.height, pix.width, pix.n)
        
        # Convert RGBA to RGB if needed
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2RGB)
        
        doc.close()
        
        return img
    
    def apply_transparency(self, image: np.ndarray, threshold: int = 50) -> np.ndarray:
        """
        Apply transparency to token image using flood fill from corners.
        Preserves original RGB colors, only modifies alpha channel.
        
        Args:
            image: Input image (RGB numpy array)
            threshold: Color distance threshold
        
        Returns:
            Image with transparency (RGBA numpy array)
        """
        # CRITICAL: Store original RGB BEFORE any conversions
        # Make a deep copy to preserve exact color values
        if len(image.shape) == 3 and image.shape[2] == 3:
            original_rgb = image.copy()  # RGB input
        elif len(image.shape) == 2:
            original_rgb = cv2.cvtColor(image, cv2.COLOR_GRAY2RGB).copy()
        else:
            original_rgb = image[:,:,0:3].copy()  # Already has more channels
        
        # Create RGBA version for alpha processing
        if len(image.shape) == 2:
            rgba_img = cv2.cvtColor(image, cv2.COLOR_GRAY2RGBA)
        elif image.shape[2] == 3:
            rgba_img = cv2.cvtColor(image, cv2.COLOR_RGB2RGBA)
        else:
            rgba_img = image.copy()
        
        data = rgba_img.copy()
        height, width = data.shape[:2]
        
        # Sample corner colors
        corners = [
            (0, 0), (0, width-1),
            (height-1, 0), (height-1, width-1),
            (0, width//2), (height//2, 0),
            (height-1, width//2), (height//2, width-1)
        ]
        
        corner_colors = []
        for y, x in corners:
            if 0 <= y < height and 0 <= x < width:
                # Use original RGB for corner sampling to get true background color
                corner_colors.append(original_rgb[y, x, :3])
        
        if not corner_colors:
            return data
        
        avg_corner_color = np.mean(corner_colors, axis=0)
        
        # Calculate color distance using ORIGINAL RGB values
        r, g, b = original_rgb[:,:,0], original_rgb[:,:,1], original_rgb[:,:,2]
        
        # Calculate both color distance from corners AND gray-tone detection
        # Since we know backgrounds are gray (R≈G≈B), detect and remove them aggressively
        color_distance = np.sqrt(
            (r - avg_corner_color[0])**2 +
            (g - avg_corner_color[1])**2 +
            (b - avg_corner_color[2])**2
        )
        
        # Detect gray tones: where R, G, B are similar (within 20 units for more aggressive removal)
        is_grayish = (np.abs(r.astype(np.int16) - g.astype(np.int16)) < 20) & \
                     (np.abs(g.astype(np.int16) - b.astype(np.int16)) < 20) & \
                     (np.abs(r.astype(np.int16) - b.astype(np.int16)) < 20)
        
        # Detect light grays (brightness > 170, lowered to catch more background)
        brightness = (r.astype(np.int16) + g.astype(np.int16) + b.astype(np.int16)) / 3
        is_light_gray = is_grayish & (brightness > 180)
        
        # Adaptive threshold
        adaptive_threshold = min(threshold, color_distance[color_distance > 0].std() * 2) if (color_distance > 0).any() else threshold
        
        gradient_range = 30
        
        # Mark as transparent: close to corner color OR light gray background
        fully_transparent = color_distance < adaptive_threshold
        fully_transparent = fully_transparent | is_light_gray  # Also remove light gray tones
        in_gradient = (color_distance >= adaptive_threshold) & (color_distance < adaptive_threshold + gradient_range)
        
        gradient_alpha = np.zeros_like(color_distance, dtype=np.uint8)
        gradient_alpha[in_gradient] = ((color_distance[in_gradient] - adaptive_threshold) / gradient_range * 255).astype(np.uint8)
        
        new_alpha = np.where(fully_transparent, 0,
                    np.where(in_gradient, gradient_alpha, 255))
        
        # Morphological cleanup - more aggressive to remove corner artifacts
        kernel = np.ones((3, 3), np.uint8)
        binary_mask = (new_alpha > 0).astype(np.uint8) * 255
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel, iterations=3)  # Fill more holes
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel, iterations=3)   # Remove more artifacts
        
        cleaned_alpha = np.where(binary_mask > 0, new_alpha, 0)
        
        # IMPORTANT: Restore original RGB values, only apply cleaned alpha
        data[:,:,0:3] = original_rgb
        data[:,:,3] = cleaned_alpha
        
        return data
    
    def extract_tokens_from_pdf(self, pdf_path: Path, output_dir: Path, 
                               apply_transparency: bool = True,
                               dpi: int = 300,
                               transparency_threshold: int = 50,
                               debug: bool = False) -> List[Dict]:
        """
        Extract tokens directly from PDF marker guide page.
        
        Args:
            pdf_path: Path to faction rules PDF
            output_dir: Output directory for tokens
            apply_transparency: Whether to apply transparency
            dpi: Resolution for PDF rendering
            transparency_threshold: Threshold for transparency
            debug: Save debug images
        
        Returns:
            List of extracted token info dicts
        """
        output_dir.mkdir(exist_ok=True, parents=True)
        
        print(f"  Rendering PDF page at {dpi} DPI...")
        doc = fitz.open(pdf_path)
        page_num = len(doc) - 1  # Last page is marker guide
        
        # Render page to high-res image
        img = self.render_pdf_page_to_image(pdf_path, page_num, dpi)
        print(f"  Rendered image size: {img.shape[1]}x{img.shape[0]}")
        
        # Extract text positions
        print(f"  Extracting text positions from PDF...")
        page = doc[page_num]
        scale_x = img.shape[1] / page.rect.width
        scale_y = img.shape[0] / page.rect.height
        token_names = self.extract_text_from_pdf_page(doc, page_num, scale_x, scale_y)
        print(f"  Found {len(token_names)} text labels")
        
        doc.close()
        
        # Convert to grayscale for detection
        img_gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        
        # Skip header (top 15%)
        skip_pixels = int(img.shape[0] * 0.15)
        img_crop = img[skip_pixels:, :]
        gray_crop = img_gray[skip_pixels:, :]
        
        # Threshold
        _, binary = cv2.threshold(gray_crop, 200, 255, cv2.THRESH_BINARY_INV)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Filter and extract tokens
        extracted_tokens = []
        min_area = 5000
        max_area = img.shape[0] * img.shape[1] * 0.3
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < min_area or area > max_area:
                continue
            
            x, y, w, h = cv2.boundingRect(contour)
            y += skip_pixels  # Adjust for header skip
            
            # Extract with padding for initial analysis
            initial_pad = 30
            x_padded = max(0, x - initial_pad)
            y_padded = max(0, y - initial_pad)
            w_padded = min(img.shape[1] - x_padded, w + 2*initial_pad)
            h_padded = min(img.shape[0] - y_padded, h + 2*initial_pad)
            
            # Extract larger region
            token_region = img[y_padded:y_padded+h_padded, x_padded:x_padded+w_padded].copy()
            
            # Find precise token boundary using edge detection on the token itself
            # Convert to grayscale for edge detection
            token_gray = cv2.cvtColor(token_region, cv2.COLOR_RGB2GRAY)
            
            # Apply Gaussian blur to reduce noise
            token_blur = cv2.GaussianBlur(token_gray, (5, 5), 0)
            
            # Use Canny edge detection to find token edges (not gray background)
            edges = cv2.Canny(token_blur, 30, 100)
            
            # Dilate edges to close gaps
            kernel = np.ones((3,3), np.uint8)
            edges_dilated = cv2.dilate(edges, kernel, iterations=2)
            
            # Find contours of the token itself
            token_contours, _ = cv2.findContours(edges_dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            # Find the largest contour (should be the token)
            if token_contours:
                largest_contour = max(token_contours, key=cv2.contourArea)
                tx, ty, tw, th = cv2.boundingRect(largest_contour)
                
                # Add minimal padding around the detected token
                token_pad = 5
                tx = max(0, tx - token_pad)
                ty = max(0, ty - token_pad)
                tw = min(token_region.shape[1] - tx, tw + 2*token_pad)
                th = min(token_region.shape[0] - ty, th + 2*token_pad)
                
                # Extract just the token with minimal background
                token_img = token_region[ty:ty+th, tx:tx+tw].copy()
            else:
                # Fallback to original padded region if edge detection fails
                token_img = token_region
            
            # Find closest text label
            center_x = x + w//2
            center_y = y + h//2
            
            closest_name = "unknown"
            min_dist = float('inf')
            
            for (tx, ty), name in token_names.items():
                dist = np.sqrt((tx - center_x)**2 + (ty - center_y)**2)
                if dist < min_dist:
                    min_dist = dist
                    closest_name = name
            
            # Determine shape
            perimeter = cv2.arcLength(contour, True)
            circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
            aspect_ratio = w / h if h > 0 else 1
            shape = "round" if circularity >= 0.75 and 0.9 <= aspect_ratio <= 1.1 else "operative"
            
            # Create filename
            filename_base = closest_name.lower().replace(' ', '-').replace("'", "")
            filename_base = re.sub(r'[^a-z0-9\-]', '', filename_base)
            if not filename_base:
                filename_base = f"token-{len(extracted_tokens)+1}"
            
            # Apply transparency if requested
            if apply_transparency:
                token_img = self.apply_transparency(token_img, transparency_threshold)
                # Convert to PIL Image
                token_pil = Image.fromarray(token_img, 'RGBA')
            else:
                token_pil = Image.fromarray(cv2.cvtColor(token_img, cv2.COLOR_RGB2RGBA))
            
            # Auto-crop to remove excess transparent space
            # Get bounding box of non-transparent pixels
            alpha = np.array(token_pil)[:,:,3]
            
            # Use a threshold to ignore very faint semi-transparent pixels
            alpha_threshold = 10  # Ignore pixels with alpha < 10
            rows = np.any(alpha > alpha_threshold, axis=1)
            cols = np.any(alpha > alpha_threshold, axis=0)
            
            if rows.any() and cols.any():
                ymin, ymax = np.where(rows)[0][[0, -1]]
                xmin, xmax = np.where(cols)[0][[0, -1]]
                
                # Add small padding
                pad = 3  # Reduced padding for tighter crop
                ymin = max(0, ymin - pad)
                xmin = max(0, xmin - pad)
                ymax = min(alpha.shape[0], ymax + pad + 1)
                xmax = min(alpha.shape[1], xmax + pad + 1)
                
                # Crop to content
                token_pil = token_pil.crop((xmin, ymin, xmax, ymax))
            
            # se:
                token_pil = Image.fromarray(cv2.cvtColor(token_img, cv2.COLOR_RGB2RGBA))
            
            # Save
            output_path = output_dir / f"{filename_base}.png"
            token_pil.save(output_path, 'PNG')
            
            extracted_tokens.append({
                'path': output_path,
                'name': closest_name,
                'shape': shape,
                'dimensions': {'width': w, 'height': h}
            })
            
            print(f"  ✓ {closest_name:30} ({shape:8}) → {output_path.name}")
        
        return extracted_tokens
    
    def process_team(self, team_name: str, apply_transparency: bool = True,
                    dpi: int = 300, transparency_threshold: int = 50,
                    debug: bool = False) -> bool:
        """
        Process a team's tokens directly from PDF.
        
        Args:
            team_name: Team name
            apply_transparency: Apply transparency during extraction
            dpi: PDF rendering resolution
            transparency_threshold: Transparency threshold
            debug: Save debug images
        
        Returns:
            True if successful
        """
        print(f"\n{'='*60}")
        print(f"Processing: {team_name}")
        print(f"{'='*60}")
        
        # Find PDF
        pdf_path = self.find_faction_rules_pdf(team_name)
        if not pdf_path:
            print(f"  ✗ Faction rules PDF not found for {team_name}")
            return False
        
        print(f"  Found PDF: {pdf_path}")
        
        # Create output directory
        output_dir = self.output_base_dir / team_name
        
        # Extract tokens
        extracted = self.extract_tokens_from_pdf(
            pdf_path, output_dir,
            apply_transparency=apply_transparency,
            dpi=dpi,
            transparency_threshold=transparency_threshold,
            debug=debug
        )
        
        print(f"  ✓ Extracted {len(extracted)} tokens")
        
        # Save metadata
        metadata = {
            'team': team_name,
            'source_pdf': str(pdf_path),
            'extraction_method': 'pdf_direct',
            'dpi': dpi,
            'transparency_applied': apply_transparency,
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
    parser = argparse.ArgumentParser(description='Extract tokens directly from PDF with transparency')
    parser.add_argument('--team', type=str, required=True,
                       help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--no-transparency', action='store_true',
                       help='Skip transparency processing')
    parser.add_argument('--dpi', type=int, default=300,
                       help='PDF rendering DPI (default: 300)')
    parser.add_argument('--threshold', type=int, default=50,
                       help='Transparency threshold (default: 50)')
    parser.add_argument('--debug', action='store_true',
                       help='Save debug images')
    parser.add_argument('--output-dir', type=str, default='dev/extracted-tokens',
                       help='Output directory')
    
    args = parser.parse_args()
    
    output_base = Path(args.output_dir)
    extractor = TokenExtractorV2(output_base)
    
    success = extractor.process_team(
        team_name=args.team,
        apply_transparency=not args.no_transparency,
        dpi=args.dpi,
        transparency_threshold=args.threshold,
        debug=args.debug
    )
    
    if not success:
        exit(1)
    
    print(f"\n✓ Token extraction complete!")
    print(f"  Output directory: {output_base.absolute()}")


if __name__ == '__main__':
    main()
