"""
Step 4b: Process Tokens to Transparent PNGs

**EXECUTOR STEP - reads token_index.json, applies processing, outputs final tokens.**

This step takes the rough-cropped token images from Step 2b and produces final
transparent PNG files suitable for TTS. All classification/matching logic lives
in Step 3 (index_cards.py); this step is purely a processor.

Algorithm:
1. Load metadata/{team}/token_index.json (names, shapes, source files)
2. For each matched token:
   a. Load rough-cropped PNG from source_file
   b. Normalize grey background to white
   c. Remove background using bg-sample color keying (border-connected only)
   d. Apply shape template cutter mask for clean edges
   e. Fill interior transparent holes
   f. Clean up edge halos
   g. Scale to target size (512x512)
   h. Save to output/{team}/tokens/{token-slug}.png

Input:  metadata/{team}/token_index.json
        layers/warcom/extracted/{team}/tokens/*.png (rough-cropped tokens)
        config/defaults/tts-token/template-{shape}-cutter.png (shape templates)
        config/defaults/tts-token/token-bg-sample.png (background reference)
Output: output/{team}/tokens/{token-slug}.png (transparent PNGs)
"""

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(message)s'
)
logger = logging.getLogger(__name__)

# Constants
TARGET_SIZE = 512
BG_SAMPLE_PATH = Path('config/defaults/tts-token/token-bg-sample.png')
TEMPLATE_DIR = Path('config/defaults/tts-token')


def slugify(text: str) -> str:
    """Convert token name to filename-safe slug.

    Strips common suffixes like 'token', 'marker', 'tokens', 'markers'
    since these are descriptive labels, not part of the token identity.
    """
    text = text.lower().strip()
    # Strip common suffixes
    for suffix in [' tokens', ' token', ' markers', ' marker']:
        if text.endswith(suffix):
            text = text[:-len(suffix)].strip()
            break
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text


# ============================================================================
# Background Color Learning
# ============================================================================

