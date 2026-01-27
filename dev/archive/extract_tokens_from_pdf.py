"""
Extract tokens directly from PDF token guide with template-based shape cutting.

This extracts tokens from the last page of the faction rules PDF (if it contains
a token guide), then fits a shape template (round or operative) to each detected
token and makes everything outside the template transparent.
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import fitz  # PyMuPDF
import sys
import re
import easyocr

# Add script directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "script"))


class PDFTokenExtractor:
    def __init__(self):
        # Template paths - use averaged template for smoother edges
        self.operative_template_path = Path("dev/averaged-operative-template.png")
        self.round_template_path = Path("output_v2/imperium/kasrkin/tts/token/kasrkin-clearance-sweep.png")
        
        # Initialize OCR reader (lazy loaded)
        self._ocr_reader = None
        
        # Team-specific name corrections (maps extracted name -> correct name)
        self.name_corrections = {
            "hearthkyn-salvagers": {
                "utility": "utility-grenade",
                "pan-spectral": "pan-spectral-scan",
                "spot-token": "spot",
                "medic-token": "medic",
                "system-jam-token-c8-hx-charge-token": "system-jam",
                "grenade-marker": "utility-grenade",
                "marker-defence-marker-writ-of-claim": "defence",
                "pan-spectral-scan-marker": "attack",
            },
            "blades-of-khaine": {
                "wraithbone-talisman-token": "wraithbone-talisman",
                "rune-of-shielding-token": "rune-of-shielding",
                "rune-of-prophecy-token": "rune-of-prophecy",
            }
        }
        
        # Team-specific shape overrides (maps token name -> shape)
        self.shape_overrides = {
            "blades-of-khaine": {
                "wraithbone-talisman": "round",
                "rune-of-shielding": "round",
                "rune-of-prophecy": "round",
            }
        }
    
    def get_ocr_reader(self):
        """Lazy load OCR reader (downloads models on first use)."""
        if self._ocr_reader is None:
            print("Initializing OCR reader (first run may download models)...")
            self._ocr_reader = easyocr.Reader(['en'], gpu=False)
        return self._ocr_reader
    
    def extract_text_with_ocr(self, img: np.ndarray, skip_header_percent: float = 5.0) -> dict:
        """Use OCR to extract text positions directly from the rendered image."""
        img_height = img.shape[0]
        skip_pixels = int(img_height * (skip_header_percent / 100))
        
        # Get OCR reader
        reader = self.get_ocr_reader()
        
        # Run OCR on full image
        results = reader.readtext(img)
        
        # Process results: results is list of (bbox, text, confidence)
        text_spans = []
        for bbox, text, confidence in results:
            if confidence < 0.3:  # Skip low confidence
                continue
            
            text = text.strip()
            if len(text) < 2:  # Skip very short text
                continue
            
            # bbox is [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            bbox_points = np.array(bbox)
            center_x = int(bbox_points[:, 0].mean())
            center_y = int(bbox_points[:, 1].mean())
            
            # Skip header area
            if center_y < skip_pixels:
                continue
            
            text_spans.append({
                'text': text,
                'x': center_x,
                'y': center_y,
                'bbox': bbox_points
            })
        
        # Group text spans that are close together (multi-line labels)
        # More aggressive grouping to combine multi-line token names
        text_spans.sort(key=lambda s: (s['y'], s['x']))
        
        grouped_texts = []
        used_indices = set()
        
        for i, span in enumerate(text_spans):
            if i in used_indices:
                continue
            
            current_group = [span]
            used_indices.add(i)
            
            # Look for text spans close vertically and horizontally
            # Use larger thresholds to combine multi-line names better
            for j in range(i + 1, len(text_spans)):
                if j in used_indices:
                    continue
                
                y_diff = text_spans[j]['y'] - current_group[-1]['y']
                x_diff = abs(text_spans[j]['x'] - current_group[0]['x'])
                
                # Larger thresholds: 60px vertical, 100px horizontal
                if y_diff < 60 and x_diff < 100:
                    current_group.append(text_spans[j])
                    used_indices.add(j)
            
            # Combine grouped texts
            combined_text = ' '.join([s['text'] for s in current_group])
            avg_x = sum([s['x'] for s in current_group]) / len(current_group)
            avg_y = sum([s['y'] for s in current_group]) / len(current_group)
            grouped_texts.append((int(avg_x), int(avg_y), combined_text))
        
        return {(x, y): text for x, y, text in grouped_texts}
        
    def extract_last_page_from_pdf(self, pdf_path: Path, dpi: int = 300, skip_header_percent: float = 5.0) -> tuple[np.ndarray | None, dict]:
        """Extract the last page of a PDF as a high-quality image and text labels."""
        try:
            doc = fitz.open(str(pdf_path))
            if len(doc) == 0:
                return None, {}
            
            # Get last page and render at high DPI
            page = doc[-1]
            mat = fitz.Matrix(dpi / 72, dpi / 72)
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to numpy array (RGB)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            
            # Convert RGB to BGR for OpenCV
            if pix.n == 3:  # RGB
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            elif pix.n == 4:  # RGBA
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            
            doc.close()
            
            # Extract text using OCR on the rendered image
            text_positions = self.extract_text_with_ocr(img, skip_header_percent)
            
            return img, text_positions
            
        except Exception as e:
            print(f"Error extracting PDF: {e}")
            return None, {}
    
    def detect_token_contours(self, img: np.ndarray, threshold: int = 200, skip_header_percent: float = 5.0) -> list:
        """Detect token contours in the image."""
        # Skip header area (just the black background at top)
        img_height = img.shape[0]
        skip_pixels = int(img_height * (skip_header_percent / 100))
        img_crop = img[skip_pixels:, :]
        
        gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
        
        # Threshold to get binary image
        _, binary = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
        
        # Morphological closing to connect breaks
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        
        # Find contours
        contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Adjust contour coordinates back to original image space
        contours_adjusted = []
        for c in contours:
            c_adj = c + np.array([0, skip_pixels])
            contours_adjusted.append(c_adj)
        
        # Filter by area and aspect ratio (skip double-stacked tokens)
        min_area = 5000  # Minimum pixel area for a token at 300 DPI
        min_dimension = 80  # Minimum width/height in pixels (lowered to capture smaller tokens)
        max_aspect_ratio = 2.0  # Skip very tall tokens (double-stacked)
        filtered = []
        for c in contours_adjusted:
            area = cv2.contourArea(c)
            x, y, w, h = cv2.boundingRect(c)
            aspect_ratio = max(h / w, w / h) if w > 0 else 999
            
            # Ensure token is big enough in both dimensions
            if area >= min_area and w >= min_dimension and h >= min_dimension and aspect_ratio <= max_aspect_ratio:
                filtered.append(c)
        
        return filtered
    
    def classify_token_shape(self, contour) -> str:
        """Determine if token is round or operative based on circularity and aspect ratio."""
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        x, y, w, h = cv2.boundingRect(contour)
        
        if perimeter == 0:
            return "operative"
        
        circularity = 4 * np.pi * area / (perimeter * perimeter)
        aspect_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 999
        
        # Round tokens must be very circular (circularity >= 0.85) AND have near 1:1 aspect ratio
        # Allow aspect ratio up to 1.15 to catch slightly non-square round tokens
        # Operative tokens are shield/badge shaped with lower circularity OR elongated aspect
        if circularity >= 0.85 and aspect_ratio < 1.15:
            return "round"
        else:
            return "operative"
    
    def load_template(self, shape: str) -> np.ndarray | None:
        """Load template image and extract alpha channel."""
        template_path = self.round_template_path if shape == "round" else self.operative_template_path
        
        if not template_path.exists():
            print(f"Warning: Template not found: {template_path}")
            return None
        
        try:
            # Try to load as grayscale first (for mask-only templates)
            img_gray = cv2.imread(str(template_path), cv2.IMREAD_GRAYSCALE)
            if img_gray is not None:
                return img_gray
            
            # Fallback: load as RGBA and extract alpha
            img = Image.open(template_path).convert('RGBA')
            alpha = np.array(img.getchannel('A'), dtype=np.uint8)
            return alpha
        except Exception as e:
            print(f"Error loading template: {e}")
            return None
    
    def fit_template_to_contour(self, token_img: np.ndarray, contour, template_alpha: np.ndarray) -> np.ndarray | None:
        """
        Fit template to token image by scaling to a standard size while preserving aspect ratio.
        Returns a binary mask where 255 = keep token, 0 = make transparent.
        """
        h, w = token_img.shape[:2]
        
        # Get template dimensions
        th, tw = template_alpha.shape[:2]
        template_aspect = tw / th
        
        # Target size: scale template to fill most of the token image
        # Use 85% of the smaller dimension to ensure template fits with padding
        target_size = int(min(h, w) * 0.85)
        
        # Calculate new dimensions preserving aspect ratio
        if template_aspect >= 1.0:
            # Width is larger or equal
            new_w = target_size
            new_h = int(target_size / template_aspect)
        else:
            # Height is larger
            new_h = target_size
            new_w = int(target_size * template_aspect)
        
        if new_w < 10 or new_h < 10:
            return None
            
        # Resize template preserving aspect ratio
        template_resized = cv2.resize(template_alpha, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
        
        # Create mask and center template on token image
        mask = np.zeros((h, w), dtype=np.uint8)
        
        # Center template on the token image
        cx = w // 2
        cy = h // 2
        
        x_start = cx - new_w // 2
        y_start = cy - new_h // 2
        x_end = x_start + new_w
        y_end = y_start + new_h
        
        # Clip to image bounds
        tx_start = max(0, -x_start)
        ty_start = max(0, -y_start)
        tx_end = new_w - max(0, x_end - w)
        ty_end = new_h - max(0, y_end - h)
        
        x_start = max(0, x_start)
        y_start = max(0, y_start)
        x_end = min(w, x_end)
        y_end = min(h, y_end)
        
        # Place template in mask
        if x_end > x_start and y_end > y_start and tx_end > tx_start and ty_end > ty_start:
            mask[y_start:y_end, x_start:x_end] = template_resized[ty_start:ty_end, tx_start:tx_end]
        
        return mask
    
    def apply_contour_mask(self, token_img: np.ndarray, contour, offset_x: int, offset_y: int) -> np.ndarray:
        """
        Apply contour as mask - make everything outside the contour transparent.
        Contour coordinates need to be adjusted by offset.
        """
        h, w = token_img.shape[:2]
        
        # Create mask from contour
        mask = np.zeros((h, w), dtype=np.uint8)
        
        # Adjust contour coordinates relative to the extracted region
        contour_local = contour - np.array([offset_x, offset_y])
        
        # Fill the contour
        cv2.drawContours(mask, [contour_local], -1, 255, -1)
        
        # Convert BGR to BGRA
        bgra = cv2.cvtColor(token_img, cv2.COLOR_BGR2BGRA)
        
        # Set alpha channel from mask
        bgra[:, :, 3] = mask
        
        # Set RGB to black in transparent areas
        transparent = (mask == 0)
        bgra[transparent, 0:3] = [0, 0, 0]
        
        return bgra
    
    def scale_token_to_fit(self, token_bgra: np.ndarray, target_border: int = 12) -> np.ndarray:
        """Scale up token content to fill image with small border."""
        # Find content bounding box
        alpha = token_bgra[:, :, 3]
        rows_with_content = np.any(alpha > 0, axis=1)
        cols_with_content = np.any(alpha > 0, axis=0)
        
        if not np.any(rows_with_content) or not np.any(cols_with_content):
            return token_bgra
        
        top = np.argmax(rows_with_content)
        bottom = len(rows_with_content) - np.argmax(rows_with_content[::-1])
        left = np.argmax(cols_with_content)
        right = len(cols_with_content) - np.argmax(cols_with_content[::-1])
        
        # Extract content
        content = token_bgra[top:bottom, left:right]
        
        # Calculate scale to fit with target border
        h, w = token_bgra.shape[:2]
        content_h, content_w = content.shape[:2]
        
        available_h = h - (2 * target_border)
        available_w = w - (2 * target_border)
        
        scale = min(available_w / content_w, available_h / content_h)
        
        # Only scale up, not down
        if scale > 1.0:
            new_w = int(content_w * scale)
            new_h = int(content_h * scale)
            content_scaled = cv2.resize(content, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
            
            # Create new image with scaled content centered
            result = np.zeros_like(token_bgra)
            y_offset = (h - new_h) // 2
            x_offset = (w - new_w) // 2
            result[y_offset:y_offset+new_h, x_offset:x_offset+new_w] = content_scaled
            
            return result
        
        return token_bgra
    
    def match_contour_to_text(self, text_pos: tuple, contours: list, max_distance: int = 400) -> tuple | None:
        """Find the closest contour to a text label position."""
        tx, ty = text_pos
        min_dist = float('inf')
        best_contour = None
        
        for contour in contours:
            # Get centroid of contour
            M = cv2.moments(contour)
            if M["m00"] == 0:
                continue
            
            cx = int(M["m10"] / M["m00"])
            cy = int(M["m01"] / M["m00"])
            
            dist = np.sqrt((cx - tx) ** 2 + (cy - ty) ** 2)
            if dist < min_dist and dist < max_distance:
                min_dist = dist
                best_contour = contour
        
        return best_contour
    
    def extract_tokens(self, pdf_path: Path, output_dir: Path, threshold: int = 200, team_name: str = "", debug: bool = False):
        """Main extraction pipeline."""
        print(f"Extracting tokens from: {pdf_path}")
        
        # Extract last page from PDF with text positions
        img, text_positions = self.extract_last_page_from_pdf(pdf_path, dpi=300)
        if img is None:
            print("Failed to extract page from PDF")
            return
        
        print(f"Extracted page: {img.shape}")
        print(f"Found {len(text_positions)} text labels")
        
        # Detect token contours
        contours = self.detect_token_contours(img, threshold=threshold)
        print(f"Found {len(contours)} token contours")
        
        # Debug: Save image with contours and text labels
        if debug:
            debug_img = img.copy()
            # Draw all contours
            cv2.drawContours(debug_img, contours, -1, (0, 255, 0), 2)
            # Draw text positions
            for (x, y), text in text_positions.items():
                cv2.circle(debug_img, (x, y), 5, (255, 0, 0), -1)
                cv2.putText(debug_img, text[:20], (x + 10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
            # Save debug image
            debug_path = output_dir / f"{team_name}-debug.png"
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(debug_path), debug_img)
            print(f"Debug image saved to: {debug_path}")
        
        # Filter text labels to meaningful token names
        ignore_patterns = [
            r'marker.*guide',
            r'token.*guide', 
            r'values?\s*\d',
            r'grudge',
            r'^page\s*\d',
        ]
        
        filtered_labels = {}
        for pos, text in text_positions.items():
            text_lower = text.lower()
            
            # Skip if matches ignore patterns
            if any(re.search(pattern, text_lower) for pattern in ignore_patterns):
                continue
            
            # Skip very short text
            if len(text) < 3:
                continue
            
            filtered_labels[pos] = text
        
        print(f"Found {len(filtered_labels)} token labels to extract")
        
        # Use name-first extraction: match each unique token name to closest contour (left/top)
        # This prevents duplicate contours being extracted
        self._extract_by_unique_names(img, contours, output_dir, team_name, filtered_labels)
    
    def _extract_by_text_labels(self, img: np.ndarray, contours: list, filtered_labels: dict, output_dir: Path, team_name: str):
        """Extract tokens by matching text labels to contours."""
        # Create output directory
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Track used contours to avoid duplicates
        used_contours = set()
        extracted_count = 0
        
        # Process each text label
        for text_pos, token_name_raw in filtered_labels.items():
            # Find nearest contour to this text label
            contour = self.match_contour_to_text(text_pos, contours, max_distance=400)
            if contour is None:
                print(f"  [!] No contour found for: {token_name_raw}")
                continue
            
            # Check if contour already used
            contour_id = id(contour)
            if contour_id in used_contours:
                continue
            used_contours.add(contour_id)
            
            # Classify shape
            shape = self.classify_token_shape(contour)
            
            # Convert text to safe filename
            safe_name = re.sub(r'[^a-z0-9]+', '-', token_name_raw.lower()).strip('-')
            
            # Apply team-specific name corrections FIRST
            if team_name in self.name_corrections and safe_name in self.name_corrections[team_name]:
                safe_name = self.name_corrections[team_name][safe_name]
            
            # THEN apply team-specific shape overrides
            if team_name in self.shape_overrides and safe_name in self.shape_overrides[team_name]:
                shape = self.shape_overrides[team_name][safe_name]
            
            # Get bounding box with padding
            x, y, w, h = cv2.boundingRect(contour)
            padding = 20
            
            # For round tokens, use square bounding box to avoid oval distortion
            if shape == "round":
                # Use the larger dimension for both width and height
                size = max(w, h)
                # Center the square on the contour center
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                else:
                    cx = x + w // 2
                    cy = y + h // 2
                
                # For round tokens, reduce the size to avoid including background
                # The contour detection tends to include background edges
                size = int(size * 0.88)  # Shrink by 12%
                
                x1 = max(0, cx - size // 2 - padding)
                y1 = max(0, cy - size // 2 - padding)
                x2 = min(img.shape[1], cx + size // 2 + padding)
                y2 = min(img.shape[0], cy + size // 2 + padding)
            else:
                # For operative tokens, use the actual bounding box
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(img.shape[1], x + w + padding)
                y2 = min(img.shape[0], y + h + padding)
            
            # Extract token image
            token_img = img[y1:y2, x1:x2].copy()
            
            # Apply contour as mask to make outside transparent
            token_bgra = self.apply_contour_mask(token_img, contour, x1, y1)
            
            # Scale token to fill image with small border
            token_bgra = self.scale_token_to_fit(token_bgra, target_border=10)
            
            # Resize to standard 512×512 for uniformity (matches output_v2)
            token_bgra = cv2.resize(token_bgra, (512, 512), interpolation=cv2.INTER_LINEAR)
            
            # Add team prefix if provided (safe_name was already corrected above)
            if team_name:
                filename = f"{team_name}-{safe_name}.png"
            else:
                filename = f"{safe_name}.png"
            
            # Save token
            output_path = output_dir / filename
            
            # Convert BGRA to RGBA for PIL
            token_rgba = cv2.cvtColor(token_bgra, cv2.COLOR_BGRA2RGBA)
            Image.fromarray(token_rgba, mode='RGBA').save(str(output_path))
            
            extracted_count += 1
            print(f"  [+] Saved: {output_path.name} ({shape}, {w}x{h})")
        
        print(f"\n[+] Extracted {extracted_count} tokens")
    
    def _extract_by_unique_names(self, img: np.ndarray, contours: list, output_dir: Path, team_name: str, text_labels: dict):
        """Extract tokens by unique names - match each name to closest contour (left/top)."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        extracted_count = 0
        used_contours = set()
        
        # For each text label, find the closest contour to the LEFT or TOP
        for (tx, ty), token_name_raw in text_labels.items():
            min_dist = float('inf')
            best_contour = None
            
            for contour in contours:
                # Skip if already used
                if id(contour) in used_contours:
                    continue
                
                # Get contour center
                M = cv2.moments(contour)
                if M["m00"] == 0:
                    continue
                
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                # Calculate distance, prioritizing left/top
                # Token is typically to the left or above the text
                dx = tx - cx  # Positive if text is to the right of contour
                dy = ty - cy  # Positive if text is below contour
                
                # Only consider contours that are left or above
                if dx < -50 or dy < -50:  # Text too far left/above contour
                    continue
                
                # Calculate distance with preference for left/top
                dist = np.sqrt(dx**2 + dy**2)
                
                if dist < min_dist:
                    min_dist = dist
                    best_contour = contour
            
            # Skip if no contour found nearby
            if best_contour is None or min_dist > 400:
                print(f"  [!] No contour found for: {token_name_raw}")
                continue
            
            # Mark contour as used
            used_contours.add(id(best_contour))
            
            # Classify shape
            shape = self.classify_token_shape(best_contour)
            
            # Convert text to safe filename
            safe_name = re.sub(r'[^a-z0-9]+', '-', token_name_raw.lower()).strip('-')
            
            # Apply team-specific name corrections
            if team_name in self.name_corrections and safe_name in self.name_corrections[team_name]:
                safe_name = self.name_corrections[team_name][safe_name]
            
            # Apply team-specific shape overrides
            if team_name in self.shape_overrides and safe_name in self.shape_overrides[team_name]:
                shape = self.shape_overrides[team_name][safe_name]
            
            # Get bounding box with padding
            x, y, w, h = cv2.boundingRect(best_contour)
            padding = 20
            
            # For round tokens, use square bounding box
            if shape == "round":
                size = max(w, h)
                M = cv2.moments(best_contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                else:
                    cx = x + w // 2
                    cy = y + h // 2
                
                size = int(size * 0.88)
                
                x1 = max(0, cx - size // 2 - padding)
                y1 = max(0, cy - size // 2 - padding)
                x2 = min(img.shape[1], cx + size // 2 + padding)
                y2 = min(img.shape[0], cy + size // 2 + padding)
            else:
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(img.shape[1], x + w + padding)
                y2 = min(img.shape[0], y + h + padding)
            
            # Extract token image
            token_img = img[y1:y2, x1:x2].copy()
            
            # Apply contour as mask
            token_bgra = self.apply_contour_mask(token_img, best_contour, x1, y1)
            
            # Scale and resize
            token_bgra = self.scale_token_to_fit(token_bgra, target_border=10)
            token_bgra = cv2.resize(token_bgra, (512, 512), interpolation=cv2.INTER_LINEAR)
            
            # Save
            if team_name:
                filename = f"{team_name}-{safe_name}.png"
            else:
                filename = f"{safe_name}.png"
            
            output_path = output_dir / filename
            token_rgba = cv2.cvtColor(token_bgra, cv2.COLOR_BGRA2RGBA)
            Image.fromarray(token_rgba, mode='RGBA').save(str(output_path))
            
            extracted_count += 1
            print(f"  [+] Saved: {output_path.name} ({shape}, {w}x{h})")
        
        print(f"\n[+] Extracted {extracted_count} tokens")
    
    def _extract_by_contours(self, img: np.ndarray, contours: list, output_dir: Path, team_name: str, text_labels: dict):
        """Extract all contours as tokens, try to find names from text labels."""
        output_dir.mkdir(parents=True, exist_ok=True)
        
        extracted_count = 0
        used_names = set()
        
        for idx, contour in enumerate(contours):
            # Try to find closest text label for naming
            min_dist = float('inf')
            best_name = None
            
            M = cv2.moments(contour)
            if M["m00"] != 0:
                cx = int(M["m10"] / M["m00"])
                cy = int(M["m01"] / M["m00"])
                
                for (tx, ty), text in text_labels.items():
                    dist = np.sqrt((cx - tx) ** 2 + (cy - ty) ** 2)
                    if dist < min_dist:
                        min_dist = dist
                        best_name = text
            
            # Use found name or generate one (use higher distance threshold for small tokens)
            if best_name and min_dist < 300:
                token_name_raw = best_name
            else:
                token_name_raw = f"token-{idx+1}"
            
            # Classify shape
            shape = self.classify_token_shape(contour)
            
            # Convert text to safe filename
            safe_name = re.sub(r'[^a-z0-9]+', '-', token_name_raw.lower()).strip('-')
            
            # Apply team-specific name corrections
            if team_name in self.name_corrections and safe_name in self.name_corrections[team_name]:
                safe_name = self.name_corrections[team_name][safe_name]
            
            # Apply team-specific shape overrides
            if team_name in self.shape_overrides and safe_name in self.shape_overrides[team_name]:
                shape = self.shape_overrides[team_name][safe_name]
            
            # Get bounding box with padding
            x, y, w, h = cv2.boundingRect(contour)
            padding = 20
            
            if shape == "round":
                size = max(w, h)
                M = cv2.moments(contour)
                if M["m00"] != 0:
                    cx = int(M["m10"] / M["m00"])
                    cy = int(M["m01"] / M["m00"])
                else:
                    cx = x + w // 2
                    cy = y + h // 2
                
                size = int(size * 0.88)
                
                x1 = max(0, cx - size // 2 - padding)
                y1 = max(0, cy - size // 2 - padding)
                x2 = min(img.shape[1], cx + size // 2 + padding)
                y2 = min(img.shape[0], cy + size // 2 + padding)
            else:
                x1 = max(0, x - padding)
                y1 = max(0, y - padding)
                x2 = min(img.shape[1], x + w + padding)
                y2 = min(img.shape[0], y + h + padding)
            
            # Extract token image
            token_img = img[y1:y2, x1:x2].copy()
            
            # Apply contour as mask
            token_bgra = self.apply_contour_mask(token_img, contour, x1, y1)
            
            # Scale token to fill image with small border
            token_bgra = self.scale_token_to_fit(token_bgra, target_border=10)
            
            # Resize to standard 512×512
            token_bgra = cv2.resize(token_bgra, (512, 512), interpolation=cv2.INTER_LINEAR)
            
            # Add team prefix
            if team_name:
                filename = f"{team_name}-{safe_name}.png"
            else:
                filename = f"{safe_name}.png"
            
            # Avoid duplicate filenames
            if filename in used_names:
                filename = f"{team_name}-{safe_name}-{idx+1}.png" if team_name else f"{safe_name}-{idx+1}.png"
            used_names.add(filename)
            
            # Save token
            output_path = output_dir / filename
            token_rgba = cv2.cvtColor(token_bgra, cv2.COLOR_BGRA2RGBA)
            Image.fromarray(token_rgba, mode='RGBA').save(str(output_path))
            
            extracted_count += 1
            print(f"  [+] Saved: {output_path.name} ({shape}, {w}x{h})")
        
        print(f"\n[+] Extracted {extracted_count} tokens")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Extract tokens from PDF with template fitting")
    parser.add_argument("--team", required=True, help="Team name (e.g., hearthkyn-salvagers)")
    parser.add_argument("--threshold", type=int, default=200, help="Threshold for contour detection")
    parser.add_argument("--debug", action="store_true", help="Save debug image with contours")
    args = parser.parse_args()
    
    team_name = args.team
    
    # Find PDF path - check both processed and output_v2
    pdf_paths = list(Path("processed").rglob(f"*{team_name}*faction*.pdf"))
    if not pdf_paths:
        pdf_paths = list(Path("output_v2").rglob(f"*{team_name}*faction*.pdf"))
    
    if not pdf_paths:
        print(f"Error: Could not find PDF for team: {team_name}")
        return
    
    pdf_path = pdf_paths[0]
    
    # Output to dev directory
    output_dir = Path("dev") / "extracted-tokens-pdf" / team_name
    
    # Extract tokens
    extractor = PDFTokenExtractor()
    extractor.extract_tokens(pdf_path, output_dir, threshold=args.threshold, team_name=team_name, debug=args.debug)
    
    print(f"\n[+] Extraction complete!")
    print(f"  Output: {output_dir}")


if __name__ == "__main__":
    main()
