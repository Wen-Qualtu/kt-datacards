"""
Token Extraction Script for Kill Team Datacards

Extracts individual token images from marker/token guide cards.
Uses PDF text extraction for accurate token names, falling back to OCR if needed.

Usage:
    poetry run python script/tools/extract_tokens.py --team farstalker-kinband
    poetry run python script/tools/extract_tokens.py --all
"""

import argparse
import os
from pathlib import Path
import shutil
from PIL import Image, ImageDraw, ImageFilter
import numpy as np
import cv2
from typing import List, Tuple, Dict
import json
import pytesseract
import fitz  # PyMuPDF
import re
import time
import yaml


class TokenExtractor:
    """Extract individual tokens from marker/token guide images."""
    
    def __init__(
        self,
        output_base_dir: Path,
        *,
        text_gap_max: float = 6.0,
        same_line_y_max: float = 15.0,
        next_line_y_min: float = 5.0,
        next_line_y_max: float = 25.0,
        next_line_x_overlap_ratio: float = 0.25,
        name_match_max_distance: float = 300.0,
    ):
        self.output_base_dir = output_base_dir
        self.output_base_dir.mkdir(exist_ok=True, parents=True)

        # PDF text grouping heuristics
        self.text_gap_max = text_gap_max
        self.same_line_y_max = same_line_y_max
        self.next_line_y_min = next_line_y_min
        self.next_line_y_max = next_line_y_max
        self.next_line_x_overlap_ratio = next_line_x_overlap_ratio

        # Token name matching
        self.name_match_max_distance = name_match_max_distance

        # Cache PDF text extraction since auto-tuning may run multiple passes per team
        # Keyed by (pdf_path, target_image_path)
        self._pdf_text_cache: Dict[Tuple[str, str], Dict[Tuple[int, int], str]] = {}

        # Cache template alpha masks for shape-cutout (keyed by path)
        self._template_alpha_cache: Dict[str, np.ndarray] = {}

        # Cache team config for token shapes
        self._team_config_cache: Dict = {}
        self._load_team_config()

        # Reference token silhouettes (used as a cookie-cutter).
        # These are *examples* with a good alpha channel that represent the intended shape.
        self._operative_template_path = Path(
            "processed/extracted-tokens/hearthkyn-salvagers/c8-hx-charge.png"
        )

        # Debug helpers (set during extract_tokens_auto when debug=True)
        self._debug_output_dir: Path | None = None
        self._debug_token_tag: str | None = None
        self._last_cutout_debug: dict | None = None

    def _load_team_config(self) -> None:
        """Load team configuration from config/team-config.yaml."""
        from . import paths
        config_path = paths.TEAM_CONFIG
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    self._team_config_cache = data.get('teams', {}) if data else {}
            except Exception as e:
                print(f"  ⚠ Could not load team config: {e}")
                self._team_config_cache = {}
        else:
            self._team_config_cache = {}

    def _get_token_shape_from_config(self, team_name: str, token_name: str) -> str | None:
        """Get the configured shape for a token from team config.
        
        Args:
            team_name: Team slug (e.g., 'murderwings')
            token_name: Token name (e.g., 'Damnation Points')
        
        Returns:
            Shape string ('round', 'octagon', 'diamond', 'operative') or None if not configured
        """
        if not self._team_config_cache:
            return None
        
        team_config = self._team_config_cache.get(team_name)
        if not team_config:
            return None
        
        tokens_config = team_config.get('tokens', [])
        if not tokens_config:
            return None
        
        # Normalize token name for matching (case-insensitive, whitespace-normalized)
        normalized_search = ' '.join(token_name.lower().split())
        
        for token_cfg in tokens_config:
            token_cfg_name = token_cfg.get('name', '')
            normalized_cfg = ' '.join(token_cfg_name.lower().split())
            
            if normalized_search == normalized_cfg:
                return token_cfg.get('shape')
        
        return None

    def _get_excluded_tokens(self, team_name: str) -> set:
        """Return normalized token identifiers to drop from auto-extraction.

        Driven by the team config ``exclude_tokens:`` list. Each entry is matched
        (case-insensitive, whitespace-normalized) against a token's ``safe_name``
        or display ``name``. Custom tokens are never affected.
        """
        if not self._team_config_cache:
            return set()
        team_cfg = self._team_config_cache.get(team_name)
        if not team_cfg:
            return set()
        return {
            ' '.join(str(entry).lower().split())
            for entry in (team_cfg.get('exclude_tokens', []) or [])
        }

    def _write_cutout_debug_overlay(self, *, token_img: np.ndarray, mask: np.ndarray, meta: dict) -> None:
        if self._debug_output_dir is None or self._debug_token_tag is None:
            return
        try:
            out_dir = self._debug_output_dir
            tag = re.sub(r"[^a-zA-Z0-9_\-]", "_", self._debug_token_tag)

            vis = token_img.copy()

            # Outline the mask.
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if contours:
                cv2.drawContours(vis, contours, -1, (0, 255, 0), 2)

            def _pt(name: str):
                p = meta.get(name)
                if p is None:
                    return None
                try:
                    return int(round(float(p[0]))), int(round(float(p[1])))
                except Exception:
                    return None

            tl = _pt('token_tl')
            bl = _pt('token_bl')
            if tl is not None:
                cv2.circle(vis, tl, 5, (0, 0, 255), -1)
                cv2.putText(vis, 'TL', (tl[0] + 6, tl[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            if bl is not None:
                cv2.circle(vis, bl, 5, (255, 0, 0), -1)
                cv2.putText(vis, 'BL', (bl[0] + 6, bl[1] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

            line1 = f"method={meta.get('method', 'unknown')} sf={meta.get('shrink_factor', '')}"
            line2 = f"out_frac={meta.get('out_frac', '')} mask_frac={meta.get('mask_frac', '')}"
            cv2.putText(vis, line1[:60], (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 2)
            cv2.putText(vis, line1[:60], (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            cv2.putText(vis, line2[:60], (6, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (20, 20, 20), 2)
            cv2.putText(vis, line2[:60], (6, 38), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

            overlay_path = out_dir / f"_debug_cutout_{tag}.png"
            mask_path = out_dir / f"_debug_cutout_{tag}_mask.png"
            cv2.imwrite(str(overlay_path), vis)
            cv2.imwrite(str(mask_path), mask)
            print(f"  ℹ Cutout debug saved: {overlay_path}")
        except Exception:
            # Debug output must never break extraction.
            return

    def _postprocess_text_labels(self, token_names: Dict[Tuple[int, int], str]) -> Dict[Tuple[int, int], str]:
        """Post-process extracted text labels to improve pairing.

        Some teams render "Values 1" and "2" as separate text items (often the "2" is just a
        standalone digit). Convert digit-only labels into "<base> Values <digit>" using the
        nearest "Values 1" label as the base.
        """

        if not token_names:
            return token_names

        labels = list(token_names.items())
        values1: List[Tuple[Tuple[int, int], str]] = []
        for pos, text in labels:
            if re.search(r"\bvalues?\b", text, flags=re.IGNORECASE) and re.search(r"\b1\b", text):
                values1.append((pos, text))

        if not values1:
            return token_names

        updated = dict(token_names)
        for (x, y), text in labels:
            t = (text or "").strip()
            if not re.fullmatch(r"\d+", t):
                continue

            digit = t
            best_text: str | None = None
            best_dist = float('inf')
            for (vx, vy), vtext in values1:
                d = ((vx - x) ** 2 + (vy - y) ** 2) ** 0.5
                if d < best_dist:
                    best_dist = d
                    best_text = vtext

            # Only borrow if reasonably nearby; avoids accidental cross-row pairing.
            if best_text is None or best_dist > 250:
                continue

            # Replace "Values 1" with "Values <digit>".
            new_text = re.sub(
                r"(\bvalues?\s*)1\b",
                rf"\g<1>{digit}",
                best_text,
                flags=re.IGNORECASE,
                count=1,
            )
            updated[(x, y)] = new_text

        # Filter out "Soul Harvest" related labels from extraction matching
        # These are handled by custom tokens and should not interfere with other token detection
        filtered = {}
        for pos, text in updated.items():
            # Skip labels matching "Soul Harvest points Values X" or similar patterns
            if re.search(r"\bsoul\s+harvest\b.*\bvalues?\b", text, flags=re.IGNORECASE):
                continue
            # Skip standalone "Soul Harvest X" numbered labels
            if re.search(r"\bsoul\s+harvest\s+\d+\b", text, flags=re.IGNORECASE):
                continue
            filtered[pos] = text

        return filtered

    def _split_double_token_image(self, token_img: np.ndarray) -> List[np.ndarray] | None:
        """Try to split a single extracted image that actually contains 2 adjacent tokens.

        This is intended for the common "Values 1/2" double-token blob, where CV contour
        detection returns a single contour spanning both token shapes.

        Returns a list of exactly 2 images (left-to-right) if a split is found; otherwise None.
        """

        if token_img is None or token_img.size == 0:
            return None

        gray = cv2.cvtColor(token_img, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel, iterations=1)

        h, w = mask.shape[:2]
        if w < 40 or h < 40:
            return None

        col_sum = mask.sum(axis=0).astype(np.float32)  # 0..255*h
        if col_sum.max() <= 0:
            return None

        # Smooth to reduce noise; deterministic window.
        win = max(9, (w // 30) | 1)  # odd
        kernel_1d = np.ones(win, dtype=np.float32) / float(win)
        smoothed = np.convolve(col_sum, kernel_1d, mode='same')

        # First try a simple valley cut near the center.
        mid_start = int(w * 0.30)
        mid_end = int(w * 0.70)
        if mid_end <= mid_start + 5:
            mid_start = max(0, (w // 2) - 5)
            mid_end = min(w, (w // 2) + 5)

        cut_x = int(mid_start + np.argmin(smoothed[mid_start:mid_end]))
        valley = float(smoothed[cut_x])
        peak = float(smoothed.max())
        if peak <= 0:
            return None

        # If there's no real valley, fall back to a more robust split.
        valley_ok = (valley / peak) <= 0.82

        if valley_ok:
            left_mask = mask[:, :cut_x]
            right_mask = mask[:, cut_x:]
            left_area = float(left_mask.sum())
            right_area = float(right_mask.sum())
            if left_area < 255 * 200 or right_area < 255 * 200:
                valley_ok = False

        def crop_to_foreground(img: np.ndarray, m: np.ndarray, *, x_offset: int) -> np.ndarray | None:
            ys, xs = np.where(m > 0)
            if len(xs) == 0 or len(ys) == 0:
                return None
            x0 = int(xs.min() + x_offset)
            x1 = int(xs.max() + x_offset)
            y0 = int(ys.min())
            y1 = int(ys.max())
            pad = 10
            x0 = max(0, x0 - pad)
            y0 = max(0, y0 - pad)
            x1 = min(img.shape[1] - 1, x1 + pad)
            y1 = min(img.shape[0] - 1, y1 + pad)
            if x1 <= x0 or y1 <= y0:
                return None
            return img[y0:y1 + 1, x0:x1 + 1]

        if valley_ok:
            left = crop_to_foreground(token_img, left_mask, x_offset=0)
            right = crop_to_foreground(token_img, right_mask, x_offset=cut_x)
            if left is not None and right is not None:
                return [left, right]

        # Fallback: k-means split on foreground pixels (handles diagonal overlap).
        ys, xs = np.where(mask > 0)
        if len(xs) < 2000:
            return None

        pts = np.column_stack([xs, ys]).astype(np.float32)
        # Deterministic sampling / initialization
        cv2.setRNGSeed(0)
        if len(pts) > 6000:
            idx = np.linspace(0, len(pts) - 1, 6000).astype(np.int32)
            pts = pts[idx]

        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.5)
        compactness, labels, centers = cv2.kmeans(
            pts,
            2,
            None,
            criteria,
            1,
            cv2.KMEANS_PP_CENTERS,
        )
        centers = centers.astype(np.float32)

        # Require clusters to be meaningfully separated.
        if abs(float(centers[0, 0] - centers[1, 0])) < (w * 0.18):
            return None

        # Order clusters left-to-right.
        order = np.argsort(centers[:, 0])
        out_imgs: List[np.ndarray] = []
        for k in order:
            cluster_pts = pts[labels.ravel() == int(k)]
            if len(cluster_pts) < 500:
                return None
            x0 = int(cluster_pts[:, 0].min())
            x1 = int(cluster_pts[:, 0].max())
            y0 = int(cluster_pts[:, 1].min())
            y1 = int(cluster_pts[:, 1].max())
            pad = 12
            x0 = max(0, x0 - pad)
            y0 = max(0, y0 - pad)
            x1 = min(w - 1, x1 + pad)
            y1 = min(h - 1, y1 + pad)
            if x1 <= x0 or y1 <= y0:
                return None
            out_imgs.append(token_img[y0:y1 + 1, x0:x1 + 1])

        if len(out_imgs) != 2:
            return None
        return out_imgs

    def _whiten_outside_token_shape(self, token_img: np.ndarray) -> np.ndarray:
        """Whiten everything outside the token silhouette.

        This is primarily used to remove remnants of adjacent/overlapped tokens (e.g. "Values 2")
        from a cropped token image.

        The heuristic assumes the final token silhouette is roughly circular and derives a circle
        (center + radius) from edge strength. Pixels outside that circle are set to white.
        """

        if token_img is None or token_img.size == 0:
            return token_img

        h, w = token_img.shape[:2]
        if h < 32 or w < 32:
            return token_img

        gray = cv2.cvtColor(token_img, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)

        # Rough foreground to estimate a sensible center.
        _, fg = cv2.threshold(blur, 245, 255, cv2.THRESH_BINARY_INV)
        fg = cv2.morphologyEx(
            fg,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )

        cx = w // 2
        cy = h // 2
        try:
            num, labels, stats, centroids = cv2.connectedComponentsWithStats(fg, connectivity=8)
            if num > 1:
                # Prefer a component whose centroid is near the center of the crop.
                best = None
                best_score = float('inf')
                for i in range(1, num):
                    area = int(stats[i, cv2.CC_STAT_AREA])
                    if area < 300:
                        continue
                    x, y, ww, hh = (
                        int(stats[i, cv2.CC_STAT_LEFT]),
                        int(stats[i, cv2.CC_STAT_TOP]),
                        int(stats[i, cv2.CC_STAT_WIDTH]),
                        int(stats[i, cv2.CC_STAT_HEIGHT]),
                    )
                    # Ignore obvious tiny fragments.
                    if ww < 10 or hh < 10:
                        continue
                    cxi, cyi = centroids[i]
                    dx = float(cxi - cx)
                    dy = float(cyi - cy)
                    dist2 = dx * dx + dy * dy
                    # Score favors near-center components; tie-break by larger area.
                    score = dist2 / max(1.0, float(area))
                    if score < best_score:
                        best_score = score
                        best = (int(round(cxi)), int(round(cyi)))

                if best is not None:
                    cx, cy = best
        except Exception:
            # Keep image-center fallback.
            pass

        edges = cv2.Canny(blur, 50, 150)

        min_dim = min(h, w)
        min_r = max(8, int(round(min_dim * 0.28)))
        max_r = max(min_r + 4, int(round(min_dim * 0.55)))
        max_r = min(max_r, (min_dim // 2) - 1)
        if max_r <= min_r:
            return token_img

        angles = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False, dtype=np.float32)
        cos_a = np.cos(angles)
        sin_a = np.sin(angles)

        best_r = None
        best_strength = -1.0
        for r in range(min_r, max_r + 1, 2):
            xs = (cx + (r * cos_a)).round().astype(np.int32)
            ys = (cy + (r * sin_a)).round().astype(np.int32)

            # Keep only in-bounds samples.
            inb = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
            if not np.any(inb):
                continue
            strength = float(np.mean(edges[ys[inb], xs[inb]]))
            if strength > best_strength:
                best_strength = strength
                best_r = r

        if best_r is None or best_strength < 5.0:
            # Fallback: use enclosing circle of the largest edge contour.
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return token_img
            c = max(contours, key=cv2.contourArea)
            (fx, fy), fr = cv2.minEnclosingCircle(c)
            cx, cy = int(round(fx)), int(round(fy))
            best_r = int(round(fr))
            if best_r <= 0:
                return token_img

        # Slightly expand to include the outer ring.
        radius = int(round(best_r * 1.04))
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.circle(mask, (int(cx), int(cy)), radius, 255, thickness=-1)

        out = token_img.copy()
        out[mask == 0] = (255, 255, 255)
        return out

    def _normalize_background_to_white(self, token_img: np.ndarray) -> np.ndarray:
        """Normalize grey/off-white background pixels to pure white.
        
        This is important for template fitting to work correctly - the cutter needs
        clean white backgrounds to accurately detect token content vs background.
        """
        if token_img is None or token_img.size == 0:
            return token_img
        
        # Convert to HSV for better background detection
        hsv = cv2.cvtColor(token_img, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        # Background characteristics:
        # - Low saturation (grey/white, not colored)
        # - High value (bright, not dark)
        # More aggressive thresholds to catch more grey shades
        is_background = (s < 35) & (v > 160)  # Increased from s<25, v>180
        
        # Apply whitening
        out = token_img.copy()
        out[is_background] = (255, 255, 255)
        
        return out

    def _detect_octagon(self, contour: np.ndarray, token_img: np.ndarray) -> bool:
        """Detect if a contour is an octagon shape.
        
        Octagons have 8 vertices with distinct flat edges.
        Must distinguish from circles which may have many vertices due to approximation.
        """
        if contour is None or len(contour) < 8:
            return False
        
        # Approximate the contour to a polygon with stricter epsilon for clearer edge detection
        epsilon = 0.015 * cv2.arcLength(contour, True)  # Stricter than 0.02
        approx = cv2.approxPolyDP(contour, epsilon, True)
        
        # Octagons should have exactly 8 vertices (allow 7-9 for imperfect shapes)
        num_vertices = len(approx)
        if 7 <= num_vertices <= 9:
            # Check circularity - octagons are more circular than rectangles but distinctly less than circles
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            if perimeter > 0:
                circularity = (4 * np.pi * area) / (perimeter ** 2)
                # Octagons typically have circularity between 0.88 and 0.93
                # Circles are > 0.94, squares are ~0.785
                # This narrower range avoids catching circles
                if 0.88 <= circularity <= 0.93:
                    # Additional check: octagons should have relatively uniform edge lengths
                    # Calculate variance in edge lengths
                    if len(approx) >= 7:
                        edges = []
                        for i in range(len(approx)):
                            p1 = approx[i][0]
                            p2 = approx[(i + 1) % len(approx)][0]
                            edge_len = np.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)
                            edges.append(edge_len)
                        
                        if edges:
                            mean_edge = np.mean(edges)
                            std_edge = np.std(edges)
                            # Octagons have relatively uniform edges (low coefficient of variation)
                            # Circles approximated as polygons have more variable edge lengths
                            cv_edges = std_edge / mean_edge if mean_edge > 0 else 1.0
                            if cv_edges < 0.15:  # Uniform edges
                                return True
        
        return False
    
    def _detect_diamond(self, contour: np.ndarray, token_img: np.ndarray) -> bool:
        """Detect if a contour is a diamond shape (square rotated 45 degrees).
        
        Diamonds have 4 vertices and are roughly square-shaped.
        The key distinction is the rotation angle.
        """
        if contour is None or len(contour) < 4:
            return False
        
        # Get the minimum area rectangle (which gives us rotation info)
        rect = cv2.minAreaRect(contour)
        (cx, cy), (width, height), angle = rect
        
        # Check if roughly square-shaped
        if width > 0 and height > 0:
            aspect_ratio = max(width, height) / min(width, height)
            # Should be roughly square (allow some tolerance)
            if aspect_ratio <= 1.35:
                # Check if rotated ~45 degrees
                # The angle from minAreaRect is between -90 and 0
                # A diamond rotated 45 degrees will have angle around -45
                # Allow tolerance for imperfect shapes
                angle_normalized = abs(angle + 45)  # Distance from -45 degrees
                if angle_normalized <= 15:  # Within 15 degrees of 45-degree rotation
                    # Also verify it has approximately 4 corners using polygon approximation
                    epsilon = 0.02 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    num_vertices = len(approx)
                    # Allow 4-5 vertices (sometimes noise adds an extra corner)
                    if 4 <= num_vertices <= 5:
                        return True
                
                # Also check the other rotation (could be rotated the other way)
                angle_normalized_alt = abs(angle + 135) if angle < -90 else abs(angle - 45)
                if angle_normalized_alt <= 15:
                    epsilon = 0.02 * cv2.arcLength(contour, True)
                    approx = cv2.approxPolyDP(contour, epsilon, True)
                    num_vertices = len(approx)
                    if 4 <= num_vertices <= 5:
                        return True
        
        return False
    
    def _infer_round_marker_from_image(self, token_img: np.ndarray) -> float | None:
        """Infer whether an extracted token image likely represents a round marker.

        Uses Hough circle detection on edges to detect the outer circular ring.
        Returns an estimated ring-confidence (0..1) if it looks round, else None.
        """

        circle = self._detect_round_circle(token_img)
        if circle is None:
            return None
        return float(circle['confidence'])

    def _detect_round_circle(self, token_img: np.ndarray) -> dict | None:
        """Detect a circular marker ring within a near-square token crop.

        Returns dict with keys: cx, cy, r, confidence, touches_edge.
        """
        if token_img is None or token_img.size == 0:
            return None

        h, w = token_img.shape[:2]
        if h < 60 or w < 60:
            return None

        aspect = w / float(h) if h > 0 else 0.0
        if aspect < 0.85 or aspect > 1.15:
            return None

        gray = cv2.cvtColor(token_img, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        edges = cv2.Canny(gray, 35, 120)
        # Strengthen broken rings.
        edges = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)), iterations=1)

        min_dim = float(min(h, w))
        # We only want the *outer* marker ring, not internal circular icons.
        min_r = int(round(min_dim * 0.42))
        max_r = int(round(min_dim * 0.56))
        if max_r <= min_r:
            return None

        circles = cv2.HoughCircles(
            edges,
            cv2.HOUGH_GRADIENT,
            dp=1.2,
            minDist=min_dim * 0.5,
            param1=120,
            param2=22,
            minRadius=min_r,
            maxRadius=max_r,
        )

        if circles is None or len(circles) == 0:
            return None

        circles = circles[0]
        # Pick the circle closest to image center.
        center_x = w / 2.0
        center_y = h / 2.0
        best = None
        best_score = float('inf')
        for cx, cy, r in circles:
            dx = float(cx) - center_x
            dy = float(cy) - center_y
            score = (dx * dx + dy * dy) ** 0.5
            if score < best_score:
                best_score = score
                best = (float(cx), float(cy), float(r))

        if best is None:
            return None

        cx, cy, r = best

        # Outer marker rings should be close to centered.
        center_dist = ((cx - center_x) ** 2 + (cy - center_y) ** 2) ** 0.5
        if center_dist > (min_dim * 0.08):
            return None

        # Validate ring support by sampling edge hits along circumference.
        angles = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False, dtype=np.float32)
        xs = (cx + r * np.cos(angles)).round().astype(np.int32)
        ys = (cy + r * np.sin(angles)).round().astype(np.int32)
        inb = (xs >= 0) & (xs < w) & (ys >= 0) & (ys < h)
        if not np.any(inb):
            return None
        hits = edges[ys[inb], xs[inb]] > 0
        hit_frac = float(np.mean(hits)) if hits.size else 0.0

        # Require meaningful ring presence.
        if hit_frac < 0.12:
            return None

        # Confidence scaled from hit fraction; cap reasonably.
        confidence = max(0.0, min(1.0, (hit_frac - 0.10) / 0.22))

        touches_edge = (
            (cx - r) <= 2.0 or (cy - r) <= 2.0 or (cx + r) >= (w - 3.0) or (cy + r) >= (h - 3.0)
        )

        return {
            'cx': cx,
            'cy': cy,
            'r': r,
            'confidence': confidence,
            'touches_edge': bool(touches_edge),
        }

    def _looks_like_side_by_side_double(self, token_img: np.ndarray) -> bool:
        """Detect a 'double token' blob: two substantial halves side-by-side.

        This is used to *skip* exports when splitting would produce incorrect silhouettes.
        """
        if token_img is None or token_img.size == 0:
            return False
        h, w = token_img.shape[:2]
        if h < 70 or w < 90:
            return False

        aspect = w / float(h) if h > 0 else 0.0
        if aspect < 1.18:
            return False

        gray = cv2.cvtColor(token_img, cv2.COLOR_BGR2GRAY)
        # Foreground = anything not near-white.
        fg = (gray < 245).astype(np.uint8)

        # Remove thin noise.
        fg = cv2.morphologyEx(
            fg,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)),
            iterations=1,
        )

        col_sum = fg.sum(axis=0).astype(np.float32)
        if col_sum.size < 10:
            return False
        # Normalize.
        mx = float(np.max(col_sum)) if float(np.max(col_sum)) > 0 else 0.0
        if mx <= 0.0:
            return False
        col_n = col_sum / mx

        # Look for a deep valley near the vertical center.
        c0 = int(round(w * 0.35))
        c1 = int(round(w * 0.65))
        c0 = max(1, min(w - 2, c0))
        c1 = max(c0 + 1, min(w - 1, c1))
        center_min = float(np.min(col_n[c0:c1])) if c1 > c0 else 1.0
        if center_min > 0.08:
            return False

        # Both halves must carry significant mass.
        total = float(fg.sum())
        if total <= 0:
            return False
        left = float(fg[:, : w // 2].sum())
        right = float(fg[:, w // 2 :].sum())
        if left / total < 0.35 or right / total < 0.35:
            return False

        return True

    def _load_template_alpha(self, template_path: Path) -> np.ndarray | None:
        """Load and cache a template alpha channel as a uint8 mask (0..255)."""

        try:
            key = str(template_path)
            if key in self._template_alpha_cache:
                return self._template_alpha_cache[key]

            if not template_path.exists():
                return None

            im = Image.open(str(template_path)).convert('RGBA')
            alpha = np.array(im.getchannel('A'), dtype=np.uint8)
            if alpha.size == 0:
                return None

            self._template_alpha_cache[key] = alpha
            return alpha
        except Exception:
            return None

    def _foreground_mask(self, token_img: np.ndarray, *, threshold: int = 245) -> np.ndarray:
        """Return a binary mask (0/255) for non-background pixels.

        Assumes background is near-white. Deterministic.
        """

        threshold = int(max(0, min(255, threshold)))

        gray = cv2.cvtColor(token_img, cv2.COLOR_BGR2GRAY)
        _, fg = cv2.threshold(gray, threshold, 255, cv2.THRESH_BINARY_INV)
        fg = cv2.morphologyEx(
            fg,
            cv2.MORPH_OPEN,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
            iterations=1,
        )
        fg = cv2.morphologyEx(
            fg,
            cv2.MORPH_CLOSE,
            cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)),
            iterations=1,
        )
        return fg

    def _crop_to_foreground(self, token_img: np.ndarray, *, pad: int = 6, threshold: int = 245) -> np.ndarray:
        """Crop to the tight non-white bounding box (with padding)."""

        if token_img is None or token_img.size == 0:
            return token_img

        fg = self._foreground_mask(token_img, threshold=threshold)
        ys, xs = np.where(fg > 0)
        if len(xs) == 0 or len(ys) == 0:
            return token_img

        h, w = fg.shape[:2]
        x0 = max(0, int(xs.min()) - pad)
        x1 = min(w - 1, int(xs.max()) + pad)
        y0 = max(0, int(ys.min()) - pad)
        y1 = min(h - 1, int(ys.max()) + pad)
        if x1 <= x0 or y1 <= y0:
            return token_img
        return token_img[y0:y1 + 1, x0:x1 + 1]

    def _best_aligned_template_mask(self, token_img: np.ndarray, template_alpha: np.ndarray) -> np.ndarray | None:
        """Find best (scale, translation) alignment of a template alpha silhouette.

        Objective: minimize foreground that falls outside the silhouette while preferring tighter
        masks when scores are similar. Deterministic grid search.
        """

        if token_img is None or token_img.size == 0:
            return None

        h, w = token_img.shape[:2]
        if h < 32 or w < 32:
            return None

        fg = self._foreground_mask(token_img, threshold=245)
        total_fg = int((fg > 0).sum())
        if total_fg < 200:
            return None

        def _left_corners_from_mask(mask01: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
            if mask01 is None or mask01.size == 0:
                return None
            m = (mask01 > 0).astype(np.uint8) * 255
            # Clean small specks deterministically.
            m = cv2.morphologyEx(
                m,
                cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
                iterations=1,
            )
            contours, _ = cv2.findContours(m, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None
            c = max(contours, key=cv2.contourArea)
            area = float(cv2.contourArea(c))
            h2, w2 = m.shape[:2]
            if area < float(h2 * w2) * 0.04:
                return None
            hull = cv2.convexHull(c)
            pts = hull.reshape(-1, 2)
            if pts.shape[0] < 8:
                return None
            xs = pts[:, 0].astype(np.float32)
            x_cut = float(np.percentile(xs, 3.0))
            tol = max(2.0, float(w2) * 0.02)
            left_pts = pts[xs <= (x_cut + tol)]
            if left_pts.shape[0] < 2:
                # Fallback: use points at/near the min-x column.
                min_x = float(xs.min())
                left_pts = pts[xs <= (min_x + tol)]
            if left_pts.shape[0] < 2:
                return None
            ys = left_pts[:, 1]
            tl = left_pts[int(np.argmin(ys))].astype(np.float32)
            bl = left_pts[int(np.argmax(ys))].astype(np.float32)
            if float(np.linalg.norm(bl - tl)) < float(h2) * 0.25:
                return None
            return tl, bl

        def _silhouette_mask(img_bgr: np.ndarray) -> np.ndarray | None:
            """Return a filled silhouette mask for the token.

            This avoids relying on the crop corners being background (often false for split tokens).
            Background is approximated as "high value + low saturation" in HSV.
            """

            if img_bgr is None or img_bgr.size == 0:
                return None

            hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
            s = hsv[:, :, 1]
            v = hsv[:, :, 2]

            # Background tends to be very bright and low-saturation.
            bg = ((v >= 228) & (s <= 42)).astype(np.uint8) * 255
            bg_frac = float((bg > 0).mean())

            # If we didn't find much background (tight crop), fall back to "non-white" threshold.
            if bg_frac < 0.015:
                gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
                _, fg = cv2.threshold(gray, 245, 255, cv2.THRESH_BINARY_INV)
            else:
                fg = cv2.bitwise_not(bg)

            fg = cv2.morphologyEx(
                fg,
                cv2.MORPH_OPEN,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)),
                iterations=1,
            )
            fg = cv2.morphologyEx(
                fg,
                cv2.MORPH_CLOSE,
                cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (9, 9)),
                iterations=2,
            )

            contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                return None

            c = max(contours, key=cv2.contourArea)
            area = float(cv2.contourArea(c))
            h2, w2 = fg.shape[:2]
            if area < float(h2 * w2) * 0.08:
                return None

            filled = np.zeros((h2, w2), dtype=np.uint8)
            cv2.drawContours(filled, [c], -1, 255, thickness=-1)
            return filled

        def _warp_template_by_left_corners() -> tuple[np.ndarray, dict] | None:
            # Token anchors from a background-distance mask (more stable than simple thresholding).
            token_mask = _silhouette_mask(token_img)
            token_anchors = _left_corners_from_mask(token_mask) if token_mask is not None else None
            if token_anchors is None:
                return None
            tl_t, bl_t = token_anchors

            # Template anchors from alpha silhouette.
            templ_mask = (template_alpha > 0).astype(np.uint8) * 255
            templ_anchors = _left_corners_from_mask(templ_mask)
            if templ_anchors is None:
                return None
            tl_s, bl_s = templ_anchors

            v = (bl_s - tl_s).astype(np.float32)
            wv = (bl_t - tl_t).astype(np.float32)
            v_norm = float(np.linalg.norm(v))
            w_norm = float(np.linalg.norm(wv))
            if v_norm < 1e-3 or w_norm < 1e-3:
                return None
            scale = w_norm / v_norm

            ang_s = float(np.arctan2(v[1], v[0]))
            ang_t = float(np.arctan2(wv[1], wv[0]))
            theta = ang_t - ang_s
            cth = float(np.cos(theta))
            sth = float(np.sin(theta))
            R = np.array([[cth, -sth], [sth, cth]], dtype=np.float32)
            # If the template silhouette is slightly larger than the real token, a strict
            # 2-point match can still overhang. Try a small deterministic shrink-to-fit sweep
            # while keeping the top-left anchor fixed.
            shrink_factors = [1.00, 0.992, 0.985, 0.978, 0.970]
            best: np.ndarray | None = None
            best_mask_frac = float('inf')
            best_out_frac = float('inf')
            best_sf = 1.00

            for sf in shrink_factors:
                A2 = ((scale * sf) * R).astype(np.float32)
                t = tl_t - (A2 @ tl_s)
                M = np.array([[A2[0, 0], A2[0, 1], t[0]], [A2[1, 0], A2[1, 1], t[1]]], dtype=np.float32)
                warped = cv2.warpAffine(
                    templ_mask,
                    M,
                    (w, h),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT,
                    borderValue=0,
                )
                mask = (warped > 0).astype(np.uint8) * 255

                out_fg = int(((fg > 0) & (mask == 0)).sum())
                out_frac = out_fg / float(total_fg)
                if out_frac > 0.10:
                    continue

                mask_frac = float((mask > 0).mean())
                if (out_frac < best_out_frac - 1e-6) or (out_frac <= best_out_frac + 0.003 and mask_frac < best_mask_frac):
                    best = mask
                    best_out_frac = out_frac
                    best_mask_frac = mask_frac
                    best_sf = sf

            if best is None:
                return None

            meta = {
                'method': 'anchored',
                'shrink_factor': float(best_sf),
                'out_frac': float(best_out_frac),
                'mask_frac': float(best_mask_frac),
                'token_tl': [float(tl_t[0]), float(tl_t[1])],
                'token_bl': [float(bl_t[0]), float(bl_t[1])],
                'templ_tl': [float(tl_s[0]), float(tl_s[1])],
                'templ_bl': [float(bl_s[0]), float(bl_s[1])],
            }
            return best, meta

        # Try corner-anchored alignment first; it tends to be tighter and more accurate for
        # overlapped/split value tokens where the token is offset.
        anchored = _warp_template_by_left_corners()
        if anchored is not None:
            anchored_mask, _meta = anchored
            # Accept only if it covers the token foreground well.
            out_fg = int(((fg > 0) & (anchored_mask == 0)).sum())
            out_frac = out_fg / float(total_fg)
            if out_frac <= 0.08:
                if self._debug_output_dir is not None:
                    self._last_cutout_debug = dict(_meta)
                    self._last_cutout_debug['accepted'] = True
                return anchored_mask
            if self._debug_output_dir is not None:
                self._last_cutout_debug = dict(_meta)
                self._last_cutout_debug['accepted'] = False

        # Tuned for speed + stability; avoids over-fitting and keeps determinism.
        scales = [0.62, 0.68, 0.74, 0.80, 0.86, 0.92, 0.98]
        max_shift_x = int(round(w * 0.18))
        max_shift_y = int(round(h * 0.18))
        step = 4

        best_out_frac = float('inf')
        best_mask_frac = float('inf')
        best_mask: np.ndarray | None = None
        best_meta: dict | None = None

        for s in scales:
            tw = max(8, int(round(template_alpha.shape[1] * s)))
            th = max(8, int(round(template_alpha.shape[0] * s)))
            if tw > int(w * 1.05) or th > int(h * 1.05):
                continue

            alpha_resized = cv2.resize(template_alpha, (tw, th), interpolation=cv2.INTER_LINEAR)
            templ = (alpha_resized > 0).astype(np.uint8) * 255

            x_base = (w - tw) // 2
            y_base = (h - th) // 2

            for dy in range(-max_shift_y, max_shift_y + 1, step):
                y0 = y_base + dy
                if y0 < -th + 1 or y0 > h - 1:
                    continue
                for dx in range(-max_shift_x, max_shift_x + 1, step):
                    x0 = x_base + dx
                    if x0 < -tw + 1 or x0 > w - 1:
                        continue

                    mask = np.zeros((h, w), dtype=np.uint8)
                    sx0 = max(0, x0)
                    sy0 = max(0, y0)
                    sx1 = min(w, x0 + tw)
                    sy1 = min(h, y0 + th)
                    if sx1 <= sx0 or sy1 <= sy0:
                        continue

                    tx0 = sx0 - x0
                    ty0 = sy0 - y0
                    tx1 = tx0 + (sx1 - sx0)
                    ty1 = ty0 + (sy1 - sy0)
                    mask[sy0:sy1, sx0:sx1] = templ[ty0:ty1, tx0:tx1]

                    out_fg = int(((fg > 0) & (mask == 0)).sum())
                    out_frac = out_fg / float(total_fg)
                    mask_frac = float((mask > 0).mean())

                    # Primary objective: cover foreground (minimize out_frac).
                    # Secondary objective: among similarly-good coverings, prefer tighter masks.
                    if out_frac < best_out_frac - 1e-6:
                        best_out_frac = out_frac
                        best_mask_frac = mask_frac
                        best_mask = mask
                        best_meta = {
                            'method': 'grid',
                            'scale': float(s),
                            'dx': int(dx),
                            'dy': int(dy),
                            'out_frac': float(out_frac),
                            'mask_frac': float(mask_frac),
                        }
                    elif out_frac <= best_out_frac + 0.003 and mask_frac < best_mask_frac:
                        best_mask_frac = mask_frac
                        best_mask = mask
                        best_meta = {
                            'method': 'grid',
                            'scale': float(s),
                            'dx': int(dx),
                            'dy': int(dy),
                            'out_frac': float(out_frac),
                            'mask_frac': float(mask_frac),
                        }

        if self._debug_output_dir is not None and best_meta is not None:
            # Attach token anchor points if we can (helps validate false detections).
            token_mask = _silhouette_mask(token_img)
            token_anchors = _left_corners_from_mask(token_mask) if token_mask is not None else None
            if token_anchors is not None:
                tl_t, bl_t = token_anchors
                best_meta['token_tl'] = [float(tl_t[0]), float(tl_t[1])]
                best_meta['token_bl'] = [float(bl_t[0]), float(bl_t[1])]
            self._last_cutout_debug = dict(best_meta)

        return best_mask

    def _whiten_outside_template_shape(self, token_img: np.ndarray, template_path: Path) -> np.ndarray:
        """Whiten everything outside a template alpha silhouette.

        The template is resized to the current token image size. Pixels where template alpha is 0
        are set to white. This is a deterministic "cookie cutter" for non-circular token shapes
        (notably operative tokens).
        """

        if token_img is None or token_img.size == 0:
            return token_img

        alpha = self._load_template_alpha(template_path)
        if alpha is None:
            return token_img

        h, w = token_img.shape[:2]
        if h <= 0 or w <= 0:
            return token_img

        mask = self._best_aligned_template_mask(token_img, alpha)
        if mask is None:
            if alpha.shape[1] != w or alpha.shape[0] != h:
                alpha_resized = cv2.resize(alpha, (w, h), interpolation=cv2.INTER_LINEAR)
            else:
                alpha_resized = alpha

            if self._debug_output_dir is not None:
                self._last_cutout_debug = {
                    'method': 'naive',
                    'out_frac': None,
                    'mask_frac': None,
                }
                # Use a binary mask for visualization.
                debug_mask = (alpha_resized > 0).astype(np.uint8) * 255
                self._write_cutout_debug_overlay(token_img=token_img, mask=debug_mask, meta=self._last_cutout_debug)

            out = token_img.copy()
            out[alpha_resized == 0] = (255, 255, 255)
            return out

        if self._debug_output_dir is not None and self._last_cutout_debug is not None:
            self._write_cutout_debug_overlay(token_img=token_img, mask=mask, meta=self._last_cutout_debug)

        out = token_img.copy()
        out[mask == 0] = (255, 255, 255)
        return out

    def _resize_to_canvas(
        self,
        token_img: np.ndarray,
        *,
        canvas_w: int,
        canvas_h: int,
    ) -> np.ndarray:
        """Resize an extracted token image onto a fixed-size canvas.

        Keeps aspect ratio, centers the token, and fills the background with an estimate of
        the original background color.
        """

        if token_img is None or token_img.size == 0:
            return token_img

        h, w = token_img.shape[:2]
        if canvas_w <= 0 or canvas_h <= 0:
            return token_img

        # Estimate background from corners (deterministic).
        corner = 12
        corners = [
            token_img[:corner, :corner],
            token_img[:corner, max(0, w - corner):w],
            token_img[max(0, h - corner):h, :corner],
            token_img[max(0, h - corner):h, max(0, w - corner):w],
        ]
        bg = np.concatenate([c.reshape(-1, 3) for c in corners if c.size > 0], axis=0)
        bg_color = tuple(int(x) for x in np.mean(bg, axis=0)) if bg.size else (255, 255, 255)

        scale = min(canvas_w / max(1, w), canvas_h / max(1, h))
        new_w = max(1, int(round(w * scale)))
        new_h = max(1, int(round(h * scale)))
        resized = cv2.resize(token_img, (new_w, new_h), interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_CUBIC)

        canvas = np.full((canvas_h, canvas_w, 3), bg_color, dtype=np.uint8)
        x0 = (canvas_w - new_w) // 2
        y0 = (canvas_h - new_h) // 2
        canvas[y0:y0 + new_h, x0:x0 + new_w] = resized
        return canvas
    
    def find_marker_guide_pages(self, pdf_path: Path) -> List[int]:
        """
        Find all pages in a PDF that contain 'MARKER/TOKEN GUIDE' text.
        
        Args:
            pdf_path: Path to the PDF file
        
        Returns:
            List of page numbers (0-indexed) containing marker/token guide content
        """
        marker_pages = []
        
        try:
            doc = fitz.open(pdf_path)
            
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text").upper()
                
                # Check if this page has the marker/token guide header
                if 'MARKER' in page_text and 'TOKEN' in page_text and 'GUIDE' in page_text:
                    marker_pages.append(page_num)
            
            doc.close()
            
            # If no pages found, fall back to last page (backward compatibility)
            if not marker_pages:
                marker_pages = [len(doc) - 1] if len(doc) > 0 else []
                
        except Exception as e:
            print(f"  ⚠ Could not find marker/token guide pages: {e}")
        
        return marker_pages
    
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
                    overlap_len = max(0.0, min(x1, group_x_max) - max(x0, group_x_min))
                    group_width = max(1.0, group_x_max - group_x_min)
                    word_width = max(1.0, x1 - x0)
                    overlap_ratio = overlap_len / min(group_width, word_width)
                    x_overlap = overlap_ratio >= self.next_line_x_overlap_ratio
                    
                    # Same line with small gap = same token name
                    same_line = y_diff < self.same_line_y_max * scale_y and gap < self.text_gap_max
                    
                    # Next line with overlapping x = continuation of multi-line token name
                    # Multi-line names have y_diff of ~11 PDF units (~45px)
                    next_line_continuation = (
                        y_diff > self.next_line_y_min * scale_y
                        and y_diff < self.next_line_y_max * scale_y
                        and x_overlap
                    )
                    
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
        # Step 1 (refactor) stores PDFs under layers/kt-app/processed/; fall back to
        # the legacy root-level processed/ directory used by the warcom pipeline.
        candidate_dirs = [
            Path("layers/kt-app/processed") / team_name,
            Path("processed") / team_name,
        ]
        for processed_dir in candidate_dirs:
            if processed_dir.exists():
                pdf_files = list(processed_dir.glob(f"{team_name}-faction-rules.pdf"))
                if pdf_files:
                    return pdf_files[0]
        return None
    
    def _extract_team_from_path(self, image_path: Path) -> str:
        """Extract team name from image path or PDF path."""
        parts = image_path.parts
        
        # Check for output_v2 structure (legacy JPG images)
        if 'output_v2' in parts:
            faction_idx = parts.index('output_v2') + 1
            if faction_idx + 1 < len(parts):
                return parts[faction_idx + 1]
        
        # Check for processed structure (PDF files)
        if 'processed' in parts:
            processed_idx = parts.index('processed') + 1
            if processed_idx < len(parts):
                return parts[processed_idx]
        
        return None
    
    def find_marker_guides(self, team_name: str) -> List[Dict]:
        """Find all marker/token guide pages for a team directly from the PDF.
        
        Returns list of dicts with 'pdf_path' and 'page_num' for each marker guide page.
        """
        # Find the faction-rules PDF
        pdf_path = self.find_faction_rules_pdf(team_name)
        if not pdf_path or not pdf_path.exists():
            return []
        
        marker_pages = []
        try:
            doc = fitz.open(pdf_path)
            for page_num in range(len(doc)):
                page = doc[page_num]
                page_text = page.get_text("text").upper()
                
                # Check if this page has the marker/token guide header
                if 'MARKER' in page_text and 'TOKEN' in page_text and 'GUIDE' in page_text:
                    marker_pages.append({
                        'pdf_path': pdf_path,
                        'page_num': page_num,
                        'page_index': len(marker_pages) + 1  # 1-indexed for display
                    })
            doc.close()
        except Exception as e:
            print(f"  ⚠ Error finding marker guide pages: {e}")
        
        return marker_pages
    
    def find_marker_guide(self, team_name: str) -> Dict | None:
        """Find the first marker/token guide page for a team (backward compatibility)."""
        guides = self.find_marker_guides(team_name)
        return guides[0] if guides else None
    
    def _render_pdf_page_to_image(self, pdf_path: Path, page_num: int, dpi: int = 300) -> np.ndarray | None:
        """Render a PDF page to a high-resolution image.
        
        Args:
            pdf_path: Path to the PDF file
            page_num: Page number (0-indexed)
            dpi: Resolution for rendering (default 300 for high quality)
        
        Returns:
            Image as numpy array (BGR format) or None if failed
        """
        try:
            doc = fitz.open(pdf_path)
            if page_num >= len(doc) or page_num < 0:
                doc.close()
                return None
            
            page = doc[page_num]
            # Render at high DPI for better quality
            mat = fitz.Matrix(dpi / 72, dpi / 72)  # 72 DPI is the default
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to numpy array
            img_data = pix.samples
            img = np.frombuffer(img_data, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            
            # Convert from RGB to BGR (OpenCV format)
            if pix.n == 3:  # RGB
                img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            elif pix.n == 4:  # RGBA
                img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
            
            doc.close()
            return img
        except Exception as e:
            print(f"  ⚠ Error rendering PDF page: {e}")
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
    
    def _label_match_score(
        self,
        token_bbox: Tuple[int, int, int, int],
        label_pos: Tuple[int, int],
    ) -> float:
        """Compute a directional proximity score for matching a label to a token.

        Guides typically place labels to the right of (or sometimes below) their token.
        We use this to avoid nearby-but-wrong labels stealing a token (e.g., dense stacks).
        Lower score is better.
        """
        x, y, w, h = token_bbox
        lx, ly = label_pos

        token_center_x = x + w / 2.0
        token_center_y = y + h / 2.0
        token_left = float(x)
        token_right = float(x + w)
        token_bottom = float(y + h)

        dx = float(lx) - token_center_x
        dy = float(ly) - token_center_y
        base = float((dx * dx + dy * dy) ** 0.5)

        # Allow a little overlap / noise in PDF->image coordinate scaling.
        tol_x = max(18.0, 0.15 * float(w))
        tol_y = max(18.0, 0.15 * float(h))

        vert_aligned = abs(float(ly) - token_center_y) <= max(26.0, 0.90 * float(h))
        horiz_aligned = abs(float(lx) - token_center_x) <= max(26.0, 0.90 * float(w))

        is_to_right = float(lx) >= (token_right - tol_x)
        is_below = float(ly) >= (token_bottom - tol_y)
        is_left = float(lx) <= (token_left + tol_x)

        # Weighting:
        # - strongly prefer right-side labels when vertically aligned
        # - then below labels
        # - penalize left-side labels to prevent wrong steals
        if is_to_right and vert_aligned:
            factor = 0.65
        elif is_to_right:
            factor = 0.85
        elif is_below and horiz_aligned:
            factor = 0.90
        elif is_left:
            factor = 1.35
        else:
            factor = 1.10

        return base * factor

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
        
        best_match: str | None = None
        best_score = float('inf')

        for (name_x, name_y), name in token_names.items():
            # Keep a hard cap so we don't match across rows/sections.
            base_dx = float(name_x) - (token_bbox[0] + token_bbox[2] / 2.0)
            base_dy = float(name_y) - (token_bbox[1] + token_bbox[3] / 2.0)
            base_dist = float((base_dx * base_dx + base_dy * base_dy) ** 0.5)
            if base_dist > self.name_match_max_distance:
                continue

            score = self._label_match_score(token_bbox, (name_x, name_y))
            if score < best_score:
                best_match = name
                best_score = score

        return best_match if best_match else 'unknown'

    def match_tokens_to_names(
        self,
        token_bboxes: List[Tuple[int, int, int, int]],
        token_names: Dict[Tuple[int, int], str],
    ) -> List[str]:
        """Assign token names to tokens with a one-to-one matching.

        Prevents multiple tokens from being assigned the same label when text labels
        are dense, by assigning the globally closest pairs first.
        """
        if not token_bboxes or not token_names:
            return ['unknown' for _ in token_bboxes]

        labels = list(token_names.items())  # [((x, y), name), ...]

        token_centers: List[Tuple[int, int]] = []
        for x, y, w, h in token_bboxes:
            token_centers.append((x + w // 2, y + h // 2))

        pairs: List[Tuple[float, int, int]] = []  # (distance, token_idx, label_idx)
        for ti, (tx, ty) in enumerate(token_centers):
            for li, ((lx, ly), _) in enumerate(labels):
                base_dist = ((lx - tx) ** 2 + (ly - ty) ** 2) ** 0.5
                if base_dist > self.name_match_max_distance:
                    continue
                score = self._label_match_score(token_bboxes[ti], (lx, ly))
                pairs.append((score, ti, li))

        pairs.sort(key=lambda t: t[0])

        assigned_tokens = set()
        assigned_labels = set()
        assignment: Dict[int, int] = {}

        for dist, ti, li in pairs:
            if ti in assigned_tokens or li in assigned_labels:
                continue
            assignment[ti] = li
            assigned_tokens.add(ti)
            assigned_labels.add(li)

        names: List[str] = []
        for ti in range(len(token_bboxes)):
            li = assignment.get(ti)
            if li is None:
                names.append('unknown')
            else:
                names.append(labels[li][1])

        return names
    
    def extract_tokens_auto(self, 
                           image_path: Path | None = None,
                           pdf_page_info: Dict | None = None,
                           output_dir: Path = None,
                           debug: bool = False,
                           skip_header_percent: float = 15.0,
                           extract_names: bool = True) -> List[Dict]:
        """
        Automatically detect and extract tokens using computer vision.
        
        Args:
            image_path: Path to the marker guide image (legacy, lower quality)
            pdf_page_info: Dict with 'pdf_path' and 'page_num' to render directly from PDF
            output_dir: Directory to save extracted tokens
            debug: If True, save debug images showing detection
            skip_header_percent: Percentage of image height to skip from top (header row)
            extract_names: If True, use OCR to extract token names
        
        Returns:
            List of dicts with 'path', 'name', 'shape' info
        """
        # Enable extra cutout debug artifacts during this run.
        prev_debug_dir = self._debug_output_dir
        self._debug_output_dir = output_dir if debug else None

        # Load or render image
        if pdf_page_info:
            # Render directly from PDF at high resolution
            img = self._render_pdf_page_to_image(
                pdf_page_info['pdf_path'],
                pdf_page_info['page_num'],
                dpi=300
            )
            if img is None:
                self._debug_output_dir = prev_debug_dir
                raise ValueError(f"Could not render PDF page: {pdf_page_info}")
            # Create a pseudo path for team extraction
            image_path = pdf_page_info['pdf_path']
        elif image_path:
            # Load from pre-extracted image (legacy)
            img = cv2.imread(str(image_path))
            if img is None:
                self._debug_output_dir = prev_debug_dir
                raise ValueError(f"Could not load image: {image_path}")
        else:
            self._debug_output_dir = prev_debug_dir
            raise ValueError("Must provide either image_path or pdf_page_info")
        
        # Try to extract token names from PDF first
        token_names_ocr = {}
        if extract_names:
            # When we were given an explicit page PDF (integration layer), use it
            # directly for text extraction. Otherwise fall back to path-based PDF
            # discovery (legacy output_v2 / processed layouts).
            if pdf_page_info:
                pdf_path = pdf_page_info['pdf_path']
                team_name = self._extract_team_from_path(image_path)
            else:
                team_name = self._extract_team_from_path(image_path)
                pdf_path = self.find_faction_rules_pdf(team_name) if team_name else None
            
            # Determine which page to use
            target_page_num = pdf_page_info['page_num'] if pdf_page_info else -1
            
            if pdf_path and pdf_path.exists():
                cache_key = (str(pdf_path), f"page_{target_page_num}")
                if cache_key in self._pdf_text_cache:
                    token_names_ocr = self._pdf_text_cache[cache_key]
                else:
                    print(f"  Extracting text from PDF: {pdf_path.name}")
                    
                    if pdf_page_info:
                        # We know the exact page
                        print(f"  Using page {target_page_num + 1}")
                        # Extract text from the specific page
                        token_names_ocr = self.extract_text_from_pdf(
                            pdf_path,
                            page_num=target_page_num,
                            target_image_path=None  # We'll scale based on rendered image
                        )
                        # Scale coordinates from PDF to rendered image
                        if token_names_ocr:
                            doc = fitz.open(pdf_path)
                            page = doc[target_page_num]
                            pdf_width = page.rect.width
                            pdf_height = page.rect.height
                            doc.close()
                            
                            img_height, img_width = img.shape[:2]
                            scale_x = img_width / pdf_width
                            scale_y = img_height / pdf_height
                            
                            # Rescale all coordinates
                            scaled_names = {}
                            for (x, y), text in token_names_ocr.items():
                                scaled_x = int(x * scale_x)
                                scaled_y = int(y * scale_y)
                                scaled_names[(scaled_x, scaled_y)] = text
                            token_names_ocr = scaled_names
                        
                        self._pdf_text_cache[cache_key] = token_names_ocr
                        print(f"  Found {len(token_names_ocr)} text labels from PDF (page {target_page_num + 1})")
                    else:
                        # Legacy: try to match image to PDF page
                        marker_pages = self.find_marker_guide_pages(pdf_path)
                        print(f"  Found {len(marker_pages)} marker/token guide page(s) in PDF")
                        
                        page_num_to_use = marker_pages[0] if marker_pages else -1
                        
                        if page_num_to_use >= 0:
                            token_names_ocr = self.extract_text_from_pdf(pdf_path, page_num=page_num_to_use, target_image_path=image_path)
                            self._pdf_text_cache[cache_key] = token_names_ocr
                            print(f"  Found {len(token_names_ocr)} text labels from PDF (page {page_num_to_use + 1})")
                        else:
                            print(f"  \u26a0 Could not match image to a PDF page, falling back to OCR")
                            token_names_ocr = self.extract_token_names_from_image(image_path)
                            print(f"  Found {len(token_names_ocr)} text regions from OCR")
            else:
                # Fallback to OCR on image
                print(f"  No PDF found, using OCR on image...")
                # For OCR, we need to save the rendered image temporarily if from PDF
                if pdf_page_info and img is not None:
                    temp_img_path = output_dir / "_temp_rendered.jpg"
                    cv2.imwrite(str(temp_img_path), img)
                    token_names_ocr = self.extract_token_names_from_image(temp_img_path)
                    temp_img_path.unlink()  # Clean up
                elif image_path:
                    token_names_ocr = self.extract_token_names_from_image(image_path)
                print(f"  Found {len(token_names_ocr)} text regions from OCR")

        if extract_names and token_names_ocr:
            token_names_ocr = self._postprocess_text_labels(token_names_ocr)
        
        img_height, img_width = img.shape[:2]
        
        # Skip header row (top X% of image)
        skip_pixels = int(img_height * (skip_header_percent / 100))
        img_crop = img[skip_pixels:, :]
        
        gray = cv2.cvtColor(img_crop, cv2.COLOR_BGR2GRAY)
        
        # Apply threshold to get binary image
        _, binary = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV)

        # Repair small breaks in token silhouettes so each token becomes a single connected
        # component. Some guides have high-contrast icons that touch/interrupt the border,
        # which can split a token into multiple disjoint contours.
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=1)
        
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

        # Additional filter: remove contours that look like text rows.
        # These can otherwise get matched to the PDF label positions (which are near the text),
        # causing the exported "token" to be the label text rather than the marker graphic.
        if len(token_contours) >= 5:
            bbs = [cv2.boundingRect(c) for c in token_contours]
            hs = np.array([bb[3] for bb in bbs if bb[3] > 0], dtype=np.float32)
            areas = np.array([float(bb[2] * bb[3]) for bb in bbs if bb[2] > 0 and bb[3] > 0], dtype=np.float32)
            if hs.size >= 3 and areas.size >= 3:
                med_h = float(np.median(hs))
                med_area = float(np.median(areas))
                filtered: List[np.ndarray] = []
                for c in token_contours:
                    x0, y0, w0, h0 = cv2.boundingRect(c)
                    if w0 <= 0 or h0 <= 0:
                        continue
                    ar0 = w0 / float(h0)
                    a0 = float(w0 * h0)

                    # Text rows are typically short (relative to tokens) and wide-ish.
                    is_text_like = (
                        (h0 < (med_h * 0.62))
                        and (ar0 >= 1.25)
                        and (a0 < (med_area * 0.80))
                    )
                    if is_text_like:
                        continue
                    filtered.append(c)
                token_contours = filtered

        # Fallback: some marker guides render tokens inside two large stacked columns, causing
        # thresholding to detect only 1-2 tall "column" contours. When we have many PDF labels
        # but very few contours, split tall column bboxes into row bboxes.
        if token_contours and token_names_ocr and len(token_contours) <= 3 and len(token_names_ocr) >= 8:
            crop_h, crop_w = img_crop.shape[:2]

            def _is_tall_column_bbox(bb: Tuple[int, int, int, int]) -> bool:
                x0, y0, ww0, hh0 = bb
                if ww0 <= 0 or hh0 <= 0:
                    return False
                if hh0 < int(crop_h * 0.60):
                    return False
                aspect0 = ww0 / float(hh0)
                return aspect0 <= 0.35

            bboxes = [cv2.boundingRect(c) for c in token_contours]
            col_indices = [i for i, bb in enumerate(bboxes) if _is_tall_column_bbox(bb)]
            if col_indices:
                col_count = len(col_indices)
                # Estimate rows per column from label count. Banker's rounding makes 13/2 -> 6.
                rows_per_col = int(round(float(len(token_names_ocr)) / float(col_count)))
                rows_per_col = max(3, min(12, rows_per_col))

                def _split_bbox_into_rows(bb: Tuple[int, int, int, int], *, rows: int) -> List[np.ndarray]:
                    x0, y0, ww0, hh0 = bb
                    if rows <= 1:
                        return []
                    roi_gray = gray[y0:y0 + hh0, x0:x0 + ww0]
                    if roi_gray.size == 0:
                        return []

                    # Use vertical gradient to find horizontal boundaries.
                    g = cv2.GaussianBlur(roi_gray, (5, 5), 0)
                    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
                    proj = np.mean(np.abs(gy), axis=1)
                    # Smooth projection.
                    win = max(9, (hh0 // 80) | 1)
                    k1 = np.ones(win, dtype=np.float32) / float(win)
                    proj_s = np.convolve(proj.astype(np.float32), k1, mode='same')

                    # Candidate boundary rows: local maxima above a relative threshold.
                    thresh = float(np.max(proj_s)) * 0.35 if proj_s.size else 0.0
                    cand: List[int] = []
                    for yy in range(2, hh0 - 2):
                        v = float(proj_s[yy])
                        if v < thresh:
                            continue
                        if v >= float(proj_s[yy - 1]) and v >= float(proj_s[yy + 1]):
                            cand.append(yy)

                    # Cluster nearby candidates.
                    cand.sort()
                    clustered: List[int] = []
                    if cand:
                        cur = [cand[0]]
                        for yy in cand[1:]:
                            if yy - cur[-1] <= 6:
                                cur.append(yy)
                            else:
                                clustered.append(int(round(float(sum(cur)) / float(len(cur)))))
                                cur = [yy]
                        clustered.append(int(round(float(sum(cur)) / float(len(cur)))))

                    # Build uniform boundaries and snap to closest cluster within tolerance.
                    step = float(hh0) / float(rows)
                    tol = max(6, int(round(step * 0.18)))
                    boundaries: List[int] = [0]
                    for i in range(1, rows):
                        target = int(round(i * step))
                        best = target
                        best_d = tol + 1
                        for yy in clustered:
                            d = abs(int(yy) - target)
                            if d <= tol and d < best_d:
                                best = int(yy)
                                best_d = d
                        boundaries.append(best)
                    boundaries.append(hh0)
                    boundaries = sorted(set(max(0, min(hh0, b)) for b in boundaries))

                    # If snapping collapsed boundaries too much, fall back to strict uniform.
                    if len(boundaries) != (rows + 1):
                        boundaries = [int(round(i * step)) for i in range(rows)] + [hh0]
                        boundaries[0] = 0
                        boundaries[-1] = hh0

                    out: List[np.ndarray] = []
                    for i in range(rows):
                        y1 = int(boundaries[i])
                        y2 = int(boundaries[i + 1])
                        if y2 - y1 < max(30, int(round(step * 0.45))):
                            continue
                        # Rect contour in crop coordinates.
                        out.append(
                            np.array(
                                [
                                    [[x0, y0 + y1]],
                                    [[x0 + ww0, y0 + y1]],
                                    [[x0 + ww0, y0 + y2]],
                                    [[x0, y0 + y2]],
                                ],
                                dtype=np.int32,
                            )
                        )
                    return out

                new_contours: List[np.ndarray] = []
                for i, c in enumerate(token_contours):
                    bb = bboxes[i]
                    if i in col_indices:
                        parts = _split_bbox_into_rows(bb, rows=rows_per_col)
                        if parts:
                            new_contours.extend(parts)
                        else:
                            new_contours.append(c)
                    else:
                        new_contours.append(c)

                if len(new_contours) > len(token_contours):
                    token_contours = new_contours

        # Some tokens can be split into multiple disjoint contours (e.g., high-contrast icons
        # touching the border). Merge nearby fragments into a single contour so we extract one
        # token image per physical token.
        #
        # Important: only attempt this when there is clear evidence of fragmentation; otherwise
        # it can perturb perfectly-good contours and make name matching worse.
        if token_contours:
            bboxes0 = [cv2.boundingRect(c) for c in token_contours]
            areas0 = sorted((w * h for (_, _, w, h) in bboxes0), reverse=True)
            top_n = max(1, len(areas0) // 2)
            typical_bbox_area = float(np.median(np.array(areas0[:top_n], dtype=np.float32)))

            min_bbox_area = float(min(areas0)) if areas0 else 0.0
            should_merge_fragments = typical_bbox_area > 0 and (min_bbox_area < typical_bbox_area * 0.60)

            def _bbox_gap(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> Tuple[int, int]:
                ax, ay, aw, ah = a
                bx, by, bw, bh = b
                dx = max(0, max(ax, bx) - min(ax + aw, bx + bw))
                dy = max(0, max(ay, by) - min(ay + ah, by + bh))
                return dx, dy

            def _union_bbox(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
                ax, ay, aw, ah = a
                bx, by, bw, bh = b
                x1 = min(ax, bx)
                y1 = min(ay, by)
                x2 = max(ax + aw, bx + bw)
                y2 = max(ay + ah, by + bh)
                return (x1, y1, x2 - x1, y2 - y1)

            gap_px = 18
            merged = True
            while should_merge_fragments and merged and len(token_contours) > 1:
                merged = False
                for i in range(len(token_contours)):
                    bi = cv2.boundingRect(token_contours[i])
                    for j in range(i + 1, len(token_contours)):
                        bj = cv2.boundingRect(token_contours[j])
                        dx, dy = _bbox_gap(bi, bj)
                        if dx > gap_px or dy > gap_px:
                            continue

                        ub = _union_bbox(bi, bj)
                        ux, uy, uw, uh = ub
                        if uh <= 0:
                            continue
                        union_aspect = uw / float(uh)
                        union_area = float(uw * uh)

                        # Don't merge across separate tokens: keep unions roughly token-sized
                        # and near-square.
                        if union_aspect > max_aspect_ratio:
                            continue
                        if union_area > typical_bbox_area * 1.35:
                            continue

                        pts = np.vstack([token_contours[i], token_contours[j]])
                        token_contours[i] = cv2.convexHull(pts)
                        token_contours.pop(j)
                        merged = True
                        break
                    if merged:
                        break
        
        # Sort contours by position (top to bottom, left to right)
        token_contours = sorted(token_contours, key=lambda c: (
            cv2.boundingRect(c)[1],  # y position
            cv2.boundingRect(c)[0]   # x position
        ))

        # Pre-assign names with one-to-one matching to avoid duplicates
        token_bboxes: List[Tuple[int, int, int, int]] = []
        for contour in token_contours:
            x, y, w, h = cv2.boundingRect(contour)
            y_actual = y + skip_pixels
            token_bboxes.append((x, y_actual, w, h))

        if extract_names:
            assigned_names = self.match_tokens_to_names(token_bboxes, token_names_ocr)
        else:
            assigned_names = ['unknown' for _ in token_bboxes]

        # If we have a numbered pair of value markers (e.g., "Grudge tokens Values 1/2"),
        # but only the "Values 1" label gets assigned to an extracted contour, it's usually
        # because the physical tokens are overlapped/stacked and are not separable.
        # In that case, it's safer to skip exporting the "1" token entirely.
        skip_unpaired_values1: set[int] = set()
        if extract_names and token_names_ocr and token_bboxes and assigned_names:
            used_labels = {n for n in assigned_names if n and n.lower() != 'unknown'}

            def _parse_values_label(text: str) -> Tuple[str, str] | None:
                if not text:
                    return None
                t = ' '.join(text.split()).strip()
                m = re.match(
                    r"^(?P<base>.+?)\s+(?:tokens?|points?)\s+values?\s+(?P<digit>[12])\s*$",
                    t,
                    flags=re.IGNORECASE,
                )
                if m is None:
                    m = re.match(
                        r"^(?P<base>.+?)\s+values?\s+(?P<digit>[12])\s*$",
                        t,
                        flags=re.IGNORECASE,
                    )
                if m is None:
                    return None
                base = ' '.join((m.group('base') or '').split()).strip().lower()
                digit = m.group('digit')
                if not base:
                    return None
                return base, digit

            # Map base -> digit -> original label text
            base_to_label: Dict[str, Dict[str, str]] = {}
            for _, text in token_names_ocr.items():
                parsed = _parse_values_label(text)
                if parsed is None:
                    continue
                base, digit = parsed
                base_to_label.setdefault(base, {})[digit] = ' '.join((text or '').split()).strip()

            for base, digits in base_to_label.items():
                if '1' not in digits or '2' not in digits:
                    continue
                label1 = digits['1']
                label2 = digits['2']

                if label1 in used_labels and label2 not in used_labels:
                    for i, n in enumerate(assigned_names):
                        if n == label1:
                            skip_unpaired_values1.add(i)

        # Determine a typical output canvas size (after padding) so smaller "value" tokens
        # can be upscaled to match the rest.
        padding = 10  # Match extraction padding
        typical_canvas_w: int | None = None
        typical_canvas_h: int | None = None
        if token_bboxes and extract_names:
            cw: List[int] = []
            ch: List[int] = []
            for i, (bx, by, bw, bh) in enumerate(token_bboxes):
                name = assigned_names[i] if i < len(assigned_names) else 'unknown'
                if not name or name.lower() == 'unknown':
                    continue
                # Exclude the combined "Values 1" label itself from the typical canvas calc.
                if re.search(r"\bvalues?\s*1\b", name, flags=re.IGNORECASE):
                    continue
                # Exclude long measuring guides / templates (not normal tokens).
                if re.search(r"\btemplate\b", name, flags=re.IGNORECASE):
                    continue
                x_pad = max(0, bx - padding)
                y_pad = max(0, by - padding)
                w_pad = min(img.shape[1] - x_pad, bw + 2 * padding)
                h_pad = min(img.shape[0] - y_pad, bh + 2 * padding)
                if w_pad > 0 and h_pad > 0:
                    cw.append(int(w_pad))
                    ch.append(int(h_pad))

            if cw and ch:
                typical_canvas_w = int(np.median(np.array(cw, dtype=np.float32)))
                typical_canvas_h = int(np.median(np.array(ch, dtype=np.float32)))

        # Detect stacked/overlapped numbered duo tokens (e.g., "Grudge 1" and "Grudge 2")
        # where both labels refer to essentially the same physical token area.
        # These are not reliably separable, so prefer skipping them deterministically.
        skip_overlapped_numbered_duo: Dict[int, str] = {}
        if extract_names and token_bboxes and assigned_names:
            def _parse_numbered_suffix(name: str) -> Tuple[str, str] | None:
                if not name or name.lower() == 'unknown':
                    return None
                m = re.match(r"^(?P<base>.+?)\s+(?P<digit>[12])\s*$", name.strip())
                if m is None:
                    return None
                base = ' '.join((m.group('base') or '').split()).strip().lower()
                digit = m.group('digit')
                if not base:
                    return None
                return base, digit

            def _bbox_intersection_area(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> int:
                ax, ay, aw, ah = a
                bx, by, bw, bh = b
                x1 = max(ax, bx)
                y1 = max(ay, by)
                x2 = min(ax + aw, bx + bw)
                y2 = min(ay + ah, by + bh)
                if x2 <= x1 or y2 <= y1:
                    return 0
                return int((x2 - x1) * (y2 - y1))

            def _bbox_iou(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> float:
                ia = _bbox_intersection_area(a, b)
                if ia <= 0:
                    return 0.0
                aa = float(a[2] * a[3])
                ba = float(b[2] * b[3])
                union = aa + ba - float(ia)
                return float(ia) / union if union > 0 else 0.0

            groups: Dict[str, Dict[str, int]] = {}
            for i, bbox in enumerate(token_bboxes):
                name = assigned_names[i] if i < len(assigned_names) else 'unknown'
                parsed = _parse_numbered_suffix(name)
                if parsed is None:
                    continue
                base, digit = parsed
                if base not in groups:
                    groups[base] = {}
                # Prefer first occurrence deterministically.
                if digit not in groups[base]:
                    groups[base][digit] = i

            for base, digits in groups.items():
                if '1' not in digits or '2' not in digits:
                    continue
                i1 = digits['1']
                i2 = digits['2']
                b1 = token_bboxes[i1]
                b2 = token_bboxes[i2]
                a1 = float(b1[2] * b1[3])
                a2 = float(b2[2] * b2[3])
                if a1 <= 0 or a2 <= 0:
                    continue
                inter = _bbox_intersection_area(b1, b2)
                overlap = float(inter) / float(min(a1, a2)) if inter > 0 else 0.0
                iou = _bbox_iou(b1, b2)
                size_ratio = max(a1, a2) / min(a1, a2)

                # High overlap + similar size strongly suggests the tokens are stacked.
                if size_ratio <= 1.25 and (overlap >= 0.92 or iou >= 0.82):
                    skip_overlapped_numbered_duo[i1] = base
                    skip_overlapped_numbered_duo[i2] = base
        
        # Extract tokens
        extracted_tokens = []
        output_dir.mkdir(exist_ok=True, parents=True)

        # Track written outputs for containment-based de-duplication. Some tokens get split into
        # multiple disjoint contours, and a fragment can incorrectly get matched to a different
        # label (commonly involving "MARKERTOKEN" labels).
        kept: List[Dict] = []
        
        if debug:
            debug_img = img.copy()
        
        for idx, contour in enumerate(token_contours):
            # Get bounding box (relative to cropped image)
            x, y, w, h = cv2.boundingRect(contour)

            # Precompute contour shape signals (used to decide when to expand crops).
            _area0 = float(cv2.contourArea(contour))
            _perim0 = float(cv2.arcLength(contour, True))
            _circ0 = float((4.0 * np.pi * _area0) / (_perim0 * _perim0)) if _perim0 > 0 else 0.0
            _aspect0 = (w / float(h)) if h > 0 else 0.0
            
            # Adjust y coordinate to account for skipped header
            y_actual = y + skip_pixels
            
            # Match token to nearby text (to the right or below)
            token_name = assigned_names[idx] if idx < len(assigned_names) else 'unknown'

            # For unpaired "Values 1" tokens (where Values 2 is stacked underneath),
            # skip them - they should be manually placed in config/teams/{team}/custom-tokens/
            is_unpaired_values1 = (idx in skip_unpaired_values1 and token_name and token_name.lower() != 'unknown')
            if is_unpaired_values1:
                print(f"  ⚠ Skipping double-stacked token (add to custom-tokens/): {token_name}")
                continue
                # Continue with normal extraction using the cropped dimensions

            if idx in skip_overlapped_numbered_duo and token_name and token_name.lower() != 'unknown':
                base = skip_overlapped_numbered_duo.get(idx, '')
                base_disp = base if base else token_name
                print(f"  ⚠ Skipping overlapped numbered duo-token for now: {base_disp}")
                continue

            # Skip long measuring guides / templates for now (low value and often mis-detected).
            if token_name and token_name.lower() != 'unknown':
                if re.search(r"\btemplate\b", token_name, flags=re.IGNORECASE):
                    print(f"  ⚠ Skipping template token for now: {token_name}")
                    continue

            # Plural "tokens" labels (not Values/Points and not MARKERTOKEN) are usually
            # multi-token sheet items. Until we can reliably cut them into the true silhouettes,
            # it's safer to skip than export a visibly-wrong token.
            if token_name and token_name.lower() != 'unknown':
                if (
                    re.search(r"\btokens\b", token_name, flags=re.IGNORECASE)
                    and not re.search(r"\bmarkertoken\b", token_name, flags=re.IGNORECASE)
                    and not re.search(r"\b(values?|points?)\b", token_name, flags=re.IGNORECASE)
                ):
                    print(f"  ⚠ Skipping plural-tokens label for now: {token_name}")
                    continue

            # Wrecka-Krew: "Wrecka 2" appears as a combined/double marker on the guide.
            # Prefer skipping rather than exporting an incorrect cutout.
            if token_name and token_name.lower() != 'unknown':
                if re.fullmatch(r"\s*wrecka\s*2\s*", token_name, flags=re.IGNORECASE):
                    print(f"  ⚠ Skipping known double-token label for now: {token_name}")
                    continue

            # Add padding to ensure white background is away from image edges
            # This helps template fitting distinguish background from white token details
            padding = 10
            x_pad = max(0, x - padding)
            y_pad = max(0, y_actual - padding)
            w_pad = min(img.shape[1] - x_pad, w + 2 * padding)
            h_pad = min(img.shape[0] - y_pad, h + 2 * padding)

            # Some round tokens can have low-contrast edges (e.g., a white bottom) which causes
            # contour detection to miss part of the circle and produce a short bbox.
            # If the typical token canvas is square-ish AND we can detect a circle ring in the
            # preview crop (touching the crop edge), expand to the typical canvas to avoid
            # cutting off the token.
            if (
                typical_canvas_w is not None
                and typical_canvas_h is not None
                and token_name
                and token_name.lower() != 'unknown'
            ):
                typical_squareish = abs(int(typical_canvas_w) - int(typical_canvas_h)) <= 12
                if typical_squareish:
                    cur_aspect = (w_pad / float(h_pad)) if h_pad > 0 else 0.0
                    typical_area = float(typical_canvas_w * typical_canvas_h)
                    cur_area = float(w_pad * h_pad)
                    is_value_like = bool(re.search(r"\b(values?|points?)\b", token_name, flags=re.IGNORECASE))

                    token_img_preview = img[y_pad:y_pad+h_pad, x_pad:x_pad+w_pad]
                    circle = self._detect_round_circle(token_img_preview)

                    if (
                        (not is_value_like)
                        and (circle is not None)
                        and bool(circle.get('touches_edge'))
                        and 0.75 <= cur_aspect <= 1.35
                        and (typical_area > 0)
                        and (cur_area >= typical_area * 0.55)
                        and (h_pad < int(round(typical_canvas_h * 0.92)) or w_pad < int(round(typical_canvas_w * 0.92)))
                    ):
                        cx = x_pad + (w_pad / 2.0)
                        cy = y_pad + (h_pad / 2.0)

                        target_w = min(int(typical_canvas_w), int(img.shape[1]))
                        target_h = min(int(typical_canvas_h), int(img.shape[0]))
                        new_x = int(round(cx - target_w / 2.0))
                        new_y = int(round(cy - target_h / 2.0))
                        new_x = max(0, min(img.shape[1] - target_w, new_x))
                        new_y = max(0, min(img.shape[0] - target_h, new_y))
                        x_pad, y_pad, w_pad, h_pad = new_x, new_y, target_w, target_h

            # Drop very small contours relative to the typical token size.
            # These are usually internal graphics/noise (and tend to get misnamed by fuzzy label matching).
            if typical_canvas_w is not None and typical_canvas_h is not None:
                typical_area = float(typical_canvas_w * typical_canvas_h)
                bbox_area = float(w_pad * h_pad)

                # Allow intentionally small value/point markers through (they tend to be smaller
                # than the rest of the guide). Everything else that's far smaller than typical
                # is almost always a fragment/noise contour.
                is_value_like = bool(
                    token_name
                    and token_name.lower() != 'unknown'
                    and re.search(r"\b(values?|points?)\b", token_name, flags=re.IGNORECASE)
                )

                if (not is_value_like) and bbox_area < (typical_area * 0.45):
                    if debug:
                        try:
                            raw_path = output_dir / f"_debug_skipped_tiny_{idx:02d}.png"
                            cv2.imwrite(str(raw_path), img[y_pad:y_pad+h_pad, x_pad:x_pad+w_pad])
                        except Exception:
                            pass
                    continue

            # Extract token from original image
            token_img = img[y_pad:y_pad+h_pad, x_pad:x_pad+w_pad]

            # Skip double-detection checks if we already cropped this token via unpaired_values1 logic
            if not is_unpaired_values1:
                # Some guides include "double" markers (two tokens inside one silhouette).
                # We currently prefer skipping these rather than exporting incorrect cutouts.
                if self._looks_like_side_by_side_double(token_img):
                    if token_name and token_name.lower() != 'unknown':
                        print(f"  ⚠ Skipping side-by-side double-token for now: {token_name}")
                    else:
                        print(f"  ⚠ Skipping side-by-side double-token for now: token-{idx:02d}")
                    if debug:
                        try:
                            raw_path = output_dir / f"_debug_double_raw_{idx:02d}.png"
                            cv2.imwrite(str(raw_path), token_img)
                        except Exception:
                            pass
                    continue

                # Detect and split common "double-token" shapes (Values 1/2) into 2 outputs.
                split_imgs: List[np.ndarray] | None = None
                if token_name and token_name.lower() != 'unknown':
                    # We only split on the "Values 1" label. For the partner token ("Values 2")
                    # we prefer to keep one-to-one matching and just normalize its naming.
                    is_values_1 = bool(re.search(r"\bvalues?\s*1\b", token_name, flags=re.IGNORECASE))
                    if is_values_1:
                        split_imgs = self._split_double_token_image(token_img)

                if split_imgs is not None:
                    # If we get here, CV found a single contour that likely contains 2 adjacent tokens.
                    # Until we can reliably cut these to the true token silhouette, it's safer to skip.
                    print(f"  ⚠ Skipping merged double-token for now: {token_name}")
                    if debug:
                        try:
                            raw_path = output_dir / f"_debug_split_raw_{idx:02d}.png"
                            cv2.imwrite(str(raw_path), token_img)
                        except Exception:
                            pass
                    continue

                # (The old single-half export logic has been replaced by the guarded two-half export above.)
            
            # Clean up name for filename
            if token_name and token_name != 'unknown':
                # Normalize "<base> (tokens/points) Values N" into "<base> N" / base_N.
                # This fixes common two-token value markers (e.g., Crossfire 1/2, Grudge 1/2).
                m = re.search(
                    r"^(?P<base>.+?)\s+(?:tokens?|points?)\s+values?\s+(?P<digit>\d+)\s*$",
                    token_name,
                    flags=re.IGNORECASE,
                )
                if m is None:
                    m = re.search(
                        r"^(?P<base>.+?)\s+values?\s+(?P<digit>\d+)\s*$",
                        token_name,
                        flags=re.IGNORECASE,
                    )

                if m is not None:
                    base_display = ' '.join(m.group('base').split()).strip()
                    digit = m.group('digit')
                    token_name = f"{base_display} {digit}".strip()

                    base_safe = re.sub(r'[^a-z0-9\-]', '-', base_display.lower())
                    base_safe = re.sub(r'-+', '-', base_safe).strip('-')
                    base_safe = base_safe.replace('-', '_')
                    safe_name = f"{base_safe}_{digit}" if base_safe else f"token-{idx:02d}"
                else:
                    safe_name = re.sub(r'[^a-z0-9\-]', '-', token_name.lower())
                    safe_name = re.sub(r'-+', '-', safe_name).strip('-')
            else:
                safe_name = f"token-{idx:02d}"

            # Wrecka-Krew: the item labeled "Wrecka 2" is a combined/double marker on the guide.
            # Skip it rather than exporting an incorrect cutout.
            if token_name and token_name.lower() != 'unknown' and safe_name == 'wrecka_2':
                print(f"  ⚠ Skipping known double-token for now: {token_name}")
                continue
            
            # Calculate shape metrics (needed for metadata)
            area = cv2.contourArea(contour)
            perimeter = cv2.arcLength(contour, True)
            circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
            aspect_ratio = w / h if h > 0 else 0
            
            # Determine shape - first check team config, then fall back to detection
            team_name = self._extract_team_from_path(image_path)
            shape = None
            
            if team_name and token_name and token_name.lower() != 'unknown':
                shape = self._get_token_shape_from_config(team_name, token_name)
            
            # Fall back to shape detection if not configured
            if shape is None:
                # Check for circle/round tokens FIRST
                # Round tokens have very high circularity (>= 0.87) and are roughly square
                # For near-square crops, try explicit circle-ring detection
                ring_conf = None
                if (w_pad >= 60 and h_pad >= 60) and (0.85 <= (w_pad / float(h_pad) if h_pad > 0 else 0.0) <= 1.15):
                    ring_conf = self._infer_round_marker_from_image(token_img)

                if ring_conf is not None and float(ring_conf) >= 0.35 and 0.90 <= aspect_ratio <= 1.10:
                    shape = "round"
                elif circularity >= 0.87 and 0.90 <= aspect_ratio <= 1.10:
                    # High circularity indicates round token
                    # This catches most circles before octagon detection
                    shape = "round"
                # Check for octagon tokens (8 sides with distinct flat edges, circularity 0.88-0.93)
                elif self._detect_octagon(contour, token_img):
                    shape = "octagon"
                # Check for diamond tokens (square rotated 45 degrees)
                elif self._detect_diamond(contour, token_img):
                    shape = "diamond"
                # Default to operative (rectangular/complex shape)
                else:
                    shape = "operative"

            # If this contour is largely contained within an already-extracted token, it's
            # usually a fragment (e.g., a high-contrast icon touching the border). Prefer keeping
            # the larger token and, when the larger token is a generic "MARKERTOKEN", rename it
            # to the more specific label.
            def _is_markertoken_label(name: str) -> bool:
                return bool(name) and bool(re.search(r"\bmarkertoken\b", name, flags=re.IGNORECASE))

            def _bbox_intersection_area(a: Tuple[int, int, int, int], b: Tuple[int, int, int, int]) -> int:
                ax, ay, aw, ah = a
                bx, by, bw, bh = b
                x1 = max(ax, bx)
                y1 = max(ay, by)
                x2 = min(ax + aw, bx + bw)
                y2 = min(ay + ah, by + bh)
                if x2 <= x1 or y2 <= y1:
                    return 0
                return int((x2 - x1) * (y2 - y1))

            cur_bbox = (int(x_pad), int(y_pad), int(w_pad), int(h_pad))
            cur_area = cur_bbox[2] * cur_bbox[3]
            cur_is_marker = _is_markertoken_label(token_name)

            should_skip_current = False
            if cur_area > 0:
                for prev in kept:
                    prev_bbox = prev['bbox']
                    prev_area = int(prev_bbox[2] * prev_bbox[3])
                    if prev_area <= 0:
                        continue
                    inter = _bbox_intersection_area(cur_bbox, prev_bbox)
                    if inter <= 0:
                        continue

                    containment = inter / float(min(prev_area, cur_area))
                    size_ratio = max(prev_area, cur_area) / float(min(prev_area, cur_area))

                    if containment >= 0.85 and size_ratio >= 1.5:
                        prev_name = prev['token_info'].get('name') or ''
                        prev_is_marker = _is_markertoken_label(prev_name)

                        # Prefer the larger token, but upgrade its label if it was a generic MARKERTOKEN.
                        if prev_area >= cur_area:
                            if prev_is_marker and (not cur_is_marker) and token_name.lower() != 'unknown':
                                # Rename previously written file and update metadata in-place.
                                new_safe_name = safe_name
                                new_path = output_dir / f"{new_safe_name}.png"
                                old_path: Path = prev['token_info']['path']
                                if new_path != old_path:
                                    try:
                                        os.replace(str(old_path), str(new_path))
                                    except Exception:
                                        # If rename fails, keep the old file rather than failing extraction.
                                        new_path = old_path
                                        new_safe_name = prev['token_info'].get('safe_name', new_safe_name)

                                prev['token_info']['path'] = new_path
                                prev['token_info']['name'] = token_name
                                prev['token_info']['safe_name'] = new_safe_name
                            should_skip_current = True
                            break
                        else:
                            # Current is the larger token. If its label is MARKERTOKEN and the contained
                            # smaller token has a more specific name, prefer the specific name.
                            if cur_is_marker and (not prev_is_marker) and prev_name.lower() != 'unknown':
                                token_name = prev_name
                                safe_name = prev['token_info'].get('safe_name', safe_name)
                            # Either way, skip writing the smaller, contained previous output.
                            try:
                                old_path: Path = prev['token_info']['path']
                                if old_path.exists():
                                    old_path.unlink()
                            except Exception:
                                pass
                            if prev['token_info'] in extracted_tokens:
                                extracted_tokens.remove(prev['token_info'])
                            kept.remove(prev)
                        break

            if should_skip_current:
                continue
            
            # Equalize background to white
            # Many token guides have grey/off-white backgrounds that need to be normalized
            token_img = self._normalize_background_to_white(token_img)
            
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
            kept.append({'bbox': cur_bbox, 'token_info': token_info})
            
            if debug:
                cv2.rectangle(debug_img, (x, y_actual), (x+w, y_actual+h), (0, 255, 0), 2)
                label = f"{safe_name[:15]}" if token_name != 'unknown' else str(idx)
                cv2.putText(debug_img, label, (x, y_actual-5), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1)
            
            
            print(f"  ✓ Extracted: {token_name} ({shape}) -> {output_path.name}")

        # Draw OCR text positions (once)
        if debug and token_names_ocr:
            for (text_x, text_y), text in token_names_ocr.items():
                cv2.circle(debug_img, (text_x, text_y), 5, (255, 0, 0), -1)
                cv2.putText(debug_img, text[:20], (text_x + 10, text_y),
                          cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
        
        if debug:
            # Draw line showing header skip region
            cv2.line(debug_img, (0, skip_pixels), (img_width, skip_pixels), (0, 0, 255), 2)
            cv2.putText(debug_img, "Header (ignored)", (10, skip_pixels - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 2)
            
            debug_path = output_dir / "_debug_detection.png"
            cv2.imwrite(str(debug_path), debug_img)
            print(f"  ℹ Debug image saved: {debug_path}")

        # Always restore debug dir, even on successful return.
        self._debug_output_dir = prev_debug_dir
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
    
    def process_team(self, team_name: str, method: str = 'auto', debug: bool = False, clean: bool = False) -> bool:
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
        marker_guide_info = self.find_marker_guide(team_name)
        if not marker_guide_info:
            print(f"  ✗ No marker/token guide found for {team_name}")
            return False
        
        print(f"  Found marker guide: PDF page {marker_guide_info['page_num'] + 1}")
        
        # Create output directory
        output_dir = self.output_base_dir / team_name / "token"
        if clean and output_dir.exists():
            shutil.rmtree(output_dir)

        extracted = self._process_team_to_dir(team_name, marker_guide_info, output_dir, method=method, debug=debug)
        if extracted is None:
            return False

        print(f"  ✓ Extracted {len(extracted)} tokens")
        return True

    def process_team_auto_tuned(
        self,
        team_name: str,
        *,
        method: str = 'auto',
        debug: bool = False,
        clean: bool = False,
        expected_token_count: int | None = None,
    ) -> bool:
        """Process a team with always-on auto-tuning.

        This pipeline is intended to be deterministic: we always run the same small
        parameter sweep and choose the best result using generic quality signals.
        """

        print(f"\n{'='*60}")
        print(f"Processing: {team_name}")
        print(f"{'='*60}")

        # Find all marker guide pages directly from PDF
        marker_guide_pages = self.find_marker_guides(team_name)
        if not marker_guide_pages:
            print(f"  ✗ No marker/token guide pages found in PDF for {team_name}")
            return False

        print(f"  Found {len(marker_guide_pages)} marker guide page(s) in PDF")
        for page_info in marker_guide_pages:
            print(f"    Page {page_info['page_index']}: PDF page {page_info['page_num'] + 1}")

        output_dir = self.output_base_dir / team_name / "token"
        if clean and output_dir.exists():
            shutil.rmtree(output_dir)

        # Process each marker guide page with auto-tuning
        all_best_metrics = []
        for page_info in marker_guide_pages:
            page_idx = page_info['page_index']
            print(f"\n  Processing page {page_idx}/{len(marker_guide_pages)}: PDF page {page_info['page_num'] + 1}")
            
            # Auto-tune sweep for this page
            best = self._auto_tune_team(
                team_name,
                page_info,  # Pass page info instead of image path
                method=method,
                debug=debug,
                expected_token_count=expected_token_count,
            )

            if best is None:
                print(f"    \u26a0 Failed to extract tokens from page {page_idx}")
                continue

            best_dir, best_metrics = best
            all_best_metrics.append(best_metrics)
            
            # Move extracted tokens from best tuning run to final output
            # For the first page, move the entire directory; for subsequent pages, merge
            if page_idx == 1:
                if output_dir.exists():
                    shutil.rmtree(output_dir)
                shutil.move(str(best_dir), str(output_dir))
            else:
                # Merge tokens from this page into the main output directory
                output_dir.mkdir(exist_ok=True, parents=True)
                for token_file in best_dir.glob("*.png"):
                    # Skip debug files
                    if token_file.name.startswith("_debug"):
                        continue
                    dest = output_dir / token_file.name
                    # If duplicate filename, append page number
                    if dest.exists():
                        stem = token_file.stem
                        dest = output_dir / f"{stem}_page{page_idx}.png"
                    shutil.copy2(token_file, dest)
                
                # Merge metadata
                metadata_src = best_dir / 'extraction-metadata.json'
                metadata_dst = output_dir / 'extraction-metadata.json'
                if metadata_src.exists() and metadata_dst.exists():
                    with open(metadata_dst, 'r', encoding='utf-8') as f:
                        metadata_main = json.load(f)
                    with open(metadata_src, 'r', encoding='utf-8') as f:
                        metadata_page = json.load(f)
                    # Append tokens from this page
                    metadata_main['tokens'].extend(metadata_page.get('tokens', []))
                    metadata_main['tokens_extracted'] = len(metadata_main['tokens'])
                    with open(metadata_dst, 'w', encoding='utf-8') as f:
                        json.dump(metadata_main, f, indent=2)
            
            print(
                f"    ✓ Extracted {best_metrics['tokens_extracted']} tokens from page {page_idx} (auto-tuned; unknown={best_metrics['unknown_count']}, numeric={best_metrics['numeric_only_count']})"
            )

        # Clean up global tuning temp (kept outside output_dir)
        tuning_root = self.output_base_dir / "_tuning" / team_name
        shutil.rmtree(tuning_root, ignore_errors=True)

        if not all_best_metrics:
            print(f"  ✗ No tokens extracted")
            return False
        
        total_tokens = sum(m['tokens_extracted'] for m in all_best_metrics)
        total_unknown = sum(m['unknown_count'] for m in all_best_metrics)
        total_numeric = sum(m['numeric_only_count'] for m in all_best_metrics)
        
        print(f"\n  ✓ Total: {total_tokens} tokens extracted across {len(marker_guide_pages)} page(s) (unknown={total_unknown}, numeric={total_numeric})")
        return True

    def _process_team_to_dir(
        self,
        team_name: str,
        marker_guide_info: Dict,  # Changed from marker_guide_path
        output_dir: Path,
        *,
        method: str,
        debug: bool,
    ) -> List[Dict] | None:
        output_dir.mkdir(exist_ok=True, parents=True)

        if method != 'auto':
            print(f"  ✗ Manual extraction not implemented")
            return None

        # Extract using PDF page info for high quality
        extracted = self.extract_tokens_auto(
            pdf_page_info=marker_guide_info,
            output_dir=output_dir,
            debug=debug
        )

        # Drop auto-extracted tokens explicitly listed in config `exclude_tokens`.
        # (Used to suppress blank misdetections and originals being replaced by
        # custom-token variants.) Custom tokens copied below are unaffected.
        excluded = self._get_excluded_tokens(team_name)
        if excluded:
            survivors: List[Dict] = []
            for tok in extracted:
                safe = ' '.join((tok.get('safe_name') or '').lower().split())
                name = ' '.join((tok.get('name') or '').lower().split())
                if safe in excluded or name in excluded:
                    tok_path = tok.get('path')
                    try:
                        if isinstance(tok_path, Path) and tok_path.exists():
                            tok_path.unlink()
                    except Exception:
                        pass
                    print(f"  ⚠ Excluded token (config exclude_tokens): {tok.get('safe_name') or name}")
                    continue
                survivors.append(tok)
            extracted = survivors

        # Copy custom tokens from config/teams/{team}/custom-tokens/
        custom_tokens_dir = Path(f"config/teams/{team_name}/custom-tokens")
        custom_base_names: set[str] = set()
        # Custom tokens are team-level, not page-level: only apply them on the first
        # token-guide page so multi-page teams don't get duplicate `_pageN` copies.
        if marker_guide_info.get('page_index', 1) == 1 and custom_tokens_dir.exists():
            for custom_token_path in custom_tokens_dir.glob("*.png"):
                if custom_token_path.name.startswith("_"):
                    continue
                
                # Strip team name prefix if present (e.g., "hearthkyn-salvagers-grudge.png" -> "grudge.png")
                filename = custom_token_path.name
                team_prefix = f"{team_name}-"
                if filename.startswith(team_prefix):
                    filename = filename[len(team_prefix):]

                base_safe = filename[:-4] if filename.lower().endswith('.png') else filename
                custom_base_names.add(base_safe)

                # Drop any auto-extracted siblings that share this custom base, including
                # numeric-suffixed misdetections like "pain_2". The custom token is
                # authoritative; mistaken duplicates from the marker guide should not survive.
                survivors: List[Dict] = []
                for tok in extracted:
                    tok_safe = tok.get('safe_name') or tok.get('path', Path('')).stem
                    if tok_safe == base_safe or re.fullmatch(rf"{re.escape(base_safe)}_\d+", tok_safe or ''):
                        try:
                            tok_path = tok.get('path')
                            if isinstance(tok_path, Path) and tok_path.exists() and tok_path != (output_dir / filename):
                                tok_path.unlink()
                        except Exception:
                            pass
                        continue
                    survivors.append(tok)
                extracted = survivors

                dest_path = output_dir / filename
                shutil.copy2(custom_token_path, dest_path)
                
                # Add to extracted list
                # Try to infer shape from filename (operative vs round)
                token_lower = filename.lower()
                if any(x in token_lower for x in ['defence', 'attack', 'round', 'point', 'objective']):
                    shape = 'round'
                else:
                    shape = 'operative'
                
                # Read image dimensions
                import cv2
                img = cv2.imread(str(custom_token_path))
                h, w = img.shape[:2] if img is not None else (0, 0)
                
                token_name = filename.replace(".png", "").replace("_", " ").title()
                
                extracted.append({
                    'path': dest_path,
                    'name': token_name,
                    'safe_name': filename.replace(".png", ""),
                    'shape': shape,
                    'dimensions': {'width': w, 'height': h},
                    'circularity': 0.0,
                    'source': 'custom'
                })
                
                print(f"  ✓ Added custom token: {filename}")

        # Save metadata
        metadata = {
            'team': team_name,
            'source_pdf': str(marker_guide_info['pdf_path']),
            'source_page': marker_guide_info['page_num'] + 1,  # 1-indexed for display
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
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2)

        print(f"  ✓ Metadata saved: {metadata_path}")
        return extracted

    def _compute_quality_metrics(self, extracted: List[Dict], *, expected_token_count: int | None) -> Dict[str, int]:
        filenames = [t['path'].name for t in extracted]
        names = [(t.get('name') or '').strip() for t in extracted]

        unknown_count = sum(1 for n in names if n.lower() == 'unknown')
        # Heuristic: names that are just digits or single-character are usually "split" labels
        numeric_only_count = sum(1 for n in names if n.isdigit() or len(n) <= 1)
        duplicate_filenames = len(filenames) - len(set(filenames))

        tokens_extracted = len(extracted)
        expected_mismatch = 0
        if expected_token_count is not None:
            expected_mismatch = abs(tokens_extracted - expected_token_count)

        return {
            'tokens_extracted': tokens_extracted,
            'unknown_count': unknown_count,
            'numeric_only_count': numeric_only_count,
            'duplicate_filenames': duplicate_filenames,
            'expected_mismatch': expected_mismatch,
        }

    def _needs_tuning(self, metrics: Dict[str, int]) -> bool:
        if metrics['duplicate_filenames'] > 0:
            return True
        if metrics['unknown_count'] > 0:
            return True
        if metrics['numeric_only_count'] > 0:
            return True
        if metrics['expected_mismatch'] > 0:
            return True
        return False

    def _auto_tune_team(
        self,
        team_name: str,
        marker_guide_info: Dict,  # Changed from marker_guide_path
        *,
        method: str,
        debug: bool,
        expected_token_count: int | None,
    ) -> tuple[Path, Dict[str, int]] | None:
        # Keep tuning runs OUTSIDE the final output folder so we can safely
        # delete/replace output_dir without deleting our best candidate.
        tuning_root = (self.output_base_dir / "_tuning" / team_name)
        shutil.rmtree(tuning_root, ignore_errors=True)
        tuning_root.mkdir(parents=True, exist_ok=True)

        original = {
            'text_gap_max': self.text_gap_max,
            'name_match_max_distance': self.name_match_max_distance,
        }

        # Deterministic candidate order. Start with current defaults so most teams
        # short-circuit immediately.
        candidates: list[tuple[float, float]] = [
            (6.0, 300.0),
            (6.0, 450.0),
            (4.0, 300.0),
            (4.0, 450.0),
            (8.0, 300.0),
            (8.0, 450.0),
        ]

        best_dir: Path | None = None
        best_metrics: Dict[str, int] | None = None
        best_score: float | None = None

        for i, (gap, dist) in enumerate(candidates, start=1):
            self.text_gap_max = gap
            self.name_match_max_distance = dist

            out_dir = tuning_root / f"run_{i:02d}_gap{gap:g}_dist{dist:g}"
            started = time.time()
            extracted = self._process_team_to_dir(team_name, marker_guide_info, out_dir, method=method, debug=debug)
            if extracted is None:
                continue

            metrics = self._compute_quality_metrics(extracted, expected_token_count=expected_token_count)
            duration = time.time() - started

            # If it's perfect, stop early (saves ~5 extra passes for most teams).
            if not self._needs_tuning(metrics):
                best_dir = out_dir
                best_metrics = metrics
                best_score = float('inf')
                break

            # Score: prioritize getting rid of unknowns/splits; avoid duplicates; then match expected count if provided.
            score = (
                (metrics['tokens_extracted'] * 10)
                - (metrics['unknown_count'] * 40)
                - (metrics['numeric_only_count'] * 10)
                - (metrics['duplicate_filenames'] * 100)
                - (metrics['expected_mismatch'] * 5)
                - (duration * 0.1)
            )

            if best_score is None or score > best_score:
                best_score = score
                best_dir = out_dir
                best_metrics = metrics

        # Restore
        self.text_gap_max = original['text_gap_max']
        self.name_match_max_distance = original['name_match_max_distance']

        if best_dir is None or best_metrics is None:
            return None

        return best_dir, best_metrics


def main():
    parser = argparse.ArgumentParser(description='Extract tokens from marker/token guides')
    parser.add_argument('--team', type=str, help='Team name (e.g., farstalker-kinband)')
    parser.add_argument('--all', action='store_true', help='Process all teams')
    parser.add_argument('--method', choices=['auto'], default='auto',
                       help='Extraction method (default: auto)')
    parser.add_argument('--debug', action='store_true', help='Save debug images')
    parser.add_argument('--clean', action='store_true', help='Delete existing extracted tokens for the team(s) before extracting')
    parser.add_argument('--output-dir', type=str, default='processed',
                       help='Output directory for extracted tokens (tokens go in {output-dir}/{team}/token/)')
    parser.add_argument('--text-gap-max', type=float, default=6.0,
                       help='Max horizontal gap (PDF units) to group words on the same label line (default: 6.0)')
    parser.add_argument('--same-line-y-max', type=float, default=15.0,
                       help='Max vertical delta (scaled) to consider words on the same line (default: 15.0)')
    parser.add_argument('--next-line-y-min', type=float, default=5.0,
                       help='Min vertical delta (scaled) to consider next-line continuation (default: 5.0)')
    parser.add_argument('--next-line-y-max', type=float, default=25.0,
                       help='Max vertical delta (scaled) to consider next-line continuation (default: 25.0)')
    parser.add_argument('--next-line-x-overlap-ratio', type=float, default=0.25,
                       help='Min x-overlap ratio to treat word as continuation on next line (default: 0.25)')
    parser.add_argument('--name-match-max-distance', type=float, default=300.0,
                       help='Max pixel distance between token center and label point (default: 300)')
    
    args = parser.parse_args()
    
    if not args.team and not args.all:
        parser.error('Must specify --team or --all')
    
    # Setup
    output_base = Path(args.output_dir)
    extractor = TokenExtractor(
        output_base,
        text_gap_max=args.text_gap_max,
        same_line_y_max=args.same_line_y_max,
        next_line_y_min=args.next_line_y_min,
        next_line_y_max=args.next_line_y_max,
        next_line_x_overlap_ratio=args.next_line_x_overlap_ratio,
        name_match_max_distance=args.name_match_max_distance,
    )
    
    if args.team:
        # Process single team
        success = extractor.process_team_auto_tuned(
            args.team,
            method=args.method,
            debug=args.debug,
            clean=args.clean,
            expected_token_count=None,
        )
        if not success:
            exit(1)
    
    elif args.all:
        # Find all teams with marker guides
        print("Searching for teams with marker/token guides...")
        teams = []
        
        # Load team config for tokens_ready check
        config_path = Path('config/team-config.yaml')
        all_teams_config = {}
        if config_path.exists():
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
                all_teams_config = data.get('teams', {}) if data else {}
        
        skipped_locked = []
        for faction_dir in Path("output_v2").iterdir():
            if faction_dir.is_dir():
                for team_dir in faction_dir.iterdir():
                    if team_dir.is_dir():
                        faction_rules = team_dir / "faction-rules"
                        if faction_rules.exists():
                            marker_files = list(faction_rules.glob("*markertoken-guide*_front.jpg"))
                            if marker_files:
                                team_slug = team_dir.name
                                team_cfg = all_teams_config.get(team_slug, {})
                                if team_cfg.get('tokens_ready', False):
                                    skipped_locked.append(team_slug)
                                else:
                                    teams.append(team_slug)
        
        print(f"Found {len(teams)} teams with marker guides")
        if skipped_locked:
            print(f"Skipped {len(skipped_locked)} locked teams (tokens_ready=true): {', '.join(sorted(skipped_locked))}")
        
        # Process each team
        success_count = 0
        for team in sorted(teams):
            if extractor.process_team_auto_tuned(
                team,
                method=args.method,
                debug=args.debug,
                clean=args.clean,
                expected_token_count=None,
            ):
                success_count += 1
        
        print(f"\n{'='*60}")
        print(f"Summary: {success_count}/{len(teams)} teams processed successfully")
        print(f"{'='*60}")
    
    print(f"\n✓ Token extraction complete!")
    print(f"  Output directory: {output_base.absolute()}")


if __name__ == '__main__':
    main()
