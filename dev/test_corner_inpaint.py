"""
Test script for corner filling approaches.
Tests 3 approaches: A (inpainting), B (color sampling), C (edge blur/extend)
"""
import cv2
import numpy as np
from pathlib import Path

def approach_a_inpaint(img, corner_radius: int = 50):
    """
    Approach A: Use inpainting to fill corner regions based on surrounding pixels.
    """
    height, width = img.shape[:2]
    
    # Create mask for corner regions (white = inpaint these areas)
    mask = np.zeros((height, width), dtype=np.uint8)
    
    # Define corner regions (circles in each corner)
    corners = [
        (0, 0),                    # Top-left
        (width - 1, 0),            # Top-right
        (0, height - 1),           # Bottom-left
        (width - 1, height - 1)    # Bottom-right
    ]
    
    # Draw circles at corners to mark regions for inpainting
    for corner_x, corner_y in corners:
        cv2.circle(mask, (corner_x, corner_y), corner_radius, 255, -1)
    
    # Perform inpainting
    result = cv2.inpaint(img, mask, inpaintRadius=3, flags=cv2.INPAINT_TELEA)
    return result


def approach_b_color_sample(img, corner_radius: int = 50):
    """
    Approach B: Sample color from adjacent pixels and fill corner regions.
    """
    height, width = img.shape[:2]
    result = img.copy()
    
    # Sample distance from corner (how far to sample the color)
    sample_offset = corner_radius + 5
    
    # Define corners with their sampling positions
    corners = [
        ((0, 0), (sample_offset, sample_offset)),                          # Top-left
        ((width - 1, 0), (width - sample_offset - 1, sample_offset)),      # Top-right
        ((0, height - 1), (sample_offset, height - sample_offset - 1)),    # Bottom-left
        ((width - 1, height - 1), (width - sample_offset - 1, height - sample_offset - 1))  # Bottom-right
    ]
    
    # Fill each corner with sampled color
    for (corner_x, corner_y), (sample_x, sample_y) in corners:
        # Sample color from adjacent area (average of small region)
        sample_region = img[max(0, sample_y-2):sample_y+3, max(0, sample_x-2):sample_x+3]
        avg_color = np.mean(sample_region, axis=(0, 1)).astype(np.uint8)
        
        # Create a mask for this corner
        mask = np.zeros((height, width), dtype=np.uint8)
        cv2.circle(mask, (corner_x, corner_y), corner_radius, 255, -1)
        
        # Fill the corner with the sampled color
        result[mask == 255] = avg_color
    
    return result


def approach_c_edge_extend(img, corner_radius: int = 50):
    """
    Approach C: Blur and extend edge pixels into corner areas.
    """
    height, width = img.shape[:2]
    
    # Create a slightly larger canvas
    border = corner_radius
    extended = cv2.copyMakeBorder(img, border, border, border, border, cv2.BORDER_REPLICATE)
    
    # Apply Gaussian blur to smooth the extended edges
    blurred = cv2.GaussianBlur(extended, (15, 15), 0)
    
    # Create mask for corner regions in original size
    mask = np.zeros((height + 2*border, width + 2*border), dtype=np.uint8)
    corners = [
        (0, 0),
        (width + 2*border - 1, 0),
        (0, height + 2*border - 1),
        (width + 2*border - 1, height + 2*border - 1)
    ]
    for corner_x, corner_y in corners:
        cv2.circle(mask, (corner_x, corner_y), corner_radius, 255, -1)
    
    # Blend blurred edges only in corner regions
    result = extended.copy()
    result[mask == 255] = blurred[mask == 255]
    
    # Crop back to original size
    result = result[border:border+height, border:border+width]
    
    return result


