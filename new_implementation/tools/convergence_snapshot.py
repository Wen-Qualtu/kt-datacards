"""Convergence snapshot / compare helper for the two-track (kt-app vs warcom) test.

Walks new_implementation/{output,layers/integration} and records a normalized
fingerprint of every file so two pipeline runs can be compared meaningfully:

  - JSON files are parsed, volatile keys (timestamps) are stripped, and every
    string has ``?v=<digits>`` cache-busters removed, then re-serialised sorted
    -> sha256.  This ignores mtime/version noise.
  - Images and other binaries are sha256'd byte-for-byte.

Usage:
  python -m tools.convergence_snapshot snapshot <label>
  python -m tools.convergence_snapshot compare <labelA> <labelB>

Snapshots are written to new_implementation/tools/_convergence/<label>.json
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # new_implementation/
SNAP_DIR = Path(__file__).resolve().parent / "_convergence"
SCAN_DIRS = [ROOT / "output", ROOT / "layers" / "integration"]

VOLATILE_KEYS = {
    "generated_at", "lastupdate", "last_update", "timestamp", "date",
    "created_at", "createdat", "updated_at", "updatedat", "token_timestamp",
}
VERSION_RE = re.compile(r"\?v=\d+")
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def _strip_versions(value):
    if isinstance(value, str):
        return VERSION_RE.sub("?v=", value)
    if isinstance(value, list):
        return [_strip_versions(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if isinstance(k, str) and k.lower() in VOLATILE_KEYS:
                continue
            out[k] = _strip_versions(v)
        return out
    return value


def _normalized_json_hash(path: Path) -> str | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    norm = _strip_versions(data)
    blob = json.dumps(norm, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return "json:" + hashlib.sha256(blob).hexdigest()


def _byte_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(label: str) -> Path:
    SNAP_DIR.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict] = {}
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for p in sorted(base.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(ROOT).as_posix()
            ext = p.suffix.lower()
            if ext == ".json":
                kind = "json"
                digest = _normalized_json_hash(p) or ("bytes:" + _byte_hash(p))
            elif ext in IMAGE_EXT:
                kind = "image"
                digest = "img:" + _byte_hash(p)
            else:
                kind = "other"
                digest = "bytes:" + _byte_hash(p)
            entries[rel] = {"kind": kind, "size": p.stat().st_size, "hash": digest}
    out = SNAP_DIR / f"{label}.json"
    out.write_text(json.dumps(entries, indent=0, sort_keys=True), encoding="utf-8")
    print(f"[snapshot] {label}: {len(entries)} files -> {out}")
    return out


def _load(label: str) -> dict:
    return json.loads((SNAP_DIR / f"{label}.json").read_text(encoding="utf-8"))


def compare(a_label: str, b_label: str) -> None:
    a, b = _load(a_label), _load(b_label)
    a_keys, b_keys = set(a), set(b)
    only_a = sorted(a_keys - b_keys)
    only_b = sorted(b_keys - a_keys)
    common = a_keys & b_keys

    diff_json, diff_img, diff_other = [], [], []
    for k in sorted(common):
        if a[k]["hash"] != b[k]["hash"]:
            kind = a[k]["kind"]
            (diff_json if kind == "json" else diff_img if kind == "image" else diff_other).append(k)

    print(f"\n===== COMPARE  {a_label}  vs  {b_label} =====")
    print(f"  files: {a_label}={len(a)}  {b_label}={len(b)}  common={len(common)}")
    print(f"  only in {a_label}: {len(only_a)}")
    print(f"  only in {b_label}: {len(only_b)}")
    print(f"  differing  ->  json(normalized): {len(diff_json)}   images(bytes): {len(diff_img)}   other: {len(diff_other)}")

    def _show(title, items, limit=40):
        if not items:
            return
        print(f"\n  -- {title} ({len(items)}) --")
        for x in items[:limit]:
            print(f"     {x}")
        if len(items) > limit:
            print(f"     ... (+{len(items) - limit} more)")

    _show(f"only in {a_label}", only_a)
    _show(f"only in {b_label}", only_b)
    _show("JSON content differs (structural/stat change)", diff_json)
    _show("OTHER (obj/txt) differs", diff_other)
    # images summarized only (expected to differ across tracks)
    if diff_img:
        print(f"\n  -- images differing (bytes): {len(diff_img)} (expected across tracks; sample) --")
        for x in diff_img[:15]:
            print(f"     {x}")

    verdict = "IDENTICAL" if not (only_a or only_b or diff_json or diff_img or diff_other) else \
              "STRUCTURALLY IDENTICAL (only image bytes differ)" if not (only_a or only_b or diff_json or diff_other) else \
              "DIFFERENCES FOUND"
    print(f"\n  VERDICT: {verdict}\n")


def main() -> None:
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "snapshot":
        snapshot(sys.argv[2])
    elif cmd == "compare":
        compare(sys.argv[2], sys.argv[3])
    else:
        print(f"unknown command: {cmd}")
        sys.exit(1)


if __name__ == "__main__":
    main()
