"""Generate the Kill Team Spawner token icon.

Renders ``output/_generic-tts-objects/team-spawner-icon.png``: an orange arrow
rising out of an open box on dark grey, matching the Command Node token style.
The team list itself lives in the spawner's in-game menu.

Run:  python -m tools.generate_spawner_image
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "_generic-tts-objects" / "team-spawner-icon.png"

SIZE = 512
SUPERSAMPLE = 4
BACKGROUND = (51, 51, 51)
ORANGE = (231, 79, 10)

SHAPES = [
    [(198, 122), (256, 60), (314, 122)],
    [(240, 116), (272, 116), (272, 236), (240, 236)],
    [(102, 226), (206, 226), (244, 276), (150, 276)],
    [(306, 226), (410, 226), (362, 276), (268, 276)],
    [(150, 290), (362, 290), (362, 430), (150, 430)],
]
BOX_SLOT = [(196, 334), (316, 334), (316, 352), (196, 352)]


def generate() -> Path:
    canvas = SIZE * SUPERSAMPLE
    img = Image.new("RGB", (canvas, canvas), BACKGROUND)
    draw = ImageDraw.Draw(img)
    for shape in SHAPES:
        draw.polygon([(x * SUPERSAMPLE, y * SUPERSAMPLE) for x, y in shape], fill=ORANGE)
    draw.polygon([(x * SUPERSAMPLE, y * SUPERSAMPLE) for x, y in BOX_SLOT], fill=BACKGROUND)
    img = img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    img.save(OUTPUT)
    return OUTPUT


if __name__ == "__main__":
    print(f"Wrote {generate()}")
