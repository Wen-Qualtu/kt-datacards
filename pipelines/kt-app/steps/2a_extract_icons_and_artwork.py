"""
Step 2a (kt-app): Extract icons and artwork from Kill Team Supplementary PDFs.

This is the kt-app counterpart to the warcom step of the same name. It works on
the "Supplementary Information" PDFs that ship in input/ (UUID-named). Those PDFs
contain the same final pages as the warcom downloads (operatives list + kill team
selection), so the same extraction logic applies — only the team is identified
from the PDF text instead of the filename.

It extracts:
  1. The team icon (orange shape on dark background) from the KILL TEAM page,
     plus a transparent PNG variant for dice / backside composition.
  2. Artwork / fluff images (with generic-background de-duplication).

Input:  input/*.pdf            (UUID-named supplementary PDFs)
Output: {output}/{team}/icons/
        {output}/{team}/artwork/

For the dev shake-out run we point --output-dir at dev/shared/ so the results can
be reviewed (and the missing team identified) before wiring it into the pipeline.

This module is intentionally self-contained: it copies the bits of logic it needs
from pipelines/warcom/steps/2a_extract_icons_and_artwork.py rather than importing
across pipelines.

Usage:
    python pipelines/kt-app/steps/2a_extract_icons_and_artwork.py \
        --input-dir input --output-dir dev/shared
"""
import argparse
import hashlib
import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import cv2
import fitz  # PyMuPDF
import numpy as np
import yaml

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# ---------------------------------------------------------------------------
# Icon extraction coordinates (as fraction of page dimensions).
# These match the warcom token-bag icon crop and have been verified to transfer
# directly to the supplementary PDFs' KILL TEAM page.
# ---------------------------------------------------------------------------
TOKEN_ICON_X1 = 0.1288
TOKEN_ICON_Y1 = 0.1625
TOKEN_ICON_X2 = 0.2724
TOKEN_ICON_Y2 = 0.2613

# When the page title "<NAME> KILL TEAM" wraps onto a second line everything
# below it shifts down. Empirically this happens once the canonical name exceeds
# 22 chars.
TITLE_WRAP_THRESHOLD_CHARS = 22
TITLE_WRAP_Y_OFFSET = 0.045


# ===========================================================================
# Artwork helpers (copied/adapted from warcom 2a)
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


def compute_image_hash(image_bytes: bytes) -> str:
    """SHA256 hash of image bytes for exact deduplication."""
    return hashlib.sha256(image_bytes).hexdigest()


def compute_perceptual_hash(image_bytes: bytes, hash_size: int = 16) -> str:
    """Perceptual hash (pHash) for visual similarity detection."""
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
    return format(hash_int, '016x')


