"""Generate numbered "counter" token images for the operative-counter UI.

A counter token type lets a team define a stepped counter (min..max) rendered as
a shared background with a number drawn on it, instead of hand-drawing one PNG per
value. The generated images are written to a ``counters/`` SUBFOLDER under the
team's output tokens dir so the box-dispenser scan (which globs the top-level
tokens dir only) never turns them into physical box tokens - they exist purely as
the above-health-bar counter art. Reusable by any team (min/max + a background).

Config (a ``generate`` block on an ``operative_counters`` entry)::

    - name: Movement Remaining
      applies_to: [MOUNTED]
      min: 1
      max: 12
      init: 1
      generate:
        background: <file in the team's custom-tokens/counters/ subfolder>
        # optional: text_color: [r,g,b]  outline_color: [r,g,b]  font_frac: 0.46
"""
import re
from pathlib import Path
from typing import Iterable, Optional

from PIL import Image, ImageDraw, ImageFont


COUNTERS_SUBDIR = "counters"


def counter_slug(name: str) -> str:
    """Stable slug for a counter name. MUST match tts_impl._oc_slug so the
    generated filenames line up with the token paths embedded in the Lua."""
    s = re.sub(r'[^a-z0-9]+', '_', str(name).lower()).strip('_')
    return s or 'counter'


def generated_counter_states(cfg: dict) -> Optional[list]:
    """If ``cfg`` is a generated counter (has a ``generate`` block and no explicit
    ``states``), synthesize the states list pointing at the counters subfolder;
    otherwise return None so callers keep the hand-authored ``states``."""
    if not isinstance(cfg, dict) or not cfg.get('generate') or cfg.get('states'):
        return None
    lo = int(cfg.get('min', 1))
    hi = int(cfg.get('max', lo))
    slug = counter_slug(cfg.get('name', 'counter'))
    return [
        {'value': v, 'label': str(v), 'token': f"{COUNTERS_SUBDIR}/{slug}-{v}.png"}
        for v in range(lo, hi + 1)
    ]


def _style_kwargs(gen: dict) -> dict:
    """Map optional style fields from a ``generate`` block to generate_counter_tokens kwargs."""
    out: dict = {}
    tc = gen.get('text_color')
    if isinstance(tc, (list, tuple)) and len(tc) >= 3:
        out['text_rgba'] = (int(tc[0]), int(tc[1]), int(tc[2]), 255)
    oc = gen.get('outline_color')
    if isinstance(oc, (list, tuple)) and len(oc) >= 3:
        out['outline_rgba'] = (int(oc[0]), int(oc[1]), int(oc[2]), 255)
    if gen.get('font_frac') is not None:
        out['font_frac'] = float(gen['font_frac'])
    return out

# Bold-font fallbacks (mirrors generate_box_texture._load_font). Never hard-fail:
# fall back to PIL's built-in font so generation still works headless.
_BOLD_FONT_CANDIDATES = [
    "C:/Windows/Fonts/arialbd.ttf",
    "C:/Windows/Fonts/Arial Bold.ttf",
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/Library/Fonts/Arial Bold.ttf",
]


def _load_bold_font(size: int):
    for path in _BOLD_FONT_CANDIDATES:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def generate_counter_tokens(
    background_path,
    values: Iterable[int],
    out_dir,
    slug: str,
    text_rgba=(255, 255, 255, 255),
    outline_rgba=(6, 46, 46, 255),
    font_frac: float = 0.46,
    y_nudge_frac: float = 0.04,
) -> list[Path]:
    """Draw each value in ``values`` centred on ``background_path`` and save as
    ``<out_dir>/<slug>-<value>.png``. Returns the written paths.
    """
    bg = Image.open(background_path).convert("RGBA")
    w, h = bg.size
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base_size = max(24, int(h * font_frac))
    written: list[Path] = []
    for v in values:
        img = bg.copy()
        draw = ImageDraw.Draw(img)
        text = str(v)

        # Shrink the font until a (possibly 2-digit) number fits the trapezoid.
        size = base_size
        font = _load_bold_font(size)
        while size > 24:
            sw = max(2, size // 12)
            bb = draw.textbbox((0, 0), text, font=font, stroke_width=sw)
            if (bb[2] - bb[0]) <= w * 0.60:
                break
            size = int(size * 0.9)
            font = _load_bold_font(size)

        sw = max(2, size // 12)
        bb = draw.textbbox((0, 0), text, font=font, stroke_width=sw)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        x = (w - tw) / 2 - bb[0]
        y = (h - th) / 2 - bb[1] + int(h * y_nudge_frac)
        draw.text((x, y), text, font=font, fill=text_rgba,
                  stroke_width=sw, stroke_fill=outline_rgba)

        p = out_dir / f"{slug}-{v}.png"
        img.save(p)
        written.append(p)
    return written
