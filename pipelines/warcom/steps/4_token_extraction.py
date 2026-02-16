"""
Step 3: Process Extracted Tokens with Template Cutout

Takes rough-cropped tokens from step 2 and:
1. Matches tokens to names using text elements
2. Looks up template shape from team config
3. Applies precise template cutout
4. Makes background transparent
5. Scales to target resolution (512x512)
6. Renames to actual token name

Usage:
    python pipelines/warcom/steps/3_token_processor_v2.py
"""

import argparse
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import yaml

import cv2
import numpy as np


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
TARGET_SIZE = 512  # Target resolution for tokens
BASE_DIR = Path("layers/warcom/extracted")
CONFIG_PATH = Path("config/team-config.yaml")
TEMPLATE_DIR = Path("config/defaults/tts-token")


def slugify(text: str) -> str:
    """Convert text to filename-safe slug."""
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


def load_team_config() -> Dict:
    """Load team configuration from YAML."""
    if not CONFIG_PATH.exists():
        logger.warning(f"Team config not found at {CONFIG_PATH}")
        return {}
    
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        return data.get('teams', {}) if data else {}


def get_token_shape(team_config: Dict, token_name: str) -> Optional[str]:
    """Get the configured shape for a token.
    
    Args:
        team_config: Team configuration dict
        token_name: Token name (e.g., 'Breach marker', 'Omniscanner token')
    
    Returns:
        Shape string ('round', 'octagon', 'diamond', 'operative') or None
    """
    tokens = team_config.get('tokens', [])
    if not tokens:
        return None
    
    # Normalize for matching (case-insensitive, whitespace-normalized, strip common suffixes)
    def normalize_name(name: str) -> str:
        norm = ' '.join(name.lower().split())
        # Strip common suffixes
        for suffix in [' token', ' marker', ' tokens', ' markers']:
            if norm.endswith(suffix):
                norm = norm[:-len(suffix)].strip()
        return norm
    
    search_norm = normalize_name(token_name)
    
    for token_cfg in tokens:
        cfg_name = token_cfg.get('name', '')
        cfg_norm = normalize_name(cfg_name)
        
        if search_norm == cfg_norm:
            return token_cfg.get('shape')
    
    return None


