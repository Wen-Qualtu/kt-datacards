"""One-shot: build transparent PNG icon for spectre-squad from its JPG.

Spectre Squad was an early-release team and only has the JPG icon variant.
Convert it to the transparent PNG format the dice generator expects:
    layers/warcom/extracted/spectre-squad/icons/spectre-squad-icon-token-transparent.png

Strategy: HSV-based mask. The icon is bright/saturated (orange ~hue 15);
the background is near-black noise. Build an alpha channel from saturation
+ value, clean it up, and write RGBA.
"""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SLUG = "spectre-squad"
SRC = ROOT / "layers" / "warcom" / "extracted" / SLUG / "icons" / f"{SLUG}-icon-token.jpg"
DST = ROOT / "layers" / "warcom" / "extracted" / SLUG / "icons" / f"{SLUG}-icon-token-transparent.png"


def main():
    bgr = cv2.imread(str(SRC), cv2.IMREAD_COLOR)
    if bgr is None:
        raise SystemExit(f"Cannot read {SRC}")
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[:, :, 0], hsv[:, :, 1], hsv[:, :, 2]

    # Tight foreground mask: orange/red hue + decent saturation + brightness.
    # JPG background is dark gray with noise (low s, low v), well below these.
    fg = ((h < 25) | (h > 165)) & (s > 110) & (v > 90)
    fg = fg.astype(np.uint8) * 255

    # Drop tiny specks (background noise), then close gaps inside the icon.
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    fg = cv2.GaussianBlur(fg, (3, 3), 0)

    rgba = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGBA)
    rgba[:, :, 3] = fg

    Image.fromarray(rgba).save(DST)
    print(f"Wrote {DST.relative_to(ROOT)}  ({DST.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
