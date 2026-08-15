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
  Mouse (via an invisible click catcher pinned to the model):
    LEFT-click  = commit the current leg and start the next one
    RIGHT-click = undo the last leg (or cancel from the first leg)
  You aim with your pointer the whole time; the ghost follows the cursor,
  clamped to the remaining budget. Hovering the ghost over a building places it
  on top (the pointer already returns the surface under the cursor), and the
  climb is charged automatically as part of the 3D leg distance. Use 1/2 to
  hand-apply any extra rule-based cost on top.

  Preview
  -------
  A grey circle shows the remaining reach from the current point. Committed legs
  are drawn dim; the active leg is green; a cyan ghost of the base (with a front
  marker) shows where the model lands.

  Injection-safe loading
  -----------------------
  Can be APPENDED to a model that already has its own script:
    * onLoad / onPickUp / onScriptingButtonDown / onNumberTyped are CHAINED.
    * It never WRITES self.script_state (only reads it to size the base ghost).
    * The click catcher is a transparent button pinned to the model, sized to the
      current reach (resized live as the 1/2 keys change it) and removed by its
      own click_function, so it never calls clearButtons().
    * Globals it adds are uniquely named (setupMoveTool, moveOnPickUp,
      moveCatcherClick, moveScriptingButton + chained handlers).

  Assumes 1 TTS unit = 1 inch. Change UNITS_PER_INCH if your table scale differs.
============================================================================ ]]

-- ------------------------------------------------------------------ tuning ---
local MOVE_DEFAULT   = 6        -- fallback Move stat when none can be read (inches)
local DASH_INCHES    = 3        -- Dash action always starts from this budget (inches)
local UNITS_PER_INCH = 1        -- world units per inch (KT-UI table = 1)

-- Click-catcher: a transparent button pinned to the model, covering the CURRENT
-- leg's REMAINING reach + a margin (a disc centred on curPos), so hovering it
-- counts as hovering the model (the number ROW works with no key binding) and it
-- only locks a small area, not the table. As budget is spent (or the 1/2 keys
-- change it) the catcher re-centres and shrinks (resizeCatcher) to what's left.
local CATCHER_MARGIN_IN    = 1           -- inches of catch area past the reach
-- button-units per inch. TUNING KNOB: raise = bigger catcher, lower = smaller.
-- (14000/9 rendered ~2-3x too wide -- 40" for an 8" move; ~450 targets it.)
local CATCHER_UNITS_PER_IN = 450

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

-- live preview cache
local prevRaw      = 0              -- inches of the active leg
local prevEndPos   = nil            -- Vector end of the active leg

local loopHandle    = nil
local catcherActive = false
local lastMoveKey   = nil       -- guard: only edit the catcher when the reach/centre changes
local resizeCatcher  -- fwd decl; defined with the catcher, called from tick()

-- readout
local readoutText = nil
local lastSig     = nil             -- last draw signature (skip identical frames)

