"""Stable output writes: keep re-renders byte-and-mtime stable.

Each write bumps the file's mtime, and downstream TTS URL generation embeds
mtime-based ``?v=`` cache-buster params, so a re-run with identical output would
needlessly churn every TTS box/URL JSON. ``stable_write`` restores the prior
mtime whenever the freshly-written bytes match the prior file.

For images the renderer is NOT byte-deterministic when the *source* PDF was
re-exported (e.g. a warcom balance dataslate re-compresses embedded art): the
rasterised card is visually identical but the JPEG bytes differ. Passing
``image_tolerance`` treats such a re-render as unchanged — if every channel of
every pixel differs by no more than the tolerance (pure re-encode/requant
noise), the PRIOR bytes are restored verbatim, so only cards whose rules text
actually changed churn.
"""

from __future__ import annotations

import io
import os
from contextlib import contextmanager
from pathlib import Path


def _perceptually_same(a_bytes: bytes, b_bytes: bytes, tolerance: int) -> bool:
    """True if two encoded images decode to visually-identical pixels.

    Flattens alpha onto white so token edge-alpha jitter folds into small RGB
    diffs, then requires the max per-channel difference to be <= tolerance. A
    real text/glyph change flips pixels fully (diff ~255) and is never within a
    small tolerance, so this only collapses pure re-encode/requant noise.
    """
    try:
        from PIL import Image, ImageChops
    except Exception:
        return False
    try:
        a = Image.open(io.BytesIO(a_bytes)).convert("RGBA")
        b = Image.open(io.BytesIO(b_bytes)).convert("RGBA")
    except Exception:
        return False
    if a.size != b.size:
        return False
    bg = Image.new("RGBA", a.size, (255, 255, 255, 255))
    a = Image.alpha_composite(bg, a).convert("RGB")
    b = Image.alpha_composite(bg, b).convert("RGB")
    diff = ImageChops.difference(a, b)
    bbox = diff.getbbox()
    if bbox is None:
        return True
    return max(ch[1] for ch in diff.getextrema()) <= tolerance


@contextmanager
def stable_write(path, image_tolerance: int | None = None):
    """Preserve the prior file when the new output is (perceptually) unchanged.

    Wrap any file-producing call::

        with stable_write(out_path, image_tolerance=40):
            pix.save(out_path, jpg_quality=95)

    If ``out_path`` already existed and the new content is byte-identical, its
    prior mtime is restored. If ``image_tolerance`` is given and the new bytes
    differ but decode to a visually-identical image (within tolerance), the
    prior bytes AND mtime are restored so nothing downstream sees churn.
    """
    p = Path(path)
    prior_bytes = None
    prior_mtime = None
    if p.exists():
        try:
            prior_bytes = p.read_bytes()
            prior_mtime = p.stat().st_mtime
        except OSError:
            prior_bytes = None
    try:
        yield p
    finally:
        if prior_bytes is not None and prior_mtime is not None:
            try:
                new_bytes = p.read_bytes()
                if new_bytes == prior_bytes:
                    os.utime(p, (prior_mtime, prior_mtime))
                elif image_tolerance is not None and _perceptually_same(
                    prior_bytes, new_bytes, image_tolerance
                ):
                    p.write_bytes(prior_bytes)
                    os.utime(p, (prior_mtime, prior_mtime))
            except OSError:
                pass