def match_tokens_to_names(
    tokens: List[Dict],
    text_elements: List[Dict],
    team_config: Dict = None,
    max_x_distance: float = 600.0,
    max_y_distance: float = 1200.0
) -> Dict[str, str]:
    """Match tokens to their names using 1-to-1 assignment.
    
    Text labels are positioned RIGHT or BELOW tokens (never left/above).
    Coordinates may be at different scales (tokens at 150 DPI, text at 300 DPI).
    We scale text coordinates to match token coordinates before matching.
    
    Filters out tokens that match custom token names from config.
    
    Args:
        tokens: List of token dicts with 'filename' and 'bbox'
        text_elements: List of text elements with 'text' and 'bbox'
        team_config: Team configuration dict (for filtering custom tokens)
        max_x_distance: Maximum horizontal distance (after scaling)
        max_y_distance: Maximum vertical distance (after scaling)
    
    Returns:
        Dict mapping filename -> token_name
    """
    if not tokens or not text_elements:
        return {}
    
    # Step 1: Detect coordinate scale difference
    # Token coordinates are at detection DPI (e.g., 150)
    # Text coordinates are at 300 DPI (from PDF extraction in Step 2)
    # This creates a 2x scale difference (300/150 = 2)
    
    # Get coordinate ranges
    token_xs = [t['bbox']['x'] + t['bbox']['width'] / 2 for t in tokens]
    token_ys = [t['bbox']['y'] + t['bbox']['height'] / 2 for t in tokens]
    label_xs = [e['bbox']['x'] + e['bbox']['width'] / 2 for e in text_elements]
    label_ys = [e['bbox']['y'] + e['bbox']['height'] / 2 for e in text_elements]
    
    # Detect scale by comparing ranges
    token_x_range = max(token_xs) - min(token_xs) if len(token_xs) > 1 else 1
    label_x_range = max(label_xs) - min(label_xs) if len(label_xs) > 1 else 1
    token_y_range = max(token_ys) - min(token_ys) if len(token_ys) > 1 else 1
    label_y_range = max(label_ys) - min(label_ys) if len(label_ys) > 1 else 1
    
    # Calculate scale ratio (text_scale / token_scale)
    x_scale_ratio = label_x_range / token_x_range if token_x_range > 1 else 1.0
    y_scale_ratio = label_y_range / token_y_range if token_y_range > 1 else 1.0
    
    # Use average scale ratio (should be ~2.0 for 150 DPI detection / 300 DPI text)
    scale_ratio = (x_scale_ratio + y_scale_ratio) / 2
    
    # Step 2: Scale text coordinates to match token coordinate system
    scaled_label_xs = [x / scale_ratio for x in label_xs]
    scaled_label_ys = [y / scale_ratio for y in label_ys]
    
    # Step 3: Calculate distances for all token-label pairs
    # KillTeam cards have text labels positioned RIGHT or BELOW tokens (never left/above).
    # We prioritize horizontal alignment (column matching) over vertical distance.
    pairs = []  # List of (priority_score, token_idx, text_idx)
    
    for tok_idx, token in enumerate(tokens):
        # Token borders (edges)
        token_right = token['bbox']['x'] + token['bbox']['width']
        token_bottom = token['bbox']['y'] + token['bbox']['height']
        
        # Token center for distance calculations
        tx = token_xs[tok_idx]
        ty = token_ys[tok_idx]
        
        for txt_idx, elem in enumerate(text_elements):
            # Only match tokens and labels from the same source card
            if token.get('source_card') != elem.get('source_card'):
                continue
            
            ex = scaled_label_xs[txt_idx]
            ey = scaled_label_ys[txt_idx]
            
            # Text center must be RIGHT of token's right edge OR BELOW token's bottom edge
            # (never left of token border or above token border)
            if ex < token_right and ey < token_bottom:
                # Text is left of right edge AND above bottom edge = overlapping token bounds
                continue
            
            # Calculate distances from token center for priority scoring
            dx = ex - tx  # Signed: positive if label right of token center
            dy = ey - ty  # Signed: positive if label below token center
            
            # Calculate absolute distances for priority calculation
            dx_abs = abs(dx)
            dy_abs = abs(dy)
            
            # Skip if too far in either direction
            if dx_abs > max_x_distance or dy_abs > max_y_distance:
                continue
            
            # For labels BELOW: prioritize column alignment
            # For labels RIGHT: prioritize row alignment
            if dy > 30:  # Label clearly below token
                # Prioritize horizontal alignment for column matching
                priority = (dx_abs * 1.5) + (dy_abs * 0.3)
            else:  # Label to the right (dy near 0 or slightly negative)
                # Prioritize vertical alignment for row matching
                priority = (dy_abs * 1.5) + (dx_abs * 0.3)
            
            pairs.append((priority, tok_idx, txt_idx))
    
    # Sort by priority (best matches first)
    pairs.sort(key=lambda x: x[0])
    
    # Greedy assignment: assign best pairs first, skip if already used
    assigned_tokens = set()
    assigned_texts = set()
    result = {}
    
    for dist, tok_idx, txt_idx in pairs:
        if tok_idx in assigned_tokens or txt_idx in assigned_texts:
            continue
        
        # Assign this pair
        token = tokens[tok_idx]
        label = text_elements[txt_idx]
        result[token['filename']] = label['text']
        
        assigned_tokens.add(tok_idx)
        assigned_texts.add(txt_idx)
    
    # Filter out tokens that match custom token names
    filtered_custom = []
    if team_config:
        custom_token_names = set()
        for token_cfg in team_config.get('tokens', []):
            if token_cfg.get('type') == 'custom':
                # Normalize name for matching
                name = token_cfg.get('name', '').lower().strip()
                custom_token_names.add(name)
        
        # Remove matches where token name matches a custom token
        filtered_result = {}
        for filename, token_name in result.items():
            # Normalize token name for comparison
            normalized = token_name.lower().strip()
            # Remove common suffixes for matching
            for suffix in [' token', ' marker', ' tokens', ' markers']:
                if normalized.endswith(suffix):
                    normalized = normalized[:-len(suffix)].strip()
                    break
            
            # Skip if this matches a custom token name
            if normalized in custom_token_names:
                logger.info(f"  Skipping '{token_name}' - matches custom token (will use custom version)")
                filtered_custom.append(filename)
                continue
            
            filtered_result[filename] = token_name
        
        return filtered_result, filtered_custom
    
    return result, filtered_custom


