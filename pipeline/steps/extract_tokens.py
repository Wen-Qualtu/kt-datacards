"""Tokens — one-off per team. Two-phase extraction from the token-guide card.

manifest.json token_guide entry (which page PDF to read) + config token shapes
   ->  output/{team}/tokens/{team}-{name}.png (+ {team}-{name}.obj)
   ->  output/{team}/tokens/tokenbag/{team}-token-bag.obj + {team}-token-bag-icon.png

Phase 1: contour-based rough token extraction from the token-guide PDF page
         (pipeline.utils.token_extractor.TokenExtractor.process_team_auto_tuned).
Phase 2: transparency + shape-template cutting.

Source-agnostic — drives off the integration manifest instead of a multi-page
``{team}-faction-rules.pdf``. ``find_marker_guides`` is overridden to return the
token-guide page(s) declared by the manifest.
"""
from __future__ import annotations

import json
import logging
import shutil
import yaml
from pathlib import Path
from typing import Dict, List, Optional

import cv2
import numpy as np

from ..utils import paths, team_config
from ..utils.stable_io import stable_write
from ..utils.state import StateIndex, StateManager
from ..utils.token_extractor import TokenExtractor

logger = logging.getLogger(__name__)

TOKEN_TEMPLATE_DIR = paths.DEFAULTS / "tts-token"
TOKEN_WORK_ROOT = paths.LAYERS / "token-extraction"

# Shared 3-D assets (identical for every team/token — production copies the same
# template files rather than generating unique geometry).
TOKEN_MESH_TEMPLATE = TOKEN_TEMPLATE_DIR / "token-mesh.obj"
TOKEN_BAG_MESH_TEMPLATE = paths.DEFAULTS / "box" / "token-bag.obj"


class IntegrationTokenExtractor(TokenExtractor):
    """TokenExtractor that sources its token-guide page(s) from the integration
    manifest instead of scanning a legacy ``{team}-faction-rules.pdf``."""

    def find_marker_guides(self, team_name: str) -> List[Dict]:
        manifest_path = paths.integration_manifest_file(team_name)
        if not manifest_path.exists():
            return []
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"  {team_name}: could not read manifest: {e}")
            return []

        # Prefer the committed classified single-card token-guide PDF(s) under
        # layers/integration/{team}. The manifest's `front` points at the per-track
        # raw extract under layers/{track}/extracted, which is GITIGNORED and thus
        # absent on a fresh clone (or after a track re-scrape) — using it breaks
        # token re-runs. The classified PDFs are committed and carry identical
        # page content, so they are the reliable source of truth.
        team_dir = paths.integration_team_dir(team_name)
        classified = sorted(team_dir.glob(f"{team_name}-token-guide-*.pdf"))
        if classified:
            return [
                {"pdf_path": p, "page_num": 0, "page_index": i + 1}
                for i, p in enumerate(classified)
            ]

        # Fallback: raw extract path from the manifest (only present mid-run when
        # the track's extracted layer still exists).
        guides: List[Dict] = []
        for entry in manifest.get("token_guide", []):
            for card in entry.get("cards", []):
                front = card.get("front")
                if not front:
                    continue
                pdf_path = Path(front)
                if not pdf_path.is_absolute():
                    pdf_path = paths.ROOT / pdf_path
                if not pdf_path.exists():
                    logger.warning(f"  {team_name}: token-guide PDF missing: {pdf_path}")
                    continue
                guides.append({
                    "pdf_path": pdf_path,
                    "page_num": 0,
                    "page_index": len(guides) + 1,
                })
        return guides


# ========================================
# Phase 2: transparency and shape cutting
# ========================================

def _load_template(path: Path) -> np.ndarray:
    img = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError(f"Failed to load template: {path}")
    if img.ndim == 2:
        return img
    elif img.shape[2] == 4:
        return img[:, :, 3]
    else:
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _get_token_shape(team_slug: str, token_name: str, extraction_metadata: dict) -> str:
    team_data = team_config.team_data(team_slug)
    tokens_config = team_data.get("tokens", []) if team_data else []
    normalized_search = " ".join(token_name.lower().split())
    for token_cfg in tokens_config:
        cfg_name = token_cfg.get("name", "")
        if normalized_search == " ".join(cfg_name.lower().split()):
            shape = token_cfg.get("shape")
            if shape:
                return shape
    meta_shape = extraction_metadata.get("shape")
    if meta_shape and meta_shape in ("operative", "round", "octagon", "diamond"):
        return meta_shape
    return "operative"


