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
    * The click catcher is a per-player Global-UI overlay (visibility = the
      driving player) added/removed by id, so it never touches the model's own
      self.UI and never locks the table for the opponent.
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

-- Leap (Exodite special move): reposition the base freely by aiming, with FREE
-- 360 rotation, clamped so ANY part of the base stays within MAX_LEAP_INCHES of
-- ANY part of the original footprint (edge-to-edge gap). Rotation is driven by
-- HOLDING numpad 1/2 (smooth) or TAPPING the number row 1/2 (stepped).
local MAX_LEAP_INCHES   = 1     -- max edge-to-edge gap from the original base
local LEAP_ROT_DEG_SEC  = 120   -- rotation speed (deg/sec) while a numpad key is held
local LEAP_ROT_STEP     = 5     -- degrees per number-row 1/2 tap
local LEAP_STEPS        = 32    -- oval perimeter samples for the gap clamp

-- Pivot/Turn aiming: how far past +/-45deg the pointer may stray before the
-- ghost hides (so aiming behind the model doesn't snap to a weird 45deg turn).
local PIVOT_AIM_TOL = 22        -- degrees of tolerance outside the turn cone

-- Live distance/angle readout drawn as a 3DText object near the ghost.
local READOUT_FONT  = 70        -- font size of the readout text

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
local PREVIEW_HZ     = 60       -- preview / rotation refresh rate (Hz)
local LINE_HEIGHT    = 0.20     -- how high above the base to draw the preview
local LINE_THICKNESS = 0.12
local COL_LEG        = { 0.20, 0.85, 0.30 }  -- active leg / corridor (green)
local COL_LEG_DONE   = { 0.12, 0.45, 0.18 }  -- already-committed legs (dim)
local COL_PIVOT      = { 1.00, 0.75, 0.10 }  -- amber pivot marker / prompts
local COL_LIMIT      = { 0.55, 0.55, 0.55 }  -- grey +/-45 guide lines
local COL_GHOST      = { 0.30, 0.90, 1.00 }  -- cyan destination footprint
local COL_ORIG       = { 0.55, 0.55, 0.55 }  -- grey original footprint (Leap)

-- --------------------------------------------------------------- constants ---
local PHASE_IDLE  = "idle"
local PHASE_S1    = "s1"        -- first step: straight OR pivot (mode-selectable)
local PHASE_PIVOT = "pivot"     -- middle step: pivot only
local PHASE_S2    = "s2"        -- last step: straight only
local PHASE_LEAP  = "leap"      -- Exodite Leap: free reposition + free rotate

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

-- Leap state (Exodite special move)
local leapOrig        = nil     -- original planar centre {x,z} (fixed anchor)
local leapOrigHeading = 0       -- original heading (the footprint doesn't turn)
local leapOrigPts     = nil     -- cached original oval perimeter points
local leapRotHeld     = {}      -- [1]/[2] = numpad rotate key currently held?
local leapLastClock   = nil     -- os.clock() of the previous Leap tick (for dt)

-- Live readout (distance/angle) + its 3DText object
local distTextObj    = nil      -- spawned 3DText that shows the live measurement
local distTextStyled = false    -- has the font size/colour been applied yet?
local readoutText    = nil      -- text to show this tick (nil = hide)
local readoutPos     = nil      -- world {x,z} to place the readout this tick

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
-- rotating about the chosen anchor. Aiming works in TWO cones: the FRONT cone
-- aims the front of the base at the pointer (normal turn); the BACK cone aims
-- the REAR of the base at the pointer (inverse turn), so pointing behind the
-- model turns it toward you instead of snapping to max. Between the cones (the
-- sides) there is no valid aim. Returns new heading, new centre Vector, the
-- anchor point, the signed turn delta, and whether the aim is valid.
local function pivotPreview(pointer, origin, pos, heading)
	local anchor  = pivotAnchor(origin, pos, heading)
	local desired = headingOf(pointer.x - anchor.x, pointer.z - anchor.z)
	local raw     = wrap180(desired - heading)          -- front-aim angle
	local rawBack = wrap180(raw - 180)                  -- rear-aim angle
	local base, valid
	if math.abs(raw) <= MAX_PIVOT_DEG + PIVOT_AIM_TOL then
		base, valid = raw, true                         -- front cone: aim the front
	elseif math.abs(rawBack) <= MAX_PIVOT_DEG + PIVOT_AIM_TOL then
		base, valid = rawBack, true                     -- back cone: aim the rear (inverse)
	else
		base, valid = 0, false                          -- side dead zone: no aim
	end
	local delta   = clamp(base, -MAX_PIVOT_DEG, MAX_PIVOT_DEG)
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
	return newH, newPos, anchor, delta, valid
end

-- --------------------------------------------------------------------- leap ---
-- Sample the model's oval base perimeter (planar {x,z}) at a centre/heading.
-- Used to measure the edge-to-edge gap for the Leap clamp.
local function ovalPerimeter(cx, cz, heading, steps)
	local aLong = halfLong()
	local bWide = halfWide()
	local fdir  = dirFromHeading(heading)
	local sdir  = dirFromHeading(heading + 90)
	local pts = {}
	for i = 0, steps - 1 do
		local t  = (i / steps) * 2 * math.pi
		local fl = aLong * math.cos(t)
		local sl = bWide * math.sin(t)
		pts[#pts + 1] = {
			x = cx + fdir.x * fl + sdir.x * sl,
			z = cz + fdir.z * fl + sdir.z * sl,
		}
	end
	return pts
end

-- Smallest distance between two sampled perimeters (world units). Once the two
-- ovals separate this equals the edge-to-edge gap; while overlapping it stays
-- near zero, which is fine for the clamp (overlap is always a legal Leap).
local function minPerimeterGap(ptsA, ptsB)
	local best = math.huge
	for _, a in ipairs(ptsA) do
		for _, b in ipairs(ptsB) do
			local dx, dz = a.x - b.x, a.z - b.z
			local d2 = dx * dx + dz * dz
			if d2 < best then best = d2 end
		end
	end
	return math.sqrt(best)
end

-- Clamp a desired Leap centre so the base's edge stays within MAX_LEAP_INCHES of
-- the original footprint. The ghost slides along the original->pointer line: if
-- the far end is legal it's used as-is, otherwise a binary search finds the
-- furthest legal point on that line for the current (ghost) heading.
local function clampLeapPos(desired, heading)
	local dx = desired.x - leapOrig.x
	local dz = desired.z - leapOrig.z
	local dist = math.sqrt(dx * dx + dz * dz)
	if dist < 1e-6 then
		return { x = leapOrig.x, y = startY, z = leapOrig.z }
	end
	local ux, uz = dx / dist, dz / dist
	local maxGapU = toUnits(MAX_LEAP_INCHES)
	local function gapAt(d)
		local cx, cz = leapOrig.x + ux * d, leapOrig.z + uz * d
		return minPerimeterGap(leapOrigPts, ovalPerimeter(cx, cz, heading, LEAP_STEPS))
	end
	if gapAt(dist) <= maxGapU then
		return { x = desired.x, y = startY, z = desired.z }
	end
	local lo, hi = 0, dist
	for _ = 1, 24 do
		local mid = (lo + hi) * 0.5
		if gapAt(mid) <= maxGapU then lo = mid else hi = mid end
	end
	return { x = leapOrig.x + ux * lo, y = startY, z = leapOrig.z + uz * lo }
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

-- Grey full-range straight guide: the swept corridor of the base over the whole
-- reachable straight distance - the two base SIDES (no centre line) plus a
-- half-oval cap of the base at EACH end (forward tip and backward tip), so you
-- can see exactly how far the base reaches either way.
local function appendRangeGuide(out, pos, heading, fwdInches, backInches, color)
	local fdir = dirFromHeading(heading)
	local side = dirFromHeading(heading + 90)
	local hw   = halfWide()
	local aL   = halfLong()
	local f    = toUnits(fwdInches)
	local b    = toUnits(backInches)
	local cf   = { x = pos.x + fdir.x * f, z = pos.z + fdir.z * f }   -- centre at max forward
	local cb   = { x = pos.x - fdir.x * b, z = pos.z - fdir.z * b }   -- centre at max backward
	local thin = LINE_THICKNESS * 0.6
	local y    = pos.y + LINE_HEIGHT
	-- Left / right swept edges (base sides).
	table.insert(out, line({ x = cb.x + side.x * hw, y = pos.y, z = cb.z + side.z * hw },
	                       { x = cf.x + side.x * hw, y = pos.y, z = cf.z + side.z * hw }, color, thin))
	table.insert(out, line({ x = cb.x - side.x * hw, y = pos.y, z = cb.z - side.z * hw },
	                       { x = cf.x - side.x * hw, y = pos.y, z = cf.z - side.z * hw }, color, thin))
	-- Half-oval cap of the base at each end (t sweeps 180deg through the tip).
	local steps = 20
	local function cap(centre, tStart)
		local pts = {}
		for i = 0, steps do
			local t  = tStart + (i / steps) * math.pi
			local fl = aL * math.cos(t)
			local sl = hw * math.sin(t)
			pts[#pts + 1] = { centre.x + fdir.x * fl + side.x * sl, y, centre.z + fdir.z * fl + side.z * sl }
		end
		table.insert(out, { points = pts, color = color, thickness = thin })
	end
	if f > 1e-3 then cap(cf, -math.pi / 2) end   -- forward half (front tip)
	if b > 1e-3 then cap(cb,  math.pi / 2) end   -- rear half (back tip)
end

-- Grey reachable cone (a "range map"): the sector the base's front tip can reach
-- by pivoting up to +/-spanDeg and then spending the remaining straight budget.
-- Drawn as an outer arc plus the two side edges from the model centre.
local function appendReachCone(out, pos, heading, spanDeg, radiusInches, color)
	local r = toUnits(radiusInches)
	local y = (pos.y or curPos.y) + LINE_HEIGHT
	local steps = 28
	local arc = {}
	for i = 0, steps do
		local h = heading - spanDeg + (2 * spanDeg) * (i / steps)
		local d = dirFromHeading(h)
		arc[#arc + 1] = { pos.x + d.x * r, y, pos.z + d.z * r }
	end
	table.insert(out, { points = arc, color = color, thickness = LINE_THICKNESS * 0.6 })
	local dL = dirFromHeading(heading - spanDeg)
	local dR = dirFromHeading(heading + spanDeg)
	table.insert(out, { points = { { pos.x, y, pos.z }, { pos.x + dL.x * r, y, pos.z + dL.z * r } }, color = color, thickness = LINE_THICKNESS * 0.6 })
	table.insert(out, { points = { { pos.x, y, pos.z }, { pos.x + dR.x * r, y, pos.z + dR.z * r } }, color = color, thickness = LINE_THICKNESS * 0.6 })
end

-- Pivot helper: a small cross drawn at the pivot anchor point. (The allowed
-- turn range is shown separately by the grey reach cone.)
local function appendPivotGuides(out, anchor, heading, y)
	local m = 0.35
	table.insert(out, line({ x = anchor.x - m, y = y, z = anchor.z }, { x = anchor.x + m, y = y, z = anchor.z }, COL_PIVOT))
	table.insert(out, line({ x = anchor.x, y = y, z = anchor.z - m }, { x = anchor.x, y = y, z = anchor.z + m }, COL_PIVOT))
end

-- Closed oval outline (the base) centred at (cx,cy,cz), long axis along heading.
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

	-- Front marker: a small chevron ">" at the front edge, pointing along the
	-- heading, so the model's facing (and any rotation) is easy to read.
	local col = color or COL_GHOST
	local m   = math.max(0.18, math.min(aLong, bWide) * 0.55)
	local fex = cx + fdir.x * aLong           -- centre of the front edge
	local fez = cz + fdir.z * aLong
	local y   = cy + LINE_HEIGHT
	local apex  = { fex + fdir.x * m, y, fez + fdir.z * m }
	local barbL = { fex + sdir.x * m * 0.8, y, fez + sdir.z * m * 0.8 }
	local barbR = { fex - sdir.x * m * 0.8, y, fez - sdir.z * m * 0.8 }
	table.insert(out, { points = { barbL, apex, barbR }, color = col, thickness = LINE_THICKNESS })
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

-- --------------------------------------------------------- distance readout --
-- A spawned 3DText object that live-shows the current step's distance/angle
-- near the ghost (like the built-in ruler) - no chat spam. Created on begin,
-- moved + updated each tick, destroyed on finish/cancel.
local function ensureDistText()
	if distTextObj ~= nil then return end
	distTextStyled = true   -- style + initial text are baked into the spawn data
	-- Spawn with an initial " " (and the font size) already set, so TTS never
	-- shows its "Type here" placeholder during the async spawn gap.
	distTextObj = spawnObjectData({
		data = {
			Name = "3DText",
			Transform = {
				posX = curPos.x, posY = startY + 0.5, posZ = curPos.z,
				rotX = 90, rotY = 0, rotZ = 0,
				scaleX = 0.35, scaleY = 0.35, scaleZ = 0.35,
			},
			Text = {
				Text       = " ",
				colorstate = { r = 1, g = 1, b = 1 },
				fontSize   = READOUT_FONT,
			},
			Locked = true,
		},
	})
end

local function updateDistText()
	if distTextObj == nil or distTextObj.TextTool == nil then return end
	if not readoutText then
		-- A single space renders as nothing, avoiding the "Type here" placeholder.
		pcall(function() distTextObj.TextTool.setValue(" ") end)
		return
	end
	local p = readoutPos or curPos
	pcall(function() distTextObj.setPosition({ p.x, startY + 0.5, p.z }) end)
	pcall(function() distTextObj.TextTool.setValue(readoutText) end)
end

local function destroyDistText()
	if distTextObj ~= nil then
		local o = distTextObj
		distTextObj = nil
		pcall(function() if o ~= nil then o.destruct() end end)
	end
end

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
	readoutText, readoutPos = nil, nil

	if phase == PHASE_S1 and s1Mode == "straight" then
		-- Grey full-range guide: the whole straight budget you could still spend.
		appendRangeGuide(active, curPos, curHeading, remainingInches(),
			math.max(0, MAX_BACK_INCHES - backSpent), COL_LIMIT)
		local d, e, h = straightPreview(pointer)
		prevStraight, prevEndPos, prevHeading = d, e, h
		appendCorridor(active, curPos, e, h, COL_LEG)
		endPos, endHeading = e, h
		readoutText = string.format('%.1f"', math.abs(d)) .. (d < 0 and " back" or "")
		readoutPos  = { x = (curPos.x + e.x) * 0.5, y = curPos.y, z = (curPos.z + e.z) * 0.5 }

	elseif phase == PHASE_S1 then
		local nh, np, anchor, delta, valid = pivotPreview(pointer, s1Origin(), curPos, curHeading)
		-- Grey reachable cones from the pivot anchor (moves with the mode): pivot
		-- +/-45, then spend the straight budget FORWARD or BACKWARD.
		local fdir = dirFromHeading(curHeading)
		local anchorFwdU = (anchor.x - curPos.x) * fdir.x + (anchor.z - curPos.z) * fdir.z
		local backRem = math.max(0, MAX_BACK_INCHES - backSpent)
		appendReachCone(active, anchor, curHeading, MAX_PIVOT_DEG,
			remainingInches() + toInches(halfLong() - anchorFwdU), COL_LIMIT)
		appendReachCone(active, anchor, curHeading + 180, MAX_PIVOT_DEG,
			backRem + toInches(halfLong() + anchorFwdU), COL_LIMIT)
		appendPivotGuides(active, anchor, curHeading, curPos.y)
		if valid then
			prevStraight, prevEndPos, prevHeading = 0, np, nh
			endPos, endHeading = np, nh
		else
			prevEndPos = nil   -- side dead zone: hide ghost, block commit
		end

	elseif phase == PHASE_PIVOT then
		local nh, np, anchor, delta, valid = pivotPreview(pointer, pivotOrigin, curPos, curHeading)
		-- Reach cones from the pivot anchor (moves with the chosen mode): forward
		-- (remaining straight budget) and backward (remaining backward budget).
		local fdir = dirFromHeading(curHeading)
		local anchorFwdU = (anchor.x - curPos.x) * fdir.x + (anchor.z - curPos.z) * fdir.z
		local backRem = math.max(0, MAX_BACK_INCHES - backSpent)
		appendReachCone(active, anchor, curHeading, MAX_PIVOT_DEG,
			remainingInches() + toInches(halfLong() - anchorFwdU), COL_LIMIT)
		appendReachCone(active, anchor, curHeading + 180, MAX_PIVOT_DEG,
			backRem + toInches(halfLong() + anchorFwdU), COL_LIMIT)
		appendPivotGuides(active, anchor, curHeading, curPos.y)
		if valid then
			prevStraight, prevEndPos, prevHeading = 0, np, nh
			endPos, endHeading = np, nh
		else
			prevEndPos = nil   -- side dead zone: hide ghost, block commit
		end

	elseif phase == PHASE_S2 then
		appendRangeGuide(active, curPos, curHeading, remainingInches(),
			math.max(0, MAX_BACK_INCHES - backSpent), COL_LIMIT)
		local d, e, h = straightPreview(pointer)
		prevStraight, prevEndPos, prevHeading = d, e, h
		appendCorridor(active, curPos, e, h, COL_LEG)
		endPos, endHeading = e, h
		readoutText = string.format('%.1f"', math.abs(d)) .. (d < 0 and " back" or "")
		readoutPos  = { x = (curPos.x + e.x) * 0.5, y = curPos.y, z = (curPos.z + e.z) * 0.5 }

	elseif phase == PHASE_LEAP then
		-- Smooth free rotation while a numpad rotate key is held. Drive it by real
		-- elapsed time (deg/sec) so the spin speed is frame-rate independent.
		local now = os.clock()
		local dt  = leapLastClock and (now - leapLastClock) or 0
		leapLastClock = now
		if leapRotHeld[1] then curHeading = curHeading - LEAP_ROT_DEG_SEC * dt end
		if leapRotHeld[2] then curHeading = curHeading + LEAP_ROT_DEG_SEC * dt end
		local pos = clampLeapPos(pointer, curHeading)
		prevStraight, prevEndPos, prevHeading = 0, pos, curHeading
		-- Grey ghost = original footprint (the 1" anchor); cyan = destination.
		appendGhost(active, leapOrig.x, startY, leapOrig.z, leapOrigHeading, COL_ORIG)
		endPos, endHeading = pos, curHeading
	end

	redraw(active, endPos, endHeading)
	updateDistText()
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
-- Per-player, screen-space click catcher (Global UI). A full-screen, effectively
-- invisible overlay shown ONLY to the driving player (visibility = controlColor).
-- Because it lives on the driver's own screen, opponents have NO such element and
-- keep interacting with the whole table while a sprint is active -- unlike a
-- physical table button, which every player can click and which therefore locked
-- the board. The click LOCATION is irrelevant (the ghost already tracks the
-- pointer and the model moves to the ghost); the overlay only turns a left/right
-- click into apply/back. It is added/removed on the shared Global canvas by id,
-- so it never clobbers the model's own self.UI or any other Global UI.
local CATCHER_UI_ID = "ktSprintCatcher"

local function uiRootTable()
	local t = UI.getXmlTable()
	if type(t) ~= "table" then t = {} end
	return t
end

-- Return a copy of the Global-UI table with our catcher element removed.
local function uiWithoutCatcher(t)
	local out = {}
	for _, el in ipairs(t) do
		if not (type(el) == "table" and el.attributes and el.attributes.id == CATCHER_UI_ID) then
			out[#out + 1] = el
		end
	end
	return out
end

-- Global UI rejects an empty array ("table was null"); when our catcher was the
-- only element, clear the whole Global canvas with setXml("") instead.
local function uiApply(t)
	if #t == 0 then UI.setXml("") else UI.setXmlTable(t) end
end

local function createCatcher(_tooltip)
	if catcherActive then return end
	if not controlColor then return end
	local t = uiWithoutCatcher(uiRootTable())
	t[#t + 1] = {
		tag = "Image",
		attributes = {
			id            = CATCHER_UI_ID,
			visibility    = controlColor,               -- only the driving player sees/clicks it
			color         = "#00000001",                -- effectively invisible, still raycasts
			raycastTarget = "true",                     -- captures the click
			width         = "100%",
			height        = "100%",
			rectAlignment = "MiddleCenter",
			-- Global-UI events default to the Global script; the GUID prefix routes
			-- the click back to THIS model's (appended) script instead.
			onClick       = self.getGUID() .. "/sprintCatcherClick",
		},
	}
	uiApply(t)
	catcherActive = true
end

local function removeCatcher()
	if not catcherActive then return end
	uiApply(uiWithoutCatcher(uiRootTable()))
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
	destroyDistText()
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
	destroyDistText()
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
	ensureDistText()
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
	createCatcher("Left: apply   Right: cancel   2/3/4: pivot point   0: cancel")
	ensureDistText()
	msg(pc, "Turn: 2/3/4 = pivot from front/centre/back, drag to turn (+/-45deg). "
		.. "Left=apply, right/0=cancel.", COL_PIVOT)
end

-- "Leap" (Exodite special move): reposition the base freely by aiming, clamped
-- so any part of the base stays within 1" of any part of the original footprint,
-- with FREE 360 rotation (hold numpad 1/2, or tap number-row 1/2). Left-click
-- applies; right-click / 0 cancels.
local function beginLeap(pc)
	refreshBaseDims()
	controlColor = pc
	local p      = self.getPosition()
	startY       = p.y
	curPos       = { x = p.x, y = p.y, z = p.z }
	local fwd    = self.getTransformForward()
	curHeading   = headingOf(fwd.x, fwd.z) + facingOffset
	leapOrig        = { x = p.x, z = p.z }
	leapOrigHeading = curHeading
	leapOrigPts     = ovalPerimeter(p.x, p.z, curHeading, LEAP_STEPS)
	leapRotHeld     = {}
	leapLastClock   = nil
	spentInches  = 0
	backSpent    = 0
	rawStraight  = 0
	committedLegs = {}
	history      = {}
	phase        = PHASE_LEAP
	lastReport   = nil
	startLoop()
	createCatcher("Left: apply   Right: cancel   Hold 1/2: rotate   0: cancel")
	ensureDistText()
	msg(pc, 'Leap: aim to move (auto-clamped to 1").  Hold numpad 1/2 = rotate '
		.. "(or tap number-row 1/2).  Left=apply, right/0=cancel.", COL_PIVOT)
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

	elseif phase == PHASE_LEAP then
		if prevEndPos then
			curPos     = { x = prevEndPos.x, y = curPos.y, z = prevEndPos.z }
			curHeading = prevHeading
		end
		finishSprint(pc, "Leap complete.")
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

-- Key 9: lock in the current step and finish. In a straight step it commits the
-- current straight move (so a short "2" and stop" needs no exact end aim). In
-- the pivot step it APPLIES the current pivot and finishes (skips the final
-- straight leg) - i.e. "apply this rotation and stop here".
local function finishStraightNoPivot(pc)
	if phase == PHASE_PIVOT then
		if prevEndPos then commitPivot(prevHeading, prevEndPos) end
		finishSprint(pc, string.format('Sprint complete: %.1f" total.', rawStraight))
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
	if phase == PHASE_LEAP then
		-- Number-row 1/2 = stepped rotate (fallback for the held-numpad spin);
		-- 9 = apply, 0 = cancel.
		if digit == 1 then curHeading = curHeading - LEAP_ROT_STEP
		elseif digit == 2 then curHeading = curHeading + LEAP_ROT_STEP
		elseif digit == 9 then advance(pc)
		elseif digit == 0 then cancelSprint(pc)
		else return false end
		return true
	end
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

-- Global-UI catcher handler. Signature is (player, mouseButton, id): a non-Button
-- element passes the mouse button as the 2nd arg -- "-2" is right-click (back),
-- anything else ("-1" left) is apply. visibility already restricts this to the
-- driving player; the controlColor check is a belt-and-braces guard.
function sprintCatcherClick(player, mouseButton, _id)
	if phase == PHASE_IDLE then return end
	local pc = player and player.color
	if controlColor and pc ~= controlColor then return end
	if mouseButton == "-2" then stepBack(pc) else advance(pc) end
end

-- TTS scripting buttons = the NUMPAD by default (index 10 == the "0" key). No
-- hover needed, so this works while aiming at the table.
function sprintScriptingButton(index, playerColor)
	local digit = index == 10 and 0 or index
	-- During a Leap, holding numpad 1/2 drives smooth free rotation; track the
	-- held state here and let the tick loop spin the ghost while the key is down.
	if phase == PHASE_LEAP and (not controlColor or playerColor == controlColor)
		and (digit == 1 or digit == 2) then
		leapRotHeld[digit] = true
		return
	end
	handleDigit(playerColor, digit)
end

-- Release handler for the numpad rotate keys (Leap only).
function sprintScriptingButtonUp(index, playerColor)
	local digit = index == 10 and 0 or index
	if digit == 1 or digit == 2 then leapRotHeld[digit] = nil end
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
	self.addContextMenuItem("Leap", function(pc)
		if phase == PHASE_IDLE then beginLeap(pc) end
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

local _sprint_prev_onScriptingButtonUp = onScriptingButtonUp
function onScriptingButtonUp(...)
	if _sprint_prev_onScriptingButtonUp then _sprint_prev_onScriptingButtonUp(...) end
	sprintScriptingButtonUp(...)
end

-- Number ROW typed while hovering the model (no binding needed). The catcher is
-- now a screen overlay rather than a table-covering button, so the number ROW
-- only fires while actually hovering the model; the NUMPAD (onScriptingButton)
-- is the reliable across-the-table path. We still consume the row here and
-- return true so the host's default (e.g. setting wounds) is suppressed; when
-- idle we defer to the host.
local _sprint_prev_onNumberTyped = onNumberTyped
function onNumberTyped(playerColor, number, alt)
	if phase ~= PHASE_IDLE and (not controlColor or playerColor == controlColor) then
		handleDigit(playerColor, number)
		return true
	end
	if _sprint_prev_onNumberTyped then return _sprint_prev_onNumberTyped(playerColor, number, alt) end
end
