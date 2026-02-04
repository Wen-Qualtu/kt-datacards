"""Background-sample-based token transparency (experimental).

This script replaces the older two-pass transparency helpers.

Goal
- Use a screenshot / crop of the *card background* (like the one you shared) to learn the
  exact light/dark grey tones.
- Key those tones to transparent on extracted token PNGs.
- Only remove background that is connected to the image border (prevents punching holes in
  interior artwork that happens to be similar grey).

Usage
    # 1) Save your background screenshot somewhere in the repo, e.g.:
    #    config/defaults/tts-token/token-bg-sample.png
  # 2) Run:
    poetry run python script/tools/add_token_transparency_bg_sample.py \
    --team farstalker-kinband \
        --bg-sample config/defaults/tts-token/token-bg-sample.png \
    --threshold 18

Notes
- Deterministic (k-means uses a fixed RNG seed).
- Overwrites token PNGs in-place (adds/overwrites alpha).
- Skips files starting with '_' (debug artifacts).
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable
from typing import Sequence

import cv2
import numpy as np
import yaml


def _ensure_bgr_alpha(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return BGR + alpha (alpha defaults to 255 if missing)."""
    bgr, alpha = _ensure_bgr(img)
    if alpha is None:
        alpha = np.full(bgr.shape[:2], 255, dtype=np.uint8)
    return bgr, alpha


