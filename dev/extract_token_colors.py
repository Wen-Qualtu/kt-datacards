#!/usr/bin/env python3
"""
Extract dominant colors from team token images for dice generation.
Tokens are designed by GW with team-appropriate colors.
Groups color shades into families by hue similarity.
"""

from PIL import Image
import numpy as np
from pathlib import Path


def rgb_to_hsv(rgb):
    """Convert RGB tuple to HSV."""
    r, g, b = [x / 255.0 for x in rgb]
    max_val = max(r, g, b)
    min_val = min(r, g, b)
    diff = max_val - min_val
    
    if max_val == min_val:
        h = 0
    elif max_val == r:
        h = (60 * ((g - b) / diff) + 360) % 360
    elif max_val == g:
        h = (60 * ((b - r) / diff) + 120) % 360
    else:
        h = (60 * ((r - g) / diff) + 240) % 360
    
    s = 0 if max_val == 0 else (diff / max_val)
    v = max_val
    
    return h, s, v


def group_colors_by_hue(pixels, hue_tolerance=30, exclude_threshold=250):
    """
    Group pixels by color family (similar hues), excluding white/near-white.
    
    Args:
        pixels: Nx3 array of RGB pixels
        hue_tolerance: Degrees of hue difference to group as same color family
        exclude_threshold: Exclude pixels with all RGB above this
    
    Returns:
        Dict of {color_family_representative: pixel_count}
    """
    # Filter out near-white pixels
    mask = np.any(pixels < exclude_threshold, axis=1)
    filtered = pixels[mask]
    
    if len(filtered) == 0:
        return {}
    
    # Group by hue families
    color_families = {}
    
    for pixel in filtered:
        rgb = tuple(pixel)
        h, s, v = rgb_to_hsv(rgb)
        
        # Find existing family or create new
        found_family = None
        for family_color in color_families.keys():
            family_h, family_s, family_v = rgb_to_hsv(family_color)
            
            # Check if hues are similar (handle wraparound at 360)
            hue_diff = min(abs(h - family_h), 360 - abs(h - family_h))
            
            if hue_diff < hue_tolerance:
                found_family = family_color
                break
        
        if found_family:
            color_families[found_family] += 1
        else:
            # Use this pixel as the family representative
            color_families[rgb] = 1
    
    return color_families