def load_template_mask(shape: str) -> Optional[np.ndarray]:
    """Load template mask for a shape.
    
    Args:
        shape: Shape name ('round', 'octagon', 'diamond', 'operative')
    
    Returns:
        Binary mask (uint8, 0 or 255) or None if not found
    """
    template_path = TEMPLATE_DIR / f"template-{shape}-cutter.png"
    if not template_path.exists():
        logger.warning(f"Template not found: {template_path}")
        return None
    
    img = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    
    # Extract alpha channel
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
    else:
        # If no alpha, use non-white pixels
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        alpha = (gray < 250).astype(np.uint8) * 255
    
    # Binary mask
    mask = (alpha > 127).astype(np.uint8) * 255
    
    # Light smoothing only (no hole filling - template shapes are already clean)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    return mask


def fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill holes in a binary mask."""
    h, w = mask.shape[:2]
    flood_mask = np.zeros((h + 2, w + 2), dtype=np.uint8)
    cv2.floodFill(mask, flood_mask, (0, 0), 255)
    
    # Invert to get holes
    holes = cv2.bitwise_not(flood_mask[1:-1, 1:-1])
    
    # Fill holes
    return cv2.bitwise_or(mask, holes)


def _mask_bbox(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Get bounding box of mask (x, y, w, h)."""
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    x0 = int(xs.min())
    x1 = int(xs.max())
    y0 = int(ys.min())
    y1 = int(ys.max())
    return (x0, y0, x1 - x0 + 1, y1 - y0 + 1)