def _mask_fill_holes(mask: np.ndarray) -> np.ndarray:
    m = (mask > 0).astype(np.uint8)
    h, w = m.shape[:2]
    if h <= 1 or w <= 1:
        return m

    inv = (m == 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(inv, connectivity=8)
    if n <= 1:
        return m

    border_labels: set[int] = set()
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


def _mask_keep_components(mask: np.ndarray, *, min_area: int, min_rel: float) -> np.ndarray:
    m = (mask > 0).astype(np.uint8)
    n, labels, stats, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    if n <= 1:
        return m

    areas = stats[1:, cv2.CC_STAT_AREA].astype(np.int64)
    if areas.size == 0:
        return m
    max_area = int(np.max(areas))
    abs_thr = int(max(1, min_area))
    rel_thr = int(max(1, round(max_area * float(max(0.0, min_rel)))))
    thr = int(max(abs_thr, rel_thr))

    keep = np.zeros(n, dtype=bool)
    for i in range(1, n):
        if int(stats[i, cv2.CC_STAT_AREA]) >= thr:
            keep[i] = True
    return np.isin(labels, np.where(keep)[0]).astype(np.uint8)


def _mask_bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    x0 = int(xs.min())
    x1 = int(xs.max())
    y0 = int(ys.min())
    y1 = int(ys.max())
    return x0, y0, (x1 - x0 + 1), (y1 - y0 + 1)


def _mask_centroid(mask: np.ndarray) -> tuple[float, float] | None:
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return None
    return float(xs.mean()), float(ys.mean())


def _load_template_mask(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to read template: {path}")
    _bgr, alpha = _ensure_bgr_alpha(img)
    m = (alpha > 0).astype(np.uint8)
    m = _mask_fill_holes(m)
    # Mild close for a smooth template edge.
    el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    m = cv2.morphologyEx(m, cv2.MORPH_CLOSE, el, iterations=1)
    m = _mask_fill_holes(m)
    return m


def _apply_inset_to_mask(mask: np.ndarray, *, scale: float) -> np.ndarray:
    if mask is None or mask.size == 0:
        return mask
    s = float(scale)
    if s >= 1.0:
        return mask
    h, w = mask.shape[:2]
    nh = max(3, int(round(h * s)))
    nw = max(3, int(round(w * s)))
    if nh >= h or nw >= w:
        return mask
    bin_mask = (mask > 0).astype(np.uint8)
    scaled = cv2.resize(bin_mask, (nw, nh), interpolation=cv2.INTER_NEAREST)
    inset = np.zeros_like(bin_mask, dtype=np.uint8)
    y0 = (h - nh) // 2
    x0 = (w - nw) // 2
    inset[y0 : y0 + nh, x0 : x0 + nw] = scaled
    return inset


def _fit_template_mask(
    *,
    cand: np.ndarray,
    templ: np.ndarray,
    scale_band: float,
    scale_steps: int,
    shift: int,
    shift_step: int,
) -> tuple[np.ndarray, dict] | tuple[None, None]:
    h, w = cand.shape
    cand_area = int((cand > 0).sum())
    if cand_area <= 0:
        return None, None

    bb = _mask_bbox(cand)
    cb = _mask_centroid(cand)
    if bb is not None:
        bx, by, bw, bh = bb
        cx0 = float(bx + bw / 2)
        cy0 = float(by + bh / 2)
    else:
        cx0 = float(w / 2)
        cy0 = float(h / 2)
    if cb is not None and not (cb[0] == 0.0 and cb[1] == 0.0):
        cx, cy = cb
    else:
        cx, cy = cx0, cy0

    templ_area = int((templ > 0).sum())
    if templ_area <= 0:
        return None, None

    # Blend area-scale with bbox-scale (more stable for split masks).
    area_scale = float(np.sqrt(cand_area / templ_area))
    tb = _mask_bbox(templ)
    if bb is not None and tb is not None:
        _tx, _ty, tw, th = tb
        _bx, _by, bw, bh = bb
        ws = float(bw / max(1, tw))
        hs = float(bh / max(1, th))
        bbox_scale = float((ws + hs) / 2.0)
        base_scale = float(0.55 * bbox_scale + 0.45 * area_scale)
    else:
        base_scale = area_scale
    
    # Scale template DOWN by 5% to ensure it fits inside the content without capturing white edges
    base_scale = base_scale * 0.95
    base_scale = float(np.clip(base_scale, 0.4, 2.2))

    scale_band = float(max(0.0, scale_band))
    steps = int(max(1, scale_steps))
    if steps == 1 or scale_band == 0:
        scales = [base_scale]
    else:
        lo = base_scale * (1.0 - scale_band)
        hi = base_scale * (1.0 + scale_band)
        scales = list(np.linspace(lo, hi, steps).astype(np.float32))

    best = None
    best_mask = None
    cand_area_f = float(cand_area)

    for sc in scales:
        th, tw = templ.shape
        nh = int(max(5, round(th * float(sc))))
        nw = int(max(5, round(tw * float(sc))))
        if nh >= h * 2 or nw >= w * 2:
            continue

        resized = cv2.resize((templ > 0).astype(np.uint8), (nw, nh), interpolation=cv2.INTER_NEAREST)

        for dy in range(-shift, shift + 1, shift_step):
            for dx in range(-shift, shift + 1, shift_step):
                x0 = int(round(cx - (nw / 2) + dx))
                y0 = int(round(cy - (nh / 2) + dy))

                tx0 = 0
                ty0 = 0
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

                templ_roi = resized[ty0 : ty0 + rh, tx0 : tx0 + rw]
                if templ_roi.size == 0:
                    continue

                cand_roi = (cand[y0:y1, x0:x1] > 0)
                templ_roi_b = templ_roi > 0

                inter = int(np.logical_and(cand_roi, templ_roi_b).sum())
                templ_area_eff = int(templ_roi_b.sum())
                union = int(cand_area + templ_area_eff - inter)
                if union <= 0 or templ_area_eff <= 0:
                    continue

                iou = float(inter / union)
                coverage = float(inter / templ_area_eff)
                recall = float(inter / cand_area_f)

                if best is None:
                    better = True
                else:
                    better = bool(
                        (iou > best["iou"] + 1e-9)
                        or (abs(iou - best["iou"]) < 1e-9 and coverage > best["coverage"] + 1e-9)
                        or (
                            abs(iou - best["iou"]) < 1e-9
                            and abs(coverage - best["coverage"]) < 1e-9
                            and recall > best["recall"] + 1e-9
                        )
                    )

                if better:
                    best = {
                        "iou": iou,
                        "coverage": coverage,
                        "recall": recall,
                        "scale": float(sc),
                        "dx": int(dx),
                        "dy": int(dy),
                        "x0": int(x0),
                        "y0": int(y0),
                        "w": int(rw),
                        "h": int(rh),
                    }
                    placed = np.zeros((h, w), dtype=np.uint8)
                    placed[y0:y1, x0:x1] = templ_roi_b.astype(np.uint8)
                    best_mask = placed

    if best is None or best_mask is None:
        return None, None
    return best_mask, best


def _fill_transparent_holes_within_template(
    alpha: np.ndarray,
    template_mask: np.ndarray,
    *,
    min_interior_dist: int = 3,
) -> np.ndarray:
    """Fill transparent regions enclosed by the template boundary.

        Heuristic:
        - If a transparent component has pixels at least `min_interior_dist` away from the
            boundary (distance-to-outside), we fill it.

        This fixes cases where an interior icon/panel got keyed out and the resulting hole is
        connected to the edge by a 1px “channel”, which would otherwise prevent hole filling.
    """
    if alpha is None or alpha.size == 0:
        return alpha
    inside = (template_mask > 0)
    if not bool(inside.any()):
        return alpha

    trans_inside = (alpha == 0) & inside
    if not bool(trans_inside.any()):
        return alpha

    inside_u8 = inside.astype(np.uint8) * 255
    # Distance to outside for pixels inside the boundary.
    dt = cv2.distanceTransform(inside_u8, cv2.DIST_L2, 3)

    mind = int(max(1, min_interior_dist))

    n, labels, _stats, _ = cv2.connectedComponentsWithStats(trans_inside.astype(np.uint8), connectivity=8)
    if n <= 1:
        return alpha

    out = alpha.copy()
    for i in range(1, n):
        comp = labels == i
        # Fill if the component reaches meaningfully into the interior.
        # (Even if it touches boundary via a thin channel.)
        if float(np.max(dt[comp])) >= float(mind):
            out[comp] = 255
    return out


def _iter_team_dirs(tokens_dir: Path) -> Iterable[Path]:
    """Iterate over team token directories (layers/kt-app/processed/{team}/token/)."""
    for child in sorted(tokens_dir.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            continue
        # Look for the token subdirectory
        token_dir = child / "token"
        if token_dir.exists() and token_dir.is_dir():
            yield token_dir


def _iter_token_pngs(team_dir: Path) -> Iterable[Path]:
    for p in sorted(team_dir.glob("*.png")):
        if p.name.startswith("_"):
            continue
        yield p


def _ensure_bgr(img: np.ndarray) -> tuple[np.ndarray, np.ndarray | None]:
    if img.ndim != 3:
        raise ValueError("Unexpected image shape")

    if img.shape[2] == 4:
        bgr = img[:, :, :3].copy()
        alpha = img[:, :, 3].copy()
        return bgr, alpha

    if img.shape[2] == 3:
        return img.copy(), None

    raise ValueError(f"Unsupported channel count: {img.shape[2]}")


def _parse_hex_color(s: str) -> np.ndarray:
    t = str(s).strip().lower()
    if t.startswith("#"):
        t = t[1:]
    if len(t) != 6:
        raise ValueError(f"Invalid hex color: {s}")
    r = int(t[0:2], 16)
    g = int(t[2:4], 16)
    b = int(t[4:6], 16)
    return np.array([b, g, r], dtype=np.uint8)


def _parse_protect_colors(items: Sequence[str]) -> np.ndarray:
    if not items:
        return np.empty((0, 3), dtype=np.uint8)

    out: list[np.ndarray] = []
    for raw in items:
        if not raw:
            continue
        # Support comma-separated lists.
        parts = [p for p in str(raw).split(",") if p.strip()]
        for p in parts:
            out.append(_parse_hex_color(p.strip()))

    if not out:
        return np.empty((0, 3), dtype=np.uint8)

    # Deduplicate
    uniq: list[np.ndarray] = []
    for c in out:
        if not uniq:
            uniq.append(c)
            continue
        d = np.max(np.abs(np.stack(uniq, axis=0).astype(np.int16) - c.astype(np.int16)), axis=1)
        if int(np.min(d)) >= 1:
            uniq.append(c)
    return np.stack(uniq, axis=0).astype(np.uint8)


def _kmeans_bg_centers_from_sample(
    sample_bgr: np.ndarray,
    *,
    k: int,
    keep: int,
    max_pixels: int,
) -> np.ndarray:
    """Learn background centers from a background screenshot.

    Works in Lab for perceptual clustering.
    Returns centers in BGR uint8.
    """

    if sample_bgr is None or sample_bgr.size == 0:
        raise ValueError("Empty bg sample")

    lab = cv2.cvtColor(sample_bgr, cv2.COLOR_BGR2LAB)
    pts = lab.reshape(-1, 3).astype(np.float32)

    if pts.shape[0] > max_pixels:
        idx = np.linspace(0, pts.shape[0] - 1, max_pixels).astype(np.int32)
        pts = pts[idx]

    k = int(max(2, min(12, k)))
    keep = int(max(1, min(k, keep)))

    cv2.setRNGSeed(0)
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 40, 0.3)
    _compactness, labels, centers = cv2.kmeans(
        pts,
        k,
        None,
        criteria,
        5,
        cv2.KMEANS_PP_CENTERS,
    )

    labels = labels.reshape(-1)
    counts = np.bincount(labels, minlength=k).astype(np.int64)
    order = np.argsort(-counts)
    top = order[:keep]

    # Convert chosen Lab centers back to BGR.
    centers_lab = centers[top].reshape(-1, 1, 3).astype(np.uint8)
    centers_bgr = cv2.cvtColor(centers_lab, cv2.COLOR_LAB2BGR).reshape(-1, 3)

    # Deduplicate near-identical centers.
    uniq: list[np.ndarray] = []
    for c in centers_bgr:
        if not uniq:
            uniq.append(c)
            continue
        d = np.max(np.abs(np.stack(uniq, axis=0).astype(np.int16) - c.astype(np.int16)), axis=1)
        if int(np.min(d)) >= 3:
            uniq.append(c)
    return np.stack(uniq, axis=0).astype(np.uint8)


def _filter_bg_centers_to_greys(
    centers_bgr: np.ndarray,
    *,
    max_saturation: int,
    min_value: int,
) -> np.ndarray:
    """Filter centers to likely background greys using HSV heuristics.

    This is important when the bg sample contains logos/shapes (e.g. the big dark V)
    and speckle colors that we *don't* want to key out from tokens.
    """
    if centers_bgr is None or centers_bgr.size == 0:
        return centers_bgr

    max_s = int(max(0, min(255, max_saturation)))
    min_v = int(max(0, min(255, min_value)))

    hsv = cv2.cvtColor(centers_bgr.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
    s = hsv[:, 1].astype(np.int32)
    v = hsv[:, 2].astype(np.int32)
    keep = (s <= max_s) & (v >= min_v)
    filtered = centers_bgr[keep]
    return filtered if filtered.size else centers_bgr


def _merge_centers(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if a is None or a.size == 0:
        return b
    if b is None or b.size == 0:
        return a
    out: list[np.ndarray] = []
    for c in np.concatenate([a.reshape(-1, 3), b.reshape(-1, 3)], axis=0):
        if not out:
            out.append(c)
            continue
        d = np.max(np.abs(np.stack(out, axis=0).astype(np.int16) - c.astype(np.int16)), axis=1)
        if int(np.min(d)) >= 3:
            out.append(c)
    return np.stack(out, axis=0).astype(np.uint8)


def _bg_centers_from_token_borders(team_dir: Path, *, max_pixels: int = 12000) -> np.ndarray:
    """Fallback: learn background from the token crops themselves (border pixels)."""
    pixels: list[np.ndarray] = []

    for p in _iter_token_pngs(team_dir):
        img = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
        if img is None:
            continue
        bgr, _a = _ensure_bgr(img)
        h, w = bgr.shape[:2]
        t = int(max(4, min(20, min(h, w) // 12)))
        border = np.concatenate(
            [
                bgr[:t, :, :].reshape(-1, 3),
                bgr[max(0, h - t) : h, :, :].reshape(-1, 3),
                bgr[:, :t, :].reshape(-1, 3),
                bgr[:, max(0, w - t) : w, :].reshape(-1, 3),
            ],
            axis=0,
        )
        pixels.append(border)

    if not pixels:
        return np.array([[228, 229, 227], [209, 210, 208]], dtype=np.uint8)

    allp = np.concatenate(pixels, axis=0)
    if allp.shape[0] > max_pixels:
        idx = np.linspace(0, allp.shape[0] - 1, max_pixels).astype(np.int32)
        allp = allp[idx]

    # Cluster in Lab and keep a few dominant background tones.
    return _kmeans_bg_centers_from_sample(allp.reshape(-1, 1, 3), k=5, keep=3, max_pixels=max_pixels)


def _remove_small_alpha_components(alpha: np.ndarray, *, min_area: int) -> np.ndarray:
    if alpha is None or alpha.size == 0:
        return alpha

    h, w = alpha.shape[:2]
    if h <= 1 or w <= 1:
        return alpha

    min_a = int(max(0, min_area))
    if min_a <= 0:
        return alpha

    mask = (alpha > 0).astype(np.uint8)
    n, labels, stats, _centroids = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if n <= 1:
        return alpha

    keep = np.ones(n, dtype=bool)
    keep[0] = True
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        if area < min_a:
            keep[i] = False

    out = alpha.copy()
    out[~np.isin(labels, np.where(keep)[0])] = 0
    return out


def _edge_halo_cleanup(
    bgr: np.ndarray,
    alpha: np.ndarray,
    *,
    bg_centers_bgr: np.ndarray,
    edge_width: int,
    edge_threshold: int,
) -> np.ndarray:
    """Remove thin bg-colored halos along the outside edge.

    This targets pixels that are currently opaque but sit very close to transparency and
    still match the learned background colors (common from antialiasing / compression).
    """

    if alpha is None or alpha.size == 0:
        return alpha

    w = int(max(0, edge_width))
    thr = int(max(0, min(255, edge_threshold)))
    if w <= 0 or thr <= 0:
        return alpha

    h, ww = alpha.shape[:2]
    if h <= 1 or ww <= 1:
        return alpha

    # Pixels near existing transparency.
    trans = (alpha == 0).astype(np.uint8)
    k = (w * 2 + 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
    near_trans = cv2.dilate(trans, kernel, iterations=1) > 0
    candidates = near_trans & (alpha > 0)
    if not np.any(candidates):
        return alpha

    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.int16)
    centers_lab = cv2.cvtColor(bg_centers_bgr.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB)
    centers_lab = centers_lab.reshape(-1, 3).astype(np.int16)

    d_all: list[np.ndarray] = []
    for i in range(centers_lab.shape[0]):
        c = centers_lab[i]
        dl = lab - c[None, None, :]
        d2 = (dl[:, :, 0].astype(np.int32) ** 2) + (dl[:, :, 1].astype(np.int32) ** 2) + (dl[:, :, 2].astype(np.int32) ** 2)
        d_all.append(d2)
    dist2 = np.min(np.stack(d_all, axis=2), axis=2)

    cutoff2 = int(thr) * int(thr)
    halo = candidates & (dist2 <= cutoff2)
    if not np.any(halo):
        return alpha

    out = alpha.copy()
    out[halo] = 0
    return out


def _infer_token_region_from_bg_candidates(
    bg_cand: np.ndarray,
    *,
    close_kernel: int,
    close_iters: int,
) -> np.ndarray:
    """Infer the token's interior region from background candidates.

    We treat the token as the largest *foreground* (not background-like) connected region
    that is preferably NOT touching the image border.

    This is used to safely apply protection rules (e.g., keep #E7ECEB) only inside the
    token, not out in the background.
    """

    if bg_cand is None or bg_cand.size == 0:
        return np.zeros((0, 0), dtype=bool)

    h, w = bg_cand.shape[:2]
    if h <= 1 or w <= 1:
        return np.zeros((h, w), dtype=bool)

    fg = (bg_cand == 0).astype(np.uint8)

    k = int(close_kernel)
    it = int(max(1, close_iters))
    if k and k >= 3:
        k = k if (k % 2 == 1) else (k + 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, kernel, iterations=it)

    n, labels, stats, _centroids = cv2.connectedComponentsWithStats(fg, connectivity=8)
    if n <= 1:
        return np.zeros((h, w), dtype=bool)

    # Prefer the largest component that does NOT touch the border.
    best_label = -1
    best_area = -1
    for i in range(1, n):
        area = int(stats[i, cv2.CC_STAT_AREA])
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        ww = int(stats[i, cv2.CC_STAT_WIDTH])
        hh = int(stats[i, cv2.CC_STAT_HEIGHT])
        touches_border = x <= 0 or y <= 0 or (x + ww) >= w or (y + hh) >= h
        if touches_border:
            continue
        if area > best_area:
            best_area = area
            best_label = i

    if best_label < 0:
        # Fallback: largest component overall.
        for i in range(1, n):
            area = int(stats[i, cv2.CC_STAT_AREA])
            if area > best_area:
                best_area = area
                best_label = i

    return (labels == best_label)


def _fill_transparent_holes(alpha: np.ndarray) -> np.ndarray:
    """Fill interior transparent regions that are not connected to the border.

    Tokens are meant to be opaque shapes; transparency is only for the outside background.
    This protects internal white-ish details that might be misclassified as background.
    """

    if alpha is None or alpha.size == 0:
        return alpha

    h, w = alpha.shape[:2]
    if h <= 1 or w <= 1:
        return alpha

    transparent = (alpha == 0).astype(np.uint8)
    n, labels, stats, _centroids = cv2.connectedComponentsWithStats(transparent, connectivity=8)
    if n <= 1:
        return alpha

    border_labels: set[int] = set()
    for i in range(1, n):
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        ww = int(stats[i, cv2.CC_STAT_WIDTH])
        hh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if x <= 0 or y <= 0 or (x + ww) >= w or (y + hh) >= h:
            border_labels.add(i)

    if not border_labels:
        # Everything transparent is a hole.
        out = alpha.copy()
        out[alpha == 0] = 255
        return out

    out = alpha.copy()
    holes = (transparent > 0) & (~np.isin(labels, list(border_labels)))
    out[holes] = 255
    return out


def _alpha_from_bg_centers(
    bgr: np.ndarray,
    *,
    bg_centers_bgr: np.ndarray,
    threshold: int,
    bg_open_kernel: int = 0,
    bg_open_iters: int = 1,
    protect_white_val: int = 0,
    protect_white_sat: int = 40,
    protect_bright_delta: int = 0,
    protect_colors_bgr: np.ndarray | None = None,
    protect_colors_threshold: int = 12,
    protect_colors_min_border_dist: int = 4,
    protect_colors_token_only: bool = True,
    token_region_close_kernel: int = 7,
    token_region_close_iters: int = 1,
) -> np.ndarray:
    """Compute alpha by keying background colors to transparent.

    Classification is done in Lab space using Euclidean distance to the nearest bg center.
    Then we remove only background regions connected to the border.
    """

    h, w = bgr.shape[:2]
    if h <= 1 or w <= 1:
        return np.full((h, w), 255, dtype=np.uint8)

    thr = int(max(0, min(255, threshold)))

    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB).astype(np.int16)
    centers_lab = cv2.cvtColor(bg_centers_bgr.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB)
    centers_lab = centers_lab.reshape(-1, 3).astype(np.int16)

    d_all: list[np.ndarray] = []
    for i in range(centers_lab.shape[0]):
        c = centers_lab[i]
        dl = lab - c[None, None, :]
        d2 = (dl[:, :, 0].astype(np.int32) ** 2) + (dl[:, :, 1].astype(np.int32) ** 2) + (dl[:, :, 2].astype(np.int32) ** 2)
        d_all.append(d2)

    dist2 = np.min(np.stack(d_all, axis=2), axis=2)

    # Convert Lab-threshold into a squared distance cutoff.
    # (thr is treated like a "radius" in Lab units.)
    cutoff2 = int(thr) * int(thr)
    bg_cand = (dist2 <= cutoff2).astype(np.uint8)

    # Optional: protect specific interior colors (e.g. #E7ECEB) from being treated as background.
    # By default we only apply this inside the inferred token region, so it won't accidentally
    # preserve actual background pixels that happen to match the protected shade.
    if protect_colors_bgr is not None and protect_colors_bgr.size:
        pthr = int(max(0, min(255, protect_colors_threshold)))
        pmin = int(max(0, protect_colors_min_border_dist))
        if pthr > 0:
            prot_lab = cv2.cvtColor(protect_colors_bgr.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2LAB).reshape(-1, 3).astype(np.int16)
            d_all_p: list[np.ndarray] = []
            for i in range(prot_lab.shape[0]):
                c = prot_lab[i]
                dl = lab - c[None, None, :]
                d2 = (dl[:, :, 0].astype(np.int32) ** 2) + (dl[:, :, 1].astype(np.int32) ** 2) + (dl[:, :, 2].astype(np.int32) ** 2)
                d_all_p.append(d2)
            dist2_p = np.min(np.stack(d_all_p, axis=2), axis=2)
            pc2 = pthr * pthr
            protect = dist2_p <= pc2

            if bool(protect_colors_token_only):
                token_region = _infer_token_region_from_bg_candidates(
                    bg_cand,
                    close_kernel=int(token_region_close_kernel),
                    close_iters=int(token_region_close_iters),
                )
                protect = protect & token_region

            if pmin > 0:
                yy = np.arange(h, dtype=np.int32)[:, None]
                xx = np.arange(w, dtype=np.int32)[None, :]
                yy_full = np.broadcast_to(yy, (h, w))
                xx_full = np.broadcast_to(xx, (h, w))
                border_dist = np.minimum.reduce([xx_full, yy_full, (w - 1) - xx_full, (h - 1) - yy_full])
                protect = protect & (border_dist >= pmin)

            bg_cand[protect] = 0

    # Optional: protect bright (white-ish) token details from being treated as background.
    # Two modes:
    # - Explicit threshold: protect_white_val (V >= protect_white_val)
    # - Adaptive threshold: protect_bright_delta (V >= max(bg_center_v) + delta)
    if int(protect_white_val) > 0 or int(protect_bright_delta) > 0:
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2].astype(np.int32)
        s = hsv[:, :, 1].astype(np.int32)
        ps = int(max(0, min(255, protect_white_sat)))

        pv: int
        if int(protect_white_val) > 0:
            pv = int(max(0, min(255, protect_white_val)))
        else:
            centers_hsv = cv2.cvtColor(bg_centers_bgr.reshape(-1, 1, 3).astype(np.uint8), cv2.COLOR_BGR2HSV).reshape(-1, 3)
            bg_v_max = int(np.max(centers_hsv[:, 2])) if centers_hsv.size else 0
            delta = int(max(0, min(255, protect_bright_delta)))
            pv = int(max(0, min(255, bg_v_max + delta)))

        protect = (v >= pv) & (s <= ps)
        bg_cand[protect] = 0

    # Optional: remove thin background bridges before checking border connectivity.
    # This helps avoid background "leaking" into interior details via 1px connections.
    k = int(bg_open_kernel)
    it = int(max(1, bg_open_iters))
    if k and k >= 3:
        k = k if (k % 2 == 1) else (k + 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k))
        bg_cand = cv2.morphologyEx(bg_cand, cv2.MORPH_OPEN, kernel, iterations=it)

    # Only remove background connected to border.
    n, labels, stats, _centroids = cv2.connectedComponentsWithStats(bg_cand, connectivity=8)
    if n <= 1:
        return np.where(bg_cand > 0, 0, 255).astype(np.uint8)

    border_labels: set[int] = set()
    for i in range(1, n):
        x = int(stats[i, cv2.CC_STAT_LEFT])
        y = int(stats[i, cv2.CC_STAT_TOP])
        ww = int(stats[i, cv2.CC_STAT_WIDTH])
        hh = int(stats[i, cv2.CC_STAT_HEIGHT])
        if x <= 0 or y <= 0 or (x + ww) >= w or (y + hh) >= h:
            border_labels.add(i)

    if not border_labels:
        # Safety: if nothing touches the border, do not remove anything.
        return np.full((h, w), 255, dtype=np.uint8)

    is_bg = np.isin(labels, list(border_labels))
    return np.where(is_bg, 0, 255).astype(np.uint8)


def _write_debug(
    out_dir: Path,
    *,
    name: str,
    bgr: np.ndarray,
    alpha: np.ndarray,
    bg_centers: np.ndarray,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # swatch image
    sw_h = 32
    sw = np.zeros((sw_h, sw_h * bg_centers.shape[0], 3), dtype=np.uint8)
    for i, c in enumerate(bg_centers):
        sw[:, i * sw_h : (i + 1) * sw_h, :] = c.reshape(1, 1, 3)
    cv2.imwrite(str(out_dir / f"{name}_bg_centers.png"), sw)

    rgba = np.dstack([bgr, alpha])
    cv2.imwrite(str(out_dir / f"{name}_rgba.png"), rgba)


_TEAM_CONFIG_CACHE: dict | None = None


def _load_team_config() -> dict:
    global _TEAM_CONFIG_CACHE
    if _TEAM_CONFIG_CACHE is not None:
        return _TEAM_CONFIG_CACHE
    config_path = Path("config/team-config.yaml")
    if not config_path.exists():
        _TEAM_CONFIG_CACHE = {}
        return _TEAM_CONFIG_CACHE
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _TEAM_CONFIG_CACHE = data.get("teams", {}) or {}
    except Exception:
        _TEAM_CONFIG_CACHE = {}
    return _TEAM_CONFIG_CACHE


def _get_token_shape_from_config(team_name: str, token_name: str) -> str | None:
    if not team_name or not token_name:
        return None
    teams = _load_team_config()
    team_cfg = teams.get(team_name) or {}
    tokens = team_cfg.get("tokens", []) or []

    token_name_norm = " ".join(str(token_name).lower().split())

    for token_cfg in tokens:
        cfg_name = " ".join(str(token_cfg.get("name", "")).lower().split())
        if cfg_name and cfg_name == token_name_norm:
            shape = token_cfg.get("shape")
            if isinstance(shape, str) and shape.strip():
                return shape.strip()
    return None


def process_file(
    path: Path,
    *,
    output_path: Path | None = None,
    bg_centers: np.ndarray,
    threshold: int,
    speck_min_area: int,
    fill_holes: bool,
    bg_open_kernel: int,
    bg_open_iters: int,
    protect_white_val: int,
    protect_white_sat: int,
    protect_bright_delta: int,
    protect_colors_bgr: np.ndarray,
    protect_colors_threshold: int,
    protect_colors_min_border_dist: int,
    protect_colors_token_only: bool,
    token_region_close_kernel: int,
    token_region_close_iters: int,
    edge_cleanup: bool,
    edge_width: int,
    edge_threshold: int,
    template_fit: bool,
    template_oper: np.ndarray | None,
    template_round: np.ndarray | None,
    template_octagon: np.ndarray | None,
    template_diamond: np.ndarray | None,
    template_scale_band: float,
    template_scale_steps: int,
    template_shift: int,
    template_shift_step: int,
    template_min_iou: float,
    template_min_coverage: float,
    template_min_recall: float,
    debug_dir: Path | None,
) -> bool:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return False

    bgr, _existing_alpha = _ensure_bgr(img)
    alpha = _alpha_from_bg_centers(
        bgr,
        bg_centers_bgr=bg_centers,
        threshold=int(threshold),
        bg_open_kernel=int(bg_open_kernel),
        bg_open_iters=int(bg_open_iters),
        protect_white_val=int(protect_white_val),
        protect_white_sat=int(protect_white_sat),
        protect_bright_delta=int(protect_bright_delta),
        protect_colors_bgr=protect_colors_bgr,
        protect_colors_threshold=int(protect_colors_threshold),
        protect_colors_min_border_dist=int(protect_colors_min_border_dist),
        protect_colors_token_only=bool(protect_colors_token_only),
        token_region_close_kernel=int(token_region_close_kernel),
        token_region_close_iters=int(token_region_close_iters),
    )
    if bool(edge_cleanup):
        # Use a slightly more permissive threshold for halo cleanup if not explicitly set.
        et = int(edge_threshold)
        if et <= 0:
            et = int(max(0, int(threshold) + 6))
        alpha = _edge_halo_cleanup(
            bgr,
            alpha,
            bg_centers_bgr=bg_centers,
            edge_width=int(edge_width),
            edge_threshold=et,
        )
    if bool(fill_holes):
        alpha = _fill_transparent_holes(alpha)
    alpha = _remove_small_alpha_components(alpha, min_area=int(speck_min_area))

    if bool(template_fit) and template_oper is not None and template_round is not None:
        # Pass 1: Simple white removal - trust the extraction
        hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
        v = hsv[:, :, 2]
        s = hsv[:, :, 1]
        
        # Remove white/near-white background
        is_white = ((v > 235) & (s < 20)) | ((bgr[:, :, 0] > 235) & (bgr[:, :, 1] > 235) & (bgr[:, :, 2] > 235))
        simple_mask = (~is_white) & (alpha > 0)
        simple_mask = simple_mask.astype(np.uint8)
        
        # Keep largest component
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(simple_mask, connectivity=8)
        if num_labels > 1:
            largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
            simple_mask = (labels == largest_label).astype(np.uint8)
        
        simple_mask = _mask_fill_holes(simple_mask * 255)
        simple_mask = (simple_mask > 0).astype(np.uint8)
        
        # Check if this simple mask is already good
        bbox_simple = _mask_bbox(simple_mask)
        cand_expanded = None
        detection_method = None
        
        if bbox_simple is not None:
            sx, sy, sw, sh = bbox_simple
            img_h, img_w = alpha.shape
            coverage = (sw * sh) / (img_w * img_h)
            aspect = sw / float(sh) if sh > 0 else 1.0
            
            if debug_dir:
                print(f"  Simple detection: coverage={coverage:.3f}, aspect={aspect:.3f}, bbox=({sx},{sy},{sw},{sh}), img={img_w}x{img_h}")
            
            # If shape has reasonable coverage and aspect ratio, accept it
            # Coverage up to 0.9 is fine - extraction adds padding so high coverage is expected
            if 0.2 < coverage < 0.9 and 0.6 < aspect < 1.8:
                # Use simple mask with minimal cleanup
                el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
                cand_expanded = cv2.morphologyEx(simple_mask, cv2.MORPH_CLOSE, el, iterations=1)
                detection_method = f"Simple white removal (coverage: {coverage:.2f}, aspect: {aspect:.2f})"
        
        # Pass 2: Advanced detection if simple method failed
        if cand_expanded is None:
            candidates = []
            
            # Strategy 1: Tight thresholds, minimal dilation
            is_content = ((v < 220) | (s > 30)) & (alpha > 0)
            cand = is_content.astype(np.uint8)
            if cand.sum() > 0:
                num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
                if num_labels > 1:
                    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
                    cand = (labels == largest_label).astype(np.uint8)
                
                el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                result = cv2.dilate(cand, el, iterations=1)
                result = result & (alpha > 0).astype(np.uint8)
                result = _mask_fill_holes(result * 255)
                result = (result > 0).astype(np.uint8)
                candidates.append(("Tight+Minimal", result))
            
            # Strategy 2: Tight thresholds, moderate dilation
            if cand.sum() > 0:
                el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
                result = cv2.dilate(cand, el, iterations=1)
                result = result & (alpha > 0).astype(np.uint8)
                result = _mask_fill_holes(result * 255)
                result = (result > 0).astype(np.uint8)
                candidates.append(("Tight+Moderate", result))
            
            # Strategy 3: Loose thresholds, minimal dilation
            is_content = ((v < 230) | (s > 25)) & (alpha > 0)
            cand = is_content.astype(np.uint8)
            if cand.sum() > 0:
                num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
                if num_labels > 1:
                    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
                    cand = (labels == largest_label).astype(np.uint8)
                
                el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
                result = cv2.dilate(cand, el, iterations=1)
                result = result & (alpha > 0).astype(np.uint8)
                result = _mask_fill_holes(result * 255)
                result = (result > 0).astype(np.uint8)
                candidates.append(("Loose+Minimal", result))
            
            # Strategy 4: Loose thresholds, moderate dilation
            if cand.sum() > 0:
                el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (15, 15))
                result = cv2.dilate(cand, el, iterations=1)
                result = result & (alpha > 0).astype(np.uint8)
                result = _mask_fill_holes(result * 255)
                result = (result > 0).astype(np.uint8)
                candidates.append(("Loose+Moderate", result))
            
            # Strategy 5: Very loose, larger dilation
            is_content = ((v < 235) | (s > 20)) & (alpha > 0)
            cand = is_content.astype(np.uint8)
            if cand.sum() > 0:
                num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(cand, connectivity=8)
                if num_labels > 1:
                    largest_label = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
                    cand = (labels == largest_label).astype(np.uint8)
                
                el = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (21, 21))
                result = cv2.dilate(cand, el, iterations=1)
                result = result & (alpha > 0).astype(np.uint8)
                result = _mask_fill_holes(result * 255)
                result = (result > 0).astype(np.uint8)
                candidates.append(("VeryLoose+Large", result))
            
            # Evaluate and pick best
            best_score = -1
            img_h, img_w = alpha.shape
            total_pixels = img_w * img_h
            
            for name, candidate in candidates:
                bbox = _mask_bbox(candidate)
                if bbox is None:
                    continue
                
                cx, cy, cw, ch = bbox
                coverage = (cw * ch) / total_pixels
                aspect = cw / float(ch) if ch > 0 else 1.0
                
                score = 0.0
                if 0.2 < coverage < 0.7:
                    score += 100
                elif 0.15 < coverage < 0.8:
                    score += 50
                elif 0.1 < coverage < 0.9:
                    score += 20
                
                if 0.7 < aspect < 1.4:
                    score += 50
                elif 0.5 < aspect < 2.0:
                    score += 30
                elif 0.4 < aspect < 2.5:
                    score += 10
                
                edge_margin = 5
                if cx < edge_margin or cy < edge_margin or (cx + cw) > (img_w - edge_margin) or (cy + ch) > (img_h - edge_margin):
                    score -= 30
                
                if "Minimal" in name:
                    score += 10
                elif "Moderate" in name:
                    score += 5
                
                if score > best_score:
                    best_score = score
                    cand_expanded = candidate
                    detection_method = f"Advanced: {name} (score: {score:.0f})"
        
        # Fallback
        if cand_expanded is None:
            cand_expanded = (alpha > 0).astype(np.uint8)
            detection_method = "Fallback: Full alpha"
        
        # Get bounding box of EXPANDED content (includes white interior)
        content_bbox = _mask_bbox(cand_expanded)
        if content_bbox is not None:
            cx, cy, cw, ch = content_bbox
            
            # Try to read shape from extraction metadata
            metadata_path = path.parent / "extraction-metadata.json"
            detected_shape = 'operative'  # Default to operative
            aspect = cw / float(ch) if ch > 0 else 1.0
            
            # First check metadata
            shape_from_metadata = None
            token_name_from_metadata = None
            if metadata_path.exists():
                try:
                    import json
                    with open(metadata_path, 'r') as f:
                        metadata = json.load(f)
                    for token in metadata.get('tokens', []):
                        if token.get('filename') == path.name:
                            shape_from_metadata = token.get('shape')
                            token_name_from_metadata = token.get('name')
                            break
                except Exception:
                    pass

            # Prefer explicit config shape when available
            team_name = path.parent.parent.name if path.parent.name == "token" else path.parent.name
            shape_from_config = None
            if token_name_from_metadata:
                shape_from_config = _get_token_shape_from_config(team_name, token_name_from_metadata)

            if shape_from_config in ['round', 'octagon', 'diamond', 'operative']:
                detected_shape = shape_from_config
            else:
                # Use metadata shape if available, with validation for round
                if shape_from_metadata in ['octagon', 'diamond', 'operative']:
                    # Trust these shapes from metadata
                    detected_shape = shape_from_metadata
                elif shape_from_metadata == 'round':
                    # Check if the content mask is actually circular
                    # A circle should have high circularity when we compute it from the content mask
                    contours, _ = cv2.findContours(cand_expanded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    if contours:
                        largest_contour = max(contours, key=cv2.contourArea)
                        area = cv2.contourArea(largest_contour)
                        perimeter = cv2.arcLength(largest_contour, True)
                        circularity = (4 * np.pi * area) / (perimeter ** 2) if perimeter > 0 else 0
                        
                        # Only override metadata if it's REALLY not circular (< 0.5)
                        # Tokens with small white gaps at edges can have low circularity but are still round
                        if circularity < 0.5 and aspect < 0.85:
                            # Low circularity AND elongated aspect - probably operative
                            detected_shape = 'operative'
                        else:
                            # Trust metadata - could just have edge artifacts
                            detected_shape = 'round'
                    else:
                        detected_shape = 'round'
                else:
                    # No metadata or unknown shape - fall back to aspect ratio
                    detected_shape = 'round' if (0.85 <= aspect <= 1.15) else 'operative'
            
            # Create perfect shape mask directly from content bounds
            h, w = bgr.shape[:2]
            best_fit = np.zeros((h, w), dtype=np.uint8)
            
            center_x = cx + cw / 2.0
            center_y = cy + ch / 2.0
            
            # Select appropriate template based on detected shape
            if detected_shape == 'round':
                # Create perfect circle
                radius = min(cw, ch) / 2.0
                Y, X = np.ogrid[:h, :w]
                dist = np.sqrt((X - center_x)**2 + (Y - center_y)**2)
                best_fit[dist <= radius] = 1
            else:
                # Use appropriate template (operative, octagon, or diamond)
                template_to_use = None
                if detected_shape == 'operative':
                    template_to_use = template_oper
                elif detected_shape == 'octagon':
                    template_to_use = template_octagon if template_octagon is not None else template_oper
                elif detected_shape == 'diamond':
                    template_to_use = template_diamond if template_diamond is not None else template_oper
                else:
                    template_to_use = template_oper  # fallback
                
                # Scale the template to match content size
                if template_to_use is not None:
                    templ_bbox = _mask_bbox(template_to_use)
                    if templ_bbox is not None:
                        tx, ty, tw, th = templ_bbox
                        scale_x = cw / float(tw)
                        scale_y = ch / float(th)
                        
                        templ_resized = cv2.resize(
                            (template_to_use > 0).astype(np.uint8),
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
            
            # DEBUG: Save both overlays only
            if debug_dir is not None:
                debug_dir.mkdir(parents=True, exist_ok=True)
                
                debug_vis = bgr.copy()
                # Show expanded area in green, template in red
                debug_vis[cand_expanded > 0] = debug_vis[cand_expanded > 0] * 0.5 + np.array([0, 255, 0], dtype=np.uint8) * 0.5
                debug_vis[best_fit > 0] = debug_vis[best_fit > 0] * 0.5 + np.array([255, 0, 0], dtype=np.uint8) * 0.5
                cv2.imwrite(str(debug_dir / f"{path.stem}_3_both_overlays.png"), debug_vis)
                
                with open(debug_dir / f"{path.stem}_metrics.txt", 'w') as f:
                    f.write(f"Detection: {detection_method}\n")
                    f.write(f"Template: {'round' if is_round else 'operative'}\n")
                    f.write(f"Content bbox: {cx}, {cy}, {cw}, {ch}\n")
                    f.write(f"Aspect ratio: {aspect:.3f}\n")
                    if is_round:
                        f.write(f"Circle radius: {radius:.1f}px\n")
                    f.write(f"Match quality: DIRECT_FIT\n")
            
            # Apply template
            # Inset the template mask by 5% before applying.
            best_fit = _apply_inset_to_mask(best_fit, scale=0.95)
            alpha = np.where(best_fit > 0, alpha, 0).astype(np.uint8)
            
            # Mask out white pixels within template
            is_white = ((v > 235) & (s < 20)) | ((bgr[:, :, 0] > 235) & (bgr[:, :, 1] > 235) & (bgr[:, :, 2] > 235))
            alpha = np.where(is_white, 0, alpha).astype(np.uint8)
            
            alpha = _fill_transparent_holes_within_template(alpha, best_fit)
            alpha = _fill_transparent_holes_within_template(alpha, best_fit)
            
            # Crop to template bounds and resize to template size (no padding)
            template_bbox = _mask_bbox(best_fit)
            if template_bbox is not None:
                x, y, w, h = template_bbox
                # Crop both BGR and alpha to template region
                bgr = bgr[y:y+h, x:x+w]
                alpha = alpha[y:y+h, x:x+w]

                # Resize directly to the template image size for this shape
                target_w = w
                target_h = h
                if detected_shape == 'round' and template_round is not None:
                    target_h, target_w = template_round.shape[:2]
                elif detected_shape == 'operative' and template_oper is not None:
                    target_h, target_w = template_oper.shape[:2]
                elif detected_shape == 'octagon' and template_octagon is not None:
                    target_h, target_w = template_octagon.shape[:2]
                elif detected_shape == 'diamond' and template_diamond is not None:
                    target_h, target_w = template_diamond.shape[:2]

                if (w, h) != (target_w, target_h):
                    bgr = cv2.resize(bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)
                    alpha = cv2.resize(alpha, (target_w, target_h), interpolation=cv2.INTER_AREA)

    out = np.dstack([bgr, alpha])
    
    # Write to output_path if provided, otherwise overwrite original
    write_path = output_path if output_path is not None else path
    ok = bool(cv2.imwrite(str(write_path), out))

    if ok and debug_dir is not None:
        _write_debug(debug_dir, name=path.stem, bgr=bgr, alpha=alpha, bg_centers=bg_centers)

    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Experimental transparency using a background screenshot")
    parser.add_argument("--tokens-dir", type=str, default="layers/kt-app/processed")
    parser.add_argument("--team", type=str, default=None)
    parser.add_argument("--all", action="store_true")

    parser.add_argument(
        "--bg-sample",
        type=str,
        default="config/defaults/tts-token/token-bg-sample.png",
        help=(
            "Path to a screenshot/crop containing only the card background tones. "
            "If omitted, the script learns background tones from token border pixels (less robust)."
        ),
    )
    parser.add_argument("--k", type=int, default=10, help="k-means clusters for bg sample. Default: 10")
    parser.add_argument("--keep", type=int, default=6, help="How many dominant bg clusters to keep. Default: 6")
    parser.add_argument("--max-sample-pixels", type=int, default=20000, help="Max pixels used from bg sample. Default: 20000")

    parser.add_argument(
        "--include-border-centers",
        action="store_true",
        help=(
            "Also learn a few background centers from token border pixels and merge them with the bg-sample centers. "
            "Helps when the extracted crops include extra background tones not present in the screenshot crop."
        ),
    )

    parser.add_argument(
        "--max-bg-sat",
        type=int,
        default=45,
        help=(
            "Max HSV saturation for learned background centers. Lower keeps only greys; higher allows colored tones. "
            "Default: 45"
        ),
    )
    parser.add_argument(
        "--min-bg-val",
        type=int,
        default=120,
        help=(
            "Min HSV value (brightness) for learned background centers. Helps drop dark logo shapes from bg sample. "
            "Default: 120"
        ),
    )

    parser.add_argument(
        "--threshold",
        type=int,
        default=18,
        help=(
            "Tolerance in Lab units. Smaller removes less background; larger removes more. "
            "Default: 18"
        ),
    )

    parser.add_argument("--speck-min-area", type=int, default=40, help="Remove alpha specks smaller than this. Default: 40")

    parser.add_argument(
        "--fill-holes",
        action="store_true",
        help=(
            "Fill interior transparent regions (holes) that are not connected to the border. "
            "Useful when white-ish internal token details get misclassified as background."
        ),
    )

    parser.add_argument(
        "--template-fit",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Fit one of two token boundary templates (operative vs round) and clamp alpha to that boundary. "
            "Also fills enclosed holes inside the fitted boundary. Default: enabled"
        ),
    )
    parser.add_argument(
        "--operative-template",
        type=str,
        default="dev/references/Generic_status_red_04_white.png",
        help="Template PNG for the operative token shape (uses its alpha).",
    )
    parser.add_argument(
        "--round-template",
        type=str,
        default="dev/references/Bomb_red_white.png",
        help="Template PNG for the round token shape (uses its alpha).",
    )
    parser.add_argument(
        "--octagon-template",
        type=str,
        default="config/defaults/tts-token/template-octagon-cutter.png",
        help="Template PNG for the octagon token shape (uses its alpha).",
    )
    parser.add_argument(
        "--diamond-template",
        type=str,
        default="config/defaults/tts-token/template-diamond-cutter.png",
        help="Template PNG for the diamond token shape (uses its alpha).",
    )
    parser.add_argument("--template-scale-band", type=float, default=0.22)
    parser.add_argument("--template-scale-steps", type=int, default=9)
    parser.add_argument("--template-shift", type=int, default=14)
    parser.add_argument("--template-shift-step", type=int, default=2)
    parser.add_argument("--template-min-iou", type=float, default=0.52)
    parser.add_argument("--template-min-coverage", type=float, default=0.80)
    parser.add_argument(
        "--template-min-recall",
        type=float,
        default=0.92,
        help=(
            "Soft template-fit threshold: if recall is this high, we will fill interior holes within the fitted boundary "
            "even if IoU/coverage aren't good enough to clamp the whole outline. Default: 0.92"
        ),
    )

    parser.add_argument(
        "--bg-open-kernel",
        type=int,
        default=5,
        help=(
            "Morphology kernel size (odd, >=3) to open the background-candidate mask before border connectivity. "
            "Helps break thin background bridges into interior details. Default: 5"
        ),
    )
    parser.add_argument("--bg-open-iters", type=int, default=1, help="Iterations for --bg-open-kernel. Default: 1")

    parser.add_argument(
        "--protect-white-val",
        type=int,
        default=0,
        help=(
            "Optional HSV V threshold to protect very bright (white-ish) pixels from being removed as background. "
            "0 disables. Typical: 245-252. Default: 0 (off)"
        ),
    )
    parser.add_argument(
        "--protect-white-sat",
        type=int,
        default=70,
        help="Max HSV saturation for protected white-ish pixels. Default: 70",
    )

    parser.add_argument(
        "--protect-bright-delta",
        type=int,
        default=18,
        help=(
            "Adaptive bright protection: protect pixels with V >= max(bg_center_v) + delta (and S <= protect-white-sat). "
            "Set to 0 to disable. Default: 18"
        ),
    )

    parser.add_argument(
        "--protect-colors",
        nargs="*",
        default=[],
        help=(
            "Hex colors to force-keep opaque (prevent from being keyed out), e.g. --protect-colors E7ECEB. "
            "Supports comma-separated lists too."
        ),
    )
    parser.add_argument(
        "--protect-colors-threshold",
        type=int,
        default=14,
        help="Tolerance (Lab units) when matching --protect-colors. Default: 14",
    )
    parser.add_argument(
        "--protect-colors-min-border-dist",
        type=int,
        default=4,
        help="Only apply --protect-colors this many pixels away from the border. Default: 4",
    )
    parser.add_argument(
        "--protect-colors-token-only",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Apply --protect-colors only inside the inferred token region (recommended). "
            "Use --no-protect-colors-token-only to allow anywhere. Default: enabled"
        ),
    )
    parser.add_argument(
        "--token-region-close-kernel",
        type=int,
        default=7,
        help="Kernel size for token-region closing (odd, >=3). Default: 7",
    )
    parser.add_argument(
        "--token-region-close-iters",
        type=int,
        default=1,
        help="Iterations for --token-region-close-kernel. Default: 1",
    )

    parser.add_argument(
        "--edge-cleanup",
        action=argparse.BooleanOptionalAction,
        default=True,
        help=(
            "Remove thin bg-colored halos along the outside edge (recommended). "
            "Use --no-edge-cleanup to disable. Default: enabled"
        ),
    )
    parser.add_argument("--edge-width", type=int, default=2, help="Radius (px) for edge halo cleanup. Default: 2")
    parser.add_argument(
        "--edge-threshold",
        type=int,
        default=0,
        help="Lab threshold for halo cleanup; 0 uses threshold+6. Default: 0",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Write debug RGBA + bg center swatches to processed/extracted-tokens/<team>/_debug_bg_sample/",
    )

    args = parser.parse_args()

    tokens_dir = Path(args.tokens_dir)
    if not tokens_dir.exists():
        raise SystemExit(f"Tokens dir not found: {tokens_dir}")

    if not args.all and not args.team:
        raise SystemExit("Provide --team TEAM or --all")
    if args.team and args.all:
        raise SystemExit("Use only one of --team or --all")

    if args.team:
        team_dirs = [tokens_dir / args.team / "token"]
    else:
        team_dirs = list(_iter_team_dirs(tokens_dir))

    template_oper = None
    template_round = None
    template_octagon = None
    template_diamond = None
    if bool(args.template_fit):
        template_oper = _load_template_mask(Path(args.operative_template))
        template_round = _load_template_mask(Path(args.round_template))
        template_octagon = _load_template_mask(Path(args.octagon_template))
        template_diamond = _load_template_mask(Path(args.diamond_template))

    sample_path = Path(str(args.bg_sample)) if str(args.bg_sample).strip() else None

    total = 0
    changed = 0

    for team_dir in team_dirs:
        if not team_dir.exists() or not team_dir.is_dir():
            print(f"⚠ Team dir missing, skipping: {team_dir}")
            continue

        # Create output directory for cut tokens (don't overwrite originals)
        team_name = team_dir.parent.name  # Get team name from path
        output_token_dir = team_dir.parent / "token-cut"
        output_token_dir.mkdir(exist_ok=True, parents=True)

        if sample_path is not None and sample_path.exists():
            sample_img = cv2.imread(str(sample_path), cv2.IMREAD_COLOR)
            if sample_img is None:
                raise SystemExit(f"Failed to read bg sample: {sample_path}")
            bg_centers = _kmeans_bg_centers_from_sample(
                sample_img,
                k=int(args.k),
                keep=int(args.keep),
                max_pixels=int(args.max_sample_pixels),
            )
            bg_centers = _filter_bg_centers_to_greys(
                bg_centers,
                max_saturation=int(args.max_bg_sat),
                min_value=int(args.min_bg_val),
            )

            if bool(args.include_border_centers):
                border_centers = _bg_centers_from_token_borders(team_dir)
                border_centers = _filter_bg_centers_to_greys(
                    border_centers,
                    max_saturation=int(args.max_bg_sat),
                    min_value=int(args.min_bg_val),
                )
                bg_centers = _merge_centers(bg_centers, border_centers)
        else:
            # Fallback: derive from token borders.
            bg_centers = _bg_centers_from_token_borders(team_dir)
            bg_centers = _filter_bg_centers_to_greys(
                bg_centers,
                max_saturation=int(args.max_bg_sat),
                min_value=int(args.min_bg_val),
            )

        debug_dir = (team_dir / "_debug_bg_sample") if bool(args.debug) else None
        protect_colors_bgr = _parse_protect_colors(list(args.protect_colors))

        for png in _iter_token_pngs(team_dir):
            total += 1
            # Save to token-cut folder to preserve originals
            output_png = output_token_dir / png.name
            ok = process_file(
                png,
                output_path=output_png,
                bg_centers=bg_centers,
                threshold=int(args.threshold),
                speck_min_area=int(args.speck_min_area),
                fill_holes=bool(args.fill_holes),
                bg_open_kernel=int(args.bg_open_kernel),
                bg_open_iters=int(args.bg_open_iters),
                protect_white_val=int(args.protect_white_val),
                protect_white_sat=int(args.protect_white_sat),
                protect_bright_delta=int(args.protect_bright_delta),
                protect_colors_bgr=protect_colors_bgr,
                protect_colors_threshold=int(args.protect_colors_threshold),
                protect_colors_min_border_dist=int(args.protect_colors_min_border_dist),
                protect_colors_token_only=bool(args.protect_colors_token_only),
                token_region_close_kernel=int(args.token_region_close_kernel),
                token_region_close_iters=int(args.token_region_close_iters),
                edge_cleanup=bool(args.edge_cleanup),
                edge_width=int(args.edge_width),
                edge_threshold=int(args.edge_threshold),
                template_fit=bool(args.template_fit),
                template_oper=template_oper,
                template_round=template_round,
                template_octagon=template_octagon,
                template_diamond=template_diamond,
                template_scale_band=float(args.template_scale_band),
                template_scale_steps=int(args.template_scale_steps),
                template_shift=int(args.template_shift),
                template_shift_step=int(args.template_shift_step),
                template_min_iou=float(args.template_min_iou),
                template_min_coverage=float(args.template_min_coverage),
                template_min_recall=float(args.template_min_recall),
                debug_dir=debug_dir,
            )
            if ok:
                changed += 1
            else:
                print(f"⚠ Failed: {png}")

    print(f"Done. Wrote alpha for {changed}/{total} PNGs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