def extract_color_families_from_tokens(token_paths: list) -> dict:
    """
    Extract color families from multiple token images, focusing on center region.
    
    Args:
        token_paths: List of paths to token images
    
    Returns:
        Dict with 'back_color' (most common family) and 'front_color' (2nd most common)
    """
    all_families = {}
    total_white_weight = 0.0  # Track white across all tokens
    
    for token_path in token_paths:
        img = Image.open(token_path).convert('RGB')
        
        # Resize to speed up processing
        img = img.resize((200, 200), Image.Resampling.LANCZOS)
        img_array = np.array(img)
        
        # Create a center-weighted mask (higher weight toward center)
        h, w = img_array.shape[:2]
        y, x = np.ogrid[:h, :w]
        center_y, center_x = h // 2, w // 2
        
        # Distance from center
        distance = np.sqrt((x - center_x)**2 + (y - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        
        # Weight: 1.0 at center, decreasing to 0.2 at edges
        weights = 1.0 - (distance / max_dist) * 0.8
        
        # Flatten arrays
        pixels = img_array.reshape(-1, 3)
        pixel_weights = weights.flatten()
        
        # Track white/near-white separately (icons are often white)
        is_white = np.all(pixels >= 240, axis=1)
        total_white_weight += np.sum(pixel_weights[is_white])
        
        # Filter pixels: exclude pure white borders (>250), but keep near-white icons (240-250)
        not_border = np.any(pixels < 250, axis=1)
        
        filtered_pixels = pixels[not_border]
        filtered_weights = pixel_weights[not_border]
        
        if len(filtered_pixels) == 0:
            continue
        
        # Group by hue family with weights
        for pixel, weight in zip(filtered_pixels, filtered_weights):
            rgb = tuple(pixel)
            h_hsv, s, v = rgb_to_hsv(rgb)
            
            # Keep saturated colors (icons) even if dark or light
            # Only skip very desaturated grays (s < 0.1) at extreme brightness (v > 0.95)
            if s < 0.1 and v > 0.95:
                continue
            
            # Find existing family or create new
            found_family = None
            for family_color in all_families.keys():
                family_h, family_s, family_v = rgb_to_hsv(family_color)
                
                # Check if hues are similar (for saturated colors)
                # For desaturated colors, also check value similarity
                hue_diff = min(abs(h_hsv - family_h), 360 - abs(h_hsv - family_h))
                
                if s > 0.2 and family_s > 0.2:
                    # Both saturated - match by hue
                    if hue_diff < 30:
                        found_family = family_color
                        break
                elif s < 0.2 and family_s < 0.2:
                    # Both desaturated - match by brightness
                    if abs(v - family_v) < 0.15:
                        found_family = family_color
                        break
            
            if found_family:
                all_families[found_family] += weight
            else:
                all_families[rgb] = weight
    
    if not all_families:
        return None
    
    # Add white as a color family if it has significant presence
    if total_white_weight > 0:
        all_families[(255, 255, 255)] = total_white_weight
    
    # Sort by weighted pixel count
    sorted_families = sorted(all_families.items(), key=lambda x: x[1], reverse=True)
    
    # Background = most common color
    back_color = sorted_families[0][0]
    back_h, back_s, back_v = rgb_to_hsv(back_color)
    
    # Icon color strategy:
    # 1. If background is light (v > 0.6), prefer dark colors (v < 0.3) for contrast
    # 2. Otherwise, prefer most saturated color (vivid icons like red)
    # 3. Fall back to white if no saturated or contrasting colors found
    
    candidates = []
    for color, weight in sorted_families[1:]:  # Skip background
        h, s, v = rgb_to_hsv(color)
        
        # Skip colors too similar to background
        if abs(v - back_v) < 0.15 and s < 0.2:
            continue
        
        # Check if it's white
        is_white = all(c >= 240 for c in color)
        
        # Score based on background brightness
        if back_v > 0.6:
            # Light background - prefer dark contrasting colors
            if v < 0.3:
                score = (0.3 - v) * 100 + s * 10  # Dark colors score high
            elif s > 0.3:
                score = s * 50  # Saturated colors are good too
            elif is_white:
                score = 20  # White is okay
            else:
                score = 5
        else:
            # Dark background - prefer saturated or light colors
            if s > 0.3:
                score = s * 100  # Saturated colors score highest
            elif is_white or v > 0.8:
                score = 50  # White/light colors good
            else:
                score = v * 20  # Lighter is better
        
        candidates.append((color, weight, score))
    
    # Sort by score (descending)
    candidates.sort(key=lambda x: x[2], reverse=True)
    
    if candidates and candidates[0][2] > 0:
        front_color = candidates[0][0]
    else:
        # No good candidates - default to white
        front_color = (255, 255, 255)
    
    return {
        'back_color': list(back_color),
        'front_color': list(front_color)
    }
    return None


def extract_team_token_colors(team_slug: str, tokens_dir: Path) -> dict:
    """
    Extract colors from a team's token images by analyzing color families.
    
    Args:
        team_slug: Team identifier
        tokens_dir: Path to team's tokens directory
    
    Returns:
        Dict with 'back_color' and 'front_color' or None if no tokens
    """
    if not tokens_dir.exists():
        return None
    
    # Find token images (exclude icon tokens, prefer larger tokens)
    token_files = [
        f for f in tokens_dir.glob('*.png')
        if 'icon' not in f.name.lower()
    ]
    
    if not token_files:
        return None
    
    # Use up to 3 tokens for analysis
    sample_tokens = token_files[:3]
    
    # Extract color families across all sampled tokens
    return extract_color_families_from_tokens(sample_tokens)


def main():
    """Extract token colors for all teams with tokens."""
    output_base = Path('output')
    
    if not output_base.exists():
        print(f"✗ Output directory not found: {output_base}")
        return
    
    results = {}
    
    # Get all team directories
    team_dirs = sorted([d for d in output_base.iterdir() if d.is_dir()])
    
    print(f"Extracting token colors from teams with tokens...\n")
    
    for team_dir in team_dirs:
        team_slug = team_dir.name
        tokens_dir = team_dir / 'tokens'
        
        colors = extract_team_token_colors(team_slug, tokens_dir)
        
        if colors:
            results[team_slug] = colors
            back = colors['back_color']
            front = colors['front_color']
            print(f"✓ {team_slug:30s} - back: rgb({back[0]:3d}, {back[1]:3d}, {back[2]:3d})  front: rgb({front[0]:3d}, {front[1]:3d}, {front[2]:3d})")
    
    print(f"\n{'='*80}")
    print(f"Found colors for {len(results)} teams with tokens")
    print(f"\nYou can use these values in config/team-config.yaml:")
    print(f"  dice_back_color: [r, g, b]")
    print(f"  dice_front_color: [r, g, b]")


if __name__ == '__main__':
    main()
