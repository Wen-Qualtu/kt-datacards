"""Shared icon + artwork extraction.

The kt-app and warcom ``2a_extract_icons_and_artwork`` scripts were ~95%
identical — the only real difference was *where the raw PDF comes from* and *how
the team is resolved*. This module holds the single shared implementation of the
actual pixel work so the two tracks never drift apart. All functions operate on
an already-open ``fitz.Document`` + an output directory, so the caller owns IO
and team resolution.

Icons produced:
  - ``{team}-icon-token.jpg``              token-bag icon (KILL TEAM page)
  - ``{team}-icon-token-transparent.png``  transparent variant (dice / backsides)
  - ``{team}-icon-portrait.jpg``           warcom card-backside icon (page 0) *
  - ``{team}-icon-landscape.jpg``          warcom card-backside icon (page 0) *

  * portrait/landscape only exist on the warcom datacards PDF (page 0 card-back
    grid). The integrated downstream (dice / box texture / backsides / TTS) uses
    only the token + transparent variants, so the kt-app track never needs them.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Crop coordinates (fraction of page dimensions). Verified identical across both
# tracks' KILL TEAM / card-back pages.
# ---------------------------------------------------------------------------
# Token-bag icon (KILL TEAM / operatives selection page).
TOKEN_ICON_X1 = 0.1288
TOKEN_ICON_Y1 = 0.1625
TOKEN_ICON_X2 = 0.2724
TOKEN_ICON_Y2 = 0.2613

# Card-backside icons (warcom datacards PDF, page 0 only).
PORTRAIT_ICON_X1 = 0.0243
PORTRAIT_ICON_Y1 = 0.0006
PORTRAIT_ICON_X2 = 0.1620
PORTRAIT_ICON_Y2 = 0.1324

LANDSCAPE_ICON_X1 = 0.0008
LANDSCAPE_ICON_Y1 = 0.0232
LANDSCAPE_ICON_X2 = 0.1839
LANDSCAPE_ICON_Y2 = 0.1027

# When the page title "<NAME> KILL TEAM" wraps to a second line, everything below
# shifts down. This is detected directly from the splash-page title geometry (see
# ``title_wraps_on_page``) rather than guessed from name length, since equal-length
# names can wrap differently depending on glyph widths.
TITLE_WRAP_Y_OFFSET = 0.045

RENDER_SCALE = 5.0  # 5x DPI render for crisp card-scale icons


# ===========================================================================
# Artwork metadata
# ===========================================================================
@dataclass
class ArtworkImage:
    """Metadata for an extracted artwork image."""
    filename: str
    page_number: int
    width: int
    height: int
    aspect_ratio: float
    file_size_kb: int
    orientation: str
    xref: int
    image_hash: str = ""
    perceptual_hash: str = ""

    def to_dict(self):
        return asdict(self)


# ===========================================================================
# Hashing / dedup helpers
# ===========================================================================
def compute_image_hash(image_bytes: bytes) -> str:
    """SHA256 hash of image bytes for exact deduplication."""
    return hashlib.sha256(image_bytes).hexdigest()


def compute_perceptual_hash(image_bytes: bytes, hash_size: int = 16) -> str:
    """Perceptual hash (pHash) for visual-similarity detection."""
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return ""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size, hash_size), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(resized))
    dct_low = dct[:8, :8]
    median = np.median(dct_low)
    hash_bits = (dct_low > median).flatten()
    hash_int = 0
    for bit in hash_bits:
        hash_int = (hash_int << 1) | int(bit)
    return format(hash_int, "016x")


def hamming_distance(hash1: str, hash2: str) -> int:
    """Hamming distance between two hex hash strings."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    xor = int(hash1, 16) ^ int(hash2, 16)
    return bin(xor).count("1")


def load_generic_hashes(generic_dir: Path) -> Tuple[Set[str], Set[str]]:
    """Load exact + perceptual hashes from the generic-backgrounds folder."""
    exact_hashes: Set[str] = set()
    perceptual_hashes: Set[str] = set()
    if not generic_dir or not generic_dir.exists():
        return exact_hashes, perceptual_hashes
    metadata_path = generic_dir / "generic-artwork-metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                metadata = json.load(f)
            for img in metadata.get("images", []):
                if img.get("image_hash"):
                    exact_hashes.add(img["image_hash"])
                if img.get("perceptual_hash"):
                    perceptual_hashes.add(img["perceptual_hash"])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"    Failed to load generic metadata: {e}")
    return exact_hashes, perceptual_hashes


def get_image_orientation(width: int, height: int) -> str:
    aspect_ratio = width / height if height > 0 else 1.0
    if 0.95 <= aspect_ratio <= 1.05:
        return "square"
    if aspect_ratio > 1.05:
        return "landscape"
    return "portrait"


