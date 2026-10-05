import json, re, sys

path = sys.argv[1] if len(sys.argv) > 1 else "output/nemesis-claw/tts_objects/Nemesis Claw.json"
d = json.load(open(path, encoding="utf-8"))
seen = {}

MARKERS = ["loadStatsToModel", "loadEverything", "Load everything", "Load stats",
           "registerSingleObjectUpdaterMenu", "Take damage", "diffAndApply",
           "findModelOnCard", "injectBlock", "click_update_single_object"]


def walk(o):
    if isinstance(o, dict):
        lua = o.get("LuaScript") or ""
        if lua.strip():
            labels = re.findall(r'addContextMenuItem\(\s*"([^"]+)"', lua)
            markers = [m for m in MARKERS if m in lua]
            key = (o.get("Name"), tuple(sorted(set(labels))), tuple(markers))
            seen.setdefault(key, [0, o.get("Nickname", "")])
            seen[key][0] += 1
        for c in o.get("ContainedObjects", []) or []:
            walk(c)
        st = o.get("States")
        if isinstance(st, dict):
            for c in st.values():
                walk(c)
    elif isinstance(o, list):
        for i in o:
            walk(i)


walk(d)
for (name, labels, markers), (cnt, nick) in sorted(seen.items(), key=lambda x: -x[1][0]):
    print(f"{cnt:3d}x  Name={name!r}")
    print(f"       labels={list(labels)}")
    print(f"       markers={list(markers)}  egNick={nick!r}")
