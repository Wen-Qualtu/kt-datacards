"""Ad-hoc recursive JSON diff between new_implementation/output and root output.

Usage: python tools/_jdiff.py <team-relative-path>
"""
import json, sys

NEW = r"C:\git\kt-datacards\new_implementation\output"
ROOT = r"C:\git\kt-datacards\output"


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def diff(a, b, path="", out=None):
    if out is None:
        out = []
    if type(a) != type(b):
        out.append((path, "TYPE", repr(a)[:70], repr(b)[:70]))
    elif isinstance(a, dict):
        for k in set(a) | set(b):
            if k not in a:
                out.append((path + "/" + str(k), "ONLY_ROOT", "", repr(b[k])[:70]))
            elif k not in b:
                out.append((path + "/" + str(k), "ONLY_NEW", repr(a[k])[:70], ""))
            else:
                diff(a[k], b[k], path + "/" + str(k), out)
    elif isinstance(a, list):
        if len(a) != len(b):
            out.append((path, "LEN", len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append((path, "VAL", repr(a)[:70], repr(b)[:70]))
    return out


rel = sys.argv[1]
d = diff(load(NEW + "\\" + rel), load(ROOT + "\\" + rel))
print(f"=== {rel} : {len(d)} diffs ===")
for p, k, x, y in d[:60]:
    print(f"  [{k}] {p}")
    if x != "" or k == "VAL":
        print(f"      new = {x}")
    if y != "" or k == "VAL":
        print(f"      root= {y}")
