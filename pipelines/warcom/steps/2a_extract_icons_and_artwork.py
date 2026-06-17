"""
Step 2a: Extract icons and artwork from Kill Team PDFs.

This step extracts:
1. Team icons (portrait, landscape, token bag) for card backsides
2. Artwork/fluff images for box textures and promotional materials

Input: PDFs in layers/warcom/staging/
Output: 
  - Icons in layers/warcom/extracted/{team}/icons/
  - Artwork in layers/warcom/extracted/{team}/artwork/
"""
import fitz  # PyMuPDF
import cv2
import numpy as np
import yaml
from pathlib import Path
import logging
import json
import hashlib
import argparse
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from concurrent.futures import ThreadPoolExecutor

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)


# Icon extraction coordinates (as percentage of page dimensions)
# Page 1 - Card backside icons
PORTRAIT_ICON_X1 = 0.0243
PORTRAIT_ICON_Y1 = 0.0006
PORTRAIT_ICON_X2 = 0.1620
PORTRAIT_ICON_Y2 = 0.1324

LANDSCAPE_ICON_X1 = 0.0008
LANDSCAPE_ICON_Y1 = 0.0232
LANDSCAPE_ICON_X2 = 0.1839
LANDSCAPE_ICON_Y2 = 0.1027

# Token bag icon page
TOKEN_ICON_X1 = 0.1288
TOKEN_ICON_Y1 = 0.1625
TOKEN_ICON_X2 = 0.2724
TOKEN_ICON_Y2 = 0.2613

# When the page title "KILL TEAM <name>" wraps onto a second line, everything
# below it (including the token icon) shifts down by roughly one title-line
# height. Empirically this happens once the canonical name exceeds 22 chars.
TITLE_WRAP_THRESHOLD_CHARS = 22
TITLE_WRAP_Y_OFFSET = 0.045  # fraction of page height to shift the token crop


@dataclass
class ArtworkImage:
    """Metadata for an extracted artwork image."""
    filename: str
    page_number: int
    width: int
    height: int
    aspect_ratio: float
    file_size_kb: int
    orientation: str  # 'portrait', 'landscape', or 'square'
    xref: int  # PDF image reference number
    image_hash: str = ""  # SHA256 hash for exact deduplication
    perceptual_hash: str = ""  # pHash for visual similarity
    
    def to_dict(self):
        return asdict(self)


def compute_image_hash(image_bytes: bytes) -> str:
    """Compute SHA256 hash of image bytes for exact deduplication."""
    return hashlib.sha256(image_bytes).hexdigest()


def compute_perceptual_hash(image_bytes: bytes, hash_size: int = 16) -> str:
    """
    Compute perceptual hash (pHash) for visual similarity detection.
    Similar images will have similar hashes even if compression differs.
    """
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
    """Compute Hamming distance between two hex hash strings."""
    if not hash1 or not hash2 or len(hash1) != len(hash2):
        return 999
    
    int1 = int(hash1, 16)
    int2 = int(hash2, 16)
    xor = int1 ^ int2
    distance = bin(xor).count('1')
    return distance


def load_generic_hashes(generic_dir: Path) -> Tuple[Set[str], Set[str]]:
    """Load image hashes from generic backgrounds folder."""
    exact_hashes = set()
    perceptual_hashes = set()
    
    if not generic_dir.exists():
        return exact_hashes, perceptual_hashes
    
    metadata_path = generic_dir / 'generic-artwork-metadata.json'
    if metadata_path.exists():
        try:
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
                for img in metadata.get('images', []):
                    if 'image_hash' in img and img['image_hash']:
                        exact_hashes.add(img['image_hash'])
                    if 'perceptual_hash' in img and img['perceptual_hash']:
                        perceptual_hashes.add(img['perceptual_hash'])
        except Exception as e:
            logger.warning(f"    Failed to load generic metadata: {e}")
    
    return exact_hashes, perceptual_hashes


def find_kill_team_page(pdf_path: Path) -> int:
    """Find the page with large 'KILL TEAM' text (operatives list page)."""
    try:
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text_dict = page.get_text("dict")
            
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").upper()
                            size = span.get("size", 0)
                            
                            if "KILL TEAM" in text and size > 20:
                                doc.close()
                                return page_num
        
        doc.close()
        return -1
        
    except Exception as e:
        logger.warning(f"    Error finding KILL TEAM page: {e}")
        return -1


