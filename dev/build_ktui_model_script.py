"""Compose the model-load Lua for our cards:

    composed = patch( vendored extractor output ) + our extension Lua

The composed script REPLACES the bundled mimic as the KTUI_MODELSCRIPT our cards
stamp onto a model, so a single "Load stats" gives the real KTUI mini (dynamic
health bar, order tokens, table Save/Load + Ready hooks) PLUS our code.

Patch layer (deterministic, anchor-based, each verified -- FAILS LOUD on drift):
  1. heal getWoundPanelWidth (bare `if` -> `elseif`)  -- append-safety, bar-neutral
  2. remove the "Movement" context item               -- we load our own movement
  3. guard the unguarded game-log call (bare-table safety)

NOT patched here: owner assignment. The CARD sets it on load
(model.call("setOwningPlayer", <clicking player's steam_id>)) because only the
card knows who clicked "Load stats".

Inputs : dev/ktui-extender-modelscript.lua (from extract_ktui_extender.py)
         dev/ktui-extension.lua              (our model-side additions)
Output : dev/ktui-model-composed.lua         (the composed KTUI_MODELSCRIPT)

Usage:
    python dev/build_ktui_model_script.py
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
VENDORED = HERE / "ktui-extender-modelscript.lua"
EXTENSION = HERE / "ktui-extension.lua"
OUT = HERE / "ktui-model-composed.lua"


def strip_header(text: str) -> str:
    """Drop our provenance header comment block (keep the extender code)."""
    lines = text.splitlines()
    i = 0
    while i < len(lines) and lines[i].startswith("--"):
        i += 1
    # also skip the blank line after the header
    while i < len(lines) and lines[i].strip() == "":
        i += 1
    return "\n".join(lines[i:])


def apply_patch(text: str, name: str, pattern: str, repl: str, *, count: int = 1,
                flags: int = 0) -> str:
    new, n = re.subn(pattern, repl, text, flags=flags)
    if n != count:
        raise SystemExit(
            f"PATCH FAILED [{name}]: expected {count} substitution(s), applied {n}. "
            "Upstream shape changed -- review the extractor/composer anchors."
        )
    print(f"  patch OK [{name}]: {n} substitution(s)")
    return new


def heal_wound_panel(text: str) -> str:
    # Two bare `if` after a `return N` should be `elseif`.
    for ret_val, nxt in (("60", "10"), ("80", "14")):
        text = apply_patch(
            text, f"heal-getWoundPanelWidth-{ret_val}",
            r"(return\s+" + ret_val + r"\s*\n\s*)if(\s+wounds\s*<=\s*" + nxt + r"\s+then)",
            r"\1elseif\2",
        )
    return text


def remove_movement(text: str) -> str:
    return apply_patch(
        text, "remove-Movement-context-item",
        r'[ \t]*self\.addContextMenuItem\(\s*"Movement"\s*,\s*function\(pc\)\s*agregaRuta\(\)\s*end\)\s*\n',
        "-- [KT] Movement context item removed (we load our own movement).\n",
    )


def guard_gamelog(text: str) -> str:
    return apply_patch(
        text, "guard-gameLogAppendOperativeChangedState",
        r'getObjectFromGUID\(gamelogGuid\)\.call\("gameLogAppendOperativeChangedState",\s*event\)',
        'local _kt_gl = getObjectFromGUID(gamelogGuid)\n'
        '    if _kt_gl then _kt_gl.call("gameLogAppendOperativeChangedState", event) end',
    )


def main() -> int:
    for p in (VENDORED, EXTENSION):
        if not p.exists():
            print(f"ERROR: missing input {p.relative_to(ROOT)} "
                  "(run extract_ktui_extender.py first?)")
            return 2

    base = strip_header(VENDORED.read_text(encoding="utf-8")).replace("\r\n", "\n")
    ext = EXTENSION.read_text(encoding="utf-8").replace("\r\n", "\n")

    print("Applying patch layer ...")
    base = heal_wound_panel(base)
    base = remove_movement(base)
    base = guard_gamelog(base)

    composed_body = base.rstrip("\n") + "\n\n" + ext.rstrip("\n") + "\n"
    h = hashlib.sha1(composed_body.encode("utf-8")).hexdigest()
    header = (
        "-- KTUI model-load script -- COMPOSED (generated; do not hand-edit)\n"
        "-- = patch(dev/ktui-extender-modelscript.lua) + dev/ktui-extension.lua\n"
        "-- Built by dev/build_ktui_model_script.py. Original extender by\n"
        "-- Nyirsh, Feuerfritas, Ixidior, Mal20k (Steam Workshop 3573927734).\n"
        "-- Patches: heal getWoundPanelWidth, remove Movement item, guard game-log call.\n"
        "-- Owner (state.owner) is set card-side via setOwningPlayer on load.\n"
        f"-- Provenance: {len(composed_body)} chars, sha1 {h}\n\n"
    )
    OUT.write_text(header + composed_body, encoding="utf-8")
    print(f"\nWrote composed -> {OUT.relative_to(ROOT)} "
          f"({len(composed_body)} chars body, sha1 {h[:10]})")

    # Prove append-safety: after healing, the whole thing should be balanced Lua.
    # TTS/MoonSharp accepts operators strict luaparser rejects (e.g. `!=`), so
    # sanitize those for the STRUCTURAL check only -- the written output stays
    # verbatim/TTS-valid.
    try:
        from luaparser import ast
        probe = re.sub(r"!=", "~=", header + composed_body)
        ast.parse(probe)
        print("Lua parse: OK (healed script + extension is balanced -> append-safe)")
    except ImportError:
        print("Lua parse: skipped (luaparser not installed)")
    except Exception as e:  # noqa: BLE001
        print(f"Lua parse: WARNING -> {e}")
        print("  (may be another MoonSharp-ism, not necessarily a real imbalance -- "
              "verify the flagged line before trusting)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