def hamming_distance(hash1: str, hash2: str) -> int:
    """Hamming distance between two hex hash strings."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    xor = int(hash1, 16) ^ int(hash2, 16)
    return bin(xor).count('1')


def load_generic_hashes(generic_dir: Path) -> Tuple[Set[str], Set[str]]:
    """Load image hashes from the generic backgrounds folder."""
    exact_hashes: Set[str] = set()
    perceptual_hashes: Set[str] = set()
    if not generic_dir.exists():
        return exact_hashes, perceptual_hashes
    metadata_path = generic_dir / 'generic-artwork-metadata.json'
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            for img in metadata.get('images', []):
                if img.get('image_hash'):
                    exact_hashes.add(img['image_hash'])
                if img.get('perceptual_hash'):
                    perceptual_hashes.add(img['perceptual_hash'])
        except Exception as e:  # noqa: BLE001
            logger.warning(f"    Failed to load generic metadata: {e}")
    return exact_hashes, perceptual_hashes


def get_image_orientation(width: int, height: int) -> str:
    aspect_ratio = width / height if height > 0 else 1.0
    if 0.95 <= aspect_ratio <= 1.05:
        return 'square'
    if aspect_ratio > 1.05:
        return 'landscape'
    return 'portrait'


def is_likely_artwork(width: int, height: int, min_dimension: int = 500,
                      max_aspect_ratio: float = 3.0, min_area: int = 250000) -> bool:
    if width < min_dimension and height < min_dimension:
        return False
    if width * height < min_area:
        return False
    aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 999
    if aspect_ratio > max_aspect_ratio:
        return False
    return True


def extract_icon_transparent(icon_bgr: np.ndarray, threshold: int = 80, margin: int = 30) -> np.ndarray:
    """Cut out a bright icon onto a transparent background (dark -> transparent)."""
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


# ===========================================================================
# Team identification (new for kt-app — input PDFs are UUID-named)
# ===========================================================================
def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def load_team_lookup() -> Dict[str, str]:
    """Build a normalized-name -> slug lookup from team-config.yaml."""
    cfg_path = PROJECT_ROOT / 'config' / 'team-config.yaml'
    lookup: Dict[str, str] = {}
    if not cfg_path.exists():
        return lookup
    with open(cfg_path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    for slug, cfg in (data.get('teams') or {}).items():
        cfg = cfg or {}
        lookup[_slugify(slug)] = slug
        canonical = cfg.get('canonical_name', '')
        if canonical:
            lookup[_slugify(canonical)] = slug
        for alias in cfg.get('aliases') or []:
            lookup[_slugify(alias)] = slug
    return lookup


def _canonical_name_for(slug: str) -> str:
    cfg_path = PROJECT_ROOT / 'config' / 'team-config.yaml'
    if not cfg_path.exists():
        return ''
    with open(cfg_path, encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    return ((data.get('teams') or {}).get(slug) or {}).get('canonical_name', '')


def _big_spans(doc: fitz.Document, min_size: float = 28.0) -> List[Tuple[int, float, str]]:
    spans: List[Tuple[int, float, str]] = []
    for page_num, page in enumerate(doc):
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if span.get("size", 0) >= min_size:
                        text = span.get("text", "").replace("\x08", "").strip()
                        if text:
                            spans.append((page_num, round(span["size"], 1), text))
    return spans


def identify_team(pdf_path: Path, lookup: Dict[str, str]) -> Optional[str]:
    """
    Determine the team slug for a supplementary PDF from its title text.

    Primary signal: page 0 "<NAME>: UPDATE LOG".
    Fallback: "<NAME> KILL TEAM" selection-page title.
    """
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"  Could not open {pdf_path.name}: {e}")
        return None

    candidates: List[str] = []
    try:
        spans = _big_spans(doc)
    finally:
        doc.close()

    for _page, _size, text in spans:
        upper = text.upper()
        if "UPDATE LOG" in upper:
            candidates.append(upper.split(":")[0].replace("UPDATE LOG", "").strip())
        elif "KILL TEAM" in upper:
            candidates.append(upper.replace("KILL TEAM", "").replace("SELECTION", "").strip())

    for name in candidates:
        slug = lookup.get(_slugify(name))
        if slug:
            return slug

    # Last resort: substring match of any known name within the gathered titles
    joined = " ".join(_slugify(c) for c in candidates)
    for norm_name, slug in lookup.items():
        if norm_name and norm_name in joined:
            return slug
    return None


def find_kill_team_page(doc: fitz.Document) -> int:
    """Find the page with large 'KILL TEAM' text (kill team selection page)."""
    for page_num, page in enumerate(doc):
        for block in page.get_text("dict").get("blocks", []):
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    if "KILL TEAM" in span.get("text", "").upper() and span.get("size", 0) > 20:
                        return page_num
    return -1


# ===========================================================================
# Extraction
# ===========================================================================
def extract_token_icon(doc: fitz.Document, output_dir: Path, team_name: str,
                       canonical_name: str = "") -> dict:
    """Extract the team token icon (+ transparent variant) from the KILL TEAM page."""
    icons_dir = output_dir / 'icons'
    icons_dir.mkdir(parents=True, exist_ok=True)
    extracted = {'token': False, 'token_transparent': False}

    title_wraps = bool(canonical_name) and len(canonical_name) > TITLE_WRAP_THRESHOLD_CHARS
    token_y_offset = TITLE_WRAP_Y_OFFSET if title_wraps else 0.0

    page_num = find_kill_team_page(doc)
    if page_num == -1:
        logger.warning(f"    No KILL TEAM page found for {team_name}")
        return extracted

    page = doc[page_num]
    pix = page.get_pixmap(matrix=fitz.Matrix(5.0, 5.0))
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
    h, w = pix.height, pix.width

    x1 = int(w * TOKEN_ICON_X1)
    y1 = int(h * (TOKEN_ICON_Y1 + token_y_offset))
    x2 = int(w * TOKEN_ICON_X2)
    y2 = int(h * (TOKEN_ICON_Y2 + token_y_offset))
    token_icon = img[y1:y2, x1:x2]

    token_path = icons_dir / f'{team_name}-icon-token.jpg'
    cv2.imwrite(str(token_path), token_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
    extracted['token'] = True

    transparent = extract_icon_transparent(token_icon)
    cv2.imwrite(str(icons_dir / f'{team_name}-icon-token-transparent.png'), transparent)
    extracted['token_transparent'] = True
    return extracted


def extract_artwork(doc: fitz.Document, output_dir: Path, team_name: str,
                    generic_exact: Set[str], generic_perceptual: Set[str],
                    perceptual_threshold: int = 15) -> List[ArtworkImage]:
    """Extract artwork images from the PDF, skipping generic backgrounds/duplicates."""
    artwork_dir = output_dir / 'artwork'
    artwork_dir.mkdir(parents=True, exist_ok=True)

    extracted_images: List[ArtworkImage] = []
    seen_xrefs: Set[int] = set()
    seen_hashes: Set[str] = set()
    counter = 0

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
                    hamming_distance(perceptual, g) <= perceptual_threshold
                    for g in generic_perceptual
                ):
                    seen_xrefs.add(xref)
                    continue
                if exact_hash in seen_hashes:
                    seen_xrefs.add(xref)
                    continue

                counter += 1
                filename = f'{team_name}-artwork-{counter:02d}.{image_ext}'
                with open(artwork_dir / filename, 'wb') as f:
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

    if extracted_images:
        with open(artwork_dir / f'{team_name}-artwork-metadata.json', 'w') as f:
            json.dump({
                'team': team_name,
                'total_images': len(extracted_images),
                'images': [img.to_dict() for img in extracted_images],
            }, f, indent=2)
    return extracted_images


def process_pdf(pdf_path: Path, output_dir: Path, lookup: Dict[str, str],
                generic_exact: Set[str], generic_perceptual: Set[str]) -> dict:
    """Identify the team for a PDF and extract its icon + artwork."""
    team_name = identify_team(pdf_path, lookup)
    if not team_name:
        logger.warning(f"  ? Could not identify team for {pdf_path.name}")
        return {'team': None, 'pdf': pdf_path.name, 'icons': 0, 'artwork': 0}

    canonical = _canonical_name_for(team_name)
    team_output = output_dir / team_name
    team_output.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf_path)
    try:
        icons = extract_token_icon(doc, team_output, team_name, canonical)
        artwork = extract_artwork(doc, team_output, team_name, generic_exact, generic_perceptual)
    finally:
        doc.close()

    icons_count = sum(1 for v in icons.values() if v)
    logger.info(f"  ✓ {team_name}: {icons_count} icon files, {len(artwork)} artwork")
    return {'team': team_name, 'pdf': pdf_path.name, 'icons': icons_count, 'artwork': len(artwork)}


def run(input_dir: Path = None, output_dir: Path = None, generic_dir: Path = None,
        max_workers: int = 1) -> dict:
    input_dir = Path(input_dir) if input_dir else PROJECT_ROOT / 'input'
    output_dir = Path(output_dir) if output_dir else PROJECT_ROOT / 'layers' / 'shared'
    generic_dir = Path(generic_dir) if generic_dir else PROJECT_ROOT / 'layers' / 'warcom' / 'extracted' / '_generic'

    logger.info("=" * 70)
    logger.info("kt-app Step 2a: Extract Icons and Artwork from Supplementary PDFs")
    logger.info("=" * 70)

    pdf_files = sorted(input_dir.glob('*.pdf'))
    if not pdf_files:
        logger.error(f"No PDF files found in {input_dir}")
        return {'success': False, 'processed': 0}

    lookup = load_team_lookup()
    all_slugs = sorted(set(lookup.values()))
    generic_exact, generic_perceptual = load_generic_hashes(generic_dir)

    logger.info(f"Found {len(pdf_files)} PDFs | {len(all_slugs)} teams in config")
    logger.info(f"Output: {output_dir}")
    logger.info("")

    results: List[dict] = []
    if max_workers <= 1:
        # PyMuPDF (fitz) is not thread-safe; sequential is the reliable default.
        for pdf in pdf_files:
            try:
                results.append(process_pdf(pdf, output_dir, lookup, generic_exact, generic_perceptual))
            except Exception as e:  # noqa: BLE001
                logger.error(f"✗ Failed {pdf.name}: {e}")
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(process_pdf, pdf, output_dir, lookup, generic_exact, generic_perceptual)
                for pdf in pdf_files
            ]
            for future in futures:
                try:
                    results.append(future.result())
                except Exception as e:  # noqa: BLE001
                    logger.error(f"✗ Failed: {e}")

    identified = {r['team'] for r in results if r['team']}
    unidentified = [r['pdf'] for r in results if not r['team']]
    missing_teams = [s for s in all_slugs if s not in identified]

    logger.info("")
    logger.info("=" * 70)
    logger.info("Summary")
    logger.info("=" * 70)
    logger.info(f"  PDFs processed : {len(results)}")
    logger.info(f"  Teams identified: {len(identified)}")
    logger.info(f"  Total icons     : {sum(r['icons'] for r in results)}")
    logger.info(f"  Total artwork   : {sum(r['artwork'] for r in results)}")
    if unidentified:
        logger.info(f"  Unidentified PDFs ({len(unidentified)}): {', '.join(unidentified)}")
    logger.info("")
    logger.info(f"  Teams in config but MISSING a PDF ({len(missing_teams)}):")
    for slug in missing_teams:
        logger.info(f"    - {slug}")

    summary = {
        'success': True,
        'processed': len(results),
        'identified': sorted(identified),
        'unidentified': unidentified,
        'missing_teams': missing_teams,
        'results': results,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    with open(output_dir / '_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)

    return summary


def main():
    parser = argparse.ArgumentParser(description='Extract icons/artwork from supplementary Kill Team PDFs (kt-app)')
    parser.add_argument('--input-dir', type=Path, default=PROJECT_ROOT / 'input',
                        help='Input directory with supplementary PDFs (default: input/)')
    parser.add_argument('--output-dir', type=Path, default=PROJECT_ROOT / 'layers' / 'shared',
                        help='Output directory (default: layers/shared; use dev/shared for dev runs)')
    parser.add_argument('--generic-dir', type=Path,
                        default=PROJECT_ROOT / 'layers' / 'warcom' / 'extracted' / '_generic',
                        help='Folder with generic-artwork-metadata.json for dedup')
    parser.add_argument('--workers', type=int, default=1,
                        help='Concurrent workers (default 1; PyMuPDF is not thread-safe)')
    args = parser.parse_args()

    result = run(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        generic_dir=args.generic_dir,
        max_workers=args.workers,
    )
    exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
