"""
Second-pass cleanup for extracted tokens using template cutters.

This script takes already-extracted token images and applies template masks
to remove any remaining background artifacts around the edges.
"""

import cv2
import numpy as np
from pathlib import Path
from PIL import Image
import sys

def load_template(template_path: Path) -> np.ndarray:
    """Load template and extract alpha channel as mask."""
    if not template_path.exists():
        return None
    
    template = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
    if template is None:
        return None
    
    # Extract alpha channel as mask (0-255)
    if len(template.shape) == 3 and template.shape[2] == 4:
        mask = template[:, :, 3]
    elif len(template.shape) == 3:
        # If no alpha, create mask from brightness
        gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    else:
        # Already grayscale
        _, mask = cv2.threshold(template, 10, 255, cv2.THRESH_BINARY)
    
    return mask

def classify_token_shape(token_img: np.ndarray, token_name: str = "") -> str:
    """Classify if token is round or operative based on content."""
    if token_img.shape[2] != 4:
        return "operative"
    
    # Get alpha channel
    alpha = token_img[:, :, 3]
    
    # Erode to remove artifacts and get main content shape
    alpha_eroded = cv2.erode(alpha, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
    
    # Threshold to get binary
    _, binary = cv2.threshold(alpha_eroded, 10, 255, cv2.THRESH_BINARY)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) == 0:
        return "operative"
    
    # Get largest contour
    contour = max(contours, key=cv2.contourArea)
    
    # Get bounding rect
    x, y, w, h = cv2.boundingRect(contour)
    
    # Calculate aspect ratio
    aspect_ratio = max(h / w, w / h) if w > 0 and h > 0 else 1.0
    
    # Calculate circularity: 4π * area / perimeter²
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)
    circularity = (4 * np.pi * area) / (perimeter * perimeter) if perimeter > 0 else 0
    
    # Debug output
    print(f"  Classification {token_name[:30]}: aspect={aspect_ratio:.3f}, circularity={circularity:.3f} -> {('round' if aspect_ratio < 1.15 and circularity >= 0.75 else 'operative')}")
    
    # Round tokens have aspect ratio close to 1 AND high circularity (lowered to 0.75 for eroded shapes)
    if aspect_ratio < 1.15 and circularity >= 0.75:
        return "round"
    else:
        return "operative"