def is_likely_artwork(width: int, height: int, min_dimension: int = 500,
                      max_aspect_ratio: float = 3.0, min_area: int = 250000) -> bool:
    """Heuristic: large-ish, not-too-extreme aspect ratio => artwork (not an icon)."""
    if width < min_dimension and height < min_dimension:
        return False
    if width * height < min_area:
        return False
    smaller = min(width, height)
    aspect_ratio = max(width, height) / smaller if smaller > 0 else 999
    return aspect_ratio <= max_aspect_ratio


# ===========================================================================
# Pixel work
# ===========================================================================
def extract_icon_transparent(icon_bgr: np.ndarray, threshold: int = 80, margin: int = 30) -> np.ndarray:
    """Cut a bright icon onto a transparent background (dark pixels -> transparent).

    Token icons are bright (orange) shapes on a near-black background, so dark
    pixels become transparent and bright pixels stay opaque, with an edge fade.
    """
    brightness = icon_bgr.max(axis=2)
    alpha = np.where(brightness < threshold, 0, 255).astype(np.uint8)
    height, width = alpha.shape
    for y in range(height):
        for x in range(width):
            if alpha[y, x] == 255:
                dist_to_edge = min(min(x, width - 1 - x), min(y, height - 1 - y))
                if dist_to_edge < margin:
                    alpha[y, x] = int(255 * (dist_to_edge / margin))
    return np.dstack([icon_bgr, alpha])


def render_page_bgr(page: fitz.Page, scale: float = RENDER_SCALE) -> np.ndarray:
    """Render a page to a BGR numpy array at the given scale."""
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def _crop_fraction(img: np.ndarray, x1: float, y1: float, x2: float, y2: float) -> np.ndarray:
    h, w = img.shape[:2]
    return img[int(h * y1):int(h * y2), int(w * x1):int(w * x2)]


def find_kill_team_page(doc: fitz.Document, min_title_size: float = 30.0) -> int:
    """Return the index of the icon-splash page (large 'KILL TEAM' title), or -1.

    The icon-splash / selection page carries a large ~40pt "KILL TEAM" title and
    holds the team symbol at the icon crop. Other "KILL TEAM" occurrences are far
    smaller — the operatives-selection heading is ~18pt and body-text mentions are
    ~8-10pt — and their layouts do NOT have the symbol at the crop (they yield a
    text mis-crop). ``min_title_size`` (default 30pt, safely between 18 and 40)
    therefore accepts ONLY the splash page. When a source lacks a splash page
    (e.g. the compact app export or an older team-rules PDF), this returns -1 so no
    wrong icon is produced. Picking the LARGEST qualifying title also lands on the
    splash even when a PDF has several "KILL TEAM" pages (the warcom full-rules PDF
    has an 18pt operatives page plus the 40pt splash).
    """
    best_page = -1
    best_size = min_title_size
    for page_num, page in enumerate(doc):
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    size = span.get("size", 0)
                    if "KILL TEAM" in span.get("text", "").upper() and size > best_size:
                        best_size = size
                        best_page = page_num
    return best_page


def title_wraps_on_page(page: fitz.Page, min_title_size: float = 30.0) -> bool:
    """True if the splash title wraps so "KILL TEAM" sits on its own line.

    On short-name splashes the whole title is one line ("KOMMANDOS KILL TEAM");
    on long-name splashes the team name fills the first line and "KILL TEAM" drops
    to a second line, shifting the team symbol (and everything below) down. Detect
    that from the largest "KILL TEAM" title span: if the span carries only the words
    "KILL TEAM" (no team name on the same line), the title wrapped.
    """
    kt_text = None
    kt_size = min_title_size
    for block in page.get_text("dict").get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                size = span.get("size", 0)
                if "KILL TEAM" in span.get("text", "").upper() and size >= kt_size:
                    kt_size = size
                    kt_text = span.get("text", "")
    if kt_text is None:
        return False
    return kt_text.strip().upper() == "KILL TEAM"


