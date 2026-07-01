"""Small filesystem helpers shared across steps."""
from __future__ import annotations

import logging
import os
import stat
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def safe_unlink(path: Path, retries: int = 3, delay: float = 0.2) -> None:
    """Remove a file if it exists, retrying on transient access/permission errors."""
    if not path.exists():
        return
    for attempt in range(retries):
        try:
            os.chmod(path, stat.S_IWRITE)
        except OSError:
            pass
        try:
            path.unlink()
            return
        except PermissionError:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