def _mask_fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill holes in mask (components not touching border)."""
    m = (mask > 0).astype(np.uint8)
    h, w = m.shape[:2]
    if h <= 1 or w <= 1:
        return m

    inv = (m == 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    if n <= 1:
        return m

    border_labels = set()
    for i in range(1, n):
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        ww = int(stats[i, cv2.CC_STAT_WIDTH])
        hh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if x <= 0 or y <= 0 or (x + ww) >= w or (y + hh) >= h:
            border_labels.add(i)

    holes = (inv > 0) & (~np.isin(labels, list(border_labels)))
    out = m.copy()
    out[holes] = 1
    return out.astype(np.uint8)


def _apply_inset_to_mask(mask: np.ndarray, scale: float = 0.95) -> np.ndarray:
    """Shrink mask by scaling around its centroid."""
    if scale >= 1.0:
        return mask
    
    m = (mask > 0).astype(np.uint8)
    ys, xs = np.where(m > 0)
    if xs.size == 0:
        return m
    
    cx = float(xs.mean())
    cy = float(ys.mean())
    
    h, w = m.shape[:2]
    
    # Create coordinate maps for inverse warping
    # For each destination pixel (y, x), we need to find which source pixel to sample from
    # To shrink around center: dest_coords = (source_coords - center) * scale + center
    # Inverse: source_coords = (dest_coords - center) / scale + center
    Y_indices, X_indices = np.meshgrid(np.arange(h), np.arange(w), indexing='ij')
    
    # Map destination coordinates back to source
    X_map = ((X_indices - cx) / scale + cx).astype(np.float32)
    Y_map = ((Y_indices - cy) / scale + cy).astype(np.float32)
    
    # Remap
    inset = cv2.remap(m, X_map, Y_map, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    return (inset > 0).astype(np.uint8)


def apply_template_mask(
    token_img: np.ndarray,
    template_mask: np.ndarray,
    shape: str,
    token_name: str,
    debug_path: Path = None
) -> np.ndarray:
    """Apply template mask using kt-app approach: simple white removal with fallback strategies.
    
    Uses content detection with multiple strategies scored by coverage/aspect/margins,
    then creates perfect shape mask from detected bounds.
    
    Args:
        token_img: Token image (BGR or BGRA)
        template_mask: Template binary mask
        shape: Token shape ('round', 'octagon', 'diamond', 'operative')
        token_name: Token name for debug output
        debug_path: Optional path to save debug visualization
    
    Returns:
        Token with transparency applied, cropped, and resized to template dimensions (BGRA)
    """
    h, w = token_img.shape[:2]
    
    # Ensure BGR for processing
    if len(token_img.shape) == 2:
        bgr = cv2.cvtColor(token_img, cv2.COLOR_GRAY2BGR)
    elif token_img.shape[2] == 4:
        bgr = token_img[:,:,:3].copy()
    else:
        bgr = token_img.copy()
    
    # Step 1: Simple white removal using HSV
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    s = hsv[:, :, 1]
    
    # Create initial alpha from non-white pixels
    is_white = ((v > 235) & (s < 20)) | ((bgr[:, :, 0] > 235) & (bgr[:, :, 1] > 235) & (bgr[:, :, 2] > 235))
    alpha = (~is_white).astype(np.uint8) * 255
    
    # Get largest foreground component
    simple_mask = alpha.copy()
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(simple_mask, connectivity=8)
    if num_labels > 1:
        largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
        simple_mask = (labels == largest_label).astype(np.uint8) * 255
    
    # Fill holes in simple mask 
    simple_mask = _mask_fill_holes(simple_mask)
    simple_mask = (simple_mask > 0).astype(np.uint8)
    
    # Step 2: Try multiple detection strategies if simple mask doesn't look good
    candidates = []
    
    # Strategy 1: Simple mask (already computed)
    candidates.append(("Simple", simple_mask.copy()))
    
    # Strategy 2: Tight thresholds + minimal dilation
    tight_mask = ((v > 245) & (s < 15)).astype(np.uint8)
    tight_fg = (tight_mask == 0).astype(np.uint8)
    if tight_fg.sum() > 100:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        tight_fg = cv2.dilate(tight_fg, k, iterations=1)
        tight_fg = _mask_fill_holes(tight_fg * 255)
        candidates.append(("Tight + Minimal", (tight_fg > 0).astype(np.uint8)))
    
    # Strategy 3: Tight + moderate dilation
    if tight_fg.sum() > 100:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        tight_mod = cv2.dilate(tight_fg, k, iterations=2)
        tight_mod = _mask_fill_holes(tight_mod * 255)
        candidates.append(("Tight + Moderate", (tight_mod > 0).astype(np.uint8)))
    
    # Strategy 4: Loose thresholds + minimal dilation
    loose_mask = ((v > 225) & (s < 25)).astype(np.uint8)
    loose_fg = (loose_mask == 0).astype(np.uint8)
    if loose_fg.sum() > 100:
        k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        loose_fg = cv2.dilate(loose_fg, k, iterations=1)
        loose_fg = _mask_fill_holes(loose_fg * 255)
        candidates.append(("Loose + Minimal", (loose_fg > 0).astype(np.uint8)))
    
    # Step 3: Score each candidate by coverage, aspect, and edge margins
    img_h, img_w = alpha.shape
    total_pixels = img_w * img_h
    
    best_score = -1000
    cand_expanded = None
    detection_method = None
    
    for name, candidate in candidates:
        bbox = _mask_bbox(candidate)
        if bbox is None:
            continue
        
        cx, cy, cw, ch = bbox
        coverage = (cw * ch) / total_pixels
        aspect = cw / float(ch) if ch > 0 else 1.0
        
        score = 0.0
        # Coverage scoring
        if 0.2 < coverage < 0.7:
            score += 100
        elif 0.15 < coverage < 0.8:
            score += 50
        elif 0.1 < coverage < 0.9:
            score += 20
        
        # Aspect scoring
        if 0.7 < aspect < 1.4:
            score += 50
        elif 0.5 < aspect < 2.0:
            score += 30
        elif 0.4 < aspect < 2.5:
            score += 10
        
        # Edge margin scoring (penalize if too close to edges)
        edge_margin = 5
        if cx < edge_margin or cy < edge_margin or (cx + cw) > (img_w - edge_margin) or (cy + ch) > (img_h - edge_margin):
            score -= 30
        
        # Prefer simpler strategies
        if "Simple" in name or "Minimal" in name:
            score += 10
        elif "Moderate" in name:
            score += 5
        
        if score > best_score:
            best_score = score
            cand_expanded = candidate
            detection_method = f"{name} (score: {score:.0f})"
    
    # Fallback: Use full alpha if no good candidate
    if cand_expanded is None:
        cand_expanded = simple_mask
        detection_method = "Fallback: Simple mask"
    
    # Step 4: Get content bounds and create perfect shape mask
    content_bbox = _mask_bbox(cand_expanded)
    if content_bbox is None:
        # Emergency fallback - just use simple mask
        token_bgra = cv2.cvtColor(bgr, cv2.COLOR_BGR2BGRA)
        token_bgra[:,:,3] = simple_mask * 255
        return token_bgra
    
    cx, cy, cw, ch = content_bbox
    center_x = cx + cw / 2.0
    center_y = cy + ch / 2.0
    
    # Create perfect shape mask based on detected shape
    best_fit = np.zeros((h, w), dtype=np.uint8)
    
    if shape == 'round':
        # Perfect circle
        radius = min(cw, ch) / 2.0
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
        best_fit[dist <= radius] = 1
    else:
        # Scale template to match content size and place at center
        templ_bbox = _mask_bbox(template_mask)
        if templ_bbox is not None:
            tx, ty, tw, th = templ_bbox
            scale_x = cw / float(tw)
            scale_y = ch / float(th)
            
            templ_resized = cv2.resize(
                (template_mask > 0).astype(np.uint8),
                (int(tw * scale_x), int(th * scale_y)),
                interpolation=cv2.INTER_LINEAR
            )
            
            # Place at content center
            th_new, tw_new = templ_resized.shape
            x0 = int(center_x - tw_new / 2.0)
            y0 = int(center_y - th_new / 2.0)
            
            x0 = max(0, x0)
            y0 = max(0, y0)
            x1 = min(w, x0 + tw_new)
            y1 = min(h, y0 + th_new)
            
            tw_crop = x1 - x0
            th_crop = y1 - y0
            
            best_fit[y0:y1, x0:x1] = templ_resized[:th_crop, :tw_crop]
        else:
            # Fallback to simple mask if template processing fails
            best_fit = cand_expanded
    
    # Debug visualization (only overlays, before inset/cropping)
    if debug_path is not None:
        debug_vis = bgr.copy()
        # Show expanded content area in green
        debug_vis[cand_expanded > 0] = (debug_vis[cand_expanded > 0] * 0.5 + np.array([0, 255, 0], dtype=np.uint8) * 0.5).astype(np.uint8)
        # Show template in red
        debug_vis[best_fit > 0] = (debug_vis[best_fit > 0] * 0.5 + np.array([255, 0, 0], dtype=np.uint8) * 0.5).astype(np.uint8)
        
        # Add text info
        text1 = f"Detection: {detection_method}"
        text2 = f"Shape: {shape}, bbox=({cx},{cy},{cw},{ch})"
        cv2.putText(debug_vis, text1, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 2)
        cv2.putText(debug_vis, text1, (10, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        cv2.putText(debug_vis, text2, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 2)
        cv2.putText(debug_vis, text2, (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        cv2.imwrite(str(debug_path), debug_vis)
    
    # Step 5: Apply 5% inset to template mask
    best_fit = _apply_inset_to_mask(best_fit, scale=0.95)
    
    # Create alpha channel (preserves white pixels inside template)
    alpha = np.where(best_fit > 0, 255, 0).astype(np.uint8)
    
    # Step 6: Fill transparent holes within template (2 passes to clean up artifacts)
    def _fill_transparent_holes_within_template(alpha_in: np.ndarray, template_in: np.ndarray) -> np.ndarray:
        """Fill small transparent holes that are surrounded by opaque pixels within template."""
        # Find transparent pixels within template
        transparent = (alpha_in == 0) & (template_in > 0)
        if not transparent.any():
            return alpha_in
        
        # Label transparent regions
        num_labels, labels = cv2.connectedComponents(transparent.astype(np.uint8))
        if num_labels <= 1:
            return alpha_in
        
        # Fill small holes (< 2% of template area)
        template_area = int((template_in > 0).sum())
        threshold_area = max(10, int(template_area * 0.02))
        
        alpha_out = alpha_in.copy()
        for i in range(1, num_labels):
            region_mask = (labels == i)
            region_area = int(region_mask.sum())
            if region_area < threshold_area:
                alpha_out[region_mask] = 255
        
        return alpha_out
    
    alpha = _fill_transparent_holes_within_template(alpha, best_fit)
    alpha = _fill_transparent_holes_within_template(alpha, best_fit)
    
    # Step 8: Crop to template bounds
    template_bbox = _mask_bbox(best_fit)
    if template_bbox is not None:
        x, y, w_crop, h_crop = template_bbox
        bgr = bgr[y:y+h_crop, x:x+w_crop]
        alpha = alpha[y:y+h_crop, x:x+w_crop]
        
        # Step 9: Resize to template size
        templ_h, templ_w = template_mask.shape[:2]
        if (w_crop, h_crop) != (templ_w, templ_h):
            bgr = cv2.resize(bgr, (templ_w, templ_h), interpolation=cv2.INTER_AREA)
            alpha = cv2.resize(alpha, (templ_w, templ_h), interpolation=cv2.INTER_AREA)
    
    # Create final BGRA
    token_bgra = np.dstack([bgr, alpha])
    
    return token_bgra


def normalize_background_to_white(img: np.ndarray) -> np.ndarray:
    """Convert light gray background to pure white."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1]
    v = hsv[:, :, 2]
    
    # Light and unsaturated = background
    background_mask = (s < 35) & (v > 160)
    
    # Set to white
    result = img.copy()
    result[background_mask] = [255, 255, 255]
    
    return result


