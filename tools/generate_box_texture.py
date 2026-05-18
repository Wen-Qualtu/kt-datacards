"""
Generate 6-face cube-net card box texture for TTS card boxes.

Design: generic-artwork-001.jpeg (dark concrete texture) stretched to fill
the canvas. Portrait icon composited onto the front face (light gray background
removed via saturation masking). Team name in title-case on the top face and
below the icon on the front face.

Canvas: 714x585 px (1x) or 1428x1170 px (2x for quality)
UV-derived face layout (1x pixel coords):
  top:    x=[130,357]  y=[0,129]
  left:   x=[0,130]    y=[129,455]
  front:  x=[130,357]  y=[129,455]  <- icon + name
  right:  x=[357,487]  y=[129,455]
  back:   x=[487,714]  y=[129,455]
  bottom: x=[130,357]  y=[455,585]
"""
import cv2
import numpy as np
from pathlib import Path
import argparse
from PIL import Image, ImageDraw, ImageFont

CANVAS_W_1X = 714
CANVAS_H_1X = 585
SCALE = 2

# Face bounding boxes at 1x: (x1, y1, x2, y2)
FACE_TOP    = (130, 0,   357, 129)
FACE_LEFT   = (0,   129, 130, 455)
FACE_FRONT  = (130, 129, 357, 455)
FACE_RIGHT  = (357, 129, 487, 455)
FACE_BACK   = (487, 129, 714, 455)
FACE_BOTTOM = (130, 455, 357, 585)


def _s(v: int) -> int:
    return v * SCALE


def _make_dark_background(background_path: Path, cw: int, ch: int) -> np.ndarray:
    """Stretch dark concrete texture to canvas size."""
    bg_src = cv2.imread(str(background_path))
    if bg_src is None:
        raise FileNotFoundError(f"Cannot load background: {background_path}")
    return cv2.resize(bg_src, (cw, ch), interpolation=cv2.INTER_LANCZOS4)


def _extract_icon_mask(icon_bgr: np.ndarray) -> np.ndarray:
    """
    Return a uint8 mask: 255 where the icon's colored parts are, 0 where the
    light gray background should be removed.  Works for any saturated icon color.
    """
    hsv = cv2.cvtColor(icon_bgr, cv2.COLOR_BGR2HSV)
    saturation = hsv[:, :, 1]
    mask = (saturation > 40).astype(np.uint8) * 255
    # Dilate slightly to include anti-aliased edges
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    return mask


def _place_icon(
    canvas: np.ndarray,
    icon_path: Path,
    face_1x: tuple,
    padding_frac: float = 0.06,
) -> None:
    """
    Load portrait icon, remove light background, composite onto face region.
    Icon fills the region with uniform padding on all sides.
    """
    x1, y1, x2, y2 = [_s(v) for v in face_1x]
    fw, fh = x2 - x1, y2 - y1
    pad_x = int(fw * padding_frac)
    pad_y = int(fh * padding_frac)
    icon_w = fw - 2 * pad_x
    icon_h = fh - 2 * pad_y

    raw = cv2.imread(str(icon_path))
    if raw is None:
        return
    icon = cv2.resize(raw, (icon_w, icon_h), interpolation=cv2.INTER_LANCZOS4)
    mask = _extract_icon_mask(icon)
    mask_3ch = cv2.merge([mask, mask, mask])

    region = canvas[y1 + pad_y:y2 - pad_y, x1 + pad_x:x2 - pad_x]
    canvas[y1 + pad_y:y2 - pad_y, x1 + pad_x:x2 - pad_x] = np.where(
        mask_3ch > 0, icon, region
    )


