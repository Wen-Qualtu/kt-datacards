"""Build a dev POC copy of a real team box wired for silent Sentry telemetry.

Takes an actual generated box from output/<team>/tts_objects/<Team>.json and, for
EVERY scripted object inside it (the box, the operative datacards with the stat-
loading script, the single-object-updater cards, the infinite bags, ...):
  * injects a single `KT` telemetry table (send/capture/log + guard + onError),
  * rewrites `self.addContextMenuItem(` -> `KT.addMenu(self, ...)` so every menu
    item self-reports: a successful click logs an "action" event (e.g. "Update
    done", "Load stats done") and a raised error is captured as an issue. Key
    actions also gain a "(FAIL) ..." clone (Update / Reset / Clear Layout /
    Load everything / Load stats) for testing the error path.
  * back-dates lastCardUpdate / lastTokenUpdate / lastUpdate on every object so the
    real Update path actually runs (success test) alongside the FAIL path.

Telemetry is pure backend: nothing is shown to players and every path is
pcall-wrapped, so a telemetry failure silently continues gameplay.

Output: dev/sentry-poc-<team>.json  (wrapped as a loadable Save & Load file).

Usage:  python dev/build_sentry_poc_box.py [team-slug] [Display Name]
Default: nemesis-claw / "Nemesis Claw"
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

SENTRY_KEY = "c7ee834628991c2845e5e7e6cf03f764"
SENTRY_INGEST = "https://o4512026767392768.ingest.de.sentry.io/api/4512026819231824/store/"
OLD_STAMP = "2000-01-01T00:00:00"
STAMP_KEYS = ("lastCardUpdate", "lastTokenUpdate", "lastUpdate")
MENU_CALL = "self.addContextMenuItem("
MENU_REPL = "KT.addMenu(self, "
PRELUDE_MARK = "-- === kt-datacards Sentry telemetry"

# Lua injected at the very top of every scripted object. One local (`KT`) plus a
# global onError, to keep the local/upvalue footprint tiny in large card scripts.
#
# Telemetry is PURE BACKEND: it reports both errors AND successful actions (e.g.
# "Update done", "Load stats done") but is completely invisible in-game. Nothing
# is ever broadcast to players; diagnostic prints only appear when KT.DEBUG=true.
# Every path is pcall-wrapped so a telemetry failure silently continues gameplay.
PRELUDE = r"""-- === kt-datacards telemetry (POC-injected; do not hand-edit) =================
local KT = {
    KEY    = "__KEY__",
    INGEST = "__INGEST__",
    RELEASE = "kt-datacards-poc@0.0.1",
    ENV    = "poc",
    TEAM   = "__TEAM__",
    DEBUG  = false,   -- false = pure backend: no prints, no in-game broadcasts
    reporting = false,
    -- Actions that also get a "(FAIL) ..." clone for testing.
    FAIL = {
        ["Update"] = true, ["Reset"] = true, ["Clear Layout"] = true,
        ["Load everything"] = true, ["Load stats"] = true,
    },
}

function KT.newEventId()
    return (("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"):gsub("x", function()
        return string.format("%x", math.random(0, 15))
    end))
end

function KT.resolvePlayer(color)
    local ok, info = pcall(function()
        local p = color and color ~= "" and Player[color]
        if p and p.steam_name then
            return { color = color, steam_name = p.steam_name, steam_id = p.steam_id, host = p.host }
        end
        for _, pl in ipairs(Player.getPlayers()) do
            if pl.host then
                return { color = pl.color, steam_name = pl.steam_name, steam_id = pl.steam_id, host = true, note = "host-fallback" }
            end
        end
        return nil
    end)
    if ok and info then return info end
    return { color = color or "none", steam_name = "unknown", steam_id = "unknown" }
end