def test_all_approaches(image_path: Path, corner_radius: int = 50, output_dir: Path = Path('dev')):
    """
    Test all three corner filling approaches on an image.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Load or convert image
    if image_path.suffix == '.pdf':
        print(f"Converting PDF to PNG: {image_path.name}")
        import fitz
        doc = fitz.open(image_path)
        if len(doc) > 0:
            page = doc[0]
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            png_path = output_dir / f"{image_path.stem}_temp.png"
            pix.save(str(png_path))
            doc.close()
            img = cv2.imread(str(png_path))
            png_path.unlink()  # Clean up temp file
        else:
            print(f"ERROR: No pages in PDF")
            return
    else:
        img = cv2.imread(str(image_path))
    
    if img is None:
        print(f"ERROR: Could not load image: {image_path}")
        return
    
    height, width = img.shape[:2]
    print(f"  Image dimensions: {width}x{height}")
    
    # Test Approach A: Inpainting
    print(f"  Testing Approach A (inpainting)...")
    result_a = approach_a_inpaint(img, corner_radius)
    output_a = output_dir / f"{image_path.stem}_approach_a_inpaint_r{corner_radius}.png"
    cv2.imwrite(str(output_a), result_a)
    print(f"    ✓ Saved: {output_a.name}")
    
    # Test Approach B: Color sampling
    print(f"  Testing Approach B (color sampling)...")
    result_b = approach_b_color_sample(img, corner_radius)
    output_b = output_dir / f"{image_path.stem}_approach_b_color_r{corner_radius}.png"
    cv2.imwrite(str(output_b), result_b)
    print(f"    ✓ Saved: {output_b.name}")
    
    # Test Approach C: Edge extend
    print(f"  Testing Approach C (edge extend)...")
    result_c = approach_c_edge_extend(img, corner_radius)
    output_c = output_dir / f"{image_path.stem}_approach_c_edge_r{corner_radius}.png"
    cv2.imwrite(str(output_c), result_c)
    print(f"    ✓ Saved: {output_c.name}")
    
    # Also save original for comparison
    output_orig = output_dir / f"{image_path.stem}_original.png"
    cv2.imwrite(str(output_orig), img)
    print(f"    ✓ Saved: {output_orig.name}")


if __name__ == '__main__':
    # Test portrait cards only with smaller radii
    test_cards = [
        Path('layers/warcom/extracted/angels-of-death/cards/page04_card1_portrait.png'),
        Path('layers/warcom/extracted/angels-of-death/cards/page04_card3_portrait.pdf'),
    ]
    
    radii = [20, 25, 30]
    
    print(f"{'='*60}")
    print(f"Testing Approach A (inpainting) - PORTRAIT cards with radii: {radii}")
    print(f"{'='*60}\n")
    
    for card_path in test_cards:
        if not card_path.exists():
            print(f"WARNING: File not found: {card_path}")
            continue
        
        print(f"Processing: {card_path.name}")
        
        # Load or convert image
        if card_path.suffix == '.pdf':
            print(f"  Converting PDF to PNG...")
            import fitz
            doc = fitz.open(card_path)
            if len(doc) > 0:
                page = doc[0]
                mat = fitz.Matrix(300 / 72, 300 / 72)
                pix = page.get_pixmap(matrix=mat)
                png_path = Path('dev') / f"{card_path.stem}_temp.png"
                pix.save(str(png_path))
                doc.close()
                img = cv2.imread(str(png_path))
                png_path.unlink()  # Clean up temp file
            else:
                print(f"  ERROR: No pages in PDF")
                continue
        else:
            img = cv2.imread(str(card_path))
        
        if img is None:
            print(f"  ERROR: Could not load image: {card_path}")
            continue
        
        height, width = img.shape[:2]
        print(f"  Image dimensions: {width}x{height}")
        
        # Test each radius
        for radius in radii:
            result = approach_a_inpaint(img, radius)
            output = Path('dev') / f"{card_path.stem}_approach_a_r{radius}.png"
            cv2.imwrite(str(output), result)
            print(f"    ✓ r{radius}: {output.name}")
        
        print()
    
    print(f"{'='*60}")
    print("All test images saved to dev/ folder")
    print(f"{'='*60}")
