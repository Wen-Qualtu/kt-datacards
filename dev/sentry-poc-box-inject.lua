-- === kt-datacards telemetry (POC-injected; do not hand-edit) =================
local KT = {
    KEY    = "c7ee834628991c2845e5e7e6cf03f764",
    INGEST = "https://o4512026767392768.ingest.de.sentry.io/api/4512026819231824/store/",
    RELEASE = "kt-datacards-poc@0.0.1",
    ENV    = "poc",
    TEAM   = "nemesis-claw",
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

