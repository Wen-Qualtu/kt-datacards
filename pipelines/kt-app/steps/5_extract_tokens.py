"""
Step 5: Extract and Process Token Images

Two-phase token extraction:
- Phase 1: Extract rough tokens from PDFs (contour detection)
- Phase 2: Apply transparency and shape cutting

Outputs final tokens to output_v3/{team}/tokens/

Usage:
    python pipelines/kt-app/steps/5_extract_tokens.py
    python pipelines/kt-app/steps/5_extract_tokens.py --teams murderwings farstalker-kinband
    python pipelines/kt-app/steps/5_extract_tokens.py --debug
"""

import argparse
import sys
from pathlib import Path
from typing import Optional, Set
import yaml
import shutil
import json
import cv2
import numpy as np

# Import token extraction from pipeline utils
sys.path.insert(0, str(Path(__file__).parent.parent / 'utils'))
from token_extractor import TokenExtractor


def load_team_config():
    """Load team configuration"""
    config_path = Path('config/team-config.yaml')
    with open(config_path) as f:
        data = yaml.safe_load(f)
        return data.get('teams', {})


def get_teams_with_tokens(team_filter: Optional[Set[str]] = None) -> list[str]:
    """Get list of teams that have tokens configured"""
    teams_config = load_team_config()
    
    teams_with_tokens = []
    for team_slug, team_data in teams_config.items():
        # Apply filter if provided
        if team_filter and team_slug not in team_filter:
            continue
        
        # Check if team has tokens ready
        if not team_data.get('tokens_ready', False):
            continue
        
        # Check if team has tokens defined
        if not team_data.get('tokens', []):
            continue
        
        teams_with_tokens.append(team_slug)
    
    return sorted(teams_with_tokens)


# ========================================
# Phase 2: Transparency and Shape Cutting
# ========================================

def load_template(path: Path) -> np.ndarray:
    """Load a shape template as an alpha mask."""
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to load template: {path}")
    
    # Extract alpha channel
    if img.ndim == 2:
        return img
    elif img.shape[2] == 4:
        return img[:, :, 3]
    else:
        # Convert to grayscale if no alpha
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def get_token_shape(team_slug: str, token_name: str, extraction_metadata: dict) -> str:
    """Determine the shape for a token.
    
    Priority: config override > metadata > aspect ratio heuristic
    """
    # Try config first
    teams_config = load_team_config()
    team_data = teams_config.get(team_slug, {})
    tokens_config = team_data.get('tokens', [])
    
    # Normalize token name for matching
    normalized_search = ' '.join(token_name.lower().split())
    
    for token_cfg in tokens_config:
        cfg_name = token_cfg.get('name', '')
        normalized_cfg = ' '.join(cfg_name.lower().split())
        if normalized_search == normalized_cfg:
            shape = token_cfg.get('shape')
            if shape:
                return shape
    
    # Try extraction metadata
    meta_shape = extraction_metadata.get('shape')
    if meta_shape and meta_shape in ['operative', 'round', 'octagon', 'diamond']:
        return meta_shape
    
    # Default to operative
    return 'operative'


def remove_background(img: np.ndarray) -> np.ndarray:
    """Remove white/gray background, return alpha mask."""
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 3:
        bgr = img
    elif img.shape[2] == 4:
        bgr = img[:, :, :3]
    else:
        raise ValueError(f"Unexpected image shape: {img.shape}")
    
    # Convert to HSV for white detection
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    s = hsv[:, :, 1]
    
    # More aggressive white/light-gray detection to catch stray background pixels
    # Lowered threshold from 245 to 235 to catch slightly off-white pixels
    # These often appear as small pixel islands outside the main token
    is_white = ((v > 235) & (s < 25)) | (
        (bgr[:, :, 0] > 235) & (bgr[:, :, 1] > 235) & (bgr[:, :, 2] > 235)
    )
    
    mask = (~is_white).astype(np.uint8) * 255
    
    # Remove only very small noise components (keep all significant content islands)
    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels > 1:
        # Keep all components above a small threshold (removes noise but keeps multi-island tokens)
        min_area = 100  # pixels - only remove tiny specks
        cleaned_mask = np.zeros_like(mask)
        for label in range(1, num_labels):
            if stats[label, cv2.CC_STAT_AREA] >= min_area:
                cleaned_mask[labels == label] = 255
        mask = cleaned_mask
    
    # Fill holes within each component
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cv2.drawContours(mask, contours, -1, 255, thickness=cv2.FILLED)
    
    # Light morphological closing to smooth edges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    
    return mask