def extract_icons_from_pdf(
    pdf_path: Path,
    output_dir: Path,
    team_name: str,
    canonical_name: Optional[str] = None,
) -> dict:
    """
    Extract team icons from PDF for card backsides and token bag.

    Returns:
        Dict with extraction results
    """
    title_wraps = bool(canonical_name) and len(canonical_name) > TITLE_WRAP_THRESHOLD_CHARS
    token_y_offset = TITLE_WRAP_Y_OFFSET if title_wraps else 0.0
    icons_dir = output_dir / 'icons'
    icons_dir.mkdir(parents=True, exist_ok=True)
    
    extracted = {
        'portrait': False,
        'landscape': False,
        'token': False
    }
    
    try:
        doc = fitz.open(pdf_path)
        
        # Extract from page 1 (card backside icons)
        if len(doc) > 0:
            page = doc[0]
            
            # Render at 5x DPI for high quality card backsides
            mat = fitz.Matrix(5.0, 5.0)
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            page_width = pix.width
            page_height = pix.height
            
            # Extract portrait icon
            port_x1 = int(page_width * PORTRAIT_ICON_X1)
            port_y1 = int(page_height * PORTRAIT_ICON_Y1)
            port_x2 = int(page_width * PORTRAIT_ICON_X2)
            port_y2 = int(page_height * PORTRAIT_ICON_Y2)
            
            portrait_icon = img[port_y1:port_y2, port_x1:port_x2]
            portrait_path = icons_dir / f'{team_name}-icon-portrait.jpg'
            cv2.imwrite(str(portrait_path), portrait_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
            extracted['portrait'] = True
            
            # Extract landscape icon
            land_x1 = int(page_width * LANDSCAPE_ICON_X1)
            land_y1 = int(page_height * LANDSCAPE_ICON_Y1)
            land_x2 = int(page_width * LANDSCAPE_ICON_X2)
            land_y2 = int(page_height * LANDSCAPE_ICON_Y2)
            
            landscape_icon = img[land_y1:land_y2, land_x1:land_x2]
            landscape_path = icons_dir / f'{team_name}-icon-landscape.jpg'
            cv2.imwrite(str(landscape_path), landscape_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
            extracted['landscape'] = True
        
        # Find and extract token bag icon
        page_num = find_kill_team_page(pdf_path)
        
        if page_num != -1:
            page = doc[page_num]
            
            # Render at 5x DPI for high quality
            mat = fitz.Matrix(5.0, 5.0)
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
            
            page_width = pix.width
            page_height = pix.height
            
            # Extract token bag icon
            tok_x1 = int(page_width * TOKEN_ICON_X1)
            tok_y1 = int(page_height * (TOKEN_ICON_Y1 + token_y_offset))
            tok_x2 = int(page_width * TOKEN_ICON_X2)
            tok_y2 = int(page_height * (TOKEN_ICON_Y2 + token_y_offset))
            
            token_icon = img[tok_y1:tok_y2, tok_x1:tok_x2]
            token_path = icons_dir / f'{team_name}-icon-token.jpg'
            cv2.imwrite(str(token_path), token_icon, [cv2.IMWRITE_JPEG_QUALITY, 95])
            extracted['token'] = True
            
            # Also create transparent version for dice generation
            transparent_icon = extract_icon_transparent(token_icon)
            transparent_path = icons_dir / f'{team_name}-icon-token-transparent.png'
            cv2.imwrite(str(transparent_path), transparent_icon)
            extracted['token_transparent'] = True
        
        doc.close()
        
    except Exception as e:
        logger.warning(f"    Error extracting icons for {team_name}: {e}")
    
    return extracted


def get_image_orientation(width: int, height: int) -> str:
    """Determine image orientation based on dimensions."""
    aspect_ratio = width / height if height > 0 else 1.0


def extract_icon_transparent(icon_bgr: np.ndarray, threshold: int = 80, margin: int = 30) -> np.ndarray:
    """
    Extract icon with transparent background using brightness-based cutout.
    
    Args:
        icon_bgr: BGR image array from cv2
        threshold: Brightness threshold (0-255) - pixels above this become transparent
        margin: Pixels to apply gradient transparency at edges
    
    Returns:
        BGRA image with alpha channel (transparent background)
    """
    # Convert BGR to RGB for processing
    icon_rgb = cv2.cvtColor(icon_bgr, cv2.COLOR_BGR2RGB)
    
    # Calculate brightness
    brightness = np.mean(icon_rgb, axis=2)
    
    # Create base alpha channel
    alpha = np.where(brightness < threshold, 255, 0).astype(np.uint8)
    
    # Apply gradient at edges for smooth transparency
    height, width = alpha.shape
    for y in range(height):
        for x in range(width):
            if alpha[y, x] == 255:
                # Check distance to transparent pixels
                dist_to_edge = min(
                    min(x, width - 1 - x),
                    min(y, height - 1 - y)
                )
                
                # Apply gradient within margin
                if dist_to_edge < margin:
                    fade_factor = dist_to_edge / margin
                    alpha[y, x] = int(255 * fade_factor)
    
    # Create BGRA image
    bgra = np.dstack([icon_bgr, alpha])
    
    return bgra


def get_image_orientation(width: int, height: int) -> str:
    """Determine image orientation based on dimensions."""
    aspect_ratio = width / height if height > 0 else 1.0
    
    if 0.95 <= aspect_ratio <= 1.05:
        return 'square'
    elif aspect_ratio > 1.05:
        return 'landscape'
    else:
        return 'portrait'


def is_likely_artwork(
    width: int,
    height: int,
    min_dimension: int = 500,
    max_aspect_ratio: float = 3.0,
    min_area: int = 250000
) -> bool:
    """Determine if an image is likely artwork vs icon/decoration."""
    # At least one dimension must be >= min_dimension
    if width < min_dimension and height < min_dimension:
        return False
    
    # Total area must be substantial
    area = width * height
    if area < min_area:
        return False
    
    # Aspect ratio shouldn't be too extreme
    aspect_ratio = max(width, height) / min(width, height) if min(width, height) > 0 else 999
    if aspect_ratio > max_aspect_ratio:
        return False
    
    return True


def extract_artwork_from_pdf(
    pdf_path: Path,
    output_dir: Path,
    team_name: str,
    generic_exact_hashes: Optional[Set[str]] = None,
    generic_perceptual_hashes: Optional[Set[str]] = None,
    perceptual_threshold: int = 15
) -> List[ArtworkImage]:
    """Extract artwork images from a PDF."""
    artwork_dir = output_dir / 'artwork'
    artwork_dir.mkdir(parents=True, exist_ok=True)
    
    extracted_images: List[ArtworkImage] = []
    seen_xrefs = set()
    seen_hashes = set()
    skipped_generic = 0
    sequential_counter = 0
    
    try:
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            image_list = page.get_images(full=True)
            
            for img_index, img_info in enumerate(image_list):
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
                    
                    # Check if this looks like artwork
                    if not is_likely_artwork(width, height):
                        continue
                    
                    # Compute image hashes for deduplication
                    img_exact_hash = compute_image_hash(image_bytes)
                    img_perceptual_hash = compute_perceptual_hash(image_bytes)
                    
                    # Skip if this is a generic background
                    if generic_exact_hashes and img_exact_hash in generic_exact_hashes:
                        skipped_generic += 1
                        seen_xrefs.add(xref)
                        continue
                    
                    # Check perceptual similarity
                    if generic_perceptual_hashes and img_perceptual_hash:
                        is_visually_similar = False
                        for generic_phash in generic_perceptual_hashes:
                            distance = hamming_distance(img_perceptual_hash, generic_phash)
                            if distance <= perceptual_threshold:
                                is_visually_similar = True
                                break
                        
                        if is_visually_similar:
                            skipped_generic += 1
                            seen_xrefs.add(xref)
                            continue
                    
                    # Skip if duplicate
                    if img_exact_hash in seen_hashes:
                        seen_xrefs.add(xref)
                        continue
                    
                    orientation = get_image_orientation(width, height)
                    aspect_ratio = width / height if height > 0 else 1.0
                    
                    sequential_counter += 1
                    filename = f'{team_name}-artwork-{sequential_counter:02d}.{image_ext}'
                    output_path = artwork_dir / filename
                    
                    with open(output_path, 'wb') as f:
                        f.write(image_bytes)
                    
                    file_size_kb = len(image_bytes) // 1024
                    
                    artwork = ArtworkImage(
                        filename=filename,
                        page_number=page_num + 1,
                        width=width,
                        height=height,
                        aspect_ratio=round(aspect_ratio, 2),
                        file_size_kb=file_size_kb,
                        orientation=orientation,
                        xref=xref,
                        image_hash=img_exact_hash,
                        perceptual_hash=img_perceptual_hash
                    )
                    
                    extracted_images.append(artwork)
                    seen_xrefs.add(xref)
                    seen_hashes.add(img_exact_hash)
                    
                except Exception as e:
                    logger.debug(f"    Error extracting image: {e}")
                    continue
        
        doc.close()
        
        # Save metadata JSON
        if extracted_images:
            metadata_path = artwork_dir / f'{team_name}-artwork-metadata.json'
            metadata = {
                'team': team_name,
                'pdf': pdf_path.name,
                'total_images': len(extracted_images),
                'images': [img.to_dict() for img in extracted_images]
            }
            
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)
        
    except Exception as e:
        logger.warning(f"    Error processing PDF {pdf_path.name}: {e}")
    
    return extracted_images


def _load_canonical_names() -> Dict[str, str]:
    """Map team slug -> canonical_name from config/team-config.yaml."""
    cfg_path = Path('config/team-config.yaml')
    if not cfg_path.exists():
        return {}
    try:
        with open(cfg_path, encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
        return {
            slug: (cfg or {}).get('canonical_name', '')
            for slug, cfg in (data.get('teams') or {}).items()
        }
    except Exception as e:
        logger.warning(f"  Could not load team-config.yaml: {e}")
        return {}


_CANONICAL_NAMES: Dict[str, str] = {}


def process_team_pdf(pdf_path: Path, output_dir: Path, generic_dir: Path) -> dict:
    """Process a single team PDF: extract icons and artwork."""
    global _CANONICAL_NAMES
    if not _CANONICAL_NAMES:
        _CANONICAL_NAMES = _load_canonical_names()

    team_name = pdf_path.stem.replace('_team_rules', '').replace('_online_rules', '')
    team_output = output_dir / team_name
    team_output.mkdir(parents=True, exist_ok=True)
    canonical_name = _CANONICAL_NAMES.get(team_name, '')

    logger.info(f"\nProcessing: {team_name}")
    
    results = {
        'team': team_name,
        'icons_extracted': 0,
        'artwork_extracted': 0
    }
    
    # Extract icons
    logger.info("  Extracting icons...")
    icons_result = extract_icons_from_pdf(pdf_path, team_output, team_name, canonical_name)
    results['icons_extracted'] = sum(1 for v in icons_result.values() if v)
    logger.info(f"  ✓ Extracted {results['icons_extracted']} icons")
    
    # Extract artwork (skip generic backgrounds)
    logger.info("  Extracting artwork...")
    generic_exact, generic_perceptual = load_generic_hashes(generic_dir)
    artwork_result = extract_artwork_from_pdf(
        pdf_path=pdf_path,
        output_dir=team_output,
        team_name=team_name,
        generic_exact_hashes=generic_exact,
        generic_perceptual_hashes=generic_perceptual,
        perceptual_threshold=15
    )
    results['artwork_extracted'] = len(artwork_result)
    
    if artwork_result:
        logger.info(f"  ✓ Extracted {len(artwork_result)} artwork images")
    else:
        logger.info("  No artwork extracted (all images were generic backgrounds or too small)")
    
    return results


def run(input_dir: Path = None, output_dir: Path = None, max_workers: int = 4) -> dict:
    """
    Main function to extract icons and artwork from PDFs.
    
    Args:
        input_dir: Directory containing PDF files (default: layers/warcom/staging)
        output_dir: Directory to save extracted files (default: layers/warcom/extracted)
        max_workers: Max concurrent workers (default: 4)
        
    Returns:
        dict with 'success' and statistics
    """
    if input_dir is None:
        input_dir = Path('layers/warcom/staging')
    
    if output_dir is None:
        output_dir = Path('layers/warcom/extracted')
    
    generic_dir = output_dir / '_generic'
    
    logger.info("=" * 70)
    logger.info("Step 2a: Extract Icons and Artwork from PDFs")
    logger.info("=" * 70)
    logger.info("")
    
    # Find all PDFs
    pdf_files = sorted(input_dir.glob('*.pdf'))
    
    if not pdf_files:
        logger.error(f"No PDF files found in {input_dir}")
        return {'success': True, 'processed': 0, 'icons': 0, 'artwork': 0}
    
    logger.info(f"Found {len(pdf_files)} PDF files")
    logger.info(f"Output: {output_dir}")
    logger.info(f"Workers: {max_workers}")
    logger.info("")
    
    total_icons = 0
    total_artwork = 0
    processed = 0
    
    # Process PDFs concurrently
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for pdf_file in pdf_files:
            future = executor.submit(process_team_pdf, pdf_file, output_dir, generic_dir)
            futures.append((pdf_file.stem, future))
        
        for team_name, future in futures:
            try:
                result = future.result()
                processed += 1
                total_icons += result['icons_extracted']
                total_artwork += result['artwork_extracted']
            except Exception as e:
                logger.error(f"✗ Failed to process {team_name}: {e}")
    
    logger.info("")
    logger.info("=" * 70)
    logger.info(f"Summary:")
    logger.info(f"  Processed: {processed} teams")
    logger.info(f"  Icons extracted: {total_icons}")
    logger.info(f"  Artwork extracted: {total_artwork}")
    logger.info("=" * 70)
    
    return {
        'success': True,
        'processed': processed,
        'icons': total_icons,
        'artwork': total_artwork
    }


def main():
    parser = argparse.ArgumentParser(description='Extract icons and artwork from Kill Team PDFs')
    parser.add_argument('--input-dir', type=Path, default=Path('layers/warcom/staging'),
                       help='Input directory with PDFs')
    parser.add_argument('--output-dir', type=Path, default=Path('layers/warcom/extracted'),
                       help='Output directory for extracted files')
    parser.add_argument('--workers', type=int, default=4,
                       help='Number of concurrent workers')
    
    args = parser.parse_args()
    
    result = run(
        input_dir=args.input_dir,
        output_dir=args.output_dir,
        max_workers=args.workers
    )
    
    exit(0 if result['success'] else 1)


if __name__ == '__main__':
    main()
