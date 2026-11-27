--[[ ============================================================================
  MOVE TOOL  (Proof of Concept, v1)
  A general Kill Team "Normal Move" helper for any operative.

  What a move is
  --------------
  Unlike the Exodite sprint (locked facing + a single pivot), a normal move is a
  FREE PATH: you travel up to your Move stat in as many straight legs as you
  like, changing direction at each leg. Each leg's distance rounds UP to the
  whole inch when spent (so a 1.5" leg costs 2"). Movement is measured in full
  3D, so climbing or dropping onto terrain automatically costs distance.

  Controls
  --------
  While a move is active, for the driving player:
    1 = -1" to the max move   (injured, difficult terrain, etc.)
    2 = +1" to the max move   (charge, terrain bonus, etc.)
    9 = finish (commits the current leg, applies the move)
    0 = cancel the whole move
  Mouse (via an invisible click catcher over the reach area, shown ONLY to the
  driving player -- the opponent clicks straight through it):
    LEFT-click  = commit the current leg and start the next one
    RIGHT-click = undo the last leg (or cancel from the first leg)
  The number ROW reaches the model only while it is HOVERED. Over the catch area
  (object UI) no object counts as hovered, so a small invisible button on the
  model follows the driver's cursor (see CURSOR_CATCHER_IN): hovering it counts
  as hovering the model, so 1/2/3/9/0 work wherever you aim. The numpad
  (scripting keys) and the bindable "KT: Move ..." game keys work from anywhere.
  You aim with your pointer the whole time; the ghost follows the cursor,
  clamped to the remaining budget. Hovering the ghost over a building places it
  on top (the pointer already returns the surface under the cursor), and the
  climb is charged automatically as part of the 3D leg distance. Use 1/2 to
  hand-apply any extra rule-based cost on top.

  Preview
  -------
  A grey circle shows the remaining reach from the current point. Committed legs
  are drawn dim; the active leg is green; a cyan ghost of the base (with a front
  marker) shows where the model lands. The model itself stays put until the move
  FINISHES (like the sprint tool): a dim ghost marks the last committed point,
  undo just moves that back, and cancel leaves the model where it started. The
  circle + committed legs + that ghost are drawn on the catcher helper and only
  re-sent when a step changes them; only the active leg + ghost follow the cursor.

  Injection-safe loading
  -----------------------
  Can be APPENDED to a model that already has its own script:
    * onLoad / onPickUp / onDestroy / onScriptingButtonDown / onNumberTyped are CHAINED.
    * It never WRITES self.script_state (only reads it to size the base ghost).
    * The click catcher lives on its OWN tiny, hidden, non-interactable helper
      object (per-player XML UI), so it never touches the model's self.UI (owned
      by KTUI) or its buttons. The legacy "button" mode only removes its own
      button, so it never calls clearButtons().
    * Globals it adds are uniquely named (setupMoveTool, moveOnPickUp,
      moveCatcherClick, moveScriptingButton + chained handlers).

  Assumes 1 TTS unit = 1 inch. Change UNITS_PER_INCH if your table scale differs.
============================================================================ ]]

-- ------------------------------------------------------------------ tuning ---
local MOVE_DEFAULT   = 6        -- fallback Move stat when none can be read (inches)
local DASH_INCHES    = 3        -- Dash action always starts from this budget (inches)
local UNITS_PER_INCH = 1        -- world units per inch (KT-UI table = 1)

