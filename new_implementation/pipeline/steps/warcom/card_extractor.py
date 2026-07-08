"""Split a warcom team-rules PDF into per-card PDFs.

Standalone port of the legacy step-2b card extractor, reduced to its essential
job: detect the per-page card layout via corner ``+`` markers and crop each card
out as its own single-page PDF (text layer preserved).

Deliberately removed from the legacy version:
  - PNG rasters of each card (only PDFs are needed downstream now).
  - Token rough-crop + metadata. Tokens are produced once per team by the shared
    ``extract_tokens`` step, not during card extraction.
"""
from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Dict, Optional

import cv2
import fitz  # PyMuPDF
import numpy as np
import yaml

from ...utils import fileio

logger = logging.getLogger(__name__)

# A 3x3 "+" marker used to detect card corners on a rendered page.
_MARKER_TEMPLATE = np.array(
    [[0, 1, 0], [1, 1, 1], [0, 1, 0]], dtype=np.uint8
) * 255


# ---------------------------------------------------------------------------
# Config / team identification
# ---------------------------------------------------------------------------

def load_templates(template_file: Path) -> dict:
    """Load the landscape/portrait card-coordinate templates."""
    with open(template_file, encoding="utf-8") as f:
        return json.load(f)


def load_team_config(config_file: Path) -> Dict[str, dict]:
    """Load the ``teams`` map from team-config.yaml."""
    if not config_file.exists():
        return {}
    with open(config_file, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return (data or {}).get("teams", {})


def _normalize(name: str) -> str:
    return name.lower().replace("-", " ").replace("_", " ").strip()


def match_team_name(extracted_name: str, team_config: Dict[str, dict]) -> Optional[str]:
    """Match an extracted team name to a config key (via canonical name + aliases)."""
    if not team_config:
        return None
    target = _normalize(extracted_name)
    for config_key, config_data in team_config.items():
        canonical = config_data.get("canonical_name", config_key)
        if target == _normalize(canonical):
            return config_key.lower().replace(" ", "-")
    for config_key, config_data in team_config.items():
        for alias in config_data.get("aliases", []):
            if target == _normalize(alias):
                return config_key.lower().replace(" ", "-")
    return None


def extract_team_name_from_pdf(pdf_path: Path) -> str:
    """Best-effort team name from the largest team-name-like text near the end of the PDF.

    Fragile by nature (relies on font size); callers should fall back to a slug of
    the filename when this returns an empty string.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        logger.warning(f"  could not open {pdf_path.name}: {e}")
        return ""

    best_name: Optional[str] = None
    max_font_size = 0.0
    try:
        start_page = max(0, len(doc) - 5)
        for page_num in range(start_page, len(doc)):
            text_dict = doc[page_num].get_text("dict")
            for block in text_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        text = span.get("text", "").strip()
                        font_size = span.get("size", 0)
                        if font_size < 20 or len(text) < 3:
                            continue
                        if font_size <= max_font_size:
                            continue
                        clean = text.upper().strip()
                        if clean == "KILL TEAM":
                            continue
                        if re.search(r"[A-Z]{3,}", clean):
                            max_font_size = font_size
                            best_name = clean
    finally:
        doc.close()

    if not best_name:
        return ""
    best_name = re.sub(r"\s*KILL\s*TEAM\s*$", "", best_name, flags=re.IGNORECASE)
    best_name = re.sub(r"\s*OPERATIVES?\s*$", "", best_name, flags=re.IGNORECASE)
    best_name = best_name.lower().replace(" ", "-").replace("_", "-")
    return re.sub(r"[^a-z0-9-]", "", best_name)


# ---------------------------------------------------------------------------
# Marker detection / template matching
# ---------------------------------------------------------------------------

def find_markers(img: np.ndarray, threshold: float = 0.55) -> list:
    """Find ``+`` corner markers via edge-based template matching.

    Returns a list of ``(x, y, confidence)`` centres, de-duplicated within 30px.
    """
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)
    result = cv2.matchTemplate(edges, _MARKER_TEMPLATE, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= threshold)

    h, w = _MARKER_TEMPLATE.shape
    markers = [
        (int(x + w / 2), int(y + h / 2), float(result[y, x]))
        for x, y in zip(*locations[::-1])
    ]
    if not markers:
        return []

    markers.sort(key=lambda m: m[2], reverse=True)
    unique: list = []
    for mx, my, conf in markers:
        if any(abs(mx - ux) < 30 and abs(my - uy) < 30 for ux, uy, _ in unique):
            continue
        unique.append((mx, my, conf))
    return unique


def template_marker_positions(template: dict) -> list:
    """Expected corner-marker positions for a template (de-duplicated shared corners)."""
    markers: list = []
    seen: set = set()
    for card in template["cards"]:
        for corner in ("top_left", "top_right", "bottom_left", "bottom_right"):
            pos = tuple(card[corner])
            if pos not in seen:
                seen.add(pos)
                markers.append((pos[0], pos[1], 1.0))
    return markers


def _scale_markers(markers: list, scale: float) -> list:
    return [(int(x * scale), int(y * scale), conf) for x, y, conf in markers]


def _match_score(detected: list, expected: list, tolerance: int = 5) -> float:
    total = 0.0
    for ex, ey, _ in expected:
        best = 0.0
        for dx, dy, conf in detected:
            if ((dx - ex) ** 2 + (dy - ey) ** 2) ** 0.5 <= tolerance and conf > best:
                best = conf
        total += best
    return total


def detect_page_template(img: np.ndarray, templates: dict, dpi_scale: float) -> Optional[str]:
    """Return 'landscape', 'portrait', or None for the best-fitting page template."""
    detected = find_markers(img, threshold=0.5)
    if len(detected) < 5:
        return None

    landscape = _scale_markers(template_marker_positions(templates["landscape"]), dpi_scale)
    portrait = _scale_markers(template_marker_positions(templates["portrait"]), dpi_scale)

    landscape_score = _match_score(detected, landscape)
    portrait_score = _match_score(detected, portrait)

    # Require ~70% of expected markers at avg confidence > 0.5.
    if landscape_score < len(landscape) * 0.7 * 0.5 and \
            portrait_score < len(portrait) * 0.7 * 0.5:
        return None
    return "landscape" if landscape_score > portrait_score else "portrait"


# ---------------------------------------------------------------------------
# Rendering / cropping
# ---------------------------------------------------------------------------

def render_page_to_image(page: fitz.Page, dpi: int = 150) -> np.ndarray:
    """Render a PDF page to a BGR image."""
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    if pix.n == 4:
        return cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
    if pix.n == 3:
        return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    if pix.n == 1:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


# Extra inward crop applied to every card side, in template-coord units (1 unit
# ≈ 2 px in the final 300-DPI render). The scraped source cards carry a thin light
# cut-line margin at their edges; nudging the crop in a few px drops it. Tunable —
# raise if an edge line remains, lower if it eats into card content.
_EDGE_INSET = 4


def save_single_card_as_pdf(page: fitz.Page, card_coords: dict, output_path: Path,
                            dpi: int = 150) -> None:
    """Crop one card region from ``page`` and save it as a single-page PDF (text preserved).

    Uses the per-card marker template coords + ``adjust`` to place the crop at the
    card boundary, then insets every side by ``_EDGE_INSET`` to drop the source
    card's thin cut-line margin (a few px on the cut sides).
    """
    scale = dpi / 300.0  # template coords are at 300 DPI
    pdf_scale = 72 / dpi  # image px -> PDF points

    corners = {k: (card_coords[k][0] * scale, card_coords[k][1] * scale)
               for k in ("top_left", "top_right", "bottom_left", "bottom_right")}
    left = min(corners["top_left"][0], corners["bottom_left"][0]) * pdf_scale
    top = min(corners["top_left"][1], corners["top_right"][1]) * pdf_scale
    right = max(corners["top_right"][0], corners["bottom_right"][0]) * pdf_scale
    bottom = max(corners["bottom_left"][1], corners["bottom_right"][1]) * pdf_scale

    adjust = card_coords.get("adjust")
    if adjust:
        left += adjust.get("left", 0) * pdf_scale
        top += adjust.get("top", 0) * pdf_scale
        right += adjust.get("right", 0) * pdf_scale
        bottom += adjust.get("bottom", 0) * pdf_scale

    inset = _EDGE_INSET * pdf_scale
    crop_rect = fitz.Rect(left + inset, top + inset, right - inset, bottom - inset)

    new_doc = fitz.open()
    new_page = new_doc.new_page(width=crop_rect.width, height=crop_rect.height)
    new_page.show_pdf_page(new_page.rect, page.parent, page.number, clip=crop_rect)

    fileio.safe_unlink(output_path)
    new_doc.save(str(output_path))
    new_doc.close()


def _card_filename(team_name: Optional[str], page_num: int, card_idx: int, template_type: str) -> str:
    prefix = f"{team_name}_" if team_name else ""
    return f"{prefix}page{page_num:02d}_card{card_idx}_{template_type}.pdf"


def extract_cards(pdf_path: Path, templates: dict, output_dir: Path,
                  team_name: Optional[str] = None, dpi: int = 150) -> dict:
    """Split ``pdf_path`` into per-card PDFs under ``output_dir``.

    Card pages carry corner markers; the first page without a recognised template
    marks the end of the card section, so processing stops there.

    Returns ``{'total_cards': int, 'pages_processed': int}``.
    """
    doc = fitz.open(pdf_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_cards = 0
    pages_processed = 0
    try:
        for page_num in range(1, len(doc) + 1):
            page = doc[page_num - 1]
            page_img = render_page_to_image(page, dpi)
            try:
                template_type = detect_page_template(page_img, templates, dpi / 300.0)
                if template_type is None:
                    break  # past the card section
                for card_idx, card_coords in enumerate(templates[template_type]["cards"], 1):
                    out_path = output_dir / _card_filename(team_name, page_num, card_idx, template_type)
                    save_single_card_as_pdf(page, card_coords, out_path, dpi)
                    total_cards += 1
                pages_processed += 1
            finally:
                del page_img
    finally:
        doc.close()

    return {"total_cards": total_cards, "pages_processed": pages_processed}