def apply_template_cleanup(token_img: np.ndarray, template_mask: np.ndarray, shape: str, debug: bool = False, token_name: str = "") -> np.ndarray:
    """Apply template mask to clean up token edges by fitting template to token."""
    # Ensure token is 512x512 BGRA
    if token_img.shape[0] != 512 or token_img.shape[1] != 512:
        token_img = cv2.resize(token_img, (512, 512), interpolation=cv2.INTER_LINEAR)
    
    if token_img.shape[2] != 4:
        # Convert to BGRA if needed
        token_img = cv2.cvtColor(token_img, cv2.COLOR_BGR2BGRA)
    
    # Get alpha channel and detect token contour
    alpha = token_img[:, :, 3]
    
    # Threshold to get binary
    _, binary = cv2.threshold(alpha, 10, 255, cv2.THRESH_BINARY)
    
    # Find contours
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    if len(contours) == 0:
        return token_img
    
    # Get the largest contour (the token)
    token_contour = max(contours, key=cv2.contourArea)
    
    result = token_img.copy()
    
    # For round tokens, use a perfect circle template
    if shape == "round":
        # Erode alpha to find main content center
        alpha_eroded = cv2.erode(alpha, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
        _, binary_clean = cv2.threshold(alpha_eroded, 10, 255, cv2.THRESH_BINARY)
        contours_clean, _ = cv2.findContours(binary_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        if len(contours_clean) > 0:
            main_contour = max(contours_clean, key=cv2.contourArea)
            (cx, cy), radius = cv2.minEnclosingCircle(main_contour)
        else:
            (cx, cy), radius = cv2.minEnclosingCircle(token_contour)
        
        cx, cy = int(cx), int(cy)
        radius = int(radius)
        
        # Reduce radius by 5% to ensure we cut off all background artifacts
        radius = int(radius * 0.95)
        
        # Create perfect circular template mask
        template_circle = np.zeros((512, 512), dtype=np.uint8)
        cv2.circle(template_circle, (cx, cy), radius, 255, -1)
        
        # Apply Gaussian blur to smooth edges
        template_circle = cv2.GaussianBlur(template_circle, (5, 5), 1)
        
        # This is our cutter
        mask = template_circle
        
        # Debug visualization
        if debug:
            debug_img = cv2.cvtColor(token_img[:, :, :3], cv2.COLOR_BGR2RGB)
            # Draw original contour in red
            cv2.drawContours(debug_img, [token_contour], -1, (255, 0, 0), 2)
            # Draw the template circle in green
            cv2.circle(debug_img, (cx, cy), radius, (0, 255, 0), 3)
            # Show semi-transparent mask overlay
            mask_colored = np.zeros_like(debug_img)
            mask_colored[:, :, 1] = mask
            debug_img = cv2.addWeighted(debug_img, 0.7, mask_colored, 0.3, 0)
            # Save debug image
            debug_path = Path(f"dev/cleaned-tokens-debug/{token_name}-debug.png")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(debug_path), cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR))
            print(f"    Debug: cx={cx}, cy={cy}, radius={radius} (perfect circle template)")
        
        # Apply template mask
        result[:, :, 3] = cv2.bitwise_and(result[:, :, 3], mask)
        
    else:
        # For operative tokens, fit the template to the token
        # Use eroded alpha to find main content without artifacts
        alpha_eroded = cv2.erode(alpha, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
        _, binary_clean = cv2.threshold(alpha_eroded, 10, 255, cv2.THRESH_BINARY)
        contours_clean, _ = cv2.findContours(binary_clean, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Get bounding box of clean content
        if len(contours_clean) > 0:
            main_contour = max(contours_clean, key=cv2.contourArea)
            x, y, w, h = cv2.boundingRect(main_contour)
        else:
            x, y, w, h = cv2.boundingRect(token_contour)
        
        # Expand the dimensions slightly to ensure template covers the full token
        scale_factor = 1.08  # 8% larger to cover edges
        w_scaled = int(w * scale_factor)
        h_scaled = int(h * scale_factor)
        
        # Center the scaled box on the original position
        x_centered = x - (w_scaled - w) // 2
        y_centered = y - (h_scaled - h) // 2
        
        # Resize template to match scaled dimensions
        template_resized = cv2.resize(template_mask, (w_scaled, h_scaled), interpolation=cv2.INTER_LINEAR)
        
        # Create full-size mask and place resized template at token position
        mask = np.zeros((512, 512), dtype=np.uint8)
        
        # Calculate placement bounds (clip to image boundaries)
        y1 = max(0, y_centered)
        y2 = min(512, y_centered + h_scaled)
        x1 = max(0, x_centered)
        x2 = min(512, x_centered + w_scaled)
        
        # Adjust template slice if token is at edge
        ty1 = 0 if y_centered >= 0 else -y_centered
        ty2 = h_scaled if y_centered + h_scaled <= 512 else 512 - y_centered
        tx1 = 0 if x_centered >= 0 else -x_centered
        tx2 = w_scaled if x_centered + w_scaled <= 512 else 512 - x_centered
        
        # Place template
        mask[y1:y2, x1:x2] = template_resized[ty1:ty2, tx1:tx2]
        
        # Apply Gaussian blur to smooth edges
        mask = cv2.GaussianBlur(mask, (5, 5), 1)
        
        # Debug visualization
        if debug:
            debug_img = cv2.cvtColor(token_img[:, :, :3], cv2.COLOR_BGR2RGB)
            # Draw original contour in red
            cv2.drawContours(debug_img, [token_contour], -1, (255, 0, 0), 2)
            # Draw clean content contour in yellow
            if len(contours_clean) > 0:
                cv2.drawContours(debug_img, [main_contour], -1, (255, 255, 0), 2)
            # Draw template bounds in green
            cv2.rectangle(debug_img, (x_centered, y_centered), (x_centered + w_scaled, y_centered + h_scaled), (0, 255, 0), 3)
            # Show semi-transparent mask overlay
            mask_colored = np.zeros_like(debug_img)
            mask_colored[:, :, 1] = mask
            debug_img = cv2.addWeighted(debug_img, 0.7, mask_colored, 0.3, 0)
            # Save debug image
            debug_path = Path(f"dev/cleaned-tokens-debug/{token_name}-debug.png")
            debug_path.parent.mkdir(parents=True, exist_ok=True)
            cv2.imwrite(str(debug_path), cv2.cvtColor(debug_img, cv2.COLOR_RGB2BGR))
            print(f"    Debug: operative template {w_scaled}x{h_scaled} at ({x_centered}, {y_centered}) [scaled {scale_factor:.0%}]")
        
        # Apply template mask
        result[:, :, 3] = cv2.bitwise_and(result[:, :, 3], mask)
    
    # Resize to 500x500 to match output_v2 format
    result = cv2.resize(result, (500, 500), interpolation=cv2.INTER_LINEAR)
    
    return result

def cleanup_token(input_path: Path, output_path: Path, template_mask: np.ndarray, round_mask: np.ndarray = None, debug: bool = False):
    """Clean up a single token using template."""
    # Load token
    token_bgra = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if token_bgra is None:
        print(f"  [!] Failed to load: {input_path.name}")
        return False
    
    # Classify shape
    shape = classify_token_shape(token_bgra, input_path.stem)
    
    # Apply cleanup with debug output
    if shape == "round" and round_mask is not None:
        cleaned = apply_template_cleanup(token_bgra, round_mask, "round", debug, input_path.stem)
    else:
        cleaned = apply_template_cleanup(token_bgra, template_mask, shape, debug, input_path.stem)
    
    # Save cleaned token
    cv2.imwrite(str(output_path), cleaned)
    
    return True

def cleanup_team_tokens(team_name: str, debug: bool = False):
    """Clean up all tokens for a team."""
    input_dir = Path("dev/extracted-tokens-pdf") / team_name
    output_dir = Path("dev/cleaned-tokens") / team_name
    
    if not input_dir.exists():
        print(f"[!] Input directory not found: {input_dir}")
        return
    
    # Load template
    template_path = Path("dev/averaged-operative-template.png")
    template_mask = load_template(template_path)
    
    if template_mask is None:
        print(f"[!] Failed to load template: {template_path}")
        return
    
    # Create circular mask for round tokens
    round_mask = np.zeros((512, 512), dtype=np.uint8)
    cv2.circle(round_mask, (256, 256), 230, 255, -1)
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Process all token images (skip debug images)
    token_files = [f for f in input_dir.glob("*.png") if not f.name.endswith("-debug.png")]
    
    print(f"Processing {len(token_files)} tokens for {team_name}...")
    
    cleaned_count = 0
    for token_file in token_files:
        output_file = output_dir / token_file.name
        if cleanup_token(token_file, output_file, template_mask, round_mask, debug):
            cleaned_count += 1
            print(f"  [+] Cleaned: {token_file.name}")
    
    print(f"\n[+] Cleaned {cleaned_count} tokens")
    print(f"  Output: {output_dir}")
    if debug:
        print(f"  Debug images: dev/cleaned-tokens-debug/")

def main():
    if len(sys.argv) < 2:
        print("Usage: python dev/cleanup_extracted_tokens.py <team-name> [--debug]")
        print("Example: python dev/cleanup_extracted_tokens.py hearthkyn-salvagers --debug")
        sys.exit(1)
    
    team_name = sys.argv[1]
    debug = "--debug" in sys.argv
    cleanup_team_tokens(team_name, debug)

if __name__ == "__main__":
    main()
