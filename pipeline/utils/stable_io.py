"""Stable output writes: keep re-renders byte-and-mtime stable.

The image renderers are deterministic — re-rendering the same source produces
byte-identical output. But each write bumps the file's mtime, and downstream
TTS URL generation embeds mtime-based ``?v=`` cache-buster params. So a forced
re-run (identical pixels, new mtime) would needlessly churn every TTS box/URL
JSON. ``stable_write`` restores the prior mtime whenever the freshly-written
bytes match the prior file, so nothing downstream sees a spurious change.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def stable_write(path):
    """Preserve the prior file's mtime when the new bytes are byte-identical.

    Wrap any file-producing call::

        with stable_write(out_path):
            pix.save(out_path, jpg_quality=95)

    If ``out_path`` already existed and the newly-written content is identical,
    its previous mtime is restored; otherwise the new file (and mtime) stands.
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
                if p.read_bytes() == prior_bytes:
                    os.utime(p, (prior_mtime, prior_mtime))
            except OSError:
                pass
