-- kt-datacards: Sentry telemetry POC  [source for dev/sentry-poc-box.json]
-- A standalone TTS "box" that reports errors to Sentry so we can verify what
-- context we can capture BEFORE touching real boxes.
--
-- Regenerate the JSON after editing this file with the inline embed command
-- (see chat / session memory): reads this .lua, writes dev/sentry-poc-box.json.

-- === Sentry config (client-side DSN key; safe to embed) =====================
local SENTRY_KEY    = "c7ee834628991c2845e5e7e6cf03f764"
local SENTRY_INGEST = "https://o4512026767392768.ingest.de.sentry.io/api/4512026819231824/store/"
local RELEASE       = "kt-datacards-poc@0.0.1"
local ENVIRONMENT   = "poc"

-- Stamped per object at generation time for real boxes. Hardcoded for the POC.
local KT_TEAM       = "poc-team"

-- 32 hex chars, no dashes (Sentry event_id format).
local function newEventId()
    return (("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"):gsub("x", function()
        return string.format("%x", math.random(0, 15))
    end))
end

-- Resolve the clicking player's Steam identity (nil color -> fall back to host).
local function resolvePlayer(color)
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

-- Build + POST a Sentry event. ctx: { source, playerColor, objectType, team, operative }
local function sentryCapture(message, ctx)
    ctx = ctx or {}
    local who = resolvePlayer(ctx.playerColor)
    local objectType = ctx.objectType or self.type or self.name

    local event = {
        event_id    = newEventId(),
        timestamp   = os.time(),
        platform    = "other",
        level       = "error",
        logger      = "tts",
        transaction = ctx.source or "unknown",
        release     = RELEASE,
        environment = ENVIRONMENT,
        server_name = "tabletop-simulator",
        message     = { formatted = tostring(message) },
        exception   = {
            values = {
                { type = "LuaError", value = tostring(message) },
            },
        },
        -- Native Sentry user -> powers "users affected" + who to contact.
        user = {
            id       = tostring(who.steam_id or "unknown"),
            username = tostring(who.steam_name or "unknown"),
        },
        -- Searchable/filterable in Sentry.
        tags = {
            team            = ctx.team or KT_TEAM,
            action          = ctx.source or "unknown",
            object_type     = tostring(objectType),
            object_nickname = self.getName(),
            operative       = ctx.operative or "",
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

    local headers = {
        ["Content-Type"]  = "application/json",
        ["X-Sentry-Auth"] = "Sentry sentry_version=7, sentry_client=kt-tts/0.0.1, sentry_key=" .. SENTRY_KEY,
    }

    WebRequest.custom(SENTRY_INGEST, "POST", true, JSON.encode(event), headers, function(req)
        if req.is_error then
            print("[Sentry] send FAILED: " .. tostring(req.error))
            broadcastToAll("Sentry send failed: " .. tostring(req.error), {1, 0.3, 0.3})
        else
            print("[Sentry] sent (" .. tostring(req.response_code) .. ") as " .. tostring(who.steam_name))
            broadcastToAll("Reported to bug tracker (" .. tostring(req.response_code) .. ") as " .. tostring(who.steam_name), {0.4, 1, 0.4})
        end
    end)
end

-- Wrap a handler so any Lua error is reported to Sentry with the clicker's
-- identity. Context-menu callbacks pass (player_color, position, object).
local function guard(source, extra, fn)
    return function(playerColor, ...)
        local ok, err = pcall(fn, playerColor, ...)
        if not ok then
            local ctx = { source = source, playerColor = playerColor }
            for k, v in pairs(extra or {}) do ctx[k] = v end
            print("[Sentry] captured '" .. source .. "': " .. tostring(err))
            sentryCapture(err, ctx)
        end
    end
end

function onLoad()
    math.randomseed(os.time())
    self.setName("KT Sentry POC Box")
    self.setDescription("Right-click to simulate box / card / model-load errors. Errors are reported to a bug tracker (includes your Steam name so we can follow up).")

    -- Simulate the three cases you want to tell apart in Sentry:
    self.addContextMenuItem("Fail: box update",         guard("box-update",         { objectType = "Bag" }, failNilIndex))
    self.addContextMenuItem("Fail: card load-stats",    guard("card-load-stats",    { objectType = "Card", operative = "Stalker Alpha" }, failNilIndex))
    self.addContextMenuItem("Fail: model feature load", guard("model-feature-load", { objectType = "Figurine", operative = "Stalker Alpha" }, failCallNil))
    self.addContextMenuItem("Send test ping",           guard("ping", {}, doPing))
end

-- Intentional errors --------------------------------------------------------
function failNilIndex()
    local payload = nil
    return payload.missing_field  -- attempt to index a nil value
end

function failCallNil()
    local apply = nil
    return apply()                 -- attempt to call a nil value
end

function doPing(playerColor)
    sentryCapture("POC manual test ping", { source = "ping", playerColor = playerColor })
end