def extract_token_icon(doc: fitz.Document, icons_dir: Path, team: str,
                       canonical_name: str = "") -> Dict[str, bool]:
    """Extract the token-bag icon (+ transparent variant) from the KILL TEAM page."""
    icons_dir.mkdir(parents=True, exist_ok=True)
    extracted = {"token": False, "token_transparent": False}

    page_num = find_kill_team_page(doc)
    if page_num == -1:
        return extracted

    title_wraps = title_wraps_on_page(doc[page_num])
    y_offset = TITLE_WRAP_Y_OFFSET if title_wraps else 0.0

    img = render_page_bgr(doc[page_num])
    token_icon = _crop_fraction(img, TOKEN_ICON_X1, TOKEN_ICON_Y1 + y_offset,
                                TOKEN_ICON_X2, TOKEN_ICON_Y2 + y_offset)

    cv2.imwrite(str(icons_dir / f"{team}-icon-token.jpg"), token_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
    extracted["token"] = True

    transparent = extract_icon_transparent(token_icon)
    cv2.imwrite(str(icons_dir / f"{team}-icon-token-transparent.png"), transparent)
    extracted["token_transparent"] = True
    return extracted


def extract_backside_icons(doc: fitz.Document, icons_dir: Path, team: str) -> Dict[str, bool]:
    """Extract portrait + landscape card-back icons from page 0 (warcom only)."""
    icons_dir.mkdir(parents=True, exist_ok=True)
    extracted = {"portrait": False, "landscape": False}
    if len(doc) == 0:
        return extracted

    img = render_page_bgr(doc[0])
    portrait = _crop_fraction(img, PORTRAIT_ICON_X1, PORTRAIT_ICON_Y1,
                              PORTRAIT_ICON_X2, PORTRAIT_ICON_Y2)
    cv2.imwrite(str(icons_dir / f"{team}-icon-portrait.jpg"), portrait, [cv2.IMWRITE_JPEG_QUALITY, 95])
    extracted["portrait"] = True

    landscape = _crop_fraction(img, LANDSCAPE_ICON_X1, LANDSCAPE_ICON_Y1,
                               LANDSCAPE_ICON_X2, LANDSCAPE_ICON_Y2)
    cv2.imwrite(str(icons_dir / f"{team}-icon-landscape.jpg"), landscape, [cv2.IMWRITE_JPEG_QUALITY, 95])
    extracted["landscape"] = True
    return extracted


def extract_artwork(doc: fitz.Document, artwork_dir: Path, team: str,
                    generic_exact: Optional[Set[str]] = None,
                    generic_perceptual: Optional[Set[str]] = None,
                    perceptual_threshold: int = 15,
                    start_counter: int = 0) -> List[ArtworkImage]:
    """Extract artwork images from a doc, skipping generic backgrounds/duplicates.

    ``start_counter`` lets a caller accumulate artwork across multiple docs of the
    same team without filename collisions.
    """
    artwork_dir.mkdir(parents=True, exist_ok=True)
    generic_exact = generic_exact or set()
    generic_perceptual = generic_perceptual or set()

    extracted_images: List[ArtworkImage] = []
    seen_xrefs: Set[int] = set()
    seen_hashes: Set[str] = set()
    counter = start_counter

    for page_num, page in enumerate(doc):
        for img_info in page.get_images(full=True):
            xref = img_info[0]
            if xref in seen_xrefs:
                continue
            try:
                base_image = doc.extract_image(xref)
                if not base_image:
                    continue
                image_bytes = base_image["image"]
                image_ext = base_image["ext"]
                width = base_image["width"]
                height = base_image["height"]

                if not is_likely_artwork(width, height):
                    continue

                exact_hash = compute_image_hash(image_bytes)
                perceptual = compute_perceptual_hash(image_bytes)

                if generic_exact and exact_hash in generic_exact:
                    seen_xrefs.add(xref)
                    continue
                if generic_perceptual and perceptual and any(
                    hamming_distance(perceptual, g) <= perceptual_threshold for g in generic_perceptual
                ):
                    seen_xrefs.add(xref)
                    continue
                if exact_hash in seen_hashes:
                    seen_xrefs.add(xref)
                    continue

                counter += 1
                filename = f"{team}-artwork-{counter:02d}.{image_ext}"
                with open(artwork_dir / filename, "wb") as f:
                    f.write(image_bytes)

                extracted_images.append(ArtworkImage(
                    filename=filename,
                    page_number=page_num + 1,
                    width=width,
                    height=height,
                    aspect_ratio=round(width / height if height else 1.0, 2),
                    file_size_kb=len(image_bytes) // 1024,
                    orientation=get_image_orientation(width, height),
                    xref=xref,
                    image_hash=exact_hash,
                    perceptual_hash=perceptual,
                ))
                seen_xrefs.add(xref)
                seen_hashes.add(exact_hash)
            except Exception as e:  # noqa: BLE001
                logger.debug(f"    Error extracting image xref {xref}: {e}")
                continue

    return extracted_images


def write_artwork_metadata(artwork_dir: Path, team: str, images: List[ArtworkImage]) -> None:
    """Write the per-team artwork metadata sidecar (only if there are images)."""
    if not images:
        return
    artwork_dir.mkdir(parents=True, exist_ok=True)
    with open(artwork_dir / f"{team}-artwork-metadata.json", "w", encoding="utf-8") as f:
        json.dump({
            "team": team,
            "total_images": len(images),
            "images": [img.to_dict() for img in images],
        }, f, indent=2)