def _add_text(
    canvas: np.ndarray,
    text: str,
    face_1x: tuple,
    font_size: int,
    color_rgb: tuple = (230, 220, 200),
    y_offset_frac: float = 0.0,
) -> np.ndarray:
    """
    Draw `text` centered horizontally inside face_1x.
    y_offset_frac shifts text vertically within the face (0=top-aligned centre,
    positive values move down).
    """
    x1, y1, x2, y2 = [_s(v) for v in face_1x]
    rw, rh = x2 - x1, y2 - y1

    canvas_rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB)
    pil_img = Image.fromarray(canvas_rgb)
    draw = ImageDraw.Draw(pil_img)

    display = text.replace("-", " ").title()

    font_options = [
        "C:/Windows/Fonts/georgiab.ttf",  # Georgia Bold
        "C:/Windows/Fonts/georgia.ttf",   # Georgia
        "C:/Windows/Fonts/arial.ttf",     # Arial
    ]

    def load_font(size):
        for path in font_options:
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
        return ImageFont.load_default()

    def measure(t, f):
        bb = draw.textbbox((0, 0), t, font=f)
        return bb[2] - bb[0], bb[3] - bb[1]

    # Auto-fit: shrink font until display fits on one line within rw
    font = load_font(font_size)
    while font_size > 18 * SCALE:
        tw, _ = measure(display, font)
        if tw <= rw:
            break
        font_size -= 2
        font = load_font(font_size)

    tw, th = measure(display, font)
    lines = [display]

    if tw > rw:
        words = display.split()
        if len(words) > 1:
            best_split, best_diff = len(words) // 2, float("inf")
            for i in range(1, len(words)):
                l1 = " ".join(words[:i])
                l2 = " ".join(words[i:])
                w1, _ = measure(l1, font)
                w2, _ = measure(l2, font)
                if w1 <= rw and w2 <= rw:
                    diff = abs(w1 - w2)
                    if diff < best_diff:
                        best_diff, best_split = diff, i
            lines = [" ".join(words[:best_split]), " ".join(words[best_split:])]

    line_sizes = [measure(ln, font) for ln in lines]
    total_h = sum(s[1] for s in line_sizes)

    y_center = y1 + rh // 2 + int(rh * y_offset_frac)
    y_cur = y_center - total_h // 2

    for line, (lw, lh) in zip(lines, line_sizes):
        x = x1 + (rw - lw) // 2
        draw.text((x, y_cur), line, fill=color_rgb, font=font)
        y_cur += lh

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def composite_box_texture(
    background_path: Path,
    portrait_icon_path: Path,
    output_path: Path,
    team_name: str,
) -> bool:
    """
    Create 6-face cube-net card box texture.
    Returns True on success.
    """
    try:
        cw, ch = CANVAS_W_1X * SCALE, CANVAS_H_1X * SCALE
        canvas = _make_dark_background(background_path, cw, ch)
    except FileNotFoundError as e:
        print(f"ERROR: {e}")
        return False

    try:
        # Portrait icon on front face (upper ~72% of face height for icon, lower 28% for text)
        front_1x = FACE_FRONT
        fx1, fy1, fx2, fy2 = front_1x
        fh = fy2 - fy1
        # Measured from reference: icon y=23-279 in 326px face, text y=279-326
        icon_zone_y2 = fy1 + int(fh * 0.855)

        icon_face = (fx1, fy1, fx2, icon_zone_y2)
        text_face = (fx1, icon_zone_y2, fx2, fy2)

        _place_icon(canvas, portrait_icon_path, icon_face, padding_frac=0.06)

        # Team name on top face
        canvas = _add_text(canvas, team_name, FACE_TOP, font_size=22 * SCALE)

        # Team name on front face below icon
        canvas = _add_text(canvas, team_name, text_face, font_size=16 * SCALE)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(output_path), canvas, [cv2.IMWRITE_JPEG_QUALITY, 95])
        print(f"OK  {output_path}")
        return True

    except Exception as e:
        import traceback
        print(f"ERROR: Failed to create box texture for {team_name}: {e}")
        traceback.print_exc()
        return False


_DEFAULT_BACKGROUND = Path("layers/warcom/extracted/_generic/generic-artwork-001.jpeg")


def generate_for_team(
    team_name: str,
    extracted_dir: Path = None,
    output_path: Path = None,
    background_path: Path = None,
) -> bool:
    """
    Generate box texture for a specific team.

    Args:
        team_name:       Team slug (also used as display text).
        extracted_dir:   Root of warcom extracted directory.
        output_path:     Explicit output path for the texture file.
        background_path: Dark concrete background texture.
    """
    if extracted_dir is None:
        extracted_dir = Path("layers/warcom/extracted")
    if background_path is None:
        background_path = _DEFAULT_BACKGROUND

    portrait_icon = extracted_dir / team_name / "icons" / f"{team_name}-icon-portrait.jpg"

    if not portrait_icon.exists():
        print(f"ERROR: Portrait icon not found: {portrait_icon}")
        return False
    if not background_path.exists():
        print(f"ERROR: Background not found: {background_path}")
        return False

    if output_path is None:
        output_path = Path("output") / team_name / "cardbox" / f"{team_name}-card-box-texture.jpg"

    return composite_box_texture(background_path, portrait_icon, output_path, team_name)


def main():
    parser = argparse.ArgumentParser(description="Generate card box textures for Kill Team datacards")
    parser.add_argument("team", nargs="?", help="Team slug (or 'all' for all teams)")
    parser.add_argument(
        "--extracted-dir", type=Path, default=Path("layers/warcom/extracted"),
        help="Extracted directory root",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path("output"),
        help="Root output directory (textures go to <output-dir>/<team>/cardbox/)",
    )
    args = parser.parse_args()

    if args.team == "all":
        ok = fail = 0
        for team_dir in sorted(args.extracted_dir.iterdir()):
            if team_dir.is_dir() and (team_dir / "icons").exists():
                slug = team_dir.name
                out = args.output_dir / slug / "cardbox" / f"{slug}-card-box-texture.jpg"
                print(f"[{slug}]")
                if generate_for_team(slug, args.extracted_dir, out):
                    ok += 1
                else:
                    fail += 1
        print(f"\nProcessed: {ok}  Failed: {fail}")
    elif args.team:
        out = args.output_dir / args.team / "cardbox" / f"{args.team}-card-box-texture.jpg"
        if not generate_for_team(args.team, args.extracted_dir, out):
            exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
