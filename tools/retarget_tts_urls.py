"""Retarget existing runtime files to acc without regenerating TTS objects."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFIXES = (
    b"https://raw.githubusercontent.com/Wen-Qualtu/kt-datacards/",
    b"https://github.com/Wen-Qualtu/kt-datacards/raw/",
    b"https://github.com/Wen-Qualtu/kt-datacards/blob/",
)
REFS = (b"refs/heads/feature/command-node", b"refs/heads/main", b"refs/heads/acc",
        b"feature/command-node", b"main", b"acc")
URL_REFERENCE = re.compile(
    b"(?P<prefix>" + b"|".join(re.escape(prefix) for prefix in PREFIXES) + b")"
    b"(?P<ref>" + b"|".join(re.escape(ref) for ref in REFS) + rb")(?=/|[?\"'\s\\]|$)"
)


def normalize_references(data: bytes) -> bytes:
    return URL_REFERENCE.sub(lambda match: match["prefix"] + b"<branch>", data)


def retarget_bytes(data: bytes) -> tuple[bytes, int]:
    count = 0

    def replace(match: re.Match) -> bytes:
        nonlocal count
        ref = b"refs/heads/acc" if match["ref"].startswith(b"refs/heads/") else b"acc"
        result = match["prefix"] + ref
        count += result != match[0]
        return result

    result = URL_REFERENCE.sub(replace, data)
    if normalize_references(data) != normalize_references(result):
        raise ValueError("Retargeting changed bytes outside repository URL references")
    return result, count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    branch = subprocess.check_output(["git", "-C", str(ROOT), "branch", "--show-current"], text=True).strip()
    if branch != "acc":
        parser.error("URL retargeting is permitted only on the acc branch")
    if args.report and not args.apply:
        parser.error("--report requires --apply; dry runs never write files")
    tracked = subprocess.check_output(["git", "-C", str(ROOT), "ls-files", "-z"]).decode("utf-8").split("\0")
    pending = []
    for relative in filter(None, tracked):
        path = ROOT / relative
        if not (path.suffix.lower() == ".json"
            or relative.split("/", 1)[0] in {"config", "output", "pipeline", "tools"}
                or relative == "dev/command-node.json"):
            continue
        if path.suffix.lower() not in {".json", ".lua", ".py", ".yaml", ".yml"} or not path.is_file():
            continue
        before = path.read_bytes()
        after, count = retarget_bytes(before)
        if before == after:
            continue
        if path.suffix.lower() == ".json":
            json.loads(before)
            json.loads(after)
        pending.append((relative, before, after, count))
    report = {"branch": branch, "files": []}
    for relative, before, after, count in pending:
        path = ROOT / relative
        if args.apply:
            if path.read_bytes() != before:
                raise RuntimeError(f"File changed during retargeting: {relative}")
            path.write_bytes(after)
            if path.read_bytes() != after:
                raise RuntimeError(f"Written file differs from URL-only plan: {relative}")
        report["files"].append({
            "path": relative, "url_references": count,
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest(),
            "normalized_sha256": hashlib.sha256(normalize_references(before)).hexdigest(),
        })
    if args.report:
        report_path = ROOT / args.report
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    references = sum(item["url_references"] for item in report["files"])
    print(f"{'Applied' if args.apply else 'DRY RUN'}: {len(pending)} files, {references} URL references")
    print("Non-URL bytes verified unchanged; no TTS regeneration, schema migration, or metadata recalculation")


if __name__ == "__main__":
    main()