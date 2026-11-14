"""Extract + patch the real KT Command Node UI Extender model script from a
Tabletop Simulator mod save, as a feasibility prototype (Option C).

This is a manual-trigger DEV tool (the extender is updated rarely; a late
refresh is fine). It:

  1. Reads a TTS mod save JSON (default: dev/3573927734.json).
  2. Walks every object's LuaScript and finds the ones that carry the KTUI
     model script (anchored on `function refreshUI` + `getWoundPanelWidth`).
  3. De-duplicates them; if there is more than one distinct variant it reports
     that (a signal the extractor's canonical pick needs review).
  4. Stores the canonical script VERBATIM (full mimic) into the tracked file
     dev/ktui-extender-modelscript.lua, with a provenance/attribution header.
  5. Prints a diff versus our bundled mimic plus the known integration targets
     (the "Movement" context item + its lua, and the getWoundPanelWidth state)
     to prep the downstream append/edit step.

The extractor is anchor-based and FAILS LOUDLY if the upstream shape changes,
so a silent bad extraction can't slip into the vendored base.

Usage:
    python dev/extract_ktui_extender.py [path/to/mod.json]

Attribution: the extracted script is the work of the KT Command Node UI Extender
authors (Nyirsh, Feuerfritas, Ixidior, Mal20k); kept in the provenance header.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_MOD = ROOT / "dev" / "3573927734.json"  # local, gitignored mod save
OUR_MIMIC = ROOT / "config" / "defaults" / "tts-script" / "ktui-mini-modelscript.lua"
VENDORED = ROOT / "config" / "defaults" / "tts-script" / "ktui-extender-modelscript.lua"
SOURCE_ID = "3573927734"  # Steam Workshop: KT Command Node UI Extender

# A script is the KTUI model script if it contains all of these anchors.
ANCHORS = ("function refreshUI", "getWoundPanelWidth", "function loadState")


def iter_lua_scripts(node):
    """Yield every LuaScript string found anywhere in the parsed save."""
    if isinstance(node, dict):
        s = node.get("LuaScript")
        if isinstance(s, str) and s.strip():
            yield s
        for v in node.values():
            yield from iter_lua_scripts(v)
    elif isinstance(node, list):
        for v in node:
            yield from iter_lua_scripts(v)


def is_model_script(s: str) -> bool:
    return all(a in s for a in ANCHORS)


def norm(s: str) -> str:
    """Whitespace-normalised form for de-duplication."""
    return re.sub(r"\s+", " ", s).strip()


def wound_panel_bare_ifs(script: str) -> int:
    """How many bare `if` branches the getWoundPanelWidth chain still has.

    0 = balanced. Non-zero means appending code after this script is unsafe
    until it's fixed (the missing `end`s swallow the appended code). Reported
    only -- we vendor verbatim; any fix is a downstream decision.
    """
    bad = 0
    for ret_val, nxt in (("60", "10"), ("80", "14")):
        if re.search(r"return\s+" + ret_val + r"\s*\n\s*if\s+wounds\s*<=\s*" + nxt, script):
            bad += 1
    return bad


def provenance_header(script: str) -> str:
    h = hashlib.sha1(script.encode("utf-8")).hexdigest()
    return (
        "-- KTUI Extender model script -- VENDORED EXTRACTION (generated; do not hand-edit)\n"
        f"-- Source: Steam Workshop mod {SOURCE_ID} (KT Command Node UI Extender)\n"
        "-- Original authors: Nyirsh, Feuerfritas, Ixidior, Mal20k\n"
        "-- Extracted by dev/extract_ktui_extender.py -- re-run to refresh.\n"
        f"-- Provenance: {len(script)} chars, sha1 {h}\n"
        "-- Verbatim (full mimic). Downstream integration removes the \"Movement\"\n"
        "-- context item + its lua and appends our KT tool blocks (like the cards).\n"
        "\n"
    )


def report_integration_targets(script: str) -> None:
    print("\n--- integration targets (for the append/edit phase) ---")
    for i, ln in enumerate(script.splitlines(), 1):
        low = ln.lower()
        if "addcontextmenuitem" in low and "movement" in low:
            print(f"  L{i}: Movement context item -> {ln.strip()}")
        elif re.match(r"\s*function\s+agregaRuta\b", ln):
            print(f"  L{i}: function agregaRuta (movement route builder)")
        elif re.match(r"\s*function\s+agregaCono\b", ln):
            print(f"  L{i}: function agregaCono (targeting lines)")
    bad = wound_panel_bare_ifs(script)
    if bad:
        print(f"  getWoundPanelWidth: {bad} bare-if branch(es) -> UNBALANCED. Appending code "
              "after this script is UNSAFE until fixed (owner patch or a heal step).")
    else:
        print("  getWoundPanelWidth: balanced (safe to append).")


def main() -> int:
    mod_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_MOD
    if not mod_path.exists():
        print(f"ERROR: mod save not found: {mod_path}")
        print("Drop the latest KTUI mod save JSON here or pass a path.")
        return 2

    print(f"Reading {mod_path} ({mod_path.stat().st_size / 1_048_576:.1f} MB) ...")
    with mod_path.open(encoding="utf-8") as f:
        save = json.load(f)

    found = [s for s in iter_lua_scripts(save) if is_model_script(s)]
    if not found:
        print("ERROR: no object carried the KTUI model script (anchors not found).")
        print("Upstream shape may have changed; extractor needs review.")
        return 1

    # Group by normalised form to detect variants.
    groups: dict[str, list[str]] = {}
    for s in found:
        groups.setdefault(norm(s), []).append(s)

    print(f"\nFound the model script on {len(found)} object(s), "
          f"{len(groups)} distinct variant(s).")
    for i, (_, members) in enumerate(sorted(groups.items(), key=lambda kv: -len(kv[1])), 1):
        rep = members[0]
        h = hashlib.sha1(rep.encode("utf-8")).hexdigest()[:10]
        print(f"  variant {i}: {len(members):>3} copies | {len(rep):>6} chars | sha1 {h}")

    if len(groups) > 1:
        print("  NOTE: multiple variants present -- picking the most common as canonical.")

    canonical = max(groups.values(), key=len)[0]
    VENDORED.write_text(provenance_header(canonical) + canonical.rstrip("\n") + "\n",
                        encoding="utf-8")
    print(f"\nStored vendored -> {VENDORED.relative_to(ROOT)} ({len(canonical)} chars + header)")

    # Compare with our bundled mimic.
    print("\n--- vs our bundled mimic ---")
    if OUR_MIMIC.exists():
        mimic = OUR_MIMIC.read_text(encoding="utf-8")
        real_fns = set(re.findall(r"function\s+([A-Za-z_][\w]*)\s*\(", canonical))
        mimic_fns = set(re.findall(r"function\s+([A-Za-z_][\w]*)\s*\(", mimic))
        print(f"  mimic size:      {len(mimic):>6} chars, {len(mimic_fns)} top-level functions")
        print(f"  extracted size:  {len(canonical):>6} chars, {len(real_fns)} top-level functions")
        only_real = sorted(real_fns - mimic_fns)
        only_mimic = sorted(mimic_fns - real_fns)
        if only_real:
            print(f"  in real, not mimic ({len(only_real)}): {', '.join(only_real)}")
        if only_mimic:
            print(f"  in mimic, not real ({len(only_mimic)}): {', '.join(only_mimic)}")
        if not only_real and not only_mimic:
            print("  function sets match.")
    else:
        print(f"  (our mimic not found at {OUR_MIMIC.relative_to(ROOT)})")

    report_integration_targets(canonical)
    print("\nDone. Re-run to refresh after an owner update.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
