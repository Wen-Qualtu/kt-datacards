"""
Production token extraction pipeline for Kill Team datacards.

This script extracts tokens from the last page of faction PDFs and applies
template-based cleanup to produce high-quality 500x500 token images.

Two-stage pipeline:
1. Extract tokens using OCR-based text detection and contour matching
2. Apply shape-specific templates (round or operative) to remove artifacts

Usage:
    python script/extract_tokens.py --team <team-name>
    python script/extract_tokens.py --team <team-name> --debug
    python script/extract_tokens.py --all
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
import argparse
import easyocr
from typing import Dict, List, Tuple, Optional


class TokenExtractor:
    """Extracts tokens from PDF using OCR and contour detection."""
    
    def __init__(self):
        self._ocr_reader = None
        self.skip_header_percent = 5.0
        self.text_vertical_threshold = 60
        self.text_horizontal_threshold = 100
        self.target_border = 10
        
        # Team-specific corrections
        self.name_corrections = {
            "hearthkyn-salvagers": {
                "utility": "utility-grenade-marker",
                "grenade-marker": "utility-grenade-marker",
                "marker-defence-marker-writ-of-claim": "defence-marker",
                "system-jam-token-c8-hx-charge-token": "system-jam-token",
            },
            "blades-of-khaine": {
                "wraithbone-talisman-token": "wraithbone-talisman-token",
                "rune-of-shielding-token": "rune-of-shielding-token",
                "rune-of-prophecy-token": "rune-of-prophecy-token",
            }
        }
        
        self.shape_overrides = {
            "blades-of-khaine": {
                "wraithbone-talisman-token": "round",
                "rune-of-shielding-token": "round",
                "rune-of-prophecy-token": "round",
            }
        }
    
    def get_ocr_reader(self):
        """Lazy load OCR reader."""
        if self._ocr_reader is None:
            print("Loading EasyOCR reader (one-time initialization)...")
            self._ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
        return self._ocr_reader
    
    def extract_text_with_ocr(self, img_array: np.ndarray, team_name: str) -> Dict[Tuple[int, int], str]:
        """Extract text positions using OCR on the rendered image."""
        reader = self.get_ocr_reader()
        results = reader.readtext(img_array, min_size=10, text_threshold=0.3)
        
        texts = {}
        text_positions = []
        
        for (bbox, text, confidence) in results:
            if confidence < 0.3:
                continue
            
            # Get center position
            x_coords = [point[0] for point in bbox]
            y_coords = [point[1] for point in bbox]
            x = int(sum(x_coords) / len(x_coords))
            y = int(sum(y_coords) / len(y_coords))
            
            text_clean = text.lower().strip()
            text_clean = ''.join(c if c.isalnum() or c in ['-', ' '] else '' for c in text_clean)
            text_clean = text_clean.replace(' ', '-')
            
            if text_clean and len(text_clean) >= 2:
                text_positions.append((x, y, text_clean))
        
        # Group multi-line text
        text_positions.sort(key=lambda t: (t[1], t[0]))
        grouped_texts = []
        current_group = []
        
        for pos in text_positions:
            if not current_group:
                current_group.append(pos)
            else:
                prev_x, prev_y, _ = current_group[-1]
                curr_x, curr_y, _ = pos
                
                vertical_dist = abs(curr_y - prev_y)
                horizontal_dist = abs(curr_x - prev_x)
                
                if vertical_dist <= self.text_vertical_threshold or \
                   (vertical_dist <= self.text_vertical_threshold * 2 and horizontal_dist <= self.text_horizontal_threshold):
                    current_group.append(pos)
                else:
                    if current_group:
                        grouped_texts.append(current_group)
                    current_group = [pos]
        
        if current_group:
            grouped_texts.append(current_group)
        
        # Combine groups
        for group in grouped_texts:
            combined_text = '-'.join([text for _, _, text in group])
            avg_x = int(sum([x for x, _, _ in group]) / len(group))
            avg_y = int(sum([y for _, y, _ in group]) / len(group))
            
            # Apply corrections
            if team_name in self.name_corrections:
                for pattern, replacement in self.name_corrections[team_name].items():
                    if pattern in combined_text:
                        combined_text = replacement
                        break
            
            texts[(avg_x, avg_y)] = combined_text
        
        return texts
    
    def extract_tokens_from_pdf(self, pdf_path: Path, output_dir: Path, team_name: str) -> List[Path]:
        """Extract tokens from PDF's last page."""
        print(f"Processing: {pdf_path}")
        
        # Render PDF
        doc = fitz.open(pdf_path)
        last_page = doc[-1]
        
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = last_page.get_pixmap(matrix=mat, alpha=False)
        img_data = pix.tobytes("png")
        
        img = Image.open(io.BytesIO(img_data))
        img_array = np.array(img)
        
        # Skip header
        skip_height = int(img_array.shape[0] * self.skip_header_percent / 100)
        img_array = img_array[skip_height:, :]
        
        # Extract text with OCR
        text_positions = self.extract_text_with_ocr(img_array, team_name)
        print(f"  Found {len(text_positions)} text labels")
        
        # Find contours
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = [c for c in contours if cv2.contourArea(c) > 500]
        print(f"  Found {len(contours)} contours")
        
        # Match text to contours (name-first)
        output_dir.mkdir(parents=True, exist_ok=True)
        extracted_tokens = []
        used_contours = set()
        
        for (text_x, text_y), text_label in text_positions.items():
            best_contour = None
            best_distance = float('inf')
            best_contour_idx = -1
            
            for idx, contour in enumerate(contours):
                if idx in used_contours:
                    continue
                
                x, y, w, h = cv2.boundingRect(contour)
                cx, cy = x + w // 2, y + h // 2
                
                dx = cx - text_x
                dy = cy - text_y
                
                # Reject if text is far to right or below
                if dx < -50 or dy < -50:
                    continue
                
                distance = np.sqrt(dx**2 + dy**2)
                
                if distance < best_distance and distance < 400:
                    # Prefer left/top placement
                    if dx > 0 or dy > 0:
                        best_distance = distance
                        best_contour = contour
                        best_contour_idx = idx
            
            if best_contour is not None:
                used_contours.add(best_contour_idx)
                
                # Extract token
                token_img = self.extract_contour_token(img_array, best_contour)
                
                # Save
                token_name = f"{team_name}-{text_label}"
                output_path = output_dir / f"{token_name}.png"
                cv2.imwrite(str(output_path), cv2.cvtColor(token_img, cv2.COLOR_RGBA2BGRA))
                extracted_tokens.append(output_path)
                print(f"  [+] Extracted: {token_name}.png")
        
        print(f"  Extracted {len(extracted_tokens)} unique tokens")
        return extracted_tokens
    
    def extract_contour_token(self, img: np.ndarray, contour: np.ndarray) -> np.ndarray:
        """Extract token by contour with alpha mask."""
        # Create mask
        mask = np.zeros(img.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask, [contour], -1, 255, -1)
        
        # Apply mask
        bgra = cv2.cvtColor(img, cv2.COLOR_RGB2BGRA)
        bgra[:, :, 3] = mask
        
        # Crop to bounding box
        x, y, w, h = cv2.boundingRect(contour)
        margin = 20
        x1 = max(0, x - margin)
        y1 = max(0, y - margin)
        x2 = min(img.shape[1], x + w + margin)
        y2 = min(img.shape[0], y + h + margin)
        
        cropped = bgra[y1:y2, x1:x2]
        
        # Scale to 512x512
        max_dim = max(cropped.shape[0], cropped.shape[1])
        scale = (512 - 2 * self.target_border) / max_dim
        
        new_w = int(cropped.shape[1] * scale)
        new_h = int(cropped.shape[0] * scale)
        
        resized = cv2.resize(cropped, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        # Center in 512x512
        final = np.zeros((512, 512, 4), dtype=np.uint8)
        offset_x = (512 - new_w) // 2
        offset_y = (512 - new_h) // 2
        final[offset_y:offset_y+new_h, offset_x:offset_x+new_w] = resized
        
        return final


class TokenCleaner:
    """Applies template-based cleanup to extracted tokens."""
    
    def __init__(self):
        self.operative_template_path = Path("dev/averaged-operative-template.png")
        self.operative_template = None
        
        # Shape classification thresholds
        self.circularity_threshold = 0.75
        self.aspect_ratio_threshold = 1.15
    
    def load_operative_template(self):
        """Lazy load operative template."""
        if self.operative_template is None:
            self.operative_template = cv2.imread(str(self.operative_template_path), cv2.IMREAD_UNCHANGED)
        return self.operative_template
    
    def classify_token_shape(self, token_img: np.ndarray, token_name: str, debug: bool = False) -> str:
        """Classify token as round or operative based on shape."""
        alpha = token_img[:, :, 3]
        
        # Erode to get clean content
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        alpha_eroded = cv2.erode(alpha, kernel, iterations=2)
        
        _, binary = cv2.threshold(alpha_eroded, 10, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours:
            return "operative"
        
        main_contour = max(contours, key=cv2.contourArea)
        
        # Calculate metrics
        area = cv2.contourArea(main_contour)
        perimeter = cv2.arcLength(main_contour, True)
        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
        
        x, y, w, h = cv2.boundingRect(main_contour)
        aspect_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 1
        
        shape = "round" if circularity >= self.circularity_threshold and aspect_ratio < self.aspect_ratio_threshold else "operative"
        
        if debug:
            print(f"  Classification {token_name[:30]}: aspect={aspect_ratio:.3f}, circularity={circularity:.3f} -> {shape}")
        
        return shape
    
    def apply_template_cleanup(self, token_img: np.ndarray, shape: str, debug: bool = False, token_name: str = "") -> np.ndarray:
        """Apply shape-specific template to remove artifacts."""
        alpha = token_img[:, :, 3]
        
        # Erode to find clean content
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        alpha_eroded = cv2.erode(alpha, kernel, iterations=2)
        _, binary_clean = cv2.threshold(alpha_eroded, 10, 255, cv2.THRESH_BINARY)
        
        contours_clean, _ = cv2.findContours(binary_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if not contours_clean:
            return cv2.resize(token_img, (500, 500), interpolation=cv2.INTER_LANCZOS4)
        
        main_contour = max(contours_clean, key=cv2.contourArea)
        
        if shape == "round":
            # Fit perfect circle to clean content
            (cx, cy), radius = cv2.minEnclosingCircle(main_contour)
            cx, cy = int(cx), int(cy)
            
            # Reduce radius by 5% to cut artifacts
            radius = int(radius * 0.95)
            
            # Create circular mask
            mask = np.zeros((512, 512), dtype=np.uint8)
            cv2.circle(mask, (cx, cy), radius, 255, -1)
            mask = cv2.GaussianBlur(mask, (5, 5), 1)
            
            if debug:
                print(f"  Debug: cx={cx}, cy={cy}, radius={radius} (perfect circle template)")
        
        else:  # operative
            # Fit operative template to clean content
            x, y, w, h = cv2.boundingRect(main_contour)
            
            # Scale template 108%
            scale_factor = 1.08
            target_w = int(w * scale_factor)
            target_h = int(h * scale_factor)
            
            template = self.load_operative_template()
            if template.ndim == 3 and template.shape[2] == 4:
                template_alpha = template[:, :, 3]
            else:
                template_alpha = template
            template_resized = cv2.resize(template_alpha, (target_w, target_h), interpolation=cv2.INTER_LANCZOS4)
            
            # Center on content
            offset_x = x + w // 2 - target_w // 2
            offset_y = y + h // 2 - target_h // 2
            
            mask = np.zeros((512, 512), dtype=np.uint8)
            
            x1 = max(0, offset_x)
            y1 = max(0, offset_y)
            x2 = min(512, offset_x + target_w)
            y2 = min(512, offset_y + target_h)
            
            tx1 = x1 - offset_x
            ty1 = y1 - offset_y
            tx2 = tx1 + (x2 - x1)
            ty2 = ty1 + (y2 - y1)
            
            mask[y1:y2, x1:x2] = template_resized[ty1:ty2, tx1:tx2]
            mask = cv2.GaussianBlur(mask, (5, 5), 1)
            
            if debug:
                print(f"  Debug: operative template {target_w}x{target_h} at ({offset_x}, {offset_y}) [scaled 108%]")
        
        # Apply mask
        result = token_img.copy()
        result[:, :, 3] = cv2.bitwise_and(alpha, mask)
        
        # Resize to 500x500
        result = cv2.resize(result, (500, 500), interpolation=cv2.INTER_LANCZOS4)
        
        return result
    
    def cleanup_token(self, token_path: Path, output_dir: Path, debug: bool = False):
        """Clean up a single token."""
        token_img = cv2.imread(str(token_path), cv2.IMREAD_UNCHANGED)
        token_name = token_path.stem
        
        # Classify shape
        shape = self.classify_token_shape(token_img, token_name, debug)
        
        # Apply template
        cleaned = self.apply_template_cleanup(token_img, shape, debug, token_name)
        
        # Save
        output_path = output_dir / token_path.name
        cv2.imwrite(str(output_path), cleaned)
        print(f"  [+] Cleaned: {token_path.name}")
    
    def cleanup_team_tokens(self, team_name: str, extracted_dir: Path, output_dir: Path, debug: bool = False):
        """Clean up all tokens for a team."""
        team_dir = extracted_dir / team_name
        
        if not team_dir.exists():
            print(f"No extracted tokens found for {team_name}")
            return
        
        output_team_dir = output_dir / team_name
        output_team_dir.mkdir(parents=True, exist_ok=True)
        
        tokens = list(team_dir.glob("*.png"))
        print(f"Processing {len(tokens)} tokens for {team_name}...")
        
        for token_path in tokens:
            self.cleanup_token(token_path, output_team_dir, debug)
        
        print(f"[+] Cleaned {len(tokens)} tokens")
        print(f"  Output: {output_team_dir}")


def main():
    parser = argparse.ArgumentParser(description="Extract and clean tokens from PDF")
    parser.add_argument("--team", help="Team name to process")
    parser.add_argument("--pdf", help="Specific PDF path (overrides auto-detection)")
    parser.add_argument("--all", action="store_true", help="Process all teams")
    parser.add_argument("--debug", action="store_true", help="Enable debug output")
    parser.add_argument("--extract-only", action="store_true", help="Only extract, don't clean")
    parser.add_argument("--clean-only", action="store_true", help="Only clean existing extracted tokens")
    
    args = parser.parse_args()
    
    if not args.team and not args.all:
        parser.error("Must specify --team or --all")
    
    # Paths
    processed_dir = Path("processed")
    extracted_dir = Path("dev/extracted-tokens-pdf")
    cleaned_dir = Path("dev/cleaned-tokens")
    
    extractor = TokenExtractor()
    cleaner = TokenCleaner()
    
    # Get teams to process
    teams = []
    if args.all:
        teams = [p.name for p in processed_dir.iterdir() if p.is_dir()]
    else:
        teams = [args.team]
    
    for team in teams:
        print(f"\n{'='*60}")
        print(f"Processing: {team}")
        print(f"{'='*60}")
        
        # Find equipment or faction rules PDF (equipment typically has full token guides)
        team_dir = processed_dir / team
        
        if args.pdf:
            pdf_path = Path(args.pdf)
        else:
            pdf_candidates = list(team_dir.glob("*-equipment.pdf"))
            
            if not pdf_candidates:
                pdf_candidates = list(team_dir.glob("*-faction-rules.pdf"))
            
            if not pdf_candidates:
                pdf_candidates = list(team_dir.glob("*.pdf"))
            
            if not pdf_candidates:
                print(f"Warning: No PDF found for {team}, skipping")
                continue
            
            pdf_path = pdf_candidates[0]
        
        # Stage 1: Extract
        if not args.clean_only:
            team_output_dir = extracted_dir / team
            extractor.extract_tokens_from_pdf(pdf_path, team_output_dir, team)
        
        # Stage 2: Clean
        if not args.extract_only:
            cleaner.cleanup_team_tokens(team, extracted_dir, cleaned_dir, args.debug)


if __name__ == "__main__":
    # Need to import io here
    import io
    main()