def learn_bg_colors(bg_sample_path: Path, k: int = 6, keep: int = 4) -> np.ndarray:
    """Learn background color centers from a sample image using k-means in Lab space.

    Args:
        bg_sample_path: Path to background sample image
        k: Number of k-means clusters
        keep: Number of top clusters to keep

    Returns:
        BGR uint8 array of background color centers, shape (N, 3)
    """
    sample = cv2.imread(str(bg_sample_path), cv2.IMREAD_COLOR)
    if sample is None:
        raise FileNotFoundError(f"Background sample not found: {bg_sample_path}")

    lab = cv2.cvtColor(sample, cv2.COLOR_BGR2LAB)
    pts = lab.reshape(-1, 3).astype(np.float32)

    max_pixels = 15000
    if pts.shape[0] > max_pixels:
        idx = np.linspace(0, pts.shape[0] - 1, max_pixels).astype(np.int32)
        pts = pts[idx]

    cv2.setRNGSeed(0)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.3)
    _compactness, labels, centers = cv2.kmeans(
        pts, k, None, criteria, 5, cv2.KMEANS_PP_CENTERS
    )

    labels = labels.reshape(-1)
    counts = np.bincount(labels, minlength=k).astype(np.int64)
    order = np.argsort(-counts)
    top = order[:keep]

    # Convert Lab centers back to BGR
    centers_lab = centers[top].reshape(-1, 1, 3).astype(np.uint8)
    centers_bgr = cv2.cvtColor(centers_lab, cv2.COLOR_LAB2BGR).reshape(-1, 3)

    # Filter to likely grey backgrounds (low saturation, high value)
    hsv = cv2.cvtColor(centers_bgr.reshape(-1, 1, 3), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    mask = (hsv[:, 1] <= 40) & (hsv[:, 2] >= 150)
    filtered = centers_bgr[mask]

    return filtered if filtered.size else centers_bgr


def learn_bg_colors_from_borders(token_paths: List[Path]) -> np.ndarray:
    """Fallback: learn background from token image borders."""
    pixels = []
    for path in token_paths:
        img = cv2.imread(str(path), cv2.IMREAD_COLOR)
        if img is None:
            continue
        h, w = img.shape[:2]
        t = max(4, min(20, min(h, w) // 12))
        border = np.concatenate([
            img[:t, :, :].reshape(-1, 3),
            img[max(0, h - t):h, :, :].reshape(-1, 3),
            img[:, :t, :].reshape(-1, 3),
            img[:, max(0, w - t):w, :].reshape(-1, 3),
        ], axis=0)
        pixels.append(border)

    if not pixels:
        return np.array([[228, 229, 227], [209, 210, 208]], dtype=np.uint8)

    all_px = np.concatenate(pixels, axis=0)
    max_pixels = 12000
    if all_px.shape[0] > max_pixels:
        idx = np.linspace(0, all_px.shape[0] - 1, max_pixels).astype(np.int32)
        all_px = all_px[idx]

    # Re-use same clustering approach
    lab = cv2.cvtColor(all_px.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.float32)
    cv2.setRNGSeed(0)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.3)
    _compactness, labels, centers = cv2.kmeans(
        lab, 5, None, criteria, 5, cv2.KMEANS_PP_CENTERS
    )
    labels = labels.reshape(-1)
    counts = np.bincount(labels, minlength=5).astype(np.int64)
    order = np.argsort(-counts)
    top = order[:3]
    centers_lab = centers[top].reshape(-1, 1, 3).astype(np.uint8)
    return cv2.cvtColor(centers_lab, cv2.COLOR_LAB2BGR).reshape(-1, 3)


# ============================================================================
# Template Loading and Fitting
# ============================================================================

def load_template_mask(shape: str) -> Optional[np.ndarray]:
    """Load a shape template cutter as a binary mask.

    Args:
        shape: Token shape name ('round', 'operative', 'octagon', 'diamond')

    Returns:
        Binary mask (uint8, 0 or 1) or None if template not found
    """
    template_path = TEMPLATE_DIR / f'template-{shape}-cutter.png'
    if not template_path.exists():
        logger.warning(f"Template not found: {template_path}")
        return None

    img = cv2.imread(str(template_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None

    # Extract alpha channel as binary mask
    if img.shape[2] == 4:
        alpha = img[:, :, 3]
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        alpha = gray

    mask = (alpha > 0).astype(np.uint8)

    # Fill holes and smooth edges
    mask = _mask_fill_holes(mask)
    el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, el, iterations=1)
    mask = _mask_fill_holes(mask)

    return mask


def prepare_template_at_target_size(
    template_mask: np.ndarray,
    target_size: int = TARGET_SIZE,
    erode_px: int = 1,
) -> np.ndarray:
    """Scale template mask to fit within target_size x target_size, centered.

    All tokens of the same shape use this identical mask, guaranteeing
    consistent output dimensions and silhouette.

    Args:
        template_mask: Raw binary mask from load_template_mask()
        target_size: Output canvas size (pixels, square)
        erode_px: Shrink the mask by this many pixels to trim edge fringe

    Returns:
        Binary mask (uint8, 0 or 1), shape (target_size, target_size)
    """
    th, tw = template_mask.shape
    # Scale to fill target_size, preserving aspect ratio, with 1px safety margin
    usable = target_size - 2
    scale = min(usable / tw, usable / th)
    new_w = int(round(tw * scale))
    new_h = int(round(th * scale))

    resized = cv2.resize(
        (template_mask > 0).astype(np.uint8), (new_w, new_h),
        interpolation=cv2.INTER_AREA
    )
    resized = (resized > 0).astype(np.uint8)

    # Erode slightly to trim the 1px fringe the user reported
    if erode_px > 0:
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                           (erode_px * 2 + 1, erode_px * 2 + 1))
        resized = cv2.erode(resized, kernel, iterations=1)

    canvas = np.zeros((target_size, target_size), dtype=np.uint8)
    x0 = (target_size - new_w) // 2
    y0 = (target_size - new_h) // 2
    canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
    return canvas


def _mask_fill_holes(mask: np.ndarray) -> np.ndarray:
    """Fill interior holes in a binary mask."""
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
    return out


def _mask_bbox(mask: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """Get bounding box of non-zero pixels."""
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1), int(ys.max() - ys.min() + 1)


def _mask_centroid(mask: np.ndarray) -> Optional[Tuple[float, float]]:
    """Get centroid of non-zero pixels."""
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    return float(xs.mean()), float(ys.mean())


def fit_template_to_content(
    content_mask: np.ndarray,
    template_mask: np.ndarray,
    *,
    scale_band: float = 0.15,
    scale_steps: int = 11,
    shift: int = 8,
    shift_step: int = 2,
) -> Optional[np.ndarray]:
    """Fit a shape template mask onto detected token content.

    Uses IoU-based search across scale and position offsets to find the best
    alignment of the template over the token content.

    Args:
        content_mask: Binary mask of the detected token content
        template_mask: Binary mask of the shape template
        scale_band: Fraction to vary scale (+/-)
        scale_steps: Number of scale steps to try
        shift: Max pixel shift in x/y
        shift_step: Step size for shift search

    Returns:
        Fitted binary mask (same size as content_mask) or None
    """
    h, w = content_mask.shape
    cand_area = int((content_mask > 0).sum())
    if cand_area <= 0:
        return None

    templ_area = int((template_mask > 0).sum())
    if templ_area <= 0:
        return None

    # Find content centroid and bounding box
    cb = _mask_centroid(content_mask)
    bb = _mask_bbox(content_mask)

    if cb is not None:
        cx, cy = cb
    elif bb is not None:
        bx, by, bw, bh = bb
        cx, cy = float(bx + bw / 2), float(by + bh / 2)
    else:
        cx, cy = float(w / 2), float(h / 2)

    # Compute base scale from area ratio and bbox ratio
    area_scale = float(np.sqrt(cand_area / templ_area))
    tb = _mask_bbox(template_mask)
    if bb is not None and tb is not None:
        _, _, bw, bh = bb
        _, _, tw, th = tb
        ws = float(bw / max(1, tw))
        hs = float(bh / max(1, th))
        bbox_scale = (ws + hs) / 2.0
        base_scale = 0.55 * bbox_scale + 0.45 * area_scale
    else:
        base_scale = area_scale

    # Scale down slightly to avoid capturing white edges
    base_scale *= 0.95
    base_scale = float(np.clip(base_scale, 0.4, 2.2))

    # Generate scale range
    if scale_steps <= 1 or scale_band == 0:
        scales = [base_scale]
    else:
        lo = base_scale * (1.0 - scale_band)
        hi = base_scale * (1.0 + scale_band)
        scales = list(np.linspace(lo, hi, scale_steps).astype(np.float32))

    best = None
    best_mask = None
    cand_area_f = float(cand_area)

    for sc in scales:
        th_t, tw_t = template_mask.shape
        nh = max(5, int(round(th_t * sc)))
        nw = max(5, int(round(tw_t * sc)))
        if nh >= h * 2 or nw >= w * 2:
            continue

        resized = cv2.resize(
            (template_mask > 0).astype(np.uint8), (nw, nh),
            interpolation=cv2.INTER_NEAREST
        )

        for dy in range(-shift, shift + 1, shift_step):
            for dx in range(-shift, shift + 1, shift_step):
                x0 = int(round(cx - (nw / 2) + dx))
                y0 = int(round(cy - (nh / 2) + dy))

                # Clip to image bounds
                tx0, ty0 = 0, 0
                x1 = x0 + nw
                y1 = y0 + nh
                if x0 < 0:
                    tx0 = -x0
                    x0 = 0
                if y0 < 0:
                    ty0 = -y0
                    y0 = 0
                if x1 > w:
                    x1 = w
                if y1 > h:
                    y1 = h

                rw = x1 - x0
                rh = y1 - y0
                if rw <= 2 or rh <= 2:
                    continue

                templ_roi = resized[ty0:ty0 + rh, tx0:tx0 + rw]
                if templ_roi.size == 0:
                    continue

                cand_roi = (content_mask[y0:y1, x0:x1] > 0)
                templ_roi_b = templ_roi > 0

                inter = int(np.logical_and(cand_roi, templ_roi_b).sum())
                templ_area_eff = int(templ_roi_b.sum())
                union = int(cand_area + templ_area_eff - inter)
                if union <= 0 or templ_area_eff <= 0:
                    continue

                iou = float(inter / union)
                coverage = float(inter / templ_area_eff)

                if best is None or iou > best['iou'] + 1e-9:
                    best = {'iou': iou, 'coverage': coverage, 'scale': float(sc)}
                    placed = np.zeros((h, w), dtype=np.uint8)
                    placed[y0:y1, x0:x1] = templ_roi_b.astype(np.uint8)
                    best_mask = placed

    return best_mask


# ============================================================================
# Background Removal
# ============================================================================

def compute_bg_alpha(
    bgr: np.ndarray,
    bg_centers_bgr: np.ndarray,
    threshold: int = 18,
) -> np.ndarray:
    """Compute alpha channel by keying background colors to transparent.

    Works in Lab space. Only removes background connected to the image border
    to prevent punching holes in interior artwork.

    Args:
        bgr: Input BGR image
        bg_centers_bgr: Background color centers (BGR uint8, shape N x 3)
        threshold: Lab-space distance threshold for background classification

    Returns:
        Alpha channel (uint8, 0=transparent, 255=opaque)
    """
    h, w = bgr.shape[:2]
    if h <= 1 or w <= 1:
        return np.full((h, w), 255, dtype=np.uint8)

    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.int16)
    centers_lab = cv2.cvtColor(
        bg_centers_bgr.reshape(-1, 1, 3).astype(np.uint8),
        cv2.COLOR_BGR2LAB
    ).reshape(-1, 3).astype(np.int16)

    # Calculate min squared distance to any bg center
    d_all = []
    for i in range(centers_lab.shape[0]):
        c = centers_lab[i]
        dl = lab - c[None, None, :]
        d2 = (dl[:, :, 0].astype(np.int32) ** 2 +
              dl[:, :, 1].astype(np.int32) ** 2 +
              dl[:, :, 2].astype(np.int32) ** 2)
        d_all.append(d2)
    dist2 = np.min(np.stack(d_all, axis=2), axis=2)

    cutoff2 = threshold * threshold
    bg_cand = (dist2 <= cutoff2).astype(np.uint8)

    # Protect bright white pixels (token content, not background)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2].astype(np.int32)
    s = hsv[:, :, 1].astype(np.int32)
    # Background greys have moderate value; pure white token details have V>245
    centers_hsv = cv2.cvtColor(
        bg_centers_bgr.reshape(-1, 1, 3).astype(np.uint8),
        cv2.COLOR_BGR2HSV
    ).reshape(-1, 3)
    bg_v_max = int(np.max(centers_hsv[:, 2])) if centers_hsv.size else 0
    protect_v = min(255, bg_v_max + 8)
    protect = (v >= protect_v) & (s <= 40)
    bg_cand[protect] = 0

    # Remove thin background bridges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    bg_cand = cv2.morphologyEx(bg_cand, cv2.MORPH_OPEN, kernel, iterations=1)

    # Only remove background connected to border
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bg_cand, connectivity=8)
    if n <= 1:
        return np.where(bg_cand > 0, 0, 255).astype(np.uint8)

    border_labels = set()
    for i in range(1, n):
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        ww = int(stats[i, cv2.CC_STAT_WIDTH])
        hh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if x <= 0 or y <= 0 or (x + ww) >= w or (y + hh) >= h:
            border_labels.add(i)

    if not border_labels:
        return np.full((h, w), 255, dtype=np.uint8)

    is_bg = np.isin(labels, list(border_labels))
    return np.where(is_bg, 0, 255).astype(np.uint8)