def create_alpha_mask(img: np.ndarray) -> np.ndarray:
    """Create alpha mask from image (non-white = opaque)."""
    # Threshold to find non-white pixels
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
    
    # Morphological operations
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    # Fill contours
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    mask_filled = np.zeros_like(mask)
    cv2.drawContours(mask_filled, contours, -1, 255, -1)
    
    return mask_filled


def crop_to_content(img: np.ndarray) -> np.ndarray:
    """Crop image to content (transparent borders removed)."""
    if img.shape[2] != 4:
        return img
    
    alpha = img[:, :, 3]
    
    # Find non-transparent pixels
    coords = cv2.findNonZero(alpha)
    if coords is None:
        return img
    
    x, y, w, h = cv2.boundingRect(coords)
    
    # Add small padding
    padding = 2
    x = max(0, x - padding)
    y = max(0, y - padding)
    w = min(img.shape[1] - x, w + 2 * padding)
    h = min(img.shape[0] - y, h + 2 * padding)
    
    return img[y:y+h, x:x+w]


def scale_to_target(img: np.ndarray, target_size: int = TARGET_SIZE) -> np.ndarray:
    """Scale image to fit within target size (preserving aspect ratio).
    
    Always scales to target size - upscales small tokens, downscales large ones.
    This ensures consistent sizing for TTS.
    """
    h, w = img.shape[:2]
    
    # Calculate scale factor to fit within target
    scale = min(target_size / w, target_size / h)
    
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # Use appropriate interpolation
    if scale > 1.0:
        # Upscaling - use cubic for smoother result
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
    else:
        # Downscaling - use area for best quality
        return cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)


