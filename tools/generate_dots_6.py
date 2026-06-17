"""Generate dots-6.png for each dice variant from existing dots-4.png.

Faces 1-5 ship as PNGs in config/defaults/dice/{variant}/dots-N.png. Face 6
was missing, so the generators substituted dots-5 (light/dark) or left it
blank (team-color). This produces a proper 6-dot stamp aligned with the
exact dot diameter and corner positions used by dots-4/dots-5.

Run on demand:
    python tools/generate_dots_6.py
"""
from pathlib import Path
import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DICE_DIR = ROOT / "config" / "defaults" / "dice"
VARIANTS = ["team_template", "light", "dark"]


def build_dots_6(variant: str):
    src_path = DICE_DIR / variant / "dots-4.png"
    dst_path = DICE_DIR / variant / "dots-6.png"
    src = np.array(Image.open(src_path).convert("RGBA"))
    h, w = src.shape[:2]
    alpha = (src[:, :, 3] > 0).astype(np.uint8)

    ncomp, labeled = cv2.connectedComponents(alpha)
    dots = []
    for i in range(1, ncomp):
        ys, xs = np.where(labeled == i)
        dots.append((int(ys.min()), int(xs.min()), int(ys.max()), int(xs.max())))
    if len(dots) != 4:
        raise RuntimeError(f"{src_path}: expected 4 dots, found {len(dots)}")

    dots.sort(key=lambda d: (d[0], d[1]))
    tl = dots[0]
    tr = next(d for d in dots if d[0] == tl[0] and d[1] != tl[1])
    bl = next(d for d in dots if d[1] == tl[1] and d[0] != tl[0])

    y0, x0, y1, x1 = tl
    stamp = src[y0:y1+1, x0:x1+1].copy()
    dh, dw = stamp.shape[:2]

    left = x0
    top = y0
    right = w - 1 - tr[3]
    bottom = h - 1 - bl[2]

    canvas = np.zeros_like(src)
    col_x = [left, w - dw - right]
    row_y = [top, (h - dh) // 2, h - dh - bottom]

    for y in row_y:
        for x in col_x:
            tgt = canvas[y:y+dh, x:x+dw]
            mask = stamp[:, :, 3:4].astype(np.float32) / 255.0
            blended = stamp.astype(np.float32) * mask + tgt.astype(np.float32) * (1.0 - mask)
            tgt[:] = blended.astype(np.uint8)
            tgt[:, :, 3] = np.maximum(tgt[:, :, 3], stamp[:, :, 3])

    Image.fromarray(canvas).save(dst_path)
    print(f"  wrote {dst_path.relative_to(ROOT)}  ({dst_path.stat().st_size} bytes)")


def main():
    for v in VARIANTS:
        print(f"variant: {v}")
        build_dots_6(v)


if __name__ == "__main__":
    main()