def fill_transparent_holes(alpha: np.ndarray) -> np.ndarray:
    """Fill interior transparent holes not connected to the border.

    Tokens should be opaque shapes; transparency is only for the outside.
    """
    if alpha is None or alpha.size == 0:
        return alpha

    h, w = alpha.shape[:2]
    transparent = (alpha == 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(transparent, connectivity=8)
    if n <= 1:
        return alpha

    border_labels = set()
    for i in range(1, n):
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        ww = int(stats[i, cv2.CC_STAT_WIDTH])
        hh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if x <= 0 or y <= 0 or (x + ww) >= w or (y + hh) >= h:
            border_labels.add(i)

    if not border_labels:
        out = alpha.copy()
        out[alpha == 0] = 255
        return out

    out = alpha.copy()
    holes = (transparent > 0) & (~np.isin(labels, list(border_labels)))
    out[holes] = 255
    return out


def fill_transparent_holes_within_template(
    alpha: np.ndarray,
    template_mask: np.ndarray,
    min_interior_dist: int = 3,
) -> np.ndarray:
    """Fill transparent regions enclosed by the template boundary.

    Fixes cases where interior artwork got keyed out.
    """
    if alpha is None or alpha.size == 0:
        return alpha

    inside = (template_mask > 0)
    if not inside.any():
        return alpha

    trans_inside = (alpha == 0) & inside
    if not trans_inside.any():
        return alpha

    inside_u8 = inside.astype(np.uint8) * 255
    dt = cv2.distanceTransform(inside_u8, cv2.DIST_L2, 3)

    n, labels, _stats, _ = cv2.connectedComponentsWithStats(
        trans_inside.astype(np.uint8), connectivity=8
    )
    if n <= 1:
        return alpha

    out = alpha.copy()
    for i in range(1, n):
        comp = labels == i
        if float(np.max(dt[comp])) >= float(min_interior_dist):
            out[comp] = 255
    return out


def compute_alpha_white_bg(bgr: np.ndarray) -> np.ndarray:
    """Remove white/near-white background using border connectivity.

    Fallback for tokens extracted from PDFs where the background is already white
    rather than the grey Kill Team texture. Detects white/near-white low-saturation
    pixels connected to the image border and makes them transparent.

    Args:
        bgr: Input BGR image (background should be white/near-white)

    Returns:
        Alpha channel (uint8, 0=transparent, 255=opaque)
    """
    h, w = bgr.shape[:2]
    if h <= 1 or w <= 1:
        return np.full((h, w), 255, dtype=np.uint8)

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    s = hsv[:, :, 1].astype(np.int32)
    v = hsv[:, :, 2].astype(np.int32)

    # White/near-white background: low saturation + high value
    bg_cand = ((s < 40) & (v > 210)).astype(np.uint8)

    # Open to remove thin bridges
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    bg_cand = cv2.morphologyEx(bg_cand, cv2.MORPH_OPEN, kernel, iterations=1)

    # Only remove border-connected regions
    n, labels, stats, _ = cv2.connectedComponentsWithStats(bg_cand, connectivity=8)
    if n <= 1:
        return np.where(bg_cand > 0, 0, 255).astype(np.uint8)

    border_labels = set()
    for i in range(1, n):
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        ww = int(stats[i, cv2.CC_STAT_WIDTH])
        hh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if x <= 0 or y <= 0 or (x + ww) >= w or (y + hh) >= h:
            border_labels.add(i)

    if not border_labels:
        return np.full((h, w), 255, dtype=np.uint8)

    is_bg = np.isin(labels, list(border_labels))
    return np.where(is_bg, 0, 255).astype(np.uint8)


def clean_edge_halos(
    bgr: np.ndarray,
    alpha: np.ndarray,
    bg_centers_bgr: np.ndarray,
    edge_width: int = 3,
    edge_threshold: int = 14,
) -> np.ndarray:
    """Remove thin bg-colored halos along transparency edges.

    Targets antialiased pixels that match background colors near existing transparency.
    """
    if alpha is None or alpha.size == 0:
        return alpha

    h, w = alpha.shape[:2]
    trans = (alpha == 0).astype(np.uint8)
    k = edge_width * 2 + 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    near_trans = cv2.dilate(trans, kernel, iterations=1) > 0
    candidates = near_trans & (alpha > 0)
    if not np.any(candidates):
        return alpha

    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.int16)
    centers_lab = cv2.cvtColor(
        bg_centers_bgr.reshape(-1, 1, 3).astype(np.uint8),
        cv2.COLOR_BGR2LAB
    ).reshape(-1, 3).astype(np.int16)

    d_all = []
    for i in range(centers_lab.shape[0]):
        c = centers_lab[i]
        dl = lab - c[None, None, :]
        d2 = (dl[:, :, 0].astype(np.int32) ** 2 +
              dl[:, :, 1].astype(np.int32) ** 2 +
              dl[:, :, 2].astype(np.int32) ** 2)
        d_all.append(d2)
    dist2 = np.min(np.stack(d_all, axis=2), axis=2)

    cutoff2 = edge_threshold * edge_threshold
    halo = candidates & (dist2 <= cutoff2)
    if not np.any(halo):
        return alpha

    out = alpha.copy()
    out[halo] = 0
    return out