def _remove_background(img: np.ndarray) -> np.ndarray:
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 3:
        bgr = img
    elif img.shape[2] == 4:
        bgr = img[:, :, :3]
    else:
        raise ValueError(f"Unexpected image shape: {img.shape}")

    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    v = hsv[:, :, 2]
    s = hsv[:, :, 1]
    is_white = ((v > 235) & (s < 25)) | (
        (bgr[:, :, 0] > 235) & (bgr[:, :, 1] > 235) & (bgr[:, :, 2] > 235)
    )
    # Treat fully/near-transparent pixels as background too. Custom-token sources
    # can be camo-on-TRANSPARENT (not camo-on-white); without this the transparent
    # RGB (0,0,0 once alpha is dropped) survives as opaque black around the token.
    if img.ndim == 3 and img.shape[2] == 4:
        is_white = is_white | (img[:, :, 3] < 16)
    mask = (~is_white).astype(np.uint8) * 255

    num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if num_labels > 1:
        # Drop components that are tiny RELATIVE to the largest one. This removes a
        # caption/label that bled into the rough crop (e.g. wrecka-krew "breach",
        # whose circle bridged to its text below) so the content bbox becomes just
        # the token — otherwise the tall bbox shrinks the token and leaves margin.
        # The absolute floor (100px) is kept for genuinely small tokens.
        areas = stats[1:, cv2.CC_STAT_AREA]
        max_area = int(areas.max()) if areas.size else 0
        min_area = max(100, int(max_area * 0.15))
        cleaned_mask = np.zeros_like(mask)
        for label in range(1, num_labels):
            if stats[label, cv2.CC_STAT_AREA] >= min_area:
                cleaned_mask[labels == label] = 255
        mask = cleaned_mask

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if contours:
        cv2.drawContours(mask, contours, -1, 255, thickness=cv2.FILLED)

    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel, iterations=1)
    return mask


def _crop_to_content(img: np.ndarray, mask: np.ndarray):
    ys, xs = np.where(mask > 0)
    if xs.size == 0:
        return img, mask
    x0, x1 = int(xs.min()), int(xs.max())
    y0, y1 = int(ys.min()), int(ys.max())
    return img[y0:y1 + 1, x0:x1 + 1], mask[y0:y1 + 1, x0:x1 + 1]


def _fit_to_template(content_mask: np.ndarray, template: np.ndarray,
                     incut_percent: float = 5.0) -> np.ndarray:
    ys, xs = np.where(content_mask > 0)
    if xs.size == 0:
        return np.zeros_like(content_mask)
    x0, y0 = int(xs.min()), int(ys.min())
    x1, y1 = int(xs.max()), int(ys.max())
    content_w = x1 - x0 + 1
    content_h = y1 - y0 + 1
    content_cx = (x0 + x1) / 2.0
    content_cy = (y0 + y1) / 2.0

    template_h, template_w = template.shape
    scale_w = (content_w / template_w) * (1.0 - incut_percent / 100.0)
    scale_h = (content_h / template_h) * (1.0 - incut_percent / 100.0)
    scale = min(scale_w, scale_h)

    new_w = int(template_w * scale)
    new_h = int(template_h * scale)
    if new_w > 0 and new_h > 0:
        scaled_template = cv2.resize(template, (new_w, new_h), interpolation=cv2.INTER_LINEAR)
    else:
        scaled_template = template
        new_w, new_h = template_w, template_h

    result = np.zeros_like(content_mask)
    offset_x = int(content_cx - new_w / 2.0)
    offset_y = int(content_cy - new_h / 2.0)

    paste_x0 = max(0, offset_x)
    paste_y0 = max(0, offset_y)
    paste_x1 = min(result.shape[1], offset_x + new_w)
    paste_y1 = min(result.shape[0], offset_y + new_h)

    src_x0 = paste_x0 - offset_x
    src_y0 = paste_y0 - offset_y
    src_x1 = src_x0 + (paste_x1 - paste_x0)
    src_y1 = src_y0 + (paste_y1 - paste_y0)

    if paste_x1 > paste_x0 and paste_y1 > paste_y0:
        result[paste_y0:paste_y1, paste_x0:paste_x1] = scaled_template[src_y0:src_y1, src_x0:src_x1]
    return result


def _standard_token_size(shape: str):
    if shape == "operative":
        return (439, 414)
    return (235, 235)  # round / octagon / diamond / default


