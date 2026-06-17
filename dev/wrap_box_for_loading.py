"""Wrap a clean team box JSON (bare object) into a TTS save-file format
for debugging via Game -> Save & Load -> Load -> .json.

The clean *.json files in output/<team>/tts_objects/ are bare objects
(Custom_Model_Bag), suitable for spawnObjectJSON but NOT for TTS's
save-file loader, which requires a top-level save wrapper with proper
Grid/Lighting/PlayArea fields.

Usage:
  python dev/wrap_box_for_loading.py hierotek-circle
  python dev/wrap_box_for_loading.py hierotek-circle --out dev/test-output/hierotek-loadable.json
  python dev/wrap_box_for_loading.py --all       # wrap every team into dev/loadable/

Output (default): dev/loadable/<Team>.json
"""
import json
import os
import sys
from datetime import datetime, timezone


def empty_save_wrapper():
    """Minimal valid TTS save-file structure that the loader accepts."""
    return {
        "SaveName": "",
        "Date": "",
        "VersionNumber": "",
        "GameMode": "",
        "GameType": "",
        "GameComplexity": "",
        "Tags": [],
        "Gravity": 0.5,
        "PlayArea": 0.5,
        "Table": "",
        "Sky": "",
        "Note": "",
        "TabStates": {},
        "LuaScript": "",
        "LuaScriptState": "",
        "XmlUI": "",
        "ObjectStates": [],
    }


def find_clean_path(team_slug):
    tdir = os.path.join("output", team_slug, "tts_objects")
    if not os.path.isdir(tdir):
        return None
    for fn in os.listdir(tdir):
        if fn.endswith(".json") and not fn.endswith(" Box.json") and "urls" not in fn.lower():
            return os.path.join(tdir, fn)
    return None


def wrap(clean_path, out_path):
    with open(clean_path, encoding="utf-8-sig") as f:
        bare = json.load(f)
    wrapper = empty_save_wrapper()
    wrapper["SaveName"] = bare.get("Nickname") or os.path.basename(clean_path)[:-5]
    wrapper["Date"] = datetime.now(timezone.utc).strftime("%m/%d/%Y %I:%M:%S %p")
    wrapper["ObjectStates"] = [bare]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(wrapper, f, indent=2, ensure_ascii=False)
    return os.path.getsize(out_path)


def main():
    args = sys.argv[1:]
    if not args or "-h" in args or "--help" in args:
        print(__doc__)
        return 1

    out_arg = None
    if "--out" in args:
        i = args.index("--out")
        out_arg = args[i + 1]
        args = args[:i] + args[i + 2 :]

    if args == ["--all"]:
        teams = sorted(
            d for d in os.listdir("output")
            if os.path.isdir(os.path.join("output", d, "tts_objects"))
        )
        out_dir = "dev/loadable"
        n = 0
        for team in teams:
            cp = find_clean_path(team)
            if not cp:
                continue
            name = os.path.basename(cp)
            wrap(cp, os.path.join(out_dir, name))
            n += 1
        print(f"Wrapped {n} teams into {out_dir}/")
        return 0

    team = args[0]
    clean = find_clean_path(team)
    if not clean:
        print(f"No clean .json found for team '{team}' in output/{team}/tts_objects/")
        return 1
    out = out_arg or os.path.join("dev/loadable", os.path.basename(clean))
    size = wrap(clean, out)
    print(f"Wrote {out}  ({size/1024:.1f} KB)")
    print("Load it via TTS: Games -> Save & Load -> bottom-right ... -> open this .json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
