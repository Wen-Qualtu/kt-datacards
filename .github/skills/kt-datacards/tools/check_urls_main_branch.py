"""Check: every github raw URL in output/*.json points to /main/ branch.

Flags any URL pointing to a non-`main` branch (feature branches, dev branches,
etc.) that would break TTS users once the change is published.

Exits with code 1 if any non-main URLs found; 0 otherwise.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _common import iter_output_files, PROJECT_ROOT

# Matches https://raw.githubusercontent.com/<owner>/<repo>/<ref>/...
URL_RE = re.compile(
    r"https://raw\.githubusercontent\.com/[^/]+/[^/]+/([^/?\"\\\s]+)"
)
ALLOWED_REF = "main"


def main() -> int:
    bad: dict[str, list[str]] = defaultdict(list)
    files_checked = 0
    for path in iter_output_files((".json",)):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        files_checked += 1
        refs_in_file: set[str] = set()
        for m in URL_RE.finditer(text):
            ref = m.group(1)
            if ref != ALLOWED_REF:
                refs_in_file.add(ref)
        if refs_in_file:
            rel = path.relative_to(PROJECT_ROOT).as_posix()
            bad[rel] = sorted(refs_in_file)

    print(f"Scanned {files_checked} JSON files under output/")
    if not bad:
        print(f"PASS  All github raw URLs point to /{ALLOWED_REF}/")
        return 0

    print(f"FAIL  {len(bad)} file(s) reference non-`{ALLOWED_REF}` branches:")
    for path, refs in sorted(bad.items())[:30]:
        print(f"  {path}  -> refs: {', '.join(refs)}")
    if len(bad) > 30:
        print(f"  ... and {len(bad) - 30} more")
    print()
    print(f"Fix: regenerate via step 7 with KT_DATACARDS_URL_BRANCH=main, or")
    print(f"     check the env var when running pipelines/kt-app/steps/7_generate_tts_objects.py.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
