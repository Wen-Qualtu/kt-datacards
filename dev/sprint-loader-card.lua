-- kt-datacards: Sprint Tool Loader (POC)  [GENERATED - do not hand-edit]
-- Source: dev/sprint-movement-tool.lua  |  Regenerate: python dev/build_sprint_loader.py
--
-- Paste this onto any card / tile. Put a scripted model (e.g. a KTUI mini) on
-- top, then right-click the card -> "Load Sprint tool to model". It APPENDS
-- the sprint movement tool to the model's existing Lua script; because the
-- tool chains onLoad/onPickUp and never touches script_state, the model's own
-- scripts and saved state stay intact.

local SPRINT_MARKER = "-- KT_SPRINT_TOOL_V1"

local SPRINT_CODE = [=[
-- KT_SPRINT_TOOL_V1
--[[ ============================================================================
  SPRINT MOVEMENT TOOL  (Proof of Concept, v2)
  For the Exodite Dragon Masters (Draconic Steeds) team.

  What a sprint is
  ----------------
  A sprint is up to two STRAIGHT legs with a SINGLE pivot between (or before)
  them. The straight distance travelled is capped at 9" total; pivots are free
  and limited to +/-45 degrees. Unlike the standard KT move tool, direction is
  locked to the model's facing and turns only happen at the one allowed pivot.

  Legal shapes
  ------------
    * move                      (one straight leg, < 9", no pivot)
    * move -> pivot -> move      (classic: turn once mid-sprint)
    * move -> pivot              (first leg used 8-9", no budget left to move on)
    * pivot -> move              (pivot BEFORE moving, then up to 9" straight)
  Only ONE pivot is ever allowed. Straight legs count toward the 9" budget
  (each rounded UP to the whole inch when spent); pivots cost nothing.

  Controls
  --------
  Number input works two ways, with NO key binding needed either way:
    * NUMPAD - TTS "scripting buttons" (which default to the numpad); these
      fire anywhere, even while aiming at the table.
    * Number ROW - via onNumberTyped, which fires while your pointer is over
      the model. During a sprint the invisible click catcher covers the whole
      table, so the row registers across the entire play area too.
  While a sprint is active, for the driving player:
    1 = straight move            (first step only)
    2 = pivot from FRONT of base
    3 = pivot from CENTRE of base
    4 = pivot from BACK of base
    9 = confirm / finish straight, no (further) pivot
    0 = cancel the whole sprint  (any step)
  (9 and 0 are used for finish/cancel - kept apart from the 1-4 mode keys so
   they aren't hit by accident, matching the standard move tool.)
  Mouse (via an invisible click catcher pinned to the model):
    LEFT-click  = apply / commit the current step (and advance)
    RIGHT-click = step back one (undo), or cancel from the first step
  You aim with your pointer the whole time; the click is captured at your
  current aim point so the distance/angle you see is what you get.

  Straight steps support BACKWARD movement: drag the line behind the model to
  reverse. Backward is capped at 3" total for the whole sprint (forward still
  uses the separate 9" budget).

  Step flow
  ---------
    idle --Begin--> S1 --(straight)--> PIVOT --(pivot)--> S2 --(straight)--> done
                       \--(pivot first)------------------> S2 --------------> done
  * S1  : default straight; press 2/3/4 to make it a pivot, 1 to go back to
          straight. Left-click commits. If committed straight -> PIVOT step.
          If committed as a pivot (pivot-first) -> jumps straight to S2.
  * PIVOT: press 2/3/4 to choose the pivot anchor, drag to turn (+/-45deg).
          Left-click commits -> S2 (or finishes if <1" budget remains).
          Press 9 here to finish with NO pivot (just the first leg) - e.g. a
          short 2" straight shuffle and done.
  * S2  : straight only. Left-click (or 9) finishes. Right-click backs up.

  Preview
  -------
  Each straight leg is drawn as a corridor: a centre line plus two parallel
  edge lines offset by half the base width, showing the swept path of the base.
  A cyan ghost of the base (oval) is drawn at the destination, oriented to the
  final heading, so you can see exactly where the model lands.

  Injection-safe loading
  -----------------------
  This file can be APPENDED to a model that already has its own script (e.g. a
  KTUI mini) without breaking it:
    * onLoad / onPickUp / onScriptingButtonDown / onNumberTyped are CHAINED
      (host runs first).
    * It never WRITES self.script_state, so saved state (wounds, roles, base,
      etc.) is untouched. It only READS script_state to size the base ghost.
    * removeCatcher() removes only its own button, never clearButtons().
    * Globals it adds are uniquely named (setupSprintTool, sprintOnPickUp,
      sprintCatcherClick, sprintScriptingButton + chained handlers).

  Assumes 1 TTS unit = 1 inch (KT-UI table convention). Change UNITS_PER_INCH
  if your table scale differs. POC: uses Global vector lines, so run one sprint
  at a time.
============================================================================ ]]

-- ------------------------------------------------------------------ tuning ---
local MAX_INCHES     = 9        -- total straight distance cap
local MAX_PIVOT_DEG  = 45       -- max single turn, left or right
local MAX_BACK_INCHES = 3       -- total BACKWARD straight distance cap
local UNITS_PER_INCH = 1        -- world units per inch (KT-UI table = 1)

-- Default base footprint (mm), used only when a model exposes NO base metadata.
-- Long axis (z) runs along the model's facing. The tool prefers each model's
-- ACTUAL base: KTUI script_state.base, then datacard GMNotes "Base", then the
-- physical footprint (so models with different base sizes all work).
local DEF_BASE_MM_LONG = 75     -- oval length (front-to-back), mm
local DEF_BASE_MM_WIDE = 42     -- oval width (side-to-side), mm
local BASE_MM_LONG   = DEF_BASE_MM_LONG
local BASE_MM_WIDE   = DEF_BASE_MM_WIDE
local MM_TO_INCH     = 0.0393701

-- KTUI minis are built facing the OPPOSITE way to their transform "forward",
-- which swaps front/back (and the forward move direction). When the tool
-- detects a KTUI base (script_state.base) it offsets its notion of facing by
-- this many degrees so "front" is the visual front. Set to 0 if a model comes
-- out reversed; plain objects (no KTUI base) always use 0.
local KTUI_FACING_OFFSET = 180

-- Drawing
local LINE_HEIGHT    = 0.20     -- how high above the base to draw the preview
local LINE_THICKNESS = 0.12
local COL_LEG        = { 0.20, 0.85, 0.30 }  -- active leg / corridor (green)
local COL_LEG_DONE   = { 0.12, 0.45, 0.18 }  -- already-committed legs (dim)
local COL_PIVOT      = { 1.00, 0.75, 0.10 }  -- amber pivot marker / prompts
local COL_LIMIT      = { 0.55, 0.55, 0.55 }  -- grey +/-45 guide lines
local COL_GHOST      = { 0.30, 0.90, 1.00 }  -- cyan destination footprint

-- --------------------------------------------------------------- constants ---
local PHASE_IDLE  = "idle"
local PHASE_S1    = "s1"        -- first step: straight OR pivot (mode-selectable)
local PHASE_PIVOT = "pivot"     -- middle step: pivot only
local PHASE_S2    = "s2"        -- last step: straight only

-- ------------------------------------------------------------------- state ---
local phase        = PHASE_IDLE
local controlColor = nil        -- player driving the current sprint

-- committed cumulative transform (updated as each step is applied)
local startY       = 0          -- model Y (kept constant)
local curPos       = nil        -- Vector, committed planar position
local curHeading   = 0          -- committed heading (degrees)
local spentInches  = 0          -- straight budget already used (rounded up)
local backSpent    = 0          -- BACKWARD straight distance used (raw inches)
local rawStraight  = 0          -- exact straight distance travelled (for readout)
local facingOffset = 0          -- deg added to transform-forward -> visual facing
local committedLegs = {}         -- { {a=,b=,heading=}, ... } straight corridors

-- current step's selected mode
--   S1:    "straight" | "pivotFront" | "pivotCenter" | "pivotBack"
--   PIVOT: pivotOrigin is used instead ("front" | "center" | "back")
local s1Mode       = "straight"
local pivotOrigin  = "center"
local turnOnly     = false      -- "Turn" action: a single pivot, no movement
local history      = {}

-- live preview cache (refreshed every tick; used by commit/confirm)
local prevStraight = 0          -- signed inches of the active straight leg
local prevEndPos   = nil        -- Vector end of the active preview
local prevHeading  = 0          -- heading at the end of the active preview

local loopHandle    = nil
local lastReport    = nil
local catcherActive = false

-- --------------------------------------------------------------- utilities ---
local function toUnits(inches) return inches * UNITS_PER_INCH end
local function toInches(units) return units / UNITS_PER_INCH end

-- Heading (degrees) of a planar vector, matching TTS yaw: forward = (sin,0,cos)
local function headingOf(x, z) return math.deg(math.atan2(x, z)) end

-- Unit planar direction for a given heading (degrees)
local function dirFromHeading(h)
	local r = math.rad(h)
	return { x = math.sin(r), z = math.cos(r) }
end

-- Normalise an angle difference into [-180, 180]
local function wrap180(a) return (a + 180) % 360 - 180 end

local function clamp(v, lo, hi)
	if v < lo then return lo end
	if v > hi then return hi end
	return v
end

local function msg(pc, text, col)
	if pc and Player[pc] then Player[pc].broadcast(text, col or { 1, 1, 1 }) end
end

-- Is this player currently acting on THIS model? (used to gate "Begin")
local function isTargeted(playerColor, hoveredObject)
	if hoveredObject == self then return true end
	local p = Player[playerColor]
	if not p then return false end
	for _, o in ipairs(p.getSelectedObjects() or {}) do
		if o == self then return true end
	end
	return false
end

-- ---------------------------------------------------------------- base dims --
-- Figure out the model's ACTUAL base so the ghost + corridor match it (and so
-- future models with different bases just work). Tries, in order:
--   1) KTUI live state:  script_state.base = { x = width, z = length } (mm)
--   2) datacard GMNotes: "Base" = "LxW" (oval) or a number (round), in mm
--   3) physical footprint: getBoundsNormalized() (world inches -> mm)
--   4) the DEF_BASE_MM_* fallback.
-- Only KTUI state (1) also applies the mesh-facing offset (see above).
local function parseBaseString(s)
	-- "75x42" / "75 x 42" -> length 75, width 42 ; a lone number -> round base.
	local a, b = tostring(s):match("(%d+%.?%d*)%s*[xX]%s*(%d+%.?%d*)")
	if a and b then return tonumber(a), tonumber(b) end
	local n = tonumber(s)
	if n then return n, n end
	return nil, nil
end

local function refreshBaseDims()
	BASE_MM_LONG, BASE_MM_WIDE = DEF_BASE_MM_LONG, DEF_BASE_MM_WIDE
	facingOffset = 0

	-- 1) KTUI live state.
	local ss = self.script_state
	if ss and ss ~= "" then
		local ok, data = pcall(function() return JSON.decode(ss) end)
		if ok and type(data) == "table" and type(data.base) == "table" then
			local bx = tonumber(data.base.x)   -- width  (side-to-side)
			local bz = tonumber(data.base.z)   -- length (front-to-back)
			if bx and bx > 0 and bz and bz > 0 then
				BASE_MM_WIDE, BASE_MM_LONG = bx, bz
				facingOffset = KTUI_FACING_OFFSET   -- KTUI mesh faces the other way
				return
			end
		end
	end

	-- 2) datacard GMNotes "Base".
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

	-- 3) physical footprint (adapts to any model's real size).
	local bOk, b = pcall(function() return self.getBoundsNormalized() end)
	if bOk and b and b.size and b.size.x > 0 and b.size.z > 0 then
		BASE_MM_WIDE = b.size.x / MM_TO_INCH
		BASE_MM_LONG = b.size.z / MM_TO_INCH
	end
end

local function halfLong() return (BASE_MM_LONG * 0.5) * MM_TO_INCH * UNITS_PER_INCH end
local function halfWide() return (BASE_MM_WIDE * 0.5) * MM_TO_INCH * UNITS_PER_INCH end

-- --------------------------------------------------------------- geometry ----
local function remainingInches() return math.max(0, MAX_INCHES - spentInches) end

-- Straight leg preview from curPos along curHeading toward the pointer. Allows
-- BACKWARD movement (negative projection); magnitude clamped to the remaining
-- budget. Returns signed inches, the end Vector, and the (unchanged) heading.
local function straightPreview(pointer)
	local fdir  = dirFromHeading(curHeading)
	local px, pz = pointer.x - curPos.x, pointer.z - curPos.z
	local proj  = px * fdir.x + pz * fdir.z          -- signed world units
	local remFwdU  = toUnits(remainingInches())
	local remBackU = toUnits(math.max(0, MAX_BACK_INCHES - backSpent))
	local d        = clamp(proj, -remBackU, remFwdU)
	local endPos = { x = curPos.x + fdir.x * d, y = curPos.y, z = curPos.z + fdir.z * d }
	return toInches(d), endPos, curHeading
end

-- The fixed anchor point of a pivot for a given origin, at (pos, heading).
local function pivotAnchor(origin, pos, heading)
	local fdir = dirFromHeading(heading)
	local hl   = halfLong()
	if origin == "front" then
		return { x = pos.x + fdir.x * hl, z = pos.z + fdir.z * hl }
	elseif origin == "back" then
		return { x = pos.x - fdir.x * hl, z = pos.z - fdir.z * hl }
	end
	return { x = pos.x, z = pos.z }                  -- centre
end

-- Pivot preview: turn the facing toward the pointer, clamped to +/-45deg,
-- rotating about the chosen anchor. Returns new heading, new centre Vector,
-- the anchor point, and the signed turn delta (degrees).
local function pivotPreview(pointer, origin, pos, heading)
	local anchor  = pivotAnchor(origin, pos, heading)
	local desired = headingOf(pointer.x - anchor.x, pointer.z - anchor.z)
	local delta   = clamp(wrap180(desired - heading), -MAX_PIVOT_DEG, MAX_PIVOT_DEG)
	local newH    = heading + delta
	local nfd     = dirFromHeading(newH)
	local hl      = halfLong()
	local newPos
	if origin == "front" then
		newPos = { x = anchor.x - nfd.x * hl, y = pos.y, z = anchor.z - nfd.z * hl }
	elseif origin == "back" then
		newPos = { x = anchor.x + nfd.x * hl, y = pos.y, z = anchor.z + nfd.z * hl }
	else
		newPos = { x = pos.x, y = pos.y, z = pos.z }
	end
	return newH, newPos, anchor, delta
end

-- ----------------------------------------------------------------- drawing ---
local function line(a, b, color, thick)
	local ay = (a.y or curPos.y) + LINE_HEIGHT
	local by = (b.y or curPos.y) + LINE_HEIGHT
	return {
		points    = { { a.x, ay, a.z }, { b.x, by, b.z } },
		color     = color,
		thickness = thick or LINE_THICKNESS,
	}
end

-- Corridor for a straight leg: centre line + two parallel edges offset by half
-- the base width, showing the swept path of the base.
local function appendCorridor(out, a, b, heading, color)
	local side = dirFromHeading(heading + 90)
	local hw   = halfWide()
	local aL = { x = a.x + side.x * hw, y = a.y, z = a.z + side.z * hw }
	local bL = { x = b.x + side.x * hw, y = b.y, z = b.z + side.z * hw }
	local aR = { x = a.x - side.x * hw, y = a.y, z = a.z - side.z * hw }
	local bR = { x = b.x - side.x * hw, y = b.y, z = b.z - side.z * hw }
	table.insert(out, line(a, b, color))
	table.insert(out, line(aL, bL, color, LINE_THICKNESS * 0.7))
	table.insert(out, line(aR, bR, color, LINE_THICKNESS * 0.7))
end

-- Pivot helpers: a cross at the anchor + faint +/-45 guide lines from the
-- anchor showing the allowed turn cone.
local function appendPivotGuides(out, anchor, heading, y)
	local m = 0.35
	table.insert(out, line({ x = anchor.x - m, y = y, z = anchor.z }, { x = anchor.x + m, y = y, z = anchor.z }, COL_PIVOT))
	table.insert(out, line({ x = anchor.x, y = y, z = anchor.z - m }, { x = anchor.x, y = y, z = anchor.z + m }, COL_PIVOT))
	local glen = halfLong() * 2 + 1
	for _, off in ipairs({ -MAX_PIVOT_DEG, MAX_PIVOT_DEG }) do
		local gdir = dirFromHeading(heading + off)
		local ge   = { x = anchor.x + gdir.x * glen, y = y, z = anchor.z + gdir.z * glen }
		table.insert(out, line({ x = anchor.x, y = y, z = anchor.z }, ge, COL_LIMIT))
	end
end

-- Closed oval outline (the base) centred at (cx,cy,cz), long axis along heading.
local function appendGhost(out, cx, cy, cz, heading)
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
	table.insert(out, { points = pts, color = COL_GHOST, thickness = LINE_THICKNESS * 0.8 })
end

-- Draw everything: committed legs (dim) + the active preview + the end ghost.
local function redraw(active, endPos, endHeading)
	local lines = {}
	for _, leg in ipairs(committedLegs) do
		appendCorridor(lines, leg.a, leg.b, leg.heading, COL_LEG_DONE)
	end
	for _, l in ipairs(active or {}) do table.insert(lines, l) end
	if endPos then
		appendGhost(lines, endPos.x, endPos.y or curPos.y, endPos.z, endHeading)
	end
	Global.setVectorLines(lines)
end

local function clearPreview() Global.setVectorLines({}) end

-- ------------------------------------------------------------- update loop ---
local function s1Origin()
	if s1Mode == "pivotFront" then return "front" end
	if s1Mode == "pivotBack" then return "back" end
	return "center"
end

local function tick()
	if phase == PHASE_IDLE or not controlColor then return end
	local pointer = Player[controlColor].getPointerPosition()
	if not pointer then return end

	local active = {}
	local endPos, endHeading

	if phase == PHASE_S1 and s1Mode == "straight" then
		local d, e, h = straightPreview(pointer)
		prevStraight, prevEndPos, prevHeading = d, e, h
		appendCorridor(active, curPos, e, h, COL_LEG)
		endPos, endHeading = e, h

	elseif phase == PHASE_S1 then
		local nh, np, anchor, delta = pivotPreview(pointer, s1Origin(), curPos, curHeading)
		prevStraight, prevEndPos, prevHeading = 0, np, nh
		appendPivotGuides(active, anchor, curHeading, curPos.y)
		endPos, endHeading = np, nh

	elseif phase == PHASE_PIVOT then
		local nh, np, anchor, delta = pivotPreview(pointer, pivotOrigin, curPos, curHeading)
		prevStraight, prevEndPos, prevHeading = 0, np, nh
		appendPivotGuides(active, anchor, curHeading, curPos.y)
		endPos, endHeading = np, nh

	elseif phase == PHASE_S2 then
		local d, e, h = straightPreview(pointer)
		prevStraight, prevEndPos, prevHeading = d, e, h
		appendCorridor(active, curPos, e, h, COL_LEG)
		endPos, endHeading = e, h
	end

	redraw(active, endPos, endHeading)
end

local function startLoop()
	if loopHandle then return end
	loopHandle = Wait.time(tick, 1 / 30, -1)
end

local function stopLoop()
	if loopHandle then
		Wait.stop(loopHandle)
		loopHandle = nil
	end
end

-- --------------------------------------------------------- click catcher ----
-- A big, fully transparent button pinned to the model. LEFT-click = apply,
-- RIGHT-click = back. No physics collider, so the pointer still aims freely.
local function createCatcher()
	if catcherActive then return end
	local sc = self.getScale()
	self.createButton({
		click_function = "sprintCatcherClick",
		function_owner = self,
		label          = "",
		position       = { 0, 0.6 / (sc.y ~= 0 and sc.y or 1), 0 },
		rotation       = { 0, 0, 0 },
		width          = 14000 / (sc.x ~= 0 and sc.x or 1),
		height         = 14000 / (sc.z ~= 0 and sc.z or 1),
		font_size      = 100,
		color          = { 0, 0, 0, 0 },   -- fully transparent; raise alpha to debug
		tooltip        = "Left: apply   Right: back   1/2/3/4: mode   9: finish   0: cancel",
	})
	catcherActive = true
end

local function removeCatcher()
	if not catcherActive then return end
	for _, b in ipairs(self.getButtons() or {}) do
		if b.click_function == "sprintCatcherClick" then
			self.removeButton(b.index)
		end
	end
	catcherActive = false
end

-- ------------------------------------------------------------ history/undo ---
local function pushHistory()
	table.insert(history, {
		phase       = phase,
		pos         = { x = curPos.x, y = curPos.y, z = curPos.z },
		heading     = curHeading,
		spent       = spentInches,
		back        = backSpent,
		raw         = rawStraight,
		legs        = #committedLegs,
		s1Mode      = s1Mode,
		pivotOrigin = pivotOrigin,
	})
end

local function restoreFrom(s)
	curPos      = { x = s.pos.x, y = s.pos.y, z = s.pos.z }
	curHeading  = s.heading
	spentInches = s.spent
	backSpent   = s.back
	rawStraight = s.raw
	while #committedLegs > s.legs do table.remove(committedLegs) end
	phase        = s.phase
	s1Mode       = s.s1Mode
	pivotOrigin  = s.pivotOrigin
end

-- ------------------------------------------------------------ state changes --
local function applyToModel()
	local r = self.getRotation()
	self.setPosition({ curPos.x, startY, curPos.z })
	-- curHeading is the VISUAL facing; convert back to the model's transform
	-- rotation (undo the KTUI mesh offset) so the mini doesn't spin 180.
	self.setRotation({ r.x, curHeading - facingOffset, r.z })
end

local function finishSprint(pc, text)
	stopLoop()
	clearPreview()
	removeCatcher()
	applyToModel()
	msg(pc, text or "Sprint complete.", COL_LEG)
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
end

local function cancelSprint(pc)
	stopLoop()
	clearPreview()
	removeCatcher()
	phase        = PHASE_IDLE
	controlColor = nil
	history      = {}
	if pc then msg(pc, "Sprint cancelled.", COL_LIMIT) end
end

local function beginSprint(pc)
	refreshBaseDims()
	controlColor = pc
	local p      = self.getPosition()
	startY       = p.y
	curPos       = { x = p.x, y = p.y, z = p.z }
	local fwd    = self.getTransformForward()
	curHeading   = headingOf(fwd.x, fwd.z) + facingOffset
	spentInches  = 0
	backSpent    = 0
	rawStraight  = 0
	committedLegs = {}
	history      = {}
	s1Mode       = "straight"
	pivotOrigin  = "center"
	turnOnly     = false
	phase        = PHASE_S1
	lastReport   = nil
	startLoop()
	createCatcher()
	msg(pc, "Sprint: drag to aim. 1=straight, 2/3/4=pivot front/centre/back. "
		.. "Left=apply, right=back, 9=finish straight, 0=cancel.", COL_PIVOT)
end

-- "Turn": a single pivot only (no movement). Starts straight in the pivot step;
-- 2/3/4 pick the anchor, drag to turn (+/-45deg), left-click applies & finishes.
local function beginTurn(pc)
	refreshBaseDims()
	controlColor = pc
	local p      = self.getPosition()
	startY       = p.y
	curPos       = { x = p.x, y = p.y, z = p.z }
	local fwd    = self.getTransformForward()
	curHeading   = headingOf(fwd.x, fwd.z) + facingOffset
	spentInches  = 0
	backSpent    = 0
	rawStraight  = 0
	committedLegs = {}
	history      = {}
	s1Mode       = "straight"
	pivotOrigin  = "center"
	turnOnly     = true
	phase        = PHASE_PIVOT
	lastReport   = nil
	startLoop()
	createCatcher()
	msg(pc, "Turn: 2/3/4 = pivot from front/centre/back, drag to turn (+/-45deg). "
		.. "Left=apply, right/0=cancel.", COL_PIVOT)
end

local function commitStraight(d, endPos)
	table.insert(committedLegs, {
		a = { x = curPos.x, y = curPos.y, z = curPos.z },
		b = { x = endPos.x, y = curPos.y, z = endPos.z },
		heading = curHeading,
	})
	curPos      = { x = endPos.x, y = curPos.y, z = endPos.z }
	rawStraight = rawStraight + math.abs(d)
	if d < 0 then
		backSpent = backSpent + math.abs(d)
	else
		spentInches = spentInches + math.ceil(math.abs(d) - 1e-6)
	end
end

local function commitPivot(newHeading, newPos)
	curPos     = { x = newPos.x, y = curPos.y, z = newPos.z }
	curHeading = newHeading
end

-- LEFT-click: apply the current step and advance.
local function advance(pc)
	if phase == PHASE_S1 then
		if s1Mode == "straight" then
			if not prevEndPos then return end
			pushHistory()
			local moved = math.abs(prevStraight)
			commitStraight(prevStraight, prevEndPos)
			phase       = PHASE_PIVOT
			pivotOrigin = "center"
			lastReport  = nil
			-- Callout: distance moved only (the next step is the pivot).
			msg(pc, string.format('Moved: %.1f"%s.', moved, prevStraight < 0 and " back" or ""), COL_LEG)
		else
			-- pivot-first: this pivot IS the single pivot; jump to the final
			-- leg. No callout - the pivot angle isn't useful info.
			if not prevEndPos then return end
			pushHistory()
			commitPivot(prevHeading, prevEndPos)
			phase      = PHASE_S2
			lastReport = nil
		end

	elseif phase == PHASE_PIVOT then
		-- Applying the pivot: no callout (angle isn't useful info).
		if not prevEndPos then return end
		pushHistory()
		commitPivot(prevHeading, prevEndPos)
		lastReport = nil
		if turnOnly then
			finishSprint(pc, "Turn complete.")
		elseif remainingInches() < 1 then
			finishSprint(pc, string.format('Sprint complete: %.1f" total.', rawStraight))
		else
			phase = PHASE_S2
		end

	elseif phase == PHASE_S2 then
		if prevEndPos then commitStraight(prevStraight, prevEndPos) end
		finishSprint(pc, string.format('Sprint complete: %.1f" total.', rawStraight))
	end
end

-- RIGHT-click: undo one step (or cancel from the first step).
local function stepBack(pc)
	if #history == 0 then
		cancelSprint(pc)
		return
	end
	local s = table.remove(history)
	restoreFrom(s)
	lastReport = nil
	msg(pc, "Stepped back.", COL_PIVOT)
end

-- Key 9: finish with a straight move and NO (further) pivot. Works at any point
-- along a straight step, so a short move (e.g. 2" and stop) can be locked in
-- without having to hand-aim the exact end point.
local function finishStraightNoPivot(pc)
	if phase == PHASE_PIVOT then
		finishSprint(pc, string.format('Sprint complete: %.1f" (no pivot).', rawStraight))
		return
	end
	if phase == PHASE_S1 or phase == PHASE_S2 then
		local pointer = Player[pc] and Player[pc].getPointerPosition()
		if pointer then
			local d, e = straightPreview(pointer)
			commitStraight(d, e)
		end
		finishSprint(pc, string.format('Sprint complete: %.1f".', rawStraight))
	end
end

-- Number-key mode selection for the current step.
local function selectMode(pc, key)
	if phase == PHASE_S1 then
		if key == 1 then s1Mode = "straight"
		elseif key == 2 then s1Mode = "pivotFront"
		elseif key == 3 then s1Mode = "pivotCenter"
		elseif key == 4 then s1Mode = "pivotBack"
		else return end
		lastReport = nil
		msg(pc, "Step 1 mode: " .. s1Mode, COL_PIVOT)
	elseif phase == PHASE_PIVOT then
		if key == 2 then pivotOrigin = "front"
		elseif key == 3 then pivotOrigin = "center"
		elseif key == 4 then pivotOrigin = "back"
		else return end
		lastReport = nil
		msg(pc, "Pivot anchor: " .. pivotOrigin, COL_PIVOT)
	end
	-- PHASE_S2 is straight-only: number keys 1-4 do nothing.
end

-- Unified digit handler (0-9), shared by the numpad scripting buttons and the
-- number ROW (onNumberTyped). Returns true if it consumed the digit.
local function handleDigit(pc, digit)
	if phase == PHASE_IDLE then return false end
	if controlColor and pc ~= controlColor then return false end
	if digit >= 1 and digit <= 4 then
		selectMode(pc, digit)
	elseif digit == 9 then
		finishStraightNoPivot(pc)
	elseif digit == 0 then
		cancelSprint(pc)
	else
		return false
	end
	return true
end

-- ----------------------------------------------------------------- wiring ----

-- Invisible catcher handler. altClick == true means a right-click.
function sprintCatcherClick(_, playerColor, altClick)
	if phase == PHASE_IDLE then return end
	if controlColor and playerColor ~= controlColor then return end
	if altClick then stepBack(playerColor) else advance(playerColor) end
end

-- TTS scripting buttons = the NUMPAD by default (index 10 == the "0" key). No
-- hover needed, so this works while aiming at the table.
function sprintScriptingButton(index, playerColor)
	handleDigit(playerColor, index == 10 and 0 or index)
end

-- Registers the context-menu items. Advancing/cancelling happen via clicks and
-- number keys, so only the two entry points live in the menu.
function setupSprintTool()
	self.addContextMenuItem("Sprint", function(pc)
		if phase == PHASE_IDLE then beginSprint(pc) end
	end, false)
	self.addContextMenuItem("Turn", function(pc)
		if phase == PHASE_IDLE then beginTurn(pc) end
	end, false)
end

-- Safety: if the model is picked up mid-sprint, abort cleanly.
function sprintOnPickUp(playerColor)
	if phase ~= PHASE_IDLE then cancelSprint(playerColor) end
end

-- onLoad / onPickUp / onScriptingButtonDown are CHAINED: any pre-existing
-- handler runs first, then ours. Standalone the previous handler is nil, so
-- only ours runs. Appended onto a host model (e.g. a KTUI mini) the host's
-- handlers still run, so nothing is lost. This is why the tool is injection-safe.
local _sprint_prev_onLoad = onLoad
function onLoad(...)
	if _sprint_prev_onLoad then _sprint_prev_onLoad(...) end
	setupSprintTool()
end

local _sprint_prev_onPickUp = onPickUp
function onPickUp(...)
	if _sprint_prev_onPickUp then _sprint_prev_onPickUp(...) end
	sprintOnPickUp(...)
end

local _sprint_prev_onScriptingButtonDown = onScriptingButtonDown
function onScriptingButtonDown(...)
	if _sprint_prev_onScriptingButtonDown then _sprint_prev_onScriptingButtonDown(...) end
	sprintScriptingButton(...)
end

-- Number ROW typed while hovering the model (no binding needed). During a
-- sprint the table-covering catcher counts as hovering the model, so the row
-- works across the play area. We consume it and return true so the host's
-- default (e.g. setting wounds) is suppressed; when idle we defer to the host.
local _sprint_prev_onNumberTyped = onNumberTyped
function onNumberTyped(playerColor, number, alt)
	if phase ~= PHASE_IDLE and (not controlColor or playerColor == controlColor) then
		handleDigit(playerColor, number)
		return true
	end
	if _sprint_prev_onNumberTyped then return _sprint_prev_onNumberTyped(playerColor, number, alt) end
end

]=]

function broadcastToColor(msg, pc, col)
    if pc and Player[pc] then Player[pc].broadcast(msg, col or {1, 1, 1}) end
end

-- Find a scripted model resting on top of this card (sphere-cast downward).
function findModelOnCard()
    local pos = self.getPosition()
    local hits = Physics.cast({
        origin       = Vector(pos.x, pos.y + 1.5, pos.z),
        direction    = {0, -1, 0},
        type         = 2,
        size         = {2, 2, 2},
        max_distance = 3,
    })
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and obj.hasTag("KTUIMini") then return obj end
    end
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and obj.type == "Custom_Model" then return obj end
    end
    for _, hit in ipairs(hits) do
        local obj = hit.hit_object
        if obj and obj ~= self and obj.type == "Figurine" then return obj end
    end
    return nil
end

function addSprintToModel(playerColor)
    local model = findModelOnCard()
    if not model then
        broadcastToColor("Place a model on this card first.", playerColor, {1, 0.6, 0})
        return
    end

    local lua = model.getLuaScript() or ""
    if lua:find(SPRINT_MARKER, 1, true) then
        broadcastToColor("Model already has the Sprint tool.", playerColor, {1, 1, 1})
        return
    end

    -- Append (never replace). Chained onLoad/onPickUp keep the host intact.
    model.setLuaScript(lua .. "\n\n" .. SPRINT_CODE)
    Wait.frames(function() if model ~= nil then model.reload() end end, 10)
    broadcastToColor("Sprint tool added. Right-click the model -> 'Sprint: Begin'.", playerColor, {0.2, 0.85, 0.3})
end

function onLoad()
    self.addContextMenuItem("Load Sprint tool to model", addSprintToModel)
end