-- Build + POST one Sentry event. `kind` is "error" (an issue, carries a stack-
-- like exception) or "action" (an informational breadcrumb at info level).
-- Telemetry must NEVER break gameplay or be seen by players: the whole body
-- (build + JSON.encode + WebRequest + response handling) is pcall-wrapped so any
-- internal failure is swallowed, and nothing is shown in-game (prints gated on
-- KT.DEBUG; no broadcasts at all).
function KT.send(kind, message, ctx)
    pcall(function()
        ctx = ctx or {}
        local isError = (kind == "error")
        local who = KT.resolvePlayer(ctx.playerColor)
        local event = {
            event_id    = KT.newEventId(),
            timestamp   = os.time(),
            platform    = "other",
            level       = isError and "error" or "info",
            logger      = "tts",
            transaction = ctx.source or "unknown",
            release     = KT.RELEASE,
            environment = KT.ENV,
            server_name = "tabletop-simulator",
            message     = { formatted = tostring(message) },
            user        = { id = tostring(who.steam_id or "unknown"), username = tostring(who.steam_name or "unknown") },
            tags = {
                team            = KT.TEAM,
                event_kind      = kind,
                action          = ctx.source or "unknown",
                object_type     = tostring(self.type or self.name),
                object_name     = tostring(self.name),
                object_nickname = self.getName(),
                steam_name      = tostring(who.steam_name or "unknown"),
            },
            extra = {
                object_guid  = self.getGUID(),
                player_color = who.color,
                is_host      = who.host,
                steam_id     = who.steam_id,
                note         = who.note,
            },
        }
        -- Only genuine errors carry an exception (so they open an Issue); action
        -- events stay as plain info messages.
        if isError then
            event.exception = { values = { { type = "LuaError", value = tostring(message) } } }
        end
        local headers = {
            ["Content-Type"]  = "application/json",
            ["X-Sentry-Auth"] = "Sentry sentry_version=7, sentry_client=kt-tts/0.0.1, sentry_key=" .. KT.KEY,
        }
        WebRequest.custom(KT.INGEST, "POST", true, JSON.encode(event), headers, function(req)
            if not KT.DEBUG then return end
            pcall(function()
                if req.is_error then
                    print("[KT] " .. kind .. " send FAILED (ignored): " .. tostring(req.error))
                else
                    print("[KT] " .. kind .. " sent (" .. tostring(req.response_code) .. ") as " .. tostring(who.steam_name))
                end
            end)
        end)
    end)
end

-- Report a genuine error (opens/updates a Sentry Issue).
function KT.capture(message, ctx) KT.send("error", message, ctx) end

-- Record a successful action (info-level breadcrumb, e.g. "Update done").
function KT.log(message, ctx) KT.send("action", message, ctx) end

-- Wrap a menu handler so it self-reports: a successful click logs the action,
-- a raised error is captured. Either way the handler's own result is returned.
function KT.guard(source, fn)
    return function(playerColor, ...)
        local ok, err = pcall(fn, playerColor, ...)
        if ok then
            KT.log(tostring(source) .. " done", { source = source, playerColor = playerColor })
        else
            if KT.DEBUG then print("[KT] captured '" .. tostring(source) .. "': " .. tostring(err)) end
            KT.capture(err, { source = source, playerColor = playerColor })
        end
        return ok
    end
end

-- Drop-in replacement for self.addContextMenuItem: registers the real (guarded)
-- item and, for key actions, a "(FAIL) ..." clone that raises on purpose.
function KT.addMenu(obj, label, fn, keepOpen, requireTable)
    obj.addContextMenuItem(label, KT.guard(label, fn), keepOpen, requireTable)
    if KT.FAIL[label] then
        obj.addContextMenuItem("(FAIL) " .. label, KT.guard(label, function()
            error("Simulated failure: " .. label)
        end), keepOpen, requireTable)
    end
end

-- Catch genuinely uncaught script errors on this object. Fully self-contained:
-- the flag is always reset even if capture somehow failed.
function onError(errorMessage)
    if KT.reporting then return end
    KT.reporting = true
    pcall(KT.capture, errorMessage, { source = "onError" })
    KT.reporting = false
end
-- === end kt-datacards telemetry =============================================

"""

# Appended ONLY to the ROOT box's script (after its own code) so the box emits a
# single usage ping each time it loads into a game -> real usage data without
# flooding (the 30+ inner objects do NOT get this). Chained so any existing
# onLoad still runs; `KT` is the local defined by PRELUDE in the same script.
SPAWN_HOOK = r"""

-- === kt-datacards spawn telemetry (box usage ping) ==========================
-- One info event each time the box loads into a game. Chained onto any existing
-- onLoad; pure backend, pcall-wrapped, so it never affects the box.
local KT_prevOnLoad = onLoad
function onLoad(saveState)
    if KT_prevOnLoad then KT_prevOnLoad(saveState) end
    pcall(function() KT.log("box spawned", { source = "spawn" }) end)