-- Click-catcher: covers the CURRENT leg's REMAINING reach + a margin (centred on
-- curPos). As budget is spent (or the 1/2 keys change it) it re-centres and
-- shrinks (resizeCatcher) to what's left.
--   "player_ui" -- a transparent XML UI square on a tiny hidden helper object,
--                  with visibility = the driving player. It is INACTIVE for
--                  everyone else, so opponents click straight through it.
--   "button"    -- legacy: a transparent button on the model. Hovering it counts
--                  as hovering the model (number row works), but buttons are
--                  shared, so it blocks that area of the table for EVERY player.
local CATCHER_MODE         = "player_ui"
local CATCHER_MARGIN_IN    = 0.25        -- inches of catch area past the grey reach circle
local CATCHER_MIN_REACH_IN = 1.5         -- smallest catch radius (to click "finish" when spent)
-- "player_ui" mode shape: "round" = a stack of horizontal strips following the
-- reach circle; "square" = one square covering it (known-good fallback).
local CATCHER_SHAPE        = "round"
local CATCHER_STRIPS       = 12
local CATCHER_LIFT_IN      = 0.6         -- catcher height above the current point
-- "button" mode: button-units per inch. TUNING KNOB: raise = bigger, lower = smaller.
-- (14000/9 rendered ~2-3x too wide -- 40" for an 8" move; ~450 targets it.)
local CATCHER_UNITS_PER_IN = 450
-- "player_ui" mode: the helper is a locked, non-interactable BlockSquare this
-- small (invisible under the base); its UI is scaled back up by 1/scale.
local CATCHER_HELPER_SCALE = 0.4
-- In-game the object UI was CLIPPED to a fixed square (~5.5" on a 0.05-scale
-- helper), whatever the element size; the clip appears to grow with the helper's
-- scale (~110" per unit of scale), so 0.4 leaves ~44" of room. A BlockSquare is
-- big: at 0.4 it is ~5" across (seen in-game as black boxes poking through the
-- table and blocking models when sunk only 1"). So the helper is sunk this far
-- BELOW the current point (it is locked, so it stays put) to sit entirely under
-- the table; the UI is lifted back above the table.
local CATCHER_HELPER_SINK_IN = 6.0
-- "player_ui" mode: the catch area is ONE square Panel (the KTUI model script's
-- proven pattern: a top-level Panel with width/height + scale = 1/object scale).
-- UI units per inch of Panel size. TUNING KNOB: raise = bigger area.
local CATCHER_UI_UNITS_PER_IN = 100
local CATCHER_HELPER_TAG   = "KTMoveCatcher"
-- "player_ui" mode: number-row keys only reach the HOVERED object, and the UI
-- area is no object. So a small invisible button on the MODEL follows the
-- driver's cursor: hovering a model's button counts as hovering the model, so
-- 1/2/3/9/0 work wherever you aim. It only blocks the opponent on that small
-- spot. It is re-placed only when the cursor drifts CURSOR_RECENTER_IN from its
-- centre, at most once per CURSOR_MIN_INTERVAL s (buttons sync to every client).
local CURSOR_CATCHER_IN   = 2.0
local CURSOR_RECENTER_IN  = 0.6
local CURSOR_MIN_INTERVAL = 0.1
local CATCHER_TOOLTIP      = "Left click: step (click again = finish)\nRight click: undo\n1: -1\"   2: +1\"\n3: 3D range\n9: finish   0: cancel"

-- Debug overrides, read from Global vars at move start (the dev test node toggles
-- them), so catcher variants can be compared in-game without rebuilding:
--   KT_MOVE_CATCHER_MODE         "button" | "player_ui"  (overrides CATCHER_MODE)
--   KT_MOVE_CATCHER_DEBUG        true -> catcher lightly visible + helper tinted red
--   KT_MOVE_HELPER_INTERACTABLE  true -> helper object stays interactable
local function catcherModeNow()
	local m = Global.getVar("KT_MOVE_CATCHER_MODE")
	if m == "button" or m == "player_ui" then return m end
	return CATCHER_MODE
end
local function catcherDebug() return Global.getVar("KT_MOVE_CATCHER_DEBUG") == true end

-- Network smoothing. Global vector lines are re-sent to EVERY client on each
-- change and rebuilt there, so a stream of tiny updates flickers for the other
-- players. Redraw only when the pointer moved at least VECTOR_GRID_IN, and at
-- most once every DRAW_EVERY_N_TICKS ticks (30 Hz / 2 = ~15 updates/s).
local VECTOR_GRID_IN     = 0.05
local DRAW_EVERY_N_TICKS = 2

-- Default base footprint (mm); used only when a model exposes no base metadata.
local DEF_BASE_MM_LONG = 32
local DEF_BASE_MM_WIDE = 32
local BASE_MM_LONG   = DEF_BASE_MM_LONG
local BASE_MM_WIDE   = DEF_BASE_MM_WIDE
local MM_TO_INCH     = 0.0393701

-- KTUI minis face the OPPOSITE way to their transform "forward"; offset the
-- ghost facing by this when a KTUI base is detected (see refreshBaseDims).
local KTUI_FACING_OFFSET = 180

-- Drawing
local PREVIEW_HZ     = 30
local LINE_HEIGHT    = 0.20
local LINE_THICKNESS = 0.12
local COL_LEG        = { 0.20, 0.85, 0.30 }  -- active leg (green)
local COL_LEG_DONE   = { 0.12, 0.45, 0.18 }  -- committed legs (dim green)
local COL_RANGE      = { 0.55, 0.55, 0.55 }  -- grey remaining-reach circle
local COL_GHOST      = { 0.30, 0.90, 1.00 }  -- cyan destination footprint

local READOUT_FONT   = 70       -- font size of the live readout text
local VERT_RANGE     = 6        -- +/- inches shown by the 3D range column (key 3; max KT climb/drop)
local RANGE_RING_STEP = 0.5    -- vertical gap (inches) between the cylinder rings

-- Ignore a 2nd left-click within this many seconds of the previous accepted one:
-- a jittery mouse can fire a stray double-click that commits an extra step (+1").
-- Real clicks -- stepping, and the same-spot finish click -- are always well over
-- this apart, so only accidental double-clicks are swallowed.
local CLICK_DEBOUNCE_SEC = 0.2

-- A leg shorter than this (inches) counts as "no move" -> finish, not a step, and
-- the readout shows 0 additional. This is the "cancel" window: bring the ghost back
-- within this of the model to zero the next leg. Kept small (0.05") so the 0.05-0.1"
-- band is still available as a 0.1" step; also absorbs the same-spot finish residual
-- (sub-pixel / parallax off the catcher plane, ~0.000x").
local FINISH_EPS_IN = 0.05

-- --------------------------------------------------------------- constants ---
local PHASE_IDLE = "idle"
local PHASE_MOVE = "move"

-- ------------------------------------------------------------------- state ---
local phase        = PHASE_IDLE
local controlColor = nil

local baseMove     = MOVE_DEFAULT   -- the model's Move stat (inches)
local modifier     = 0              -- +/- inches from the 1/2 keys
local adjustQueue  = 0              -- queued 1/2 presses, applied in the tick loop
local usedInches   = 0              -- budget already spent (rounded up per leg)
local baseHeading  = 0              -- ghost facing (degrees; movement doesn't turn)
local facingOffset = 0
local startPos     = nil            -- Vector, where the move began
local curPos       = nil            -- Vector, current committed point (3D)
local committedLegs = {}            -- { {a=,b=}, ... }
local history      = {}
local rangeMode    = "flat"         -- "flat" circle or "3d" vertical column (key 3)
local lastLeftClickAt = -1          -- os.clock() of the last accepted left-click (debounce)

-- live preview cache
local prevRaw      = 0              -- inches of the active leg
local prevEndPos   = nil            -- Vector end of the active leg

local loopHandle    = nil
local catcherActive = false
local catcherHelper = nil       -- "player_ui" mode: the spawned helper object
local catcherSpawning = false   -- helper spawn in flight (spawnObject is async)
local activeCatcherMode = nil   -- catcher mode fixed for the current move
local lastMoveKey   = nil       -- guard: only edit the catcher when the reach/centre changes
local resizeCatcher  -- fwd decl; defined with the catcher, called from tick()
local followCursor   -- fwd decl; cursor-following number-key button, called from tick()

-- readout
local readoutText = nil
local lastSig     = nil             -- last draw signature (skip identical frames)
local ticksSinceDraw = 0            -- draw throttle (see DRAW_EVERY_N_TICKS)
local hudText     = nil             -- last HUD text sent (skip identical updates)
local lastAreaKey = nil             -- last area drawn on the helper (see areaLines)
local lastAreaOnHelper = false      -- whether the area is drawn on the helper

-- --------------------------------------------------------------- utilities ---
local function toUnits(inches) return inches * UNITS_PER_INCH end
local function toInches(units) return units / UNITS_PER_INCH end

-- Ceil inches to the 1-decimal precision the HUD shows. Both the readout and the
-- whole-inch charge are CEILINGS -- just at different accuracy (1 vs 0 decimals) --
-- so they always agree and never grant free movement (round-to-nearest would
-- shave up to ~0.05"). The tiny epsilon only absorbs float noise on a clean whole.
local function ceilToShown(inches) return math.ceil((inches - 1e-6) * 10) / 10 end

local function headingOf(x, z) return math.deg(math.atan2(x, z)) end
local function dirFromHeading(h)
	local r = math.rad(h)
	return { x = math.sin(r), z = math.cos(r) }
end

local function msg(pc, text, col)
	if pc and Player[pc] then Player[pc].broadcast(text, col or { 1, 1, 1 }) end
end

-- Active-move registry: one Global var per player color holding the GUID of the
-- model that player is currently moving (or "" for none), so the global
-- +1"/-1"/finish/cancel game-keys can reach that model even when the cursor is
-- aimed away from it (past the click-catcher).
--
-- IMPORTANT: use PRIMITIVE string vars, never a shared table. A table stored via
-- Global.setVar is OWNED by the script that created it; another model's script
-- (or the same model after a reload()) crashes with "Attempt to perform
-- operations with resources owned by different scripts" when it re-stores it.
-- Strings are copied across scripts, so they are safe to share.
local function setActiveMove(pc, on)
	if not pc then return end
	local key = "KT_MOVE_ACTIVE_" .. pc
	if on then
		Global.setVar(key, self.getGUID())
	elseif Global.getVar(key) == self.getGUID() then
		Global.setVar(key, "")
	end
end

-- ---------------------------------------------------------------- base dims --
local function parseBaseString(s)
	local a, b = tostring(s):match("(%d+%.?%d*)%s*[xX]%s*(%d+%.?%d*)")
	if a and b then return tonumber(a), tonumber(b) end
	local n = tonumber(s)
	if n then return n, n end
	return nil, nil
end

local function refreshBaseDims()
	BASE_MM_LONG, BASE_MM_WIDE = DEF_BASE_MM_LONG, DEF_BASE_MM_WIDE
	facingOffset = 0

	local ss = self.script_state
	if ss and ss ~= "" then
		local ok, data = pcall(function() return JSON.decode(ss) end)
		if ok and type(data) == "table" and type(data.base) == "table" then
			local bx = tonumber(data.base.x)
			local bz = tonumber(data.base.z)
			if bx and bx > 0 and bz and bz > 0 then
				BASE_MM_WIDE, BASE_MM_LONG = bx, bz
				facingOffset = KTUI_FACING_OFFSET
				return
			end
		end
	end

	local gmOk, gm = pcall(function() return self.getGMNotes() end)
	if gmOk and gm and gm ~= "" then
		local ok, data = pcall(function() return JSON.decode(gm) end)
		if ok and type(data) == "table" and data.Base ~= nil then
			local L, W = parseBaseString(data.Base)
			if L and W and L > 0 and W > 0 then
				BASE_MM_LONG, BASE_MM_WIDE = L, W
				return
			end
		end
	end

	local bOk, b = pcall(function() return self.getBoundsNormalized() end)
	if bOk and b and b.size and b.size.x > 0 and b.size.z > 0 then
		local wmm = b.size.x / MM_TO_INCH
		local lmm = b.size.z / MM_TO_INCH
		-- Reject a polluted read: getBoundsNormalized can balloon to the whole
		-- reach area if a leftover click-catcher BUTTON is counted in the bounds
		-- (seen on blank models). A real base -- even a winged/oval model -- is
		-- well under 120mm, so anything bigger keeps the sane default instead of
		-- an area-sized ghost.
		if wmm <= 120 and lmm <= 120 then
			BASE_MM_WIDE, BASE_MM_LONG = wmm, lmm
		end
	end
end

local function halfLong() return (BASE_MM_LONG * 0.5) * MM_TO_INCH * UNITS_PER_INCH end
local function halfWide() return (BASE_MM_WIDE * 0.5) * MM_TO_INCH * UNITS_PER_INCH end

-- Read the operative's Move stat: KTUI live state first (script_state.stats.Move),
-- then datacard GMNotes (stats.Move), else the default. This is why teams don't
-- need to set a move per operative - it comes from the datacard stat.
local function readMoveStat()
	-- 1) KTUI live state.
	local ss = self.script_state
	if ss and ss ~= "" then
		local ok, data = pcall(function() return JSON.decode(ss) end)
		if ok and type(data) == "table" and type(data.stats) == "table" then
			local v = data.stats.Move or data.stats.MOVE or data.stats.M
			local n = v and tonumber(tostring(v):match("%d+%.?%d*"))
			if n and n > 0 then return n end
		end
	end
	-- 2) datacard GMNotes.
	local gmOk, gm = pcall(function() return self.getGMNotes() end)
	if gmOk and gm and gm ~= "" then
		local ok, data = pcall(function() return JSON.decode(gm) end)
		if ok and type(data) == "table" and type(data.stats) == "table" then
			for _, key in ipairs({ "Move", "MOVE", "M", "Movement" }) do
				local v = data.stats[key]
				if v ~= nil then
					local n = tonumber(tostring(v):match("%d+%.?%d*"))
					if n and n > 0 then return n end
				end
			end
		end
	end
	return MOVE_DEFAULT
end

-- --------------------------------------------------------------- geometry ----
local function maxInches() return math.max(0, baseMove + modifier) end
local function remainingInches() return math.max(0, maxInches() - usedInches) end

-- True surface height at world (x, z): a downward physics ray that ignores the
-- moving model itself, so it sees the real table/terrain/building surface even
-- when the cursor is over the (non-collider) click-catcher. When an `aimY` is
-- given (the cursor's reported height, lifted ~0.6 by the catcher) the ray picks
-- the surface NEAREST that level, so a landing point UNDER an overhang stays on
-- the lower floor instead of snapping to the overhang's top; only when aimY is
-- omitted does it keep the legacy "highest surface" pick. Only called when the
-- cursor moves (tick's signature gate), so the cast rate stays low.
local function surfaceY(x, z, fallbackY, aimY)
	local base = (curPos and curPos.y) or self.getPosition().y
	local hits = Physics.cast({
		origin       = { x = x, y = base + 25, z = z },
		direction    = { 0, -1, 0 },
		type         = 1,   -- ray
		max_distance = 60,
	})
	local best = nil
	for _, h in ipairs(hits or {}) do
		if h.hit_object ~= self and h.hit_object ~= catcherHelper and h.point then
			if aimY == nil then
				if best == nil or h.point.y > best then best = h.point.y end
			elseif best == nil or math.abs(h.point.y - aimY) < math.abs(best - aimY) then
				best = h.point.y
			end
		end
	end
	return best or fallbackY
end

-- Active leg preview: HORIZONTAL (2D) distance from curPos toward the pointer,
-- clamped to the remaining budget. Kill Team measures the move in 2D; a vertical
-- climb/drop is a separate penalty the player applies with the 1/2 keys. The
-- ghost sits on the ACTUAL surface under its landing point (via surfaceY), so it
-- tracks terrain/buildings instead of floating on the click-catcher's plane.
local function legPreview(pointer)
	-- No budget left: freeze the ghost exactly at the current point so it doesn't
	-- bob up/down with the cursor's surface height (there is nowhere left to go).
	if remainingInches() <= 1e-6 then
		return 0, { x = curPos.x, y = curPos.y, z = curPos.z }
	end
	local dx = pointer.x - curPos.x
	local dz = pointer.z - curPos.z
	local horiz = math.sqrt(dx * dx + dz * dz)
	if horiz < 1e-6 then
		return 0, { x = curPos.x, y = surfaceY(curPos.x, curPos.z, curPos.y, curPos.y), z = curPos.z }
	end
	local d = math.min(horiz, toUnits(remainingInches()))
	local s = d / horiz
	local ex = curPos.x + dx * s
	local ez = curPos.z + dz * s
	local endPos = { x = ex, y = surfaceY(ex, ez, curPos.y, pointer.y), z = ez }
	return toInches(d), endPos
end

-- ----------------------------------------------------------------- drawing ---
local function line(a, b, color, thick)
	return {
		points    = { { a.x, a.y + LINE_HEIGHT, a.z }, { b.x, b.y + LINE_HEIGHT, b.z } },
		color     = color,
		thickness = thick or LINE_THICKNESS,
	}
end

-- Grey remaining-reach circle on the plane of the current point.
local function appendCircle(out, centre, radiusInches, color)
	local r = toUnits(radiusInches)
	if r <= 0 then return end
	local pts, steps = {}, 48
	for i = 0, steps do
		local t = (i / steps) * 2 * math.pi
		pts[#pts + 1] = { centre.x + math.cos(t) * r, centre.y + LINE_HEIGHT, centre.z + math.sin(t) * r }
	end
	table.insert(out, { points = pts, color = color, thickness = LINE_THICKNESS * 0.6 })
end

-- 3D range column (key 3): the remaining-reach circle stacked as closely spaced
-- thin rings from VERT below to VERT above the current level, joined by a few
-- vertical struts, so it reads as a cylinder while staying light. Lets the 2D
-- range be measured against the height of nearby terrain / buildings.
local function appendRangeVolume(out, centre, radiusInches, vertInches, color)
	local r = toUnits(radiusInches)
	if r <= 0 then return end
	local v    = toUnits(vertInches)
	local yc   = centre.y + LINE_HEIGHT
	local seg  = 32
	local step = toUnits(RANGE_RING_STEP)
	if step <= 0 then step = toUnits(0.5) end
	local y = yc - v
	while y <= yc + v + 1e-6 do
		local pts = {}
		for i = 0, seg do
			local t = (i / seg) * 2 * math.pi
			pts[#pts + 1] = { centre.x + math.cos(t) * r, y, centre.z + math.sin(t) * r }
		end
		table.insert(out, { points = pts, color = color, thickness = LINE_THICKNESS * 0.6 })
		y = y + step
	end
	local struts = 16
	for i = 0, struts - 1 do
		local t = (i / struts) * 2 * math.pi
		local x = centre.x + math.cos(t) * r
		local z = centre.z + math.sin(t) * r
		table.insert(out, { points = { { x, yc - v, z }, { x, yc + v, z } }, color = color, thickness = LINE_THICKNESS * 0.6 })
	end
end

-- Corridor for one leg: centre line + two parallel edges offset by half the base
-- width, so the path shows the swept SIDES of the base (not just the centre).
local function appendLegCorridor(out, a, b, color)
	table.insert(out, line(a, b, color))
	local dx, dz = b.x - a.x, b.z - a.z
	local len = math.sqrt(dx * dx + dz * dz)
	if len < 1e-6 then return end
	local sx, sz = -dz / len, dx / len          -- unit perpendicular
	local hw = halfWide()
	local aL = { x = a.x + sx * hw, y = a.y, z = a.z + sz * hw }
	local bL = { x = b.x + sx * hw, y = b.y, z = b.z + sz * hw }
	local aR = { x = a.x - sx * hw, y = a.y, z = a.z - sz * hw }
	local bR = { x = b.x - sx * hw, y = b.y, z = b.z - sz * hw }
	table.insert(out, line(aL, bL, color, LINE_THICKNESS * 0.7))
	table.insert(out, line(aR, bR, color, LINE_THICKNESS * 0.7))
end

-- Closed oval base outline centred at (cx,cy,cz). No facing marker - a normal
-- move doesn't care about rotation.
local function appendGhost(out, cx, cy, cz, heading, color)
	local aLong = halfLong()
	local bWide = halfWide()
	local fdir  = dirFromHeading(heading)
	local sdir  = dirFromHeading(heading + 90)
	local pts, steps = {}, 40
	for i = 0, steps do
		local t  = (i / steps) * 2 * math.pi
		local fl = aLong * math.cos(t)
		local sl = bWide * math.sin(t)
		table.insert(pts, {
			cx + fdir.x * fl + sdir.x * sl,
			cy + LINE_HEIGHT,
			cz + fdir.z * fl + sdir.z * sl,
		})
	end
	table.insert(out, { points = pts, color = color or COL_GHOST, thickness = LINE_THICKNESS * 0.8 })
end

-- The static "area": the remaining-reach range (flat circle or 3D column) plus
-- the committed legs. It only changes when a step commits / is undone, the 1/2
-- keys change the budget or 3 toggles the range mode -- not when the cursor moves.
-- Range shows where the base EDGE can reach: the centre's travel budget plus the
-- base half-length, so the ring lands at the operative's max footprint.
local function areaLines()
	local lines = {}
	for _, leg in ipairs(committedLegs) do
		appendLegCorridor(lines, leg.a, leg.b, COL_LEG_DONE)
	end
	local reach = remainingInches() + toInches(halfLong())
	if rangeMode == "3d" then
		appendRangeVolume(lines, curPos, reach, VERT_RANGE, COL_RANGE)
	else
		appendCircle(lines, curPos, reach, COL_RANGE)
	end
	-- The model only moves when the move finishes: mark the committed point
	-- (where the model will be) with a dim ghost base.
	if #committedLegs > 0 then
		appendGhost(lines, curPos.x, curPos.y, curPos.z, baseHeading, COL_LEG_DONE)
	end
	return lines
end

-- Draw world-space lines as the helper object's OWN vector lines. Object lines
-- are in the object's local (scaled) space, so points and thickness are divided
-- by the helper scale (it is never rotated). Only re-sent when the area changes,
-- so other players don't receive the whole range circle / 3D column every time
-- the driver's cursor moves.
local function drawAreaOnHelper(helper, lines)
	local p   = helper.getPosition()
	local inv = 1 / CATCHER_HELPER_SCALE
	local out = {}
	for _, l in ipairs(lines) do
		local pts = {}
		for i, q in ipairs(l.points) do
			pts[i] = { (q[1] - p.x) * inv, (q[2] - p.y) * inv, (q[3] - p.z) * inv }
		end
		out[#out + 1] = { points = pts, color = l.color, thickness = (l.thickness or LINE_THICKNESS) * inv }
	end
	helper.setVectorLines(out)
end

-- Global lines carry only what follows the cursor (active leg + ghost), plus the
-- area when it can't live on the helper (button mode / helper still spawning).
local function redraw(active, endPos, includeArea)
	local lines = includeArea and areaLines() or {}
	for _, l in ipairs(active or {}) do table.insert(lines, l) end
	if endPos then
		appendGhost(lines, endPos.x, endPos.y, endPos.z, baseHeading)
	end
	Global.setVectorLines(lines)
end

local function clearPreview() Global.setVectorLines({}) end

-- --------------------------------------------------- distance readout (HUD) --
-- A screen-space, top-centre readout via Global.UI. Unlike a world 3DText it is
-- NEVER hidden by terrain and is NOT written to chat. One row per player colour,
-- coloured to that player, so simultaneous moves stack (blue + red, ...) and
-- every player can read them.
--
-- Global.UI is shared, and setXml REPLACES it wholesale; another feature
-- (Chapter Tactics' fr_info_panel) also uses it. So we APPEND our container to
-- whatever UI already exists (never clobber it) and re-append if it goes
-- missing. Per-row updates use setAttribute/setValue, which don't replace the UI.
local HUD_COLORS = { "White", "Brown", "Red", "Orange", "Yellow",
                     "Green", "Teal", "Blue", "Purple", "Pink" }

local function hudColorHex(c)
	local col = Color.fromString(c)
	if not col then return "#FFFFFF" end
	-- Lighten toward white so darker player colours stay readable via the outline.
	col = col:lerp(Color.White, 0.25)
	return "#" .. col:toHex(false)
end

local function buildHudXml()
	-- Bare outlined text per colour (no background box, so it hugs the value and
	-- can't stretch). A strong black outline keeps it readable over any terrain.
	-- The layout forces each text to the container width and centres it, so it
	-- always renders (a width-less Text can collapse to nothing in a layout).
	local rows = ""
	for _, c in ipairs(HUD_COLORS) do
		rows = rows .. string.format(
			'<Text id="ktmove_txt_%s" active="false" color="%s" fontSize="26" '
			.. 'fontStyle="Bold" alignment="Center" preferredHeight="32" '
			.. 'outline="#000000" outlineSize="2 -2" raycastTarget="false"> </Text>', c, hudColorHex(c))
	end
	return '<Panel id="ktmove_hud" active="true" rectAlignment="UpperCenter" '
		.. 'width="600" height="120" offsetXY="0 -80" color="#00000000" raycastTarget="false">'
		.. '<VerticalLayout childAlignment="UpperCenter" childForceExpandWidth="true" '
		.. 'childForceExpandHeight="false" spacing="2" raycastTarget="false">'
		.. rows
		.. '</VerticalLayout></Panel>'
end

-- Ensure our HUD container exists in the (possibly shared) Global UI WITHOUT
-- wiping anything else already there. Called at move start (once), not per frame.
local function ensureHud()
	local cur = ""
	pcall(function() cur = Global.UI.getXml() or "" end)
	if type(cur) ~= "string" then cur = "" end
	if cur:find("ktmove_hud", 1, true) then return end
	pcall(function() Global.UI.setXml(cur .. buildHudXml()) end)
	-- The new XML loads a few frames later; updates sent before then are lost,
	-- so re-apply the current readout once it is there.
	Wait.frames(function()
		if controlColor and hudText then
			local c, t = controlColor, hudText
			pcall(function()
				Global.UI.setAttribute("ktmove_txt_" .. c, "active", "true")
				Global.UI.setValue("ktmove_txt_" .. c, t)
			end)
		end
	end, 5)
end

-- Show/update this player's HUD row. Global UI changes are synced to every
-- client, so only push when the text changed -- re-sending identical attributes
-- every tick made the HUD flicker remotely. "active" is re-asserted with each
-- change: a freshly appended HUD (ensureHud) only loads a few frames later, so a
-- one-off activation could be lost and leave the row hidden.
local function hudShow(color, text)
	if not color then return end
	text = text or " "
	if text == hudText then return end
	hudText = text
	pcall(function()
		Global.UI.setAttribute("ktmove_txt_" .. color, "active", "true")
		Global.UI.setValue("ktmove_txt_" .. color, text)
	end)
end

local function hudHide(color)
	hudText = nil
	if not color then return end
	pcall(function()
		Global.UI.setAttribute("ktmove_txt_" .. color, "active", "false")
		Global.UI.setValue("ktmove_txt_" .. color, " ")
	end)
end

-- ------------------------------------------------------------- update loop ---
local function tick()
	if phase ~= PHASE_MOVE or not controlColor then return end

	-- Drain queued 1/2 budget presses. The key handler only ADDS to the queue
	-- (cheapest possible), so no press is ever lost even when hit faster than the
	-- frame rate; here we apply the whole accumulated total at once.
	if adjustQueue ~= 0 then
		local applied = adjustQueue
		if maxInches() + applied < usedInches then
			applied = usedInches - maxInches()
		end
		modifier = modifier + applied
		adjustQueue = 0
	end

	local pointer = Player[controlColor].getPointerPosition()
	if not pointer then return end
	resizeCatcher()   -- match the catch area to the CURRENT leg's remaining reach (no-op unless it changed)
	followCursor(pointer)

	-- The area lives on the helper and is redrawn only when it changes. When it
	-- moves on/off the helper (spawn finished), force a Global redraw so it isn't
	-- drawn twice or dropped.
	local areaOnHelper = (catcherHelper ~= nil)
	if areaOnHelper then
		local areaKey = string.format("%.3f_%.3f_%.3f_%d_%d_%s_%d",
			curPos.x, curPos.y, curPos.z, usedInches, modifier, rangeMode, #committedLegs)
		if areaKey ~= lastAreaKey then
			lastAreaKey = areaKey
			drawAreaOnHelper(catcherHelper, areaLines())
		end
	end
	if areaOnHelper ~= lastAreaOnHelper then
		lastAreaOnHelper = areaOnHelper
		lastSig = nil
	end

	-- Skip the whole rebuild when nothing that affects the drawing changed
	-- (pointer still + no budget / leg / mode change). This keeps the tool light
	-- instead of re-sending all vector lines and text every frame.
	-- With no budget left the ghost is frozen at curPos (see legPreview), so drop
	-- the pointer from the signature: roaming the cursor over terrain of different
	-- heights must NOT rebuild the draw or make the ghost bob up/down.
	local px, py, pz = pointer.x, pointer.y, pointer.z
	if remainingInches() <= 1e-6 then px, py, pz = 0, 0, 0 end
	-- Snap the pointer to a coarse grid so sub-grid jitter doesn't re-send lines.
	local g = toUnits(VECTOR_GRID_IN)
	local sig = string.format("%d_%d_%d_%d_%d_%s_%d",
		math.floor(px / g + 0.5), math.floor(py / g + 0.5), math.floor(pz / g + 0.5),
		usedInches, modifier, rangeMode, #committedLegs)
	ticksSinceDraw = ticksSinceDraw + 1
	if sig == lastSig then return end
	-- Throttle: leave lastSig untouched so the change is drawn on a later tick.
	if lastSig ~= nil and ticksSinceDraw < DRAW_EVERY_N_TICKS then return end
	lastSig = sig
	ticksSinceDraw = 0

	local active = {}
	readoutText = nil

	local raw, e = legPreview(pointer)
	prevRaw, prevEndPos = raw, e
	appendLegCorridor(active, curPos, e, COL_LEG)

	-- Live total shows the distance CEIL'd to one decimal (committed whole inches +
	-- the current leg). A leg below FINISH_EPS_IN reads as 0 here because a click
	-- there FINISHES (no step), so a sub-threshold hover doesn't look like it costs
	-- the next whole inch -- you can bring the ghost back onto the committed point to cancel.
	local legShown = (raw < FINISH_EPS_IN) and 0 or ceilToShown(raw)
	local liveTotal = usedInches + legShown
	readoutText = string.format('%.1f" / %d"', liveTotal, maxInches())
		.. (modifier ~= 0 and string.format(" (%+d)", modifier) or "")

	redraw(active, e, not areaOnHelper)
	hudShow(controlColor, readoutText)
end

local function startLoop()
	if loopHandle then return end
	loopHandle = Wait.time(tick, 1 / PREVIEW_HZ, -1)
end

local function stopLoop()
	if loopHandle then
		Wait.stop(loopHandle)
		loopHandle = nil
	end
end

-- --------------------------------------------------------- click catcher ----
-- An invisible catch area over the CURRENT leg's reach (a square of half-size =
-- REMAINING budget + margin, centred on curPos). LEFT-click = step, RIGHT-click =
-- undo. As you spend budget it re-centres on the new point and shrinks to what's
-- left, so it never claims more than needed. See CATCHER_MODE for the two kinds.

-- Half-reach (inches) of the catch area for the CURRENT leg: the same radius as
-- the grey reach circle (remaining budget + base half-length) plus a small
-- margin, floored so a nearly-spent move still has a clickable area to finish.
local function catcherReachIn()
	local r = remainingInches() + toInches(halfLong()) + CATCHER_MARGIN_IN
	return (r < CATCHER_MIN_REACH_IN) and CATCHER_MIN_REACH_IN or r
end

local function catcherKey()
	if not curPos then return "none" end
	return string.format("%.2f:%.2f:%.2f", curPos.x, curPos.z, catcherReachIn())
end

-- Remove every catcher/follower button currently on the model. Collect indices
-- first and remove high->low: removeButton(index) reshuffles the remaining
-- indices, so removing while iterating by index can skip a button (leaving a
-- stale catcher). Also clears a stale button left by an older version.
local function clearCatcherButtons()
	local idx = {}
	for _, b in ipairs(self.getButtons() or {}) do
		if b.click_function == "moveCatcherClick" or b.click_function == "moveFollowerClick" then
			idx[#idx + 1] = b.index
		end
	end
	table.sort(idx, function(a, b) return a > b end)
	for _, i in ipairs(idx) do self.removeButton(i) end
end

-- "button" mode: (re)create the catcher as a FRESH square button centred on the
-- current committed point (curPos -- the model itself only moves on finish).
-- We remove+recreate rather than editButton because editing a button's
-- size/position does not reliably rebuild its invisible click hitbox in TTS.
-- hover/press colours are fully transparent too: the defaults tint the area
-- whenever ANY player's mouse passes over it, which reads as flicker for the
-- opponent.
local function placeCatcherButton()
	clearCatcherButtons()
	local sc   = self.getScale()
	local span = 2 * catcherReachIn() * CATCHER_UNITS_PER_IN
	-- Debug: a light green tint shows the exact catch area (visible to everyone --
	-- buttons can't be per-player).
	local col  = catcherDebug() and { 0.2, 1, 0.2, 0.25 } or { 0, 0, 0, 0 }
	local lp   = self.positionToLocal({ curPos.x, curPos.y + toUnits(CATCHER_LIFT_IN), curPos.z })
	self.createButton({
		click_function = "moveCatcherClick",
		function_owner = self,
		label          = "",
		-- Button positions mirror x vs positionToLocal (see followCursor).
		position       = { -lp.x, lp.y, lp.z },
		rotation       = { 0, 0, 0 },
		width          = span / (sc.x ~= 0 and sc.x or 1),
		height         = span / (sc.z ~= 0 and sc.z or 1),
		font_size      = 100,
		color          = col,
		hover_color    = col,
		press_color    = col,
		tooltip        = CATCHER_TOOLTIP,
	})
end

-- "player_ui" mode: the catch area is object XML UI on a helper object, scale =
-- 1/helper scale (UI units per inch: CATCHER_UI_UNITS_PER_IN). "square": one
-- Panel covering the reach circle. "round": CATCHER_STRIPS horizontal Panels,
-- each as wide as the circle at its widest point within the strip, so the whole
-- circle is covered with only small steps past its edge (strips overlap a
-- little: no gaps). A resize re-sends the XML. visibility = the driving player
-- makes it INACTIVE (no raycast) for everyone else. onClick is routed to THIS
-- model's script via the "GUID/function" prefix.
local function catcherRects(r)
	if CATCHER_SHAPE ~= "round" then
		return { { z = 0, width = 2 * r, depth = 2 * r } }
	end
	local n, out = CATCHER_STRIPS, {}
	local h = 2 * r / n
	for i = 0, n - 1 do
		local y0, y1 = -r + i * h, -r + (i + 1) * h
		local ym = (y0 <= 0 and y1 >= 0) and 0 or math.min(math.abs(y0), math.abs(y1))
		out[#out + 1] = {
			z     = (y0 + y1) / 2,
			width = 2 * math.sqrt(math.max(0, r * r - ym * ym)),
			depth = h * 1.04,
		}
	end
	return out
end

local function catcherUiXml()
	local inv  = 1 / CATCHER_HELPER_SCALE
	local u    = CATCHER_UI_UNITS_PER_IN
	local col  = catcherDebug() and "#33FF3340" or "#00000001"
	-- Negative z = up; lift from the sunk helper to CATCHER_LIFT_IN above the point.
	local lift = -toUnits(CATCHER_HELPER_SINK_IN + CATCHER_LIFT_IN) * u * inv
	local parts = {}
	for i, s in ipairs(catcherRects(catcherReachIn())) do
		parts[#parts + 1] = string.format(
			'<Panel id="ktMoveCatcher%d" visibility="%s" color="%s" raycastTarget="true" '
			.. 'width="%d" height="%d" position="0 %.1f %.1f" rotation="0 0 0" scale="%.4f %.4f %.4f" '
			.. 'onClick="%s/moveCatcherUIClick" tooltip="%s"></Panel>',
			i, controlColor or "", col,
			math.floor(toUnits(s.width) * u + 0.5), math.floor(toUnits(s.depth) * u + 0.5),
			toUnits(s.z) * u * inv, lift, inv, inv, inv, self.getGUID(),
			(CATCHER_TOOLTIP:gsub('"', "&quot;"):gsub("\n", "&#10;")))
	end
	return table.concat(parts)
end

-- Destroy stray helpers: any tagged helper that isn't the one this model is using
-- AND whose owner (memo = owner GUID) isn't moving right now (per the
-- KT_MOVE_ACTIVE_<color> registry). Catches helpers left by a save/reload
-- mid-move or by a model that was respawned with a new GUID.
local function destroyOwnHelpers()
	local ok, list = pcall(getObjectsWithTag, CATCHER_HELPER_TAG)
	if not ok or type(list) ~= "table" then return end
	local me, active = self.getGUID(), {}
	for _, c in ipairs(HUD_COLORS) do
		local g = Global.getVar("KT_MOVE_ACTIVE_" .. c)
		if type(g) == "string" and g ~= "" then active[g] = true end
	end
	for _, o in ipairs(list) do
		if o ~= nil and o ~= catcherHelper then
			local owner = o.getMemo()
			if owner == me or not active[owner] then o.destruct() end
		end
	end
end

-- Where the helper sits: under the current point, sunk below the surface.
local function helperSpot()
	return { curPos.x, curPos.y - toUnits(CATCHER_HELPER_SINK_IN), curPos.z }
end

local function placeCatcherHelper()
	if catcherHelper ~= nil then
		catcherHelper.setPosition(helperSpot())
		catcherHelper.UI.setXml(catcherUiXml())
		return
	end
	if catcherSpawning then return end
	catcherSpawning = true
	local s   = CATCHER_HELPER_SCALE
	local pos = helperSpot()
	spawnObjectData({
		data = {
			Name      = "BlockSquare",
			Transform = { posX = pos[1], posY = pos[2], posZ = pos[3], rotX = 0, rotY = 0, rotZ = 0,
			              scaleX = s, scaleY = s, scaleZ = s },
			Nickname  = "KT move catcher",
			Memo      = self.getGUID(),
			Tags      = { CATCHER_HELPER_TAG },
			Locked    = true,
			Tooltip   = false,
			DragSelectable = false,
		},
		callback_function = function(o)
			catcherSpawning = false
			-- The move ended while the spawn was in flight: don't leave it behind.
			if not catcherActive or not curPos then o.destruct(); return end
			o.setLock(true)
			local debug = catcherDebug()
			o.interactable = (Global.getVar("KT_MOVE_HELPER_INTERACTABLE") == true)
			o.setColorTint(debug and { 1, 0.1, 0.1, 0.8 } or { 0, 0, 0, 0 })
			o.setName("KT move catcher")
			o.setMemo(self.getGUID())
			o.addTag(CATCHER_HELPER_TAG)
			catcherHelper = o
			-- A leg may have been committed while spawning: use the CURRENT point.
			o.setPosition(helperSpot())
			o.UI.setXml(catcherUiXml())
			if debug then
				local hp = o.getPosition()
				msg(controlColor, string.format(
					"[move debug] helper %s at %.2f, %.2f, %.2f  scale %.2f  interactable=%s  catch %.1f\" wide",
					o.getGUID(), hp.x, hp.y, hp.z, CATCHER_HELPER_SCALE, tostring(o.interactable),
					2 * catcherReachIn()), { 0.6, 1, 0.6 })
			end
		end,
	})
end

local function placeCatcher()
	if activeCatcherMode == "button" then
		placeCatcherButton()
	else
		placeCatcherHelper()
	end
end

local function createCatcher()
	if catcherActive then return end
	catcherActive = true
	activeCatcherMode = catcherModeNow()
	clearCatcherButtons()
	destroyOwnHelpers()
	if catcherDebug() then
		msg(controlColor, "[move debug] catcher mode: " .. activeCatcherMode, { 0.6, 1, 0.6 })
	end
	placeCatcher()
	lastMoveKey   = catcherKey()
end

-- Re-centre + resize the catcher to the CURRENT leg's reachable area (remaining
-- budget around curPos). Guarded so it only rebuilds when the reach/centre
-- actually changes (a leg commits, a 1/2 budget change, or a step-back), never
-- per frame -- so there is no cursor-follow lag. Assigns the forward-declared
-- upvalue so tick() (defined earlier) can call it.
resizeCatcher = function()
	if not catcherActive or not curPos then return end
	local key = catcherKey()
	if key == lastMoveKey then return end   -- nothing changed -> no rebuild (no lag)
	lastMoveKey = key
	placeCatcher()
	if catcherDebug() then
		msg(controlColor, string.format("[move debug] catch area should now be %.1f\" wide", 2 * catcherReachIn()), { 0.6, 1, 0.6 })
	end
end

-- Cursor follower (player_ui mode only; see CURSOR_CATCHER_IN). Created ONCE
-- per move and then only MOVED with editButton: removing + recreating it each
-- time left a trail of stale buttons for the other players (the removals reach
-- them late), blocking those spots of the table. Its click does the same
-- step/undo as the catcher. It carries the key-help tooltip: it is always under
-- the cursor, so the help pops up just like it did on the old shared button.
local followerAt, followerKey, followerTime = nil, nil, -1

local function followerIndex()
	for _, b in ipairs(self.getButtons() or {}) do
		if b.click_function == "moveFollowerClick" then return b.index end
	end
	return nil
end

local function clearFollower()
	followerAt, followerKey = nil, nil
	clearCatcherButtons()
end

followCursor = function(pointer)
	if not catcherActive or activeCatcherMode == "button" or not pointer then return end
	local key = catcherKey()   -- the committed point changes on commit/undo: re-place
	if followerAt and key == followerKey then
		local dx, dz = pointer.x - followerAt.x, pointer.z - followerAt.z
		if dx * dx + dz * dz < toUnits(CURSOR_RECENTER_IN) ^ 2 then return end
	end
	local now = os.clock()
	if followerAt and key == followerKey and now - followerTime < CURSOR_MIN_INTERVAL then return end
	followerTime = now
	followerAt   = { x = pointer.x, z = pointer.z }
	followerKey  = key
	local lp  = self.positionToLocal({ pointer.x, pointer.y + toUnits(CATCHER_LIFT_IN + 0.1), pointer.z })
	-- Button positions use a MIRRORED x axis vs positionToLocal (seen in-game:
	-- unflipped, the follower moved away from the cursor sideways).
	local pos = { -lp.x, lp.y, lp.z }
	local idx = followerIndex()
	if idx then
		self.editButton({ index = idx, position = pos })
		return
	end
	local sc   = self.getScale()
	local span = CURSOR_CATCHER_IN * CATCHER_UNITS_PER_IN
	local col  = catcherDebug() and { 0.2, 0.5, 1, 0.35 } or { 0, 0, 0, 0 }
	self.createButton({
		click_function = "moveFollowerClick",
		function_owner = self,
		label          = "",
		position       = pos,
		rotation       = { 0, 0, 0 },
		width          = span / ((sc.x ~= 0) and sc.x or 1),
		height         = span / ((sc.z ~= 0) and sc.z or 1),
		font_size      = 100,
		color          = col,
		hover_color    = col,
		press_color    = col,
		tooltip        = CATCHER_TOOLTIP,
	})
end

local function removeCatcher()
	if not catcherActive then return end
	catcherActive = false
	clearFollower()
	if catcherHelper ~= nil then catcherHelper.destruct() end
	catcherHelper = nil
end

-- ------------------------------------------------------------ history/undo ---
local function pushHistory()
	table.insert(history, {
		pos      = { x = curPos.x, y = curPos.y, z = curPos.z },
		used     = usedInches,
		modifier = modifier,
		legs     = #committedLegs,
	})
end

local function restoreFrom(s)
	curPos      = { x = s.pos.x, y = s.pos.y, z = s.pos.z }
	usedInches  = s.used
	modifier    = s.modifier
	while #committedLegs > s.legs do table.remove(committedLegs) end
end

-- ------------------------------------------------------------ state changes --
local function applyToModel()
	local r = self.getRotation()
	self.setPosition({ curPos.x, curPos.y, curPos.z })
	self.setRotation({ r.x, r.y, r.z })   -- movement doesn't change facing
end

local function finishMove(pc, text)
	stopLoop()
	clearPreview()
	removeCatcher()
	hudHide(pc or controlColor)
	setActiveMove(pc or controlColor, false)
	applyToModel()
	msg(pc, text or string.format('Move complete: %d" used.', usedInches), COL_LEG)
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
end

local function cancelMove(pc)
	stopLoop()
	clearPreview()
	removeCatcher()
	hudHide(pc or controlColor)
	setActiveMove(pc or controlColor, false)
	-- The model never left its start point (only the ghost moved): nothing to undo.
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
	if pc then msg(pc, "Move cancelled.", COL_RANGE) end
end

-- A quiet teardown for when the player physically PICKS UP the model mid-move:
-- stop the preview, drop the HUD/catcher and clear the active flag, but DON'T
-- snap the model back and DON'T broadcast a "cancelled" message -- the pickup is
-- a deliberate manual reposition, not a cancel, so it shouldn't give false
-- "Move cancelled" feedback.
local function abortMove()
	stopLoop()
	clearPreview()
	removeCatcher()
	hudHide(controlColor)
	setActiveMove(controlColor, false)
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
end

local function beginMove(pc, forcedBase)
	refreshBaseDims()
	controlColor = pc
	local p      = self.getPosition()
	startPos     = { x = p.x, y = p.y, z = p.z }
	curPos       = { x = p.x, y = p.y, z = p.z }
	local fwd    = self.getTransformForward()
	baseHeading  = headingOf(fwd.x, fwd.z) + facingOffset
	baseMove     = forcedBase or readMoveStat()
	modifier     = 0
	adjustQueue  = 0
	usedInches   = 0
	rangeMode    = "flat"
	committedLegs = {}
	history      = {}
	lastSig      = nil
	ticksSinceDraw = 0
	hudText      = nil
	lastAreaKey  = nil
	lastAreaOnHelper = false
	lastLeftClickAt = -1
	phase        = PHASE_MOVE
	startLoop()
	createCatcher()
	ensureHud()
	setActiveMove(pc, true)
end

local function commitLeg(rawIn, endPos)
	if rawIn <= 1e-6 then return false end
	pushHistory()
	table.insert(committedLegs, {
		a = { x = curPos.x, y = curPos.y, z = curPos.z },
		b = { x = endPos.x, y = endPos.y, z = endPos.z },
	})
	usedInches = usedInches + math.ceil(ceilToShown(rawIn) - 1e-6)
	curPos     = { x = endPos.x, y = endPos.y, z = endPos.z }
	-- The model itself stays put until the move finishes (applyToModel); a ghost
	-- marks the committed point (areaLines) and the catcher follows curPos.
	-- Each committed step lands flat; the next increment starts in 2D again.
	-- (3D is only needed while measuring a climb/drop; re-toggle with 3 if so.)
	rangeMode  = "flat"
	return true
end

-- LEFT-click: commit the current leg and start the next. A click that would
-- commit a ZERO-length leg finishes the move instead - this happens when the
-- budget is spent (ghost can't advance) or when you click again without moving
-- the cursor (a "double-click" to confirm). Recompute from the live pointer so a
-- double-click faster than a tick still reads the true leg length.
local function advance(pc)
	local pointer = Player[pc] and Player[pc].getPointerPosition()
	if pointer then
		local raw, e = legPreview(pointer)
		prevRaw, prevEndPos = raw, e
	end
	if not prevEndPos then return end
	if prevRaw < FINISH_EPS_IN then
		-- Finish only if we've already moved or the budget is spent; otherwise
		-- ignore, so a stray click at the very start doesn't end the move instantly.
		if #committedLegs > 0 or remainingInches() <= 0 then
			finishMove(pc, string.format('Move complete: %d" used.', usedInches))
		end
		return
	end
	commitLeg(prevRaw, prevEndPos)
end

-- RIGHT-click: undo the last leg (or cancel from the first).
local function stepBack(pc)
	if #history == 0 then
		cancelMove(pc)
		return
	end
	local s = table.remove(history)
	restoreFrom(s)
	msg(pc, "Stepped back.", COL_LEG)
end

-- Key 9: commit the current leg (if any) and finish.
local function finishNow(pc)
	if prevEndPos then commitLeg(prevRaw, prevEndPos) end
	finishMove(pc, string.format('Move complete: %d" used.', usedInches))
end

-- Handle a number key. IMPORTANT: TTS can merge rapid same-key presses on the
-- number row into a single multi-digit number (two quick 1s arrive as 11), so
-- for the budget keys we DECOMPOSE the number into its digits and queue each one
-- (11 -> two -1; 12 -> -1 then +1). The tick loop applies the summed total, so
-- no press is lost no matter how fast you tap. 1 = -1", 2 = +1".
local function handleDigit(pc, number)
	if phase ~= PHASE_MOVE then return false end
	if controlColor and pc ~= controlColor then return false end
	-- Deliberate single-press commands.
	if number == 3 then
		rangeMode = (rangeMode == "3d") and "flat" or "3d"
		return true
	elseif number == 9 then
		finishNow(pc)
		return true
	elseif number == 0 then
		cancelMove(pc)
		return true
	end
	local matched = false
	for d in tostring(number):gmatch("%d") do
		if d == "1" then adjustQueue = adjustQueue - 1; matched = true
		elseif d == "2" then adjustQueue = adjustQueue + 1; matched = true end
	end
	return matched
end

-- ----------------------------------------------------------------- wiring ----
-- Invisible catcher handler. altClick == true means a right-click (undo).
function moveCatcherClick(_, playerColor, altClick)
	if phase ~= PHASE_MOVE then return end
	if controlColor and playerColor ~= controlColor then return end
	if altClick then
		stepBack(playerColor)
	else
		-- Debounce accidental double-clicks (jittery mice): swallow a left-click that
		-- lands within CLICK_DEBOUNCE_SEC of the last accepted one so it can't eat an
		-- extra step. Intentional step/finish clicks are always well over this apart.
		local now = os.clock()
		if now - lastLeftClickAt < CLICK_DEBOUNCE_SEC then return end
		lastLeftClickAt = now
		advance(playerColor)
	end
end

-- Per-player XML catcher handler ("player_ui" mode). UI events pass (player,
-- mouseButton, id): "-1" left = step, "-2" right = undo, "-3" middle = ignored.
function moveCatcherUIClick(player, mouseButton, _id)
	if mouseButton == "-3" then return end
	moveCatcherClick(nil, player and player.color, mouseButton == "-2")
end

-- Cursor-follower button click (see followCursor): same as the catcher.
function moveFollowerClick(obj, playerColor, altClick)
	moveCatcherClick(obj, playerColor, altClick)
end

function moveScriptingButton(index, playerColor)
	handleDigit(playerColor, index == 10 and 0 or index)
end

-- Hotkey entry point (called on the HOVERED model by the global hotkey below).
function moveHotkeyTrigger(params)
	if phase == PHASE_IDLE then beginMove((params or {}).color) end
end

-- Dash is identical to Move but always starts from a fixed DASH_INCHES budget
-- instead of the model's Move stat.
function dashHotkeyTrigger(params)
	if phase == PHASE_IDLE then beginMove((params or {}).color, DASH_INCHES) end
end

-- Per-action entry points for the global game-keys, called on the active-move
-- model. The +/-1" nudges only ADD to the per-tick queue (like the number keys),
-- so presses are coalesced and applied once per tick (no redraw-per-press cost),
-- yet each press is captured instantly (no number-row multi-digit input wait).
function moveAdjustPlus(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	adjustQueue = adjustQueue + 1
end

function moveAdjustMinus(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	adjustQueue = adjustQueue - 1
end

function moveFinishHotkey(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	finishNow(pc)
end

function moveCancelHotkey(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	cancelMove(pc)
end

function moveToggleRangeHotkey(params)
	local pc = (params or {}).color
	if phase ~= PHASE_MOVE then return end
	if controlColor and pc and pc ~= controlColor then return end
	rangeMode = (rangeMode == "3d") and "flat" or "3d"
end

-- Resolve the model a player is currently moving: prefer the active-move
-- registry (works even when the cursor is aimed away from it), fall back to the
-- hovered object.
local function moveAdjustDispatch(color, hovered, fn)
	local obj = nil
	local guid = Global.getVar("KT_MOVE_ACTIVE_" .. color)
	if type(guid) == "string" and guid ~= "" then obj = getObjectFromGUID(guid) end
	if obj == nil and hovered ~= nil and hovered.call ~= nil then obj = hovered end
	if obj ~= nil and obj.call ~= nil then obj.call(fn, { color = color }) end
end

function setupMoveTool()
	destroyOwnHelpers()
	self.addContextMenuItem("Move", function(pc)
		if phase == PHASE_IDLE then beginMove(pc) end
	end, false)
	self.addContextMenuItem("Dash", function(pc)
		if phase == PHASE_IDLE then beginMove(pc, DASH_INCHES) end
	end, false)
	-- Optional keyboard shortcuts. Registered ONCE globally (guarded via Global
	-- vars) so they aren't re-registered by every model; each callback starts the
	-- action on whatever model the player is HOVERING. Bind keys under
	-- Options -> Controls -> Game Keys ("KT: Move/Dash (hovered model)").
	if Global.getVar("KT_MOVE_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_HOTKEY", true)
		addHotkey("KT: Move (hovered model)", function(color, hovered)
			if hovered ~= nil and hovered.call ~= nil then
				hovered.call("moveHotkeyTrigger", { color = color })
			end
		end, false)
	end
	if Global.getVar("KT_DASH_HOTKEY") ~= true then
		Global.setVar("KT_DASH_HOTKEY", true)
		addHotkey("KT: Dash (hovered model)", function(color, hovered)
			if hovered ~= nil and hovered.call ~= nil then
				hovered.call("dashHotkeyTrigger", { color = color })
			end
		end, false)
	end
	-- Per-action game-keys (instant, rebindable). They feed the SAME per-tick queue
	-- as the number keys and reach the active-move model via the registry, so
	-- binding them sidesteps the number row's built-in multi-digit input wait.
	if Global.getVar("KT_MOVE_PLUS_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_PLUS_HOTKEY", true)
		addHotkey("KT: Move +1 inch", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveAdjustPlus")
		end, false)
	end
	if Global.getVar("KT_MOVE_MINUS_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_MINUS_HOTKEY", true)
		addHotkey("KT: Move -1 inch", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveAdjustMinus")
		end, false)
	end
	if Global.getVar("KT_MOVE_FINISH_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_FINISH_HOTKEY", true)
		addHotkey("KT: Move finish", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveFinishHotkey")
		end, false)
	end
	if Global.getVar("KT_MOVE_CANCEL_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_CANCEL_HOTKEY", true)
		addHotkey("KT: Move cancel", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveCancelHotkey")
		end, false)
	end
	if Global.getVar("KT_MOVE_RANGE_HOTKEY") ~= true then
		Global.setVar("KT_MOVE_RANGE_HOTKEY", true)
		addHotkey("KT: Move toggle 3D range", function(color, hovered)
			moveAdjustDispatch(color, hovered, "moveToggleRangeHotkey")
		end, false)
	end
end

function moveOnPickUp(playerColor)
	-- A manual pickup is NOT a cancel: tear down the preview/HUD/catcher quietly
	-- and leave the model where the player drops it (no snap-back, no callout).
	if phase ~= PHASE_IDLE then abortMove() end
end

local _move_prev_onLoad = onLoad
function onLoad(...)
	-- pcall-guard the host's onLoad: a broken host extender (e.g. a third-party
	-- KTUI / Command Node extender that errors inside its own refreshUI) must not
	-- abort loading and drop the Move tool. Our setup always runs; the host keeps
	-- whatever it managed to complete before the error.
	if _move_prev_onLoad then pcall(_move_prev_onLoad, ...) end
	setupMoveTool()
end

local _move_prev_onPickUp = onPickUp
function onPickUp(...)
	if _move_prev_onPickUp then _move_prev_onPickUp(...) end
	moveOnPickUp(...)
end

local _move_prev_onDestroy = onDestroy
function onDestroy(...)
	if _move_prev_onDestroy then pcall(_move_prev_onDestroy, ...) end
	-- Deleting the model mid-move: take the helper (and HUD row) with it.
	if phase ~= PHASE_IDLE then abortMove() end
end

local _move_prev_onScriptingButtonDown = onScriptingButtonDown
function onScriptingButtonDown(...)
	if _move_prev_onScriptingButtonDown then _move_prev_onScriptingButtonDown(...) end
	moveScriptingButton(...)
end

local _move_prev_onNumberTyped = onNumberTyped
function onNumberTyped(playerColor, number, alt)
	if phase ~= PHASE_IDLE and (not controlColor or playerColor == controlColor) then
		handleDigit(playerColor, number)
		return true
	end
	if _move_prev_onNumberTyped then return _move_prev_onNumberTyped(playerColor, number, alt) end
end