def crop_to_content(img: np.ndarray, mask: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Crop image and mask to non-transparent content bounds.
    
    Removes fully transparent rows/columns to get a tight bounding box.
    Returns (cropped_img, cropped_mask)
    """
    # Find bounding box of non-transparent content
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        # No content - return original
        return img, mask
    
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    
    # Crop both image and mask
    cropped_img = img[y0:y1+1, x0:x1+1]
    cropped_mask = mask[y0:y1+1, x0:x1+1]
    
    return cropped_img, cropped_mask


def fit_to_template(content_mask: np.ndarray, template: np.ndarray, incut_percent: float = 5.0) -> np.ndarray:
    """Fit template to content with slight incut to avoid jagged edges.
    
    Args:
        content_mask: Binary mask of content (after background removal)
        template: Template shape to fit
        incut_percent: Percentage to shrink template (default 5%)
    
    Returns:
        Scaled and positioned template mask fitted to content
    """
    # Find content bounding box
    ys, xs = np.where(content_mask > 0)
    if xs.size == 0:
        # Empty mask - return blank template-sized
        return np.zeros_like(content_mask)
    
    x0, y0 = int(xs.min()), int(ys.min())
    x1, y1 = int(xs.max()), int(ys.max())
    content_w = x1 - x0 + 1
    content_h = y1 - y0 + 1
    content_cx = (x0 + x1) / 2.0
    content_cy = (y0 + y1) / 2.0
    
    # Get template dimensions
    template_h, template_w = template.shape
    
    # Calculate scale to fit template to content
    # Template should fit slightly inside content (incut)
    scale_w = (content_w / template_w) * (1.0 - incut_percent / 100.0)
    scale_h = (content_h / template_h) * (1.0 - incut_percent / 100.0)
    scale = min(scale_w, scale_h)  # Use smaller scale to ensure template fits inside
    
    # Scale template
    new_template_w = int(template_w * scale)
    new_template_h = int(template_h * scale)
    
    if new_template_w > 0 and new_template_h > 0:
        scaled_template = cv2.resize(template, (new_template_w, new_template_h), interpolation=cv2.INTER_LINEAR)
    else:
        scaled_template = template
        new_template_w, new_template_h = template_w, template_h
    
    # Position scaled template centered on content
    result = np.zeros_like(content_mask)
    offset_x = int(content_cx - new_template_w / 2.0)
    offset_y = int(content_cy - new_template_h / 2.0)
    
    # Calculate paste region with bounds checking
    paste_x0 = max(0, offset_x)
    paste_y0 = max(0, offset_y)
    paste_x1 = min(result.shape[1], offset_x + new_template_w)
    paste_y1 = min(result.shape[0], offset_y + new_template_h)
    
    # Calculate source region
    src_x0 = paste_x0 - offset_x
    src_y0 = paste_y0 - offset_y
    src_x1 = src_x0 + (paste_x1 - paste_x0)
    src_y1 = src_y0 + (paste_y1 - paste_y0)
    
    # Paste scaled template
    if paste_x1 > paste_x0 and paste_y1 > paste_y0:
        result[paste_y0:paste_y1, paste_x0:paste_x1] = scaled_template[src_y0:src_y1, src_x0:src_x1]
    
    return result


def get_standard_token_size(shape: str) -> tuple[int, int]:
    """Get standard output size for token shape.
    
    Returns (width, height)
    """
    if shape == 'round':
        return (235, 235)
    elif shape == 'operative':
        return (439, 414)  # Operative tokens are wider than tall
    elif shape == 'octagon':
        return (235, 235)  # Assume same as round
    elif shape == 'diamond':
        return (235, 235)  # Assume same as round
    else:
        return (235, 235)  # Default


def process_token(
    input_path: Path,
    output_path: Path,
    shape: str,
    templates: dict[str, np.ndarray],
    debug: bool = False
) -> bool:
    """Process a single token: remove background, crop, fit template, fill transparent, output RGBA."""
    
    # Load image
    img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        print(f"      ⚠ Failed to load: {input_path.name}")
        return False
    
    # Extract BGR
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 3:
        bgr = img
    elif img.shape[2] == 4:
        bgr = img[:, :, :3]
    else:
        print(f"      ⚠ Unexpected image format: {input_path.name}")
        return False
    
    # Step 1: Remove white/almost-white background
    content_mask = remove_background(img)
    
    # Step 2: Crop to non-transparent bounds (removes excess transparent areas)
    cropped_bgr, cropped_mask = crop_to_content(bgr, content_mask)
    
    # Get appropriate template
    template = templates.get(shape)
    if template is None:
        print(f"      ⚠ No template for shape '{shape}', using operative")
        template = templates.get('operative')
        if template is None:
            print(f"      ✗ No operative template available")
            return False
    
    # Step 3: Fit template to cropped content (with 5% incut)
    fitted_template = fit_to_template(cropped_mask, template, incut_percent=5.0)
    
    # Step 4: Create alpha channel - use fitted template as boundary
    alpha = np.zeros(cropped_bgr.shape[:2], dtype=np.uint8)
    template_area = fitted_template > 127  # Where template defines content should be
    
    # Set alpha to 255 where template is
    alpha[template_area] = 255
    
    # SAFETY: Force remove any content pixels outside the template boundary
    # This catches stray pixels that survived background removal
    cropped_bgr[~template_area] = [255, 255, 255]  # Set to white
    
    # Step 5: Fill transparent areas within template with white
    # Any pixel inside template that's transparent gets filled with white
    rgba = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = alpha
    
    # Fill all areas within template boundary with opaque color
    # If original content was removed as background, fill with white
    transparent_holes = (cropped_mask == 0) & template_area
    rgba[transparent_holes, :3] = [255, 255, 255]  # Fill with white
    rgba[transparent_holes, 3] = 255  # Make opaque
    
    # Step 6: Resize to standard size for this shape
    target_w, target_h = get_standard_token_size(shape)
    if rgba.shape[1] != target_w or rgba.shape[0] != target_h:
        rgba = cv2.resize(rgba, (target_w, target_h), interpolation=cv2.INTER_AREA)
    
    # Save
    output_path.parent.mkdir(parents=True, exist_ok=True)
    success = cv2.imwrite(str(output_path), rgba)
    
    if not success:
        print(f"      ✗ Failed to write: {output_path}")
        return False
    
    if debug:
        print(f"      ✓ {input_path.name} → {shape} shape ({target_w}x{target_h})")
    
    return True


def process_tokens_phase2(
    team_slug: str,
    input_dir: Path,
    output_dir: Path,
    templates: dict[str, np.ndarray],
    debug: bool = False
) -> int:
    """Process all tokens for a team (Phase 2).
    
    Returns the number of tokens successfully processed.
    """
    # Load extraction metadata to get token names
    metadata_path = input_dir / 'extraction-metadata.json'
    metadata_by_file = {}
    
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r', encoding='utf-8') as f:
                metadata = json.load(f)
                # Handle both formats: list or dict with "tokens" key
                if isinstance(metadata, dict):
                    metadata_list = metadata.get('tokens', [])
                elif isinstance(metadata, list):
                    metadata_list = metadata
                else:
                    metadata_list = []
                
                for item in metadata_list:
                    filename = item.get('filename', '')
                    if filename:
                        metadata_by_file[filename] = item
        except Exception as e:
            print(f"      ⚠ Could not load metadata: {e}")
    
    # Process each token PNG
    token_files = list(input_dir.glob('*.png'))
    if not token_files:
        print(f"      ⚠ No token files found in {input_dir}")
        return 0
    
    success_count = 0
    for token_path in token_files:
        # Skip debug files
        if token_path.name.startswith('_'):
            continue
        
        # Get token metadata
        metadata = metadata_by_file.get(token_path.name, {})
        token_name = metadata.get('name', token_path.stem)
        
        # Determine shape
        shape = get_token_shape(team_slug, token_name, metadata)
        
        # Process token - add team prefix to output filename
        # Convert filename format: token-name.png -> {team}-token-name.png
        output_filename = f"{team_slug}-{token_path.name}"
        output_path = output_dir / output_filename
        if process_token(token_path, output_path, shape, templates, debug):
            success_count += 1
    
    return success_count


# ========================================
# Phase 1 & 2 Orchestration
# ========================================

def extract_tokens_for_team(team_slug: str, output_base: str = 'layers/kt-app/extracted', debug: bool = False) -> bool:
    """
    Extract and process tokens for a single team (2-phase process).
    
    Phase 1: Extract rough tokens from PDF (integrated - contour detection)
    Phase 2: Apply transparency and shape cutting (integrated - clean implementation)
    
    Returns True if successful, False otherwise.
    """
    print(f"\n  Processing {team_slug}...")
    
    # Phase 1: Extract rough tokens using integrated extractor
    print(f"    Phase 1: Extracting rough tokens...")
    
    extractor = TokenExtractor(
        output_base_dir=Path(output_base),
        text_gap_max=6.0,
        same_line_y_max=15.0,
        next_line_y_min=5.0,
        next_line_y_max=25.0,
        next_line_x_overlap_ratio=0.25,
        name_match_max_distance=300.0,
    )
    
    # Run extraction with auto-tuning
    success = extractor.process_team_auto_tuned(
        team_slug,
        method='auto',
        debug=debug,
        clean=False,
        expected_token_count=None,
    )
    
    if not success:
        print(f"      ✗ Phase 1 failed")
        return False
    
    # Check extracted tokens
    token_dir = Path(output_base) / team_slug / 'token'
    if not token_dir.exists():
        print(f"      ✗ Token directory not found: {token_dir}")
        return False
    
    token_files = [f for f in token_dir.glob('*.png') if not f.name.startswith('_')]
    print(f"      ✓ Extracted {len(token_files)} rough tokens")
    
    # Phase 2: Apply transparency and shape cutting (integrated implementation)
    print(f"    Phase 2: Applying transparency and shape cutting...")
    
    # Load shape templates
    template_dir = Path('config/defaults/tts-token')
    try:
        templates = {
            'operative': load_template(template_dir / 'template-operative-cutter.png'),
            'round': load_template(template_dir / 'template-round-cutter.png'),
            'octagon': load_template(template_dir / 'template-octagon-cutter.png'),
            'diamond': load_template(template_dir / 'template-diamond-cutter.png'),
        }
    except Exception as e:
        print(f"      ✗ Failed to load templates: {e}")
        return False
    
    # Process tokens - output directly to output_v3
    output_tokens_dir = Path('output_v3') / team_slug / 'tokens'
    output_tokens_dir.mkdir(parents=True, exist_ok=True)
    
    processed_count = process_tokens_phase2(
        team_slug=team_slug,
        input_dir=token_dir,
        output_dir=output_tokens_dir,
        templates=templates,
        debug=debug
    )
    
    if processed_count == 0:
        print(f"      ✗ No tokens processed")
        return False
    
    print(f"      ✓ Processed {processed_count} tokens with transparency → output_v3/{team_slug}/tokens/")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Step 5: Extract and process token images (2-phase: extraction + transparency/cutting)'
    )
    parser.add_argument(
        '--teams',
        nargs='+',
        help='Specific team(s) to process (e.g., murderwings farstalker-kinband)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug output'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='layers/kt-app/extracted',
        help='Output base directory for intermediate tokens (default: layers/kt-app/extracted)'
    )

    args = parser.parse_args()

    # Get teams to process
    team_filter = set(args.teams) if args.teams else None
    teams_to_process = get_teams_with_tokens(team_filter)
    
    if not teams_to_process:
        print("No teams found with tokens configured (tokens_ready: true)")
        return 1
    
    print(f"\n{'='*60}")
    print(f"Step 5: Extract and Process Token Images")
    print(f"{'='*60}")
    print(f"Processing {len(teams_to_process)} teams (2-phase: extraction + transparency/cutting)...")
    print(f"Phase 1: Extract rough tokens from PDFs")
    print(f"Phase 2: Apply transparency, shape cutting, and resize")
    print(f"")
    
    processed_count = 0
    error_count = 0
    
    for team_slug in teams_to_process:
        try:
            success = extract_tokens_for_team(team_slug, args.output_dir, args.debug)
            if success:
                processed_count += 1
            else:
                error_count += 1
        except Exception as e:
            print(f"    ✗ Error: {e}")
            error_count += 1
    
    # Summary
    print(f"\n{'='*60}")
    print(f"Summary:")
    print(f"  Processed: {processed_count}")
    print(f"  Errors: {error_count}")
    print(f"{'='*60}\n")
    
    return 0 if error_count == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