end
-- === end kt-datacards spawn telemetry =======================================
"""


def backdate_state(raw: str) -> str:
    if not raw:
        return raw
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return raw
    changed = False
    if isinstance(data, dict):
        for key in STAMP_KEYS:
            if key in data and isinstance(data[key], str):
                data[key] = OLD_STAMP
                changed = True
    return json.dumps(data) if changed else raw


def process(obj, prelude, stats, is_root=False) -> None:
    """Recursively inject telemetry + back-date stamps on every scripted object.

    The root box additionally gets a chained onLoad spawn ping (box-only usage).
    """
    if isinstance(obj, dict):
        lua = obj.get("LuaScript") or ""
        if lua.strip() and PRELUDE_MARK not in lua:
            n = lua.count(MENU_CALL)
            new_lua = prelude + lua.replace(MENU_CALL, MENU_REPL)
            if is_root:
                new_lua += SPAWN_HOOK
                stats["spawn_hook"] = True
            obj["LuaScript"] = new_lua
            stats["objects"] += 1
            stats["menus"] += n
        if isinstance(obj.get("LuaScriptState"), str):
            obj["LuaScriptState"] = backdate_state(obj["LuaScriptState"])
        for child in obj.get("ContainedObjects", []) or []:
            process(child, prelude, stats)
        st = obj.get("States")
        if isinstance(st, dict):
            for child in st.values():
                process(child, prelude, stats)
    elif isinstance(obj, list):
        for item in obj:
            process(item, prelude, stats)


def main() -> int:
    team = sys.argv[1] if len(sys.argv) > 1 else "nemesis-claw"
    display = sys.argv[2] if len(sys.argv) > 2 else "Nemesis Claw"

    src_path = REPO / "output" / team / "tts_objects" / f"{display}.json"
    if not src_path.exists():
        print(f"ERROR: source box not found: {src_path}")
        return 1

    box = json.loads(src_path.read_text(encoding="utf-8"))
    prelude = (PRELUDE.replace("__KEY__", SENTRY_KEY)
                      .replace("__INGEST__", SENTRY_INGEST)
                      .replace("__TEAM__", team))

    stats = {"objects": 0, "menus": 0, "spawn_hook": False}
    process(box, prelude, stats, is_root=True)

    # Make the POC box obvious in-game.
    box["Nickname"] = f"[POC] {box.get('Nickname', display)}"
    box["Description"] = (
        "SENTRY POC BOX. Every scripted object (box, datacards, cards, bags) silently\n"
        "reports to the bug tracker: successful actions log an 'action' event and\n"
        "errors open an issue. (FAIL) menu clones exist for key actions\n"
        "(Update / Reset / Clear Layout / Load everything / Load stats).\n"
        "Timestamps are back-dated so real Update runs the success path.\n"
        "Telemetry is invisible in-game; reports include your Steam name.\n\n"
    ) + box.get("Description", "")

    save = {
        "SaveName": f"KT Sentry POC - {display}",
        "Date": "", "VersionNumber": "", "GameMode": "", "GameType": "",
        "GameComplexity": "", "Tags": [], "Gravity": 0.5, "PlayArea": 0.5,
        "Table": "", "Sky": "", "Note": "", "TabStates": {},
        "LuaScript": "", "LuaScriptState": "", "XmlUI": "",
        "ObjectStates": [box],
    }
    out_path = REPO / "dev" / f"sentry-poc-{team}.json"
    out_path.write_text(json.dumps(save, indent=2), encoding="utf-8")

    inject_path = REPO / "dev" / "sentry-poc-box-inject.lua"
    # Review copy: shared telemetry + the box-only spawn ping (box gets both).
    inject_path.write_text(prelude + SPAWN_HOOK, encoding="utf-8")

    print(f"wrote {out_path.relative_to(REPO)}")
    print(f"wrote {inject_path.relative_to(REPO)}  (review-only)")
    print(f"team={team}  injected into {stats['objects']} scripted objects, "
          f"rewired {stats['menus']} menu registrations; "
          f"spawn-ping on box={stats['spawn_hook']}; stamps back-dated to {OLD_STAMP}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