def process_token(
    token_path: Path,
    token_meta: Dict,
    token_name: Optional[str],
    shape: str,
    template_mask: Optional[np.ndarray],
    team_slug: str,
    debug_dir: Path = None
) -> Tuple[Optional[np.ndarray], str]:
    """Process a single token.
    
    Args:
        token_path: Path to token image file
        token_meta: Token metadata dict
        token_name: Token name (e.g., 'Breach marker')
        shape: Token shape ('round', 'octagon', 'diamond', 'operative')
        template_mask: Template binary mask
        team_slug: Team slug for filename prefix
        debug_dir: Optional debug output directory
    
    Returns:
        (processed_image, output_filename) or (None, error_message)
    """
    # Load token
    img = cv2.imread(str(token_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None, f"Failed to load {token_path}"
    
    # Ensure BGR
    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
    
    # Normalize background
    img = normalize_background_to_white(img)
    
    # Apply template mask (required - should never be None now)
    if template_mask is None:
        return None, f"ERROR: No template mask for {token_path.name}"
    
    # Generate debug path if debug_dir is provided
    debug_path = None
    if debug_dir and token_name:
        debug_path = debug_dir / f"{slugify(token_name)}_debug.png"
    
    # Apply template mask (includes cropping and resizing to template size ~200px)
    img = apply_template_mask(img, template_mask, shape, token_name, debug_path)
    
    # Generate output filename with team prefix
    if token_name:
        output_name = f'{team_slug}-{slugify(token_name)}.png'
    else:
        # Fallback to original filename with prefix
        output_name = f'{team_slug}-{token_path.name}'
    
    return img, output_name


def process_team(team_slug: str, team_config: Dict, all_teams_config: Dict) -> Dict[str, int]:
    """Process all tokens for a team.
    
    Returns:
        Dict with 'processed', 'skipped', 'failed' counts
    """
    team_path = BASE_DIR / team_slug
    tokens_dir = team_path / "tokens"
    metadata_path = tokens_dir / 'tokens_metadata.json'
    output_dir = Path("output") / team_slug / "tokens"
    
    stats = {'processed': 0, 'skipped': 0, 'failed': 0}
    
    # Check if metadata exists
    if not metadata_path.exists():
        logger.warning(f"No metadata found for {team_slug}, skipping")
        return stats
    
    # Load metadata
    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
    
    tokens = metadata.get('tokens', [])
    text_elements = metadata.get('text_elements', [])
    
    if not tokens:
        logger.warning(f"No tokens in metadata for {team_slug}")
        return stats
    
    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create debug directory for template fit visualization (only for first team)
    debug_dir = None
    if team_slug == 'battleclade':
        debug_dir = team_path / 'debug'
        debug_dir.mkdir(parents=True, exist_ok=True)
    
    # Match ALL tokens to names at once (1-to-1 assignment)
    # Text coordinates are scaled to match token coordinate system (handles 2x DPI difference)
    # Filters out tokens matching custom token names from config
    token_names, filtered_custom = match_tokens_to_names(
        tokens,
        text_elements,
        team_config=team_config,
        max_x_distance=600,  # Wide card layouts
        max_y_distance=1200  # Labels can be far below or to the right
    )
    
    # STRICT VALIDATION 1: All tokens must be matched to names (excluding custom-filtered tokens)
    unmatched_tokens = [t['filename'] for t in tokens if t['filename'] not in token_names and t['filename'] not in filtered_custom]
    if unmatched_tokens:
        logger.error(f"  ERROR: {len(unmatched_tokens)} tokens could not be matched to names:")
        for fname in unmatched_tokens[:5]:  # Show first 5
            logger.error(f"    - {fname}")
        if len(unmatched_tokens) > 5:
            logger.error(f"    ... and {len(unmatched_tokens) - 5} more")
        logger.error(f"  This indicates a problem with token-to-label matching or team config.")
    
    # STRICT VALIDATION 2: All matched names must exist in config with shapes
    missing_in_config = []
    missing_shapes = []
    for filename, token_name in token_names.items():
        shape = get_token_shape(team_config, token_name)
        if not shape:
            # Check if token exists in config but has no shape, or doesn't exist at all
            tokens_cfg = team_config.get('tokens', []) if team_config else []
            def normalize_name(name: str) -> str:
                norm = ' '.join(name.lower().split())
                for suffix in [' token', ' marker', ' tokens', ' markers']:
                    if norm.endswith(suffix):
                        norm = norm[:-len(suffix)].strip()
                return norm
            
            search_norm = normalize_name(token_name)
            found_in_config = any(normalize_name(t.get('name', '')) == search_norm for t in tokens_cfg)
            
            if found_in_config:
                missing_shapes.append((filename, token_name))
            else:
                missing_in_config.append((filename, token_name))
    
    if missing_in_config:
        logger.error(f"  ERROR: {len(missing_in_config)} token names NOT FOUND in team config:")
        for fname, tname in missing_in_config[:5]:
            logger.error(f"    - {fname} -> '{tname}'")
        if len(missing_in_config) > 5:
            logger.error(f"    ... and {len(missing_in_config) - 5} more")
        logger.error(f"  These tokens must be added to config/team-config.yaml")
    
    if missing_shapes:
        logger.error(f"  ERROR: {len(missing_shapes)} tokens found in config BUT MISSING SHAPES:")
        for fname, tname in missing_shapes[:5]:
            logger.error(f"    - {fname} -> '{tname}'")
        if len(missing_shapes) > 5:
            logger.error(f"    ... and {len(missing_shapes) - 5} more")
        logger.error(f"  Fix by adding 'shape' field to these tokens in config/team-config.yaml")
    
    # Validate: check if expected tokens from config exist
    if team_config and team_config.get('tokens'):
        expected_count = len(team_config['tokens'])
        matched_count = len(token_names)
        if matched_count < expected_count:
            logger.warning(f"  Expected {expected_count} tokens (from config), but only matched {matched_count}")
    
    # Copy custom tokens to output directory BEFORE processing extracted tokens
    if team_config and filtered_custom:
        custom_tokens_dir = Path('config/teams') / team_slug / 'custom-tokens'
        if custom_tokens_dir.exists():
            for token_cfg in team_config.get('tokens', []):
                if token_cfg.get('type') == 'custom':
                    cfg_name = token_cfg.get('name', '').lower().strip()
                    shape = token_cfg.get('shape', 'round')
                    # Try to find matching custom token file
                    custom_pattern = f"{team_slug}-{cfg_name.replace(' ', '-')}.png"
                    custom_path = custom_tokens_dir / custom_pattern
                    if custom_path.exists():
                        # Load and process custom token with template mask
                        token_img = cv2.imread(str(custom_path), cv2.IMREAD_UNCHANGED)
                        if token_img is not None:
                            # Ensure BGR
                            if len(token_img.shape) == 2:
                                token_img = cv2.cvtColor(token_img, cv2.COLOR_GRAY2BGR)
                            elif token_img.shape[2] == 4:
                                token_img = cv2.cvtColor(token_img, cv2.COLOR_BGRA2BGR)
                            
                            # Normalize background
                            token_img = normalize_background_to_white(token_img)
                            
                            # Load template mask
                            template_mask = load_template_mask(shape)
                            if template_mask is not None:
                                # Apply template mask
                                processed = apply_template_mask(
                                    token_img,
                                    template_mask,
                                    shape,
                                    cfg_name,
                                    debug_path=None
                                )
                                
                                # Save to processed output
                                output_name = cfg_name.replace(' ', '-') + '.png'
                                output_path = output_dir / output_name
                                cv2.imwrite(str(output_path), processed)
                                logger.info(f"  ✓ Processed custom token: {output_name}")
                                stats['processed'] += 1
    
    # Process each token
    for token_meta in tokens:
        filename = token_meta.get('filename')
        if not filename:
            stats['failed'] += 1
            continue
        
        token_path = tokens_dir / filename
        if not token_path.exists():
            logger.warning(f"  Token file not found: {filename}")
            stats['failed'] += 1
            continue
        
        # Get matched name for this token
        token_name = token_names.get(filename)
        
        if not token_name:
            # No match = already logged error above, skip
            stats['failed'] += 1
            continue
        
        # Get template shape (already validated above, but check again)
        shape = get_token_shape(team_config, token_name)
        if not shape:
            # Already logged error above, skip
            stats['failed'] += 1
            continue
        
        template_mask = load_template_mask(shape)
        if template_mask is None:
            logger.error(f"  ERROR: Could not load template for shape '{shape}', SKIPPING")
            stats['failed'] += 1
            continue
        
        # Process token with template
        processed, output_name = process_token(
            token_path,
            token_meta,
            token_name,
            shape,
            template_mask,
            team_slug,
            debug_dir
        )
        
        if processed is None:
            logger.warning(f"  Failed: {output_name}")
            stats['failed'] += 1
            continue
        
        # Save
        output_path = output_dir / output_name
        cv2.imwrite(str(output_path), processed)
        stats['processed'] += 1
    
    return stats


def main():
    parser = argparse.ArgumentParser(description='Process extracted tokens with template cutout')
    args = parser.parse_args()
    
    logger.info("=" * 80)
    logger.info("Step 4: Process Tokens with Template Cutout")
    logger.info("=" * 80)
    logger.info(f"Input: {BASE_DIR}")
    logger.info(f"Output: output/{{team}}/tokens")
    logger.info(f"Target size: {TARGET_SIZE}x{TARGET_SIZE}")
    logger.info("")
    
    # Clean up old output directories
    logger.info("Cleaning up old processed tokens...")
    output_base = Path("output")
    if output_base.exists():
        for team_dir in output_base.iterdir():
            if team_dir.is_dir():
                tokens_dir = team_dir / "tokens"
                if tokens_dir.exists():
                    import shutil
                    shutil.rmtree(tokens_dir)
    logger.info("")
    
    # Load team config
    all_teams_config = load_team_config()
    
    # Process each team
    total_stats = {'processed': 0, 'skipped': 0, 'failed': 0, 'teams': 0}
    
    for team_dir in sorted(BASE_DIR.iterdir()):
        if not team_dir.is_dir():
            continue
        
        team_slug = team_dir.name
        tokens_dir = team_dir / "tokens"
        
        if not tokens_dir.exists():
            continue
        
        # Get team config
        team_config = all_teams_config.get(team_slug, {})
        
        # Count tokens
        tokens = list(tokens_dir.glob("*.png"))
        if not tokens:
            continue
        
        logger.info(f"Processing {team_slug} ({len(tokens)} tokens)...")
        
        stats = process_team(team_slug, team_config, all_teams_config)
        
        if stats['processed'] > 0:
            logger.info(f"  ✓ Processed: {stats['processed']}")
        if stats['failed'] > 0:
            logger.warning(f"  ✗ Failed: {stats['failed']}")
        if stats['skipped'] > 0:
            logger.info(f"  ○ Skipped: {stats['skipped']}")
        
        total_stats['processed'] += stats['processed']
        total_stats['skipped'] += stats['skipped']
        total_stats['failed'] += stats['failed']
        total_stats['teams'] += 1
    
    logger.info("")
    logger.info("=" * 80)
    logger.info("Processing complete!")
    logger.info(f"  Teams: {total_stats['teams']}")
    logger.info(f"  Processed: {total_stats['processed']}")
    logger.info(f"  Skipped: {total_stats['skipped']}")
    logger.info(f"  Failed: {total_stats['failed']}")
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