def _process_token(input_path: Path, output_path: Path, shape: str,
                   templates: Dict[str, np.ndarray]) -> bool:
    img = cv2.imread(str(input_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return False
    if img.ndim == 2:
        bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 3:
        bgr = img
    elif img.shape[2] == 4:
        bgr = img[:, :, :3]
    else:
        return False

    content_mask = _remove_background(img)
    cropped_bgr, cropped_mask = _crop_to_content(bgr, content_mask)

    template = templates.get(shape)
    if template is None:
        template = templates.get("operative")
    if template is None:
        return False

    fitted_template = _fit_to_template(cropped_mask, template, incut_percent=5.0)
    alpha = np.zeros(cropped_bgr.shape[:2], dtype=np.uint8)
    template_area = fitted_template > 127
    alpha[template_area] = 255
    cropped_bgr[~template_area] = [255, 255, 255]

    rgba = cv2.cvtColor(cropped_bgr, cv2.COLOR_BGR2BGRA)
    rgba[:, :, 3] = alpha
    transparent_holes = (cropped_mask == 0) & template_area
    rgba[transparent_holes, :3] = [255, 255, 255]
    rgba[transparent_holes, 3] = 255

    target_w, target_h = _standard_token_size(shape)
    # For symmetric (square-target) shapes — round/octagon/diamond — pad the canvas
    # to a square before resizing to the fixed token size. Otherwise a non-square
    # content bounding box (e.g. a tall glyph) gets squished into the square target,
    # turning a circular cut into an oval. This is a no-op for already-square canvases
    # and never touches the operative shape (which has a non-square target).
    if target_w == target_h and rgba.shape[0] != rgba.shape[1]:
        side = max(rgba.shape[0], rgba.shape[1])
        padded = np.zeros((side, side, 4), dtype=rgba.dtype)
        y_off = (side - rgba.shape[0]) // 2
        x_off = (side - rgba.shape[1]) // 2
        padded[y_off:y_off + rgba.shape[0], x_off:x_off + rgba.shape[1]] = rgba
        rgba = padded
    if rgba.shape[1] != target_w or rgba.shape[0] != target_h:
        rgba = cv2.resize(rgba, (target_w, target_h), interpolation=cv2.INTER_AREA)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with stable_write(output_path):
        ok = bool(cv2.imwrite(str(output_path), rgba))
    return ok


def _process_tokens_phase2(team_slug: str, input_dir: Path, output_dir: Path,
                           templates: Dict[str, np.ndarray]) -> int:
    metadata_by_file: Dict[str, dict] = {}
    metadata_path = input_dir / "extraction-metadata.json"
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(metadata, dict):
                metadata_list = metadata.get("tokens", [])
            elif isinstance(metadata, list):
                metadata_list = metadata
            else:
                metadata_list = []
            for item in metadata_list:
                filename = item.get("filename", "")
                if filename:
                    metadata_by_file[filename] = item
        except Exception as e:
            logger.warning(f"  {team_slug}: could not load extraction metadata: {e}")

    token_files = list(input_dir.glob("*.png"))
    if not token_files:
        return 0

    success = 0
    for token_path in token_files:
        if token_path.name.startswith("_"):
            continue
        meta = metadata_by_file.get(token_path.name, {})
        token_name = meta.get("name", token_path.stem)
        shape = _get_token_shape(team_slug, token_name, meta)
        output_path = output_dir / f"{team_slug}-{token_path.name}"
        if _process_token(token_path, output_path, shape, templates):
            success += 1
    return success


# ========================================
# Orchestration
# ========================================

def _extract_team(team: str) -> bool:
    extractor = IntegrationTokenExtractor(
        output_base_dir=TOKEN_WORK_ROOT,
        text_gap_max=6.0,
        same_line_y_max=15.0,
        next_line_y_min=5.0,
        next_line_y_max=25.0,
        next_line_x_overlap_ratio=0.25,
        name_match_max_distance=300.0,
    )

    if not extractor.find_marker_guides(team):
        logger.info(f"  {team}: no token-guide page in manifest — skipping")
        return None  # not a failure: this team simply has no tokens

    ok = extractor.process_team_auto_tuned(team, method="auto", debug=False,
                                           clean=False, expected_token_count=None)
    if not ok:
        logger.warning(f"  {team}: phase 1 (rough extraction) failed")
        return False

    token_dir = TOKEN_WORK_ROOT / team / "token"
    if not token_dir.exists():
        logger.warning(f"  {team}: no rough tokens produced")
        return False

    try:
        templates = {
            "operative": _load_template(TOKEN_TEMPLATE_DIR / "template-operative-cutter.png"),
            "round": _load_template(TOKEN_TEMPLATE_DIR / "template-round-cutter.png"),
            "octagon": _load_template(TOKEN_TEMPLATE_DIR / "template-octagon-cutter.png"),
            "diamond": _load_template(TOKEN_TEMPLATE_DIR / "template-diamond-cutter.png"),
        }
    except Exception as e:
        logger.warning(f"  {team}: failed to load shape templates: {e}")
        return False

    output_tokens_dir = paths.team_output(team) / "tokens"
    output_tokens_dir.mkdir(parents=True, exist_ok=True)
    # Clean stale top-level token textures/meshes so tokens excluded or renamed
    # since the previous run don't linger (regeneration is authoritative). The
    # tokenbag/ subdir is left alone — _emit_token_meshes overwrites it.
    for stale in list(output_tokens_dir.glob(f"{team}-*.png")) + list(output_tokens_dir.glob(f"{team}-*.obj")):
        try:
            stale.unlink()
        except Exception:
            pass
    count = _process_tokens_phase2(team, token_dir, output_tokens_dir, templates)
    if count == 0:
        logger.warning(f"  {team}: no tokens processed")
        return False

    _emit_token_meshes(team, output_tokens_dir)
    _generate_counter_tokens_for_team(team, output_tokens_dir)

    logger.info(f"  {team}: {count} tokens -> output/{team}/tokens/")
    return True


def _generate_counter_tokens_for_team(team: str, output_tokens_dir: Path) -> int:
    """Render min..max numbered images for any operative_counter that has a
    ``generate`` block, into output/{team}/tokens/counters/ -- a subfolder the box
    dispenser scan ignores (glob is non-recursive), so they stay counter-only art
    and never become physical box tokens. Authoritative: clears the subfolder first.
    """
    try:
        cfg = yaml.safe_load(paths.TEAM_CONFIG.read_text(encoding="utf-8")) or {}
    except Exception as e:
        logger.warning(f"  {team}: could not read team config for counters: {e}")
        return 0
    team_info = (cfg.get("teams") or {}).get(team) or {}
    counters = team_info.get("operative_counters") or []
    gen = [c for c in counters if isinstance(c, dict) and c.get("generate")]
    if not gen:
        return 0

    from ..utils.counter_tokens import (
        generate_counter_tokens, counter_slug, COUNTERS_SUBDIR, _style_kwargs,
    )
    counters_dir = output_tokens_dir / COUNTERS_SUBDIR
    if counters_dir.exists():
        for stale in counters_dir.glob("*.png"):
            try:
                stale.unlink()
            except Exception:
                pass
    custom_dir = paths.team_config_dir(team) / "custom-tokens" / COUNTERS_SUBDIR
    total = 0
    for c in gen:
        g = c["generate"] or {}
        bg = custom_dir / str(g.get("background", ""))
        if not bg.exists():
            logger.warning(f"  {team}: counter '{c.get('name')}' background not found: {bg}")
            continue
        lo = int(c.get("min", 1))
        hi = int(c.get("max", lo))
        slug = counter_slug(c.get("name", "counter"))
        written = generate_counter_tokens(bg, range(lo, hi + 1), counters_dir, slug, **_style_kwargs(g))
        total += len(written)
    if total:
        logger.info(f"  {team}: {total} counter tokens -> output/{team}/tokens/{COUNTERS_SUBDIR}/")
    return total


def _emit_token_meshes(team: str, output_tokens_dir: Path) -> None:
    """Copy the shared 3-D assets alongside the extracted token textures:

    - a per-token ``{name}.obj`` (single shared quad template) for every ``*.png``
    - ``tokenbag/{team}-token-bag.obj`` (shared bag mesh)
    - ``tokenbag/{team}-token-bag-icon.png`` (the team token icon, copied as-is)

    All three are byte-identical to production; nothing is generated here.
    """
    if TOKEN_MESH_TEMPLATE.exists():
        for png in sorted(output_tokens_dir.glob(f"{team}-*.png")):
            shutil.copy2(TOKEN_MESH_TEMPLATE, png.with_suffix(".obj"))
    else:
        logger.warning(f"  {team}: token mesh template missing ({TOKEN_MESH_TEMPLATE})")

    bag_dir = output_tokens_dir / "tokenbag"
    bag_dir.mkdir(parents=True, exist_ok=True)
    if TOKEN_BAG_MESH_TEMPLATE.exists():
        shutil.copy2(TOKEN_BAG_MESH_TEMPLATE, bag_dir / f"{team}-token-bag.obj")
    else:
        logger.warning(f"  {team}: token-bag mesh template missing ({TOKEN_BAG_MESH_TEMPLATE})")

    icon_src = paths.integration_team_dir(team) / "artwork" / "icons" / f"{team}-icon-token.jpg"
    if icon_src.exists():
        shutil.copy2(icon_src, bag_dir / f"{team}-token-bag-icon.png")
    else:
        logger.warning(f"  {team}: token icon source missing ({icon_src})")


def get_all_teams() -> List[str]:
    """Integration teams whose manifest declares a token guide."""
    if not paths.INTEGRATION.exists():
        return []
    teams = []
    for d in sorted(paths.INTEGRATION.iterdir()):
        if not d.is_dir():
            continue
        manifest = d / "manifest.json"
        if not manifest.exists():
            continue
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("token_guide"):
            teams.append(d.name)
    return teams


def _inputs_for(team: str) -> list:
    """Source files this step consumes: the manifest + classified PDFs (the token
    guide is among them), any custom-token overrides, the team icon (copied as the
    bag icon), and the shared team config (token shape/name lookups)."""
    team_dir = paths.integration_team_dir(team)
    inputs = [
        paths.integration_manifest_file(team),
        paths.TEAM_CONFIG,
        team_dir / "artwork" / "icons" / f"{team}-icon-token.jpg",
    ]
    inputs.extend(sorted(team_dir.glob("*.pdf")))
    inputs.extend(sorted((paths.team_config_dir(team) / "custom-tokens").glob("*.png")))
    return inputs


def run(teams: Optional[list] = None, source=None, force: bool = False):
    """Orchestrator entry point. Shared step — ``source`` is ignored."""
    if teams is None:
        teams = get_all_teams()
    if not teams:
        logger.error("No integration teams with a token guide found")
        return {"processed": 0, "failed": 0}

    logger.info(f"extract_tokens: {len(teams)} team(s)")

    processed = failed = skipped = 0
    newly_ready: list = []  # teams confirmed complete this run -> flag tokens_ready
    for team in teams:
        logger.info(f"[{team}]")
        if team_config.asset_ready(team, "tokens") and not force:
            logger.info("  tokens_ready in config, skip")
            skipped += 1
            continue
        state = StateManager(team)
        inputs = _inputs_for(team)
        if state.can_skip("extract_tokens", inputs, force):
            logger.info("  unchanged, skip")
            skipped += 1
            newly_ready.append(team)  # asset present -> mark done
            continue

        try:
            ok = _extract_team(team)
        except Exception as e:
            logger.warning(f"  {team}: extraction error: {e}")
            ok = False
        finally:
            # Per-team scratch cleanup: remove only THIS team's work dir so
            # parallel workers never delete each other's in-progress extraction
            # (the old global rmtree of TOKEN_WORK_ROOT raced under --jobs).
            shutil.rmtree(TOKEN_WORK_ROOT / team, ignore_errors=True)

        if ok is None:
            skipped += 1  # no token guide -> nothing to do (not a failure)
            newly_ready.append(team)  # nothing to make -> done
            continue
        if not ok:
            failed += 1
            continue

        processed += 1
        tokens_dir = paths.team_output(team) / "tokens"
        for f in sorted(tokens_dir.glob(f"{team}-*.png")):
            state.record_output("extract_tokens", f"tokens/{f.name}", f)
        for f in sorted(tokens_dir.glob(f"{team}-*.obj")):
            state.record_output("extract_tokens", f"tokens/{f.name}", f)
        bag_dir = tokens_dir / "tokenbag"
        for f in sorted(bag_dir.glob("*")):
            if f.is_file():
                state.record_output("extract_tokens", f"tokens/tokenbag/{f.name}", f)
        state.record_inputs("extract_tokens", inputs)
        state.mark_complete("extract_tokens")
        state.save()
        newly_ready.append(team)

    n = team_config.mark_ready((t, "tokens") for t in newly_ready)
    if n:
        logger.info(f"  set tokens_ready for {n} team(s)")
    StateIndex().rebuild_and_save()
    logger.info(f"extract_tokens done: processed={processed} skipped={skipped} failed={failed}")
    return {"processed": processed, "skipped": skipped, "failed": failed}