def remove_small_alpha_components(alpha: np.ndarray, min_area: int = 50) -> np.ndarray:
    """Remove tiny opaque fragments that are noise."""
    if alpha is None or alpha.size == 0:
        return alpha

    mask = (alpha > 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return alpha

    out = alpha.copy()
    for i in range(1, n):
        if int(stats[i, cv2.CC_STAT_AREA]) < min_area:
            out[labels == i] = 0
    return out


# ============================================================================
# Token Processing Pipeline
# ============================================================================

def normalize_background_to_white(bgr: np.ndarray) -> np.ndarray:
    """Normalize grey/off-white background pixels to pure white.

    Helps the template fitting and bg removal work more accurately.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h_ch, s, v = cv2.split(hsv)

    # Background: low saturation + high value (grey/white)
    is_background = (s < 35) & (v > 160)

    out = bgr.copy()
    out[is_background] = (255, 255, 255)
    return out


def process_single_token(
    source_path: Path,
    shape: str,
    bg_centers: np.ndarray,
    target_templates: Dict[str, np.ndarray],
    bg_threshold: int = 18,
) -> Optional[np.ndarray]:
    """Process a single token image to transparent PNG.

    Uses fixed-size templates at TARGET_SIZE so every token of the same shape
    produces an identical silhouette. Content is scaled to fit inside the
    template and centered on the canvas.

    Args:
        source_path: Path to rough-cropped token image
        shape: Token shape ('round', 'operative', 'octagon', 'diamond')
        bg_centers: Background color centers (BGR)
        target_templates: Dict of shape -> binary mask at TARGET_SIZE x TARGET_SIZE
        bg_threshold: Lab-space threshold for bg removal

    Returns:
        BGRA image (uint8, TARGET_SIZE x TARGET_SIZE) with transparent background,
        or None on failure
    """
    # Load source image
    img = cv2.imread(str(source_path), cv2.IMREAD_COLOR)
    if img is None:
        logger.error(f"    Failed to load image: {source_path}")
        return None

    h, w = img.shape[:2]

    # Step 1: Normalize background to white
    normalized = normalize_background_to_white(img)

    # Step 2: Remove background using color keying
    alpha = compute_bg_alpha(normalized, bg_centers, threshold=bg_threshold)

    # Fallback: if bg keying removed almost nothing (e.g., warcom white-bg tokens),
    # detect white background directly
    total_px = h * w
    bg_removed = int((alpha == 0).sum())
    if bg_removed < total_px * 0.05:
        alpha = compute_alpha_white_bg(normalized)

    # Step 3: Fill interior holes before cropping
    alpha = fill_transparent_holes(alpha)

    # Step 4: Find content bounding box and crop
    ys, xs = np.where(alpha > 0)
    if len(xs) == 0:
        logger.error(f"    No content detected after bg removal: {source_path}")
        return None

    cx0, cy0 = int(xs.min()), int(ys.min())
    cx1, cy1 = int(xs.max()) + 1, int(ys.max()) + 1
    content_bgr = img[cy0:cy1, cx0:cx1]
    content_alpha = alpha[cy0:cy1, cx0:cx1]
    ch, cw = content_bgr.shape[:2]

    # Step 5: Place content into fixed-size template
    template = target_templates.get(shape)
    if template is not None:
        # Find the template shape bbox within the TARGET_SIZE canvas
        tys, txs = np.where(template > 0)
        tx0, ty0 = int(txs.min()), int(tys.min())
        tx1, ty1 = int(txs.max()) + 1, int(tys.max()) + 1
        templ_w = tx1 - tx0
        templ_h = ty1 - ty0

        # Scale content to fit inside template bbox with small inset
        inset = 2
        fit_w = templ_w - 2 * inset
        fit_h = templ_h - 2 * inset
        scale = min(fit_w / max(1, cw), fit_h / max(1, ch))
        new_w = max(1, int(round(cw * scale)))
        new_h = max(1, int(round(ch * scale)))

        scaled_bgr = cv2.resize(content_bgr, (new_w, new_h), interpolation=cv2.INTER_AREA)
        scaled_alpha = cv2.resize(content_alpha, (new_w, new_h), interpolation=cv2.INTER_AREA)

        # Build canvas
        canvas_bgr = np.full((TARGET_SIZE, TARGET_SIZE, 3), 255, dtype=np.uint8)
        canvas_alpha = np.zeros((TARGET_SIZE, TARGET_SIZE), dtype=np.uint8)

        # Center content within template bbox
        px = tx0 + (templ_w - new_w) // 2
        py = ty0 + (templ_h - new_h) // 2
        canvas_bgr[py:py + new_h, px:px + new_w] = scaled_bgr
        canvas_alpha[py:py + new_h, px:px + new_w] = scaled_alpha

        # Apply template mask - everything outside shape becomes transparent
        canvas_alpha[template == 0] = 0

        # Fill interior holes within template (e.g., white artwork areas keyed out)
        canvas_alpha = fill_transparent_holes_within_template(canvas_alpha, template)

        # Clean edge halos near template boundary
        canvas_alpha = clean_edge_halos(canvas_bgr, canvas_alpha, bg_centers)

        # Remove tiny fragments
        canvas_alpha = remove_small_alpha_components(canvas_alpha)

        return np.dstack([canvas_bgr, canvas_alpha])

    # No template available - just resize content to target
    alpha = clean_edge_halos(img, alpha, bg_centers)
    alpha = remove_small_alpha_components(alpha)
    bgra = np.dstack([img, alpha])
    return cv2.resize(bgra, (TARGET_SIZE, TARGET_SIZE), interpolation=cv2.INTER_AREA)


def process_team_tokens(
    team_name: str,
    base_dir: Path = None,
    bg_threshold: int = 18,
    force: bool = False,
) -> Dict:
    """Process all tokens for a team.

    Args:
        team_name: Team slug
        base_dir: Workspace root (default: cwd)
        bg_threshold: Lab-space threshold for bg removal
        force: Overwrite existing tokens

    Returns:
        Stats dict with counts
    """
    if base_dir is None:
        base_dir = Path.cwd()

    # Load token index
    index_path = base_dir / 'metadata' / team_name / 'token_index.json'
    if not index_path.exists():
        logger.error(f"  Token index not found: {index_path}")
        logger.error(f"  Run step 3 (index_cards) first")
        return {'processed': 0, 'total': 0, 'errors': ['missing_index']}

    with open(index_path, 'r', encoding='utf-8') as f:
        token_index = json.load(f)

    tokens = token_index.get('tokens', [])
    if not tokens:
        logger.info(f"  No tokens in index for {team_name}")
        return {'processed': 0, 'total': 0, 'errors': []}

    logger.info(f"  Found {len(tokens)} tokens to process")

    # Learn background colors
    bg_sample_path = base_dir / BG_SAMPLE_PATH
    if bg_sample_path.exists():
        logger.info(f"  Learning background from: {BG_SAMPLE_PATH}")
        bg_centers = learn_bg_colors(bg_sample_path)
    else:
        logger.info(f"  BG sample not found, learning from token borders")
        token_paths = [base_dir / t['source_file'] for t in tokens]
        bg_centers = learn_bg_colors_from_borders(token_paths)

    logger.info(f"  Learned {len(bg_centers)} background color centers")

    # Load shape templates, pre-scaled to TARGET_SIZE for consistent output
    target_templates = {}
    for shape in ['round', 'operative', 'octagon', 'diamond']:
        raw_mask = load_template_mask(shape)
        if raw_mask is not None:
            target_templates[shape] = prepare_template_at_target_size(raw_mask)
            logger.debug(f"  Loaded template: {shape}")

    # Output directory
    output_dir = base_dir / 'output' / team_name / 'tokens'
    output_dir.mkdir(parents=True, exist_ok=True)

    processed = 0
    errors = []

    for token in tokens:
        token_name = token['name']
        token_shape = token['shape']
        source_file = token['source_file']
        token_slug = slugify(token_name)

        output_path = output_dir / f'{token_slug}.png'
        if output_path.exists() and not force:
            logger.info(f"    {token_name} → already exists (skip)")
            processed += 1
            continue

        source_path = base_dir / source_file
        if not source_path.exists():
            logger.error(f"    {token_name} → source not found: {source_file}")
            errors.append(f"missing_source:{token_name}")
            continue

        logger.info(f"    Processing: {token_name} ({token_shape})")

        result = process_single_token(
            source_path, token_shape, bg_centers, target_templates,
            bg_threshold=bg_threshold
        )

        if result is None:
            logger.error(f"    {token_name} → processing failed")
            errors.append(f"processing_failed:{token_name}")
            continue

        # Save
        cv2.imwrite(str(output_path), result)
        logger.info(f"    ✓ {token_name} → {output_path.name}")
        processed += 1

    return {'processed': processed, 'total': len(tokens), 'errors': errors}


# ============================================================================
# Entry Points
# ============================================================================

def run(teams: List[str] = None, base_dir: Path = None, bg_threshold: int = 18, force: bool = False) -> Dict:
    """Main entry point for token processing.

    Args:
        teams: List of team slugs to process (None = all with token indexes)
        base_dir: Workspace root
        bg_threshold: Lab-space threshold for bg removal
        force: Overwrite existing tokens

    Returns:
        Results dict
    """
    if base_dir is None:
        base_dir = Path.cwd()

    # Discover teams
    if teams:
        team_list = teams
    else:
        metadata_dir = base_dir / 'metadata'
        if not metadata_dir.exists():
            logger.error(f"Metadata directory not found: {metadata_dir}")
            return {'error': 'no_metadata_dir'}

        team_list = []
        for team_dir in sorted(metadata_dir.iterdir()):
            if team_dir.is_dir() and (team_dir / 'token_index.json').exists():
                team_list.append(team_dir.name)

    results = {
        'processed_teams': [],
        'failed_teams': [],
        'total_tokens': 0,
    }

    for team_name in team_list:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"Processing tokens: {team_name}")
        logger.info(f"{'=' * 60}")

        stats = process_team_tokens(
            team_name, base_dir=base_dir,
            bg_threshold=bg_threshold, force=force
        )

        if stats.get('errors'):
            logger.warning(f"  ⚠ {len(stats['errors'])} errors")
            for err in stats['errors']:
                logger.warning(f"    - {err}")

        if stats['processed'] > 0:
            results['processed_teams'].append(team_name)
            results['total_tokens'] += stats['processed']
        elif stats.get('errors'):
            results['failed_teams'].append(team_name)

    # Summary
    logger.info(f"\n{'=' * 60}")
    logger.info("TOKEN PROCESSING COMPLETE")
    logger.info(f"{'=' * 60}")
    logger.info(f"Teams processed: {len(results['processed_teams'])}")
    logger.info(f"Total tokens: {results['total_tokens']}")
    if results['failed_teams']:
        logger.warning(f"Failed: {len(results['failed_teams'])} teams")

    return results


def main():
    parser = argparse.ArgumentParser(
        description='Step 4b: Process tokens to transparent PNGs'
    )
    parser.add_argument('--team', type=str, nargs='+',
                        help='Team slug(s) to process')
    parser.add_argument('--base-dir', type=Path,
                        help='Base directory (default: cwd)')
    parser.add_argument('--bg-threshold', type=int, default=18,
                        help='Lab-space threshold for background removal (default: 18)')
    parser.add_argument('--force', action='store_true',
                        help='Overwrite existing token PNGs')
    parser.add_argument('--log-level', default='INFO',
                        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                        help='Log level')

    args = parser.parse_args()

    logging.getLogger().setLevel(getattr(logging, args.log_level))

    run(
        teams=args.team,
        base_dir=args.base_dir,
        bg_threshold=args.bg_threshold,
        force=args.force,
    )


if __name__ == '__main__':
    main()