-- --------------------------------------------------------------- utilities ---
local function toUnits(inches) return inches * UNITS_PER_INCH end
local function toInches(units) return units / UNITS_PER_INCH end

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
		BASE_MM_WIDE = b.size.x / MM_TO_INCH
		BASE_MM_LONG = b.size.z / MM_TO_INCH
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
-- moving model itself. We can't trust the pointer's reported Y because the
-- click-catcher (a UI button pinned ~0.6 above the model) lifts it and keeps it
-- flat; the catcher is NOT a physics collider, so the ray sees the real
-- table/terrain/building surface instead. Only called when the cursor actually
-- moves (tick's signature gate), so the cast rate stays low even on slow PCs.
local function surfaceY(x, z, fallbackY)
	local base = (curPos and curPos.y) or self.getPosition().y
	local hits = Physics.cast({
		origin       = { x = x, y = base + 25, z = z },
		direction    = { 0, -1, 0 },
		type         = 1,   -- ray
		max_distance = 60,
	})
	local best = nil
	for _, h in ipairs(hits or {}) do
		if h.hit_object ~= self and h.point and (best == nil or h.point.y > best) then
			best = h.point.y
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
		return 0, { x = curPos.x, y = surfaceY(curPos.x, curPos.z, curPos.y), z = curPos.z }
	end
	local d = math.min(horiz, toUnits(remainingInches()))
	local s = d / horiz
	local ex = curPos.x + dx * s
	local ez = curPos.z + dz * s
	local endPos = { x = ex, y = surfaceY(ex, ez, curPos.y), z = ez }
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

local function redraw(active, endPos)
	local lines = {}
	for _, leg in ipairs(committedLegs) do
		appendLegCorridor(lines, leg.a, leg.b, COL_LEG_DONE)
	end
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
end

local function hudShow(color, text)
	if not color then return end
	pcall(function()
		Global.UI.setAttribute("ktmove_txt_" .. color, "active", "true")
		Global.UI.setValue("ktmove_txt_" .. color, text or " ")
	end)
end

local function hudHide(color)
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

	-- Skip the whole rebuild when nothing that affects the drawing changed
	-- (pointer still + no budget / leg / mode change). This keeps the tool light
	-- instead of re-sending all vector lines and text every frame.
	-- With no budget left the ghost is frozen at curPos (see legPreview), so drop
	-- the pointer from the signature: roaming the cursor over terrain of different
	-- heights must NOT rebuild the draw or make the ghost bob up/down.
	local px, py, pz = pointer.x, pointer.y, pointer.z
	if remainingInches() <= 1e-6 then px, py, pz = 0, 0, 0 end
	local sig = string.format("%.2f_%.2f_%.2f_%d_%d_%s_%d",
		px, py, pz, usedInches, modifier, rangeMode, #committedLegs)
	if sig == lastSig then return end
	lastSig = sig

	local active = {}
	readoutText = nil

	-- Remaining-reach range from the current point (flat circle, or a 3D column).
	-- Range shows where the base EDGE can reach: the centre's travel budget plus
	-- the base half-length, so the ring lands at the operative's max footprint
	-- rather than where the centre stops.
	local reach = remainingInches() + toInches(halfLong())
	if rangeMode == "3d" then
		appendRangeVolume(active, curPos, reach, VERT_RANGE, COL_RANGE)
	else
		appendCircle(active, curPos, reach, COL_RANGE)
	end

	local raw, e = legPreview(pointer)
	prevRaw, prevEndPos = raw, e
	appendLegCorridor(active, curPos, e, COL_LEG)

	-- Live total shows the EXACT distance to one decimal (committed whole inches +
	-- the current leg's raw length) so the ghost readout tracks smoothly. The leg
	-- still COSTS a whole inch (rounded up) when committed, so the running total
	-- snaps to the whole number on the next step.
	local liveTotal = usedInches + raw
	readoutText = string.format('%.1f" / %d"', liveTotal, maxInches())
		.. (modifier ~= 0 and string.format(" (%+d)", modifier) or "")

	redraw(active, e)
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
-- A transparent button pinned to the model, covering the CURRENT leg's reach (a
-- disc of radius = REMAINING budget + margin, centred on curPos). LEFT-click =
-- step, RIGHT-click = undo. Because it is a button ON the model, hovering it
-- counts as hovering the model, so the number ROW works with no binding. It only
-- locks that small area (not the table); as you spend budget it re-centres on
-- the new point and shrinks to what's left, so it never claims more than needed.

-- Half-reach (inches) of the catch disc for the CURRENT leg: remaining budget +
-- margin, floored so a nearly-spent move still has a clickable area.
local function catcherReachIn()
	local r = remainingInches() + CATCHER_MARGIN_IN
	return (r < 3) and 3 or r
end

local function catcherKey()
	if not curPos then return "none" end
	return string.format("%.2f:%.2f:%.2f", curPos.x, curPos.z, catcherReachIn())
end

-- Remove every catcher button currently on the model. Collect indices first and
-- remove high->low: removeButton(index) reshuffles the remaining indices, so
-- removing while iterating by index can skip a button (leaving a stale catcher).
local function clearCatcherButtons()
	local idx = {}
	for _, b in ipairs(self.getButtons() or {}) do
		if b.click_function == "moveCatcherClick" then idx[#idx + 1] = b.index end
	end
	table.sort(idx, function(a, b) return a > b end)
	for _, i in ipairs(idx) do self.removeButton(i) end
end

-- (Re)create the catcher as a FRESH button at the model CENTRE, sized to the
-- current leg's remaining reach. The model steps to each committed leg (see
-- commitLeg), so a CENTRED button always sits on the operative's current spot --
-- rotation/scale-proof, no offset math, and the catch area stays the reachable
-- bubble. We remove+recreate rather than editButton because editing a button's
-- size/position does not reliably rebuild its invisible click hitbox in TTS.
local function placeCatcher()
	clearCatcherButtons()
	local sc   = self.getScale()
	local span = 2 * catcherReachIn() * CATCHER_UNITS_PER_IN
	self.createButton({
		click_function = "moveCatcherClick",
		function_owner = self,
		label          = "",
		position       = { 0, 0.6 / (sc.y ~= 0 and sc.y or 1), 0 },
		rotation       = { 0, 0, 0 },
		width          = span / (sc.x ~= 0 and sc.x or 1),
		height         = span / (sc.z ~= 0 and sc.z or 1),
		font_size      = 100,
		color          = { 0, 0, 0, 0 },
		tooltip        = "Left: step (double=finish)  Right: undo  1:-1\"  2:+1\"  3:3D range  0:cancel",
	})
end

local function createCatcher()
	if catcherActive then return end
	placeCatcher()
	catcherActive = true
	lastMoveKey   = catcherKey()
end

-- Re-centre + resize the catcher to the CURRENT leg's reachable area (a disc of
-- radius = remaining budget around curPos). Guarded so it only rebuilds when the
-- reach/centre actually changes (a leg commits, a 1/2 budget change, or a
-- step-back), never per frame -- so there is no cursor-follow lag. Assigns the
-- forward-declared upvalue so tick() (defined earlier) can call it.
resizeCatcher = function()
	if not catcherActive or not curPos then return end
	local key = catcherKey()
	if key == lastMoveKey then return end   -- nothing changed -> no rebuild (no lag)
	lastMoveKey = key
	placeCatcher()
end

local function removeCatcher()
	if not catcherActive then return end
	clearCatcherButtons()
	catcherActive = false
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
	-- Move the model back to the restored point (it steps with each leg).
	self.setPosition({ curPos.x, curPos.y, curPos.z })
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
	-- Return the model to where the move began (it steps with each committed leg).
	if startPos then self.setPosition({ startPos.x, startPos.y, startPos.z }) end
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
	usedInches = usedInches + math.ceil(rawIn - 1e-6)
	curPos     = { x = endPos.x, y = endPos.y, z = endPos.z }
	-- Step the model to the committed point so the (centred) catcher rides with
	-- it -- keeps the catch area on the operative's real spot, rotation-proof.
	self.setPosition({ curPos.x, curPos.y, curPos.z })
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
	if prevRaw <= 1e-6 then
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
	if altClick then stepBack(playerColor) else advance(playerColor) end
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
