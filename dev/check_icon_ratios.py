"""
Check aspect ratios of extracted icons vs TTS card dimensions.
"""
import cv2
from pathlib import Path

# TTS card dimensions (from step 3)
TTS_LANDSCAPE_WIDTH = 1430
TTS_LANDSCAPE_HEIGHT = 827
TTS_PORTRAIT_WIDTH = 827
TTS_PORTRAIT_HEIGHT = 1430

landscape_ratio = TTS_LANDSCAPE_WIDTH / TTS_LANDSCAPE_HEIGHT
portrait_ratio = TTS_PORTRAIT_WIDTH / TTS_PORTRAIT_HEIGHT

print("=" * 60)
print("Aspect Ratio Analysis")
print("=" * 60)

print("\nTTS Card Dimensions:")
print(f"  Landscape: {TTS_LANDSCAPE_WIDTH}x{TTS_LANDSCAPE_HEIGHT} (ratio: {landscape_ratio:.4f}:1)")
print(f"  Portrait:  {TTS_PORTRAIT_WIDTH}x{TTS_PORTRAIT_HEIGHT} (ratio: {portrait_ratio:.4f}:1)")

print("\nExtracted Icon Dimensions:")
icons_dir = Path('dev/test_icons_output/icons')

if icons_dir.exists():
    for icon_path in sorted(icons_dir.glob('*.jpg')):
        img = cv2.imread(str(icon_path))
        if img is not None:
            height, width = img.shape[:2]
            ratio = width / height
            
            icon_type = icon_path.stem.split('-')[-1]  # portrait, landscape, or token
            
            if icon_type == 'portrait':
                expected_ratio = portrait_ratio
                diff = ratio - expected_ratio
                status = "✓" if abs(diff) < 0.01 else "✗"
            elif icon_type == 'landscape':
                expected_ratio = landscape_ratio
                diff = ratio - expected_ratio
                status = "✓" if abs(diff) < 0.01 else "✗"
            else:
                expected_ratio = None
                diff = 0
                status = "-"
            
            print(f"\n  {icon_path.name}:")
            print(f"    Dimensions: {width}x{height}")
            print(f"    Ratio: {ratio:.4f}:1")
            if expected_ratio:
                print(f"    Expected: {expected_ratio:.4f}:1")
                print(f"    Difference: {diff:+.4f} {status}")

print("\n" + "=" * 60)
print("Recommendations:")
print("=" * 60)

# Calculate ideal extraction coordinates for proper aspect ratios
# Page 1 dimensions: 1191x1684
page_width = 1191
page_height = 1684

print("\nFor portrait icon (ratio should be 0.5783:1):")
print("  Current appears to be too wide/tall")
print("  Need to adjust coordinates to match portrait card aspect ratio")

print("\nFor landscape icon (ratio should be 1.7290:1):")
print("  Current appears close but may need slight adjustment")

# Suggest new coordinates that maintain same center but correct aspect ratio
from pipelines.warcom.steps.2_card_extractor import PORTRAIT_ICON_X1, PORTRAIT_ICON_Y1, PORTRAIT_ICON_X2, PORTRAIT_ICON_Y2
from pipelines.warcom.steps.2_card_extractor import LANDSCAPE_ICON_X1, LANDSCAPE_ICON_Y1, LANDSCAPE_ICON_X2, LANDSCAPE_ICON_Y2

import importlib.util
spec = importlib.util.spec_from_file_location("step2", "pipelines/warcom/steps/2_card_extractor.py")
step2 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(step2)

# Portrait icon adjustment
port_center_x = (step2.PORTRAIT_ICON_X1 + step2.PORTRAIT_ICON_X2) / 2
port_center_y = (step2.PORTRAIT_ICON_Y1 + step2.PORTRAIT_ICON_Y2) / 2
port_current_height = (step2.PORTRAIT_ICON_Y2 - step2.PORTRAIT_ICON_Y1) * page_height

# Keep height, adjust width to match portrait ratio
port_new_width = port_current_height * portrait_ratio
port_new_width_pct = port_new_width / page_width

port_new_x1 = port_center_x - (port_new_width_pct / 2)
port_new_x2 = port_center_x + (port_new_width_pct / 2)

print(f"\nSuggested portrait coordinates:")
print(f"  X1: {port_new_x1:.4f} (was {step2.PORTRAIT_ICON_X1:.4f})")
print(f"  Y1: {step2.PORTRAIT_ICON_Y1:.4f} (no change)")
print(f"  X2: {port_new_x2:.4f} (was {step2.PORTRAIT_ICON_X2:.4f})")
print(f"  Y2: {step2.PORTRAIT_ICON_Y2:.4f} (no change)")

# Landscape icon adjustment
land_center_x = (step2.LANDSCAPE_ICON_X1 + step2.LANDSCAPE_ICON_X2) / 2
land_center_y = (step2.LANDSCAPE_ICON_Y1 + step2.LANDSCAPE_ICON_Y2) / 2
land_current_height = (step2.LANDSCAPE_ICON_Y2 - step2.LANDSCAPE_ICON_Y1) * page_height

# Keep height, adjust width to match landscape ratio
land_new_width = land_current_height * landscape_ratio
land_new_width_pct = land_new_width / page_width

land_new_x1 = land_center_x - (land_new_width_pct / 2)
land_new_x2 = land_center_x + (land_new_width_pct / 2)

print(f"\nSuggested landscape coordinates:")
print(f"  X1: {land_new_x1:.4f} (was {step2.LANDSCAPE_ICON_X1:.4f})")
print(f"  Y1: {step2.LANDSCAPE_ICON_Y1:.4f} (no change)")
print(f"  X2: {land_new_x2:.4f} (was {step2.LANDSCAPE_ICON_X2:.4f})")
print(f"  Y2: {step2.LANDSCAPE_ICON_Y2:.4f} (no change)")

print("\n" + "=" * 60)
