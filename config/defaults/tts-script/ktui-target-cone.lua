-- KTUI targeting cone ("Targeting lines" context item on KTUI minis).
-- Derived from "KTMT Target Cone" (KT24 Table / KTMT by xSpaghettyx & Ixidior),
-- which treated every base as a circle of diameter base.x. This version models
-- each base as the oval KTUI draws: base.x wide, base.z long along the model's
-- facing (transform forward, plus kt_front on command-node models). The lines
-- run to the two outermost points of the target base as seen from the origin
-- (the tangents), the cone stays on the origin's base edge, and the range is
-- measured base edge to base edge. Line colour shows the target's cover (orange
-- light, red heavy), a purple arc marks it obscured, and the state is shown in
-- the top-centre HUD. When either base is more than 1" above the floor, the
-- default lines stay and the HUD says Vantage isn't supported yet (one Vantage piece mixes
-- heavy walls below the platform with light walls above it).

pickedUp = false
newX = 0
newZ = 0
posY = 0
colorLinea = Color(1,1,1)
mtoi = 0.0393701
estado_cono = 0
ObjMiniTarget = nil
objModel = nil

lockEnabled = true

local SAMPLES = 72
local atan2 = math.atan2 or math.atan

-- Base footprint of a model as an oval: centre, half-width a (side-to-side),
-- half-length b (front-to-back) and heading h (radians, TTS yaw convention:
-- forward = (sin h, cos h)). Non-KTUI objects fall back to a circle from bounds.
local function baseEllipse(obj)
	local pos = obj.getPosition()
	local st = obj.getTable("state")
	local bx, bz
	if type(st) == "table" and type(st.base) == "table" then
		bx = tonumber(st.base.x)
		bz = tonumber(st.base.z) or bx
	end
	if not bx or not bz or bx <= 0 or bz <= 0 then
		local size = obj.getBoundsNormalized().size
		local r = math.max(size.x, size.z) * 0.5
		return { x = pos.x, z = pos.z, a = r, b = r, h = 0 }
	end
	local heading = obj.getRotation().y
	if st.kt_node_ui then heading = heading + (tonumber(st.kt_front) or 0) end
	return { x = pos.x, z = pos.z, a = bx * mtoi * 0.5, b = bz * mtoi * 0.5, h = math.rad(heading) }
end

local function shrink(e, by)
	return { x = e.x, z = e.z, a = math.max(0.01, e.a - by), b = math.max(0.01, e.b - by), h = e.h }
end

local function toLocal(e, wx, wz)
	local dx, dz = wx - e.x, wz - e.z
	local c, s = math.cos(e.h), math.sin(e.h)
	return dx * c - dz * s, dx * s + dz * c
end

local function toWorld(e, u, v)
	local c, s = math.cos(e.h), math.sin(e.h)
	return e.x + u * c + v * s, e.z - u * s + v * c
end

local function pointAt(e, t)
	return toWorld(e, e.a * math.cos(t), e.b * math.sin(t))
end

-- Point on the oval's edge along the ray from its centre towards (wx, wz).
local function edgeToward(e, wx, wz)
	local u, v = toLocal(e, wx, wz)
	local k = math.sqrt((u / e.a) ^ 2 + (v / e.b) ^ 2)
	if k < 1e-9 then return toWorld(e, e.a, 0) end
	return toWorld(e, u / k, v / k)
end

-- The two points of the oval that bound it as seen from (px, pz): the tangent
-- points. Scaling the oval to a unit circle keeps tangency, so solve it there.
local function tangentPoints(e, px, pz)
	local u, v = toLocal(e, px, pz)
	local U, V = u / e.a, v / e.b
	local d = math.sqrt(U * U + V * V)
	if d <= 1 + 1e-6 then
		-- Viewer inside the base: use the extremes across the line of sight.
		local nu, nv = -v, u
		if math.abs(nu) + math.abs(nv) < 1e-9 then nu, nv = 1, 0 end
		local k = math.sqrt(e.a * e.a * nu * nu + e.b * e.b * nv * nv)
		local su, sv = e.a * e.a * nu / k, e.b * e.b * nv / k
		local x1, z1 = toWorld(e, su, sv)
		local x2, z2 = toWorld(e, -su, -sv)
		return x1, z1, x2, z2
	end
	local phi, alpha = atan2(V, U), math.acos(1 / d)
	local x1, z1 = pointAt(e, phi + alpha)
	local x2, z2 = pointAt(e, phi - alpha)
	return x1, z1, x2, z2
end

-- Parameter of the point on the oval closest to (px, pz): start at the point's
-- own angle in the oval's scaled frame (on the near side, so in the right
-- basin), then a shrinking pattern search so the ceil()'d range is exact.
local function closestT(e, px, pz, t0, span)
	local function dist2(t)
		local x, z = pointAt(e, t)
		return (x - px) ^ 2 + (z - pz) ^ 2
	end
	if not t0 then
		local u, v = toLocal(e, px, pz)
		t0, span = atan2(v / e.b, u / e.a), 0.25
	end
	local best, bestD = t0, dist2(t0)
	for _ = 1, 24 do
		local l, r = dist2(best - span), dist2(best + span)
		if l < bestD then best, bestD = best - span, l
		elseif r < bestD then best, bestD = best + span, r
		else span = span * 0.5 end
	end
	return best, math.sqrt(bestD)
end

-- Edge-to-edge gap between two ovals (0 when they touch or overlap).
local function ovalGap(e1, e2)
	local u, v = toLocal(e1, e2.x, e2.z)
	if (u / e1.a) ^ 2 + (v / e1.b) ^ 2 <= 1 then return 0 end
	u, v = toLocal(e2, e1.x, e1.z)
	if (u / e2.a) ^ 2 + (v / e2.b) ^ 2 <= 1 then return 0 end
	for i = 0, SAMPLES - 1 do
		local x, z = pointAt(e1, i * 2 * math.pi / SAMPLES)
		local inU, inV = toLocal(e2, x, z)
		if (inU / e2.a) ^ 2 + (inV / e2.b) ^ 2 <= 1 then return 0 end
	end
	local t1 = closestT(e1, e2.x, e2.z)
	local t2, gap
	for _ = 1, 6 do
		local x1, z1 = pointAt(e1, t1)
		t2 = closestT(e2, x1, z1, t2, 0.2)
		local x2, z2 = pointAt(e2, t2)
		t1, gap = closestT(e1, x2, z2, t1, 0.2)
	end
	return gap
end

local function pointGap(px, pz, e)
	local u, v = toLocal(e, px, pz)
	if (u / e.a) ^ 2 + (v / e.b) ^ 2 <= 1 then return 0 end
	local _, gap = closestT(e, px, pz)
	return gap
end

-- Cover / obscured. Rays fan from the cone tip to points across the facing part
-- of the target base, just above both bases; each is cast both ways so every
-- piece of terrain it crosses yields the stretch of the line inside it (a ray
-- only reports where it enters a collider). Operatives,
-- tokens, tools and mats/boards/tiles are ignored, and so is the terrain the
-- shooter stands on (and the target's, unless the target is shot at from below).
-- Per stretch (so one piece can do both):
--   light/heavy within 1" of the target  -> light/heavy cover (heavy wins),
--                                            none if the bases are within 2"
--   heavy more than 1" from BOTH bases    -> obscured
-- Terrain type comes from the name, else the description's first line, else
-- the whole description ("Light Rubble", "Capillary Tower (Heavy)",
-- "Portable barricade" = light); untyped is heavy.
-- Name lists below are matched against the START of the lower-cased name (so
-- "Heavy, Vantage ... / Ladder: Heavy" is not a ladder). They bridge tables
-- whose terrain isn't tagged yet.
local FAN_RAYS = 9
local RAY_LIFT = 0.1             -- sight rays run this far above each base
local SHOOTING_UP = 0.5          -- target this much higher: its own terrain intervenes
-- Stopgap until Vantage-aware detection: one terrain object mixes heavy walls
-- below the Vantage with light walls above it, so when either base is more
-- than this above the floor (on Vantage) there is no auto result.
local HEIGHT_CHECK = 1
local CONTROL_RANGE = 1
local COVER_DENIED_WITHIN = 2
local ANALYSE_EVERY = 6          -- frames between terrain checks while dragging
local COL_LIGHT = { 1, 0.55, 0 }
local COL_HEAVY = { 0.95, 0.1, 0.1 }
local COL_OBSCURED = { 0.7, 0.3, 1 }
local IGNORE_TYPES = { Scripting = true, Surface = true, Hand = true, Card = true, Deck = true, Dice = true,
                       Tile = true }
local IGNORE_TAGS = { "KTUIMini", "KTUI_ToolActive", "KT24Token", "KT_Objective" }
-- Board-type objects are terrain unless this wide on their shorter side
-- (game boards/mats; the base table's are >= 14.8", its terrain <= 8.8").
local BOARD_MIN_SIDE = 12
-- Exposed / insignificant pieces: never cover, never obscure.
local NO_COVER_NAMES = { "teleport", "fire step", "razor wire", "ladder" }
-- Real terrain that carries an ignored tag (KT_Objective).
local TERRAIN_NAMES = { "g4: objective marker" }
-- A marker's bounds can be just its flat base disc, so its cylinder is at
-- least this tall.
local MARKER_MIN_HEIGHT = 1
local MARKER_MAX_RADIUS = 20 * 0.0393701
-- Open states: the centred fraction of the long side is an exposed access
-- point; the wall either side still gives cover / obscures. Calibrated from
-- in-game screenshots against the 50% edge: Tomb World door ~41% (mesh gap
-- 36-40%), breach ~46% (a V: 26% at the floor to ~45% at the rim), Gallowdark
-- hatchway estimated from screenshots.
local OPENING_FRACTIONS = { ["open door"] = 0.40, ["breached wall"] = 0.45, ["open hatchway"] = 0.45 }
local OPENING_NAMES = {}
for prefix in pairs(OPENING_FRACTIONS) do OPENING_NAMES[#OPENING_NAMES + 1] = prefix end

coverState = nil      -- nil | "light" | "heavy"
obscuredState = false
vantageState = false  -- a base is on Vantage (above the floor): no auto cover/obscured
tooCloseState = false -- bases within 2": cover is ignored
activeColor = nil     -- player using the cone (gets the HUD readout)
local dragFrames = 0

local function facingPoints(e, px, pz)
	local u, v = toLocal(e, px, pz)
	local U, V = u / e.a, v / e.b
	local d = math.sqrt(U * U + V * V)
	if d <= 1 + 1e-6 then
		local x1, z1, x2, z2 = tangentPoints(e, px, pz)
		return { { x1, z1 }, { x2, z2 } }
	end
	local phi, alpha = atan2(V, U), math.acos(1 / d)
	local pts = {}
	for i = 0, FAN_RAYS - 1 do
		local x, z = pointAt(e, phi - alpha + 2 * alpha * i / (FAN_RAYS - 1))
		pts[#pts + 1] = { x, z }
	end
	return pts
end

local function nameStarts(obj, list)
	local name = tostring(obj.getName() or ""):lower()
	local first = name:find("%S") or 1
	for _, prefix in ipairs(list) do
		if name:sub(first, first + #prefix - 1) == prefix then return true end
	end
	return false
end

-- First non-blank line of a description, lower-cased. Plain finds only: Lua
-- patterns over long table text can throw "pattern too complex" in TTS.
local function firstLine(obj)
	local text = tostring(obj.getDescription() or ""):lower()
	local start = text:find("%S") or 1
	local stop = text:find("\n", start, true)
	return text:sub(start, stop and stop - 1 or #text)
end

-- Objective markers that are terrain (TERRAIN_NAMES), despite KT_Objective.
local function isTerrainMarker(obj)
	return nameStarts(obj, TERRAIN_NAMES)
end

-- Why an object never counts as terrain (nil = it can).
local function ignoreReason(obj)
	if obj == nil or obj == self or obj == objModel or obj == ObjMiniTarget then return "model/cone" end
	if IGNORE_TYPES[obj.type] then return "type " .. tostring(obj.type) end
	if isTerrainMarker(obj) then return nil end
	if nameStarts(obj, NO_COVER_NAMES) then return "no-cover name" end
	if obj.type == "Board" then
		local size = obj.getBoundsNormalized().size
		if math.min(size.x, size.z) >= BOARD_MIN_SIDE then return "board/mat" end
	end
	for _, tag in ipairs(IGNORE_TAGS) do
		if obj.hasTag(tag) then return "tag " .. tag end
	end
	for _, tag in ipairs(obj.getTags() or {}) do
		if tostring(tag):find("KTUIToken", 1, true) == 1 then return "tag " .. tostring(tag) end
	end
	return nil
end

local function isIgnored(obj)
	return ignoreReason(obj) ~= nil
end

-- Type from the name, else the description's first line (its keyword list,
-- e.g. "Light, Insignificant, Vantage"; later rules text can mention other
-- types), else the whole description. Untyped is heavy.
local function terrainKind(obj)
	local desc = tostring(obj.getDescription() or ""):lower()
	for _, text in ipairs({ tostring(obj.getName() or ""):lower(), firstLine(obj), desc }) do
		if text:find("heavy", 1, true) then return "heavy" end
		if text:find("light", 1, true) or text:find("portable", 1, true) then return "light" end
	end
	return "heavy"
end

-- Position of world (x, z) along an open piece's long side, measured from the
-- middle of its world bounds (the piece's origin can sit at one end), and the
-- half-width of its access point there.
local function openingPos(obj, x, z)
	local fraction = 0
	for prefix, f in pairs(OPENING_FRACTIONS) do
		if nameStarts(obj, { prefix }) then fraction = f end
	end
	local size = obj.getBoundsNormalized().size
	local c = obj.getBounds().center
	local u, v = toLocal({ x = c.x, z = c.z, h = math.rad(obj.getRotation().y) }, x, z)
	if size.x >= size.z then
		return u, size.x * fraction * 0.5
	end
	return v, size.z * fraction * 0.5
end

-- Whether the sight line crosses an open piece (OPENING_NAMES) at world (x, z)
-- inside its access point: the centred OPENING_FRACTIONS share of its long side.
local function throughOpening(obj, x, z)
	if not nameStarts(obj, OPENING_NAMES) then return false end
	local along, half = openingPos(obj, x, z)
	return math.abs(along) < half
end

local function baseBottom(obj)
	local b = obj.getBounds()
	return b.center.y - b.size.y * 0.5
end

local function guidOf(obj)
	return obj.getGUID and obj.getGUID() or tostring(obj)
end

local function addStretch(pieces, obj, s)
	local key = guidOf(obj)
	local piece = pieces[key]
	if piece then
		piece.sIn, piece.sOut = math.min(piece.sIn, s), math.max(piece.sOut, s)
	else
		pieces[key] = { obj = obj, sIn = s, sOut = s }
	end
end

-- What a model stands on (a platform, a floor tile). Never a terrain marker:
-- its collider includes the flat control-range disc models stand in, which
-- isn't standing on the marker itself.
local function supportsOf(model, skip)
	local pos, bottom = model.getPosition(), baseBottom(model)
	local hits = Physics.cast({ origin = { x = pos.x, y = bottom + 0.5, z = pos.z },
		direction = { x = 0, y = -1, z = 0 }, type = 1, max_distance = 1.5 }) or {}
	for _, hit in ipairs(hits) do
		local obj = hit.hit_object
		if not isIgnored(obj) and not isTerrainMarker(obj) then skip[guidOf(obj)] = true end
	end
end

-- How high a model's base is above the floor under it: the highest table,
-- tile or mat/board (>= BOARD_MIN_SIDE on its short side) the downward ray
-- hits. With no floor found, `fallbackFloor` (the lower of the two bases).
local function heightAboveFloor(model, fallbackFloor)
	local pos, bottom = model.getPosition(), baseBottom(model)
	local hits = Physics.cast({ origin = { x = pos.x, y = bottom + 0.05, z = pos.z },
		direction = { x = 0, y = -1, z = 0 }, type = 1, max_distance = 100 }) or {}
	local floor = nil
	for _, hit in ipairs(hits) do
		local obj = hit.hit_object
		if hit.point and obj ~= nil and obj ~= model then
			local isFloor = obj.type == "Surface" or obj.type == "Tile"
			if not isFloor then
				local size = obj.getBoundsNormalized().size
				isFloor = math.min(size.x, size.z) >= BOARD_MIN_SIDE
			end
			if isFloor and (floor == nil or hit.point.y > floor) then floor = hit.point.y end
		end
	end
	floor = floor or fallbackFloor or bottom
	return math.max(0, bottom - floor)
end

-- Whether either model is on Vantage (its base > HEIGHT_CHECK above the floor).
local function onVantage()
	local low = math.min(baseBottom(objModel), baseBottom(ObjMiniTarget))
	return heightAboveFloor(objModel, low) > HEIGHT_CHECK or heightAboveFloor(ObjMiniTarget, low) > HEIGHT_CHECK
end

-- TERRAIN_NAMES pieces are round markers whose colliders the sight rays don't
-- reliably hit (the base table's G4 marker collides with its antenna only), so
-- they are tested as an upright cylinder from their bounds instead.
local markerCache = nil
local function namedMarkers()
	if markerCache == nil then
		markerCache = {}
		for _, obj in ipairs(getAllObjects() or {}) do
			if not IGNORE_TYPES[obj.type] and isTerrainMarker(obj) then markerCache[#markerCache + 1] = obj end
		end
	end
	return markerCache
end

-- Adds the stretch where the segment from `a` (unit direction u, length len)
-- crosses obj's bounds cylinder; true if it does.
local function markerStretch(pieces, obj, a, u, len)
	local b = obj.getBounds()
	-- The bounds can include the 1" control-range decal: cap at a 40mm marker.
	local r = math.min(math.min(b.size.x, b.size.z) * 0.5, MARKER_MAX_RADIUS)
	local ox, oz = a.x - b.center.x, a.z - b.center.z
	local qa = u.x * u.x + u.z * u.z
	if qa < 1e-12 then return false end
	local qb = 2 * (ox * u.x + oz * u.z)
	local disc = qb * qb - 4 * qa * (ox * ox + oz * oz - r * r)
	if disc < 0 then return false end
	local sq = math.sqrt(disc)
	local s1, s2 = math.max(0, (-qb - sq) / (2 * qa)), math.min(len, (-qb + sq) / (2 * qa))
	if s1 > s2 then return false end
	local y1, y2 = a.y + u.y * s1, a.y + u.y * s2
	local bottom = b.center.y - b.size.y * 0.5
	local top = math.max(b.center.y + b.size.y * 0.5, bottom + MARKER_MIN_HEIGHT)
	if math.max(y1, y2) < bottom or math.min(y1, y2) > top then
		return false
	end
	addStretch(pieces, obj, s1)
	addStretch(pieces, obj, s2)
	return true
end

-- Stretches of one ray inside each terrain piece: { [guid] = {obj=, sIn=, sOut=} }
-- with s measured along the ray from `a` (0..len). Exposed pieces it crosses
-- (NO_COVER_NAMES) are added to `exposed` when given, for the key 4 report.
local function rayStretches(a, b, skip, exposed)
	local d = { x = b.x - a.x, y = b.y - a.y, z = b.z - a.z }
	local len = math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z)
	local pieces = {}
	if len < 1e-6 then return pieces, len, d end
	local u = { x = d.x / len, y = d.y / len, z = d.z / len }
	local function record(hits)
		for _, hit in ipairs(hits or {}) do
			local obj = hit.hit_object
			local why = ignoreReason(obj)
			if not why and not skip[guidOf(obj)] and hit.point then
				local p = hit.point
				local s = (p.x - a.x) * u.x + (p.y - a.y) * u.y + (p.z - a.z) * u.z
				addStretch(pieces, obj, math.max(0, math.min(len, s)))
			elseif why == "no-cover name" and exposed then
				exposed[guidOf(obj)] = obj
			end
		end
	end
	record(Physics.cast({ origin = a, direction = d, type = 1, max_distance = len }))
	record(Physics.cast({ origin = b, direction = { x = -d.x, y = -d.y, z = -d.z }, type = 1, max_distance = len }))
	for _, obj in ipairs(namedMarkers()) do
		if obj ~= nil and not skip[guidOf(obj)] then markerStretch(pieces, obj, a, u, len) end
	end
	return pieces, len, d
end

-- Where a ray from (ax, az) with planar step (dx, dz) per unit s enters and
-- leaves the oval grown by `grow` (the 1" zone around a base; exact for round
-- bases, within a few hundredths of an inch for ovals). nil if it misses.
local function rayThroughZone(e, ax, az, dx, dz, grow)
	local A, B = e.a + grow, e.b + grow
	local u0, v0 = toLocal(e, ax, az)
	local c, s = math.cos(e.h), math.sin(e.h)
	local du, dv = dx * c - dz * s, dx * s + dz * c
	local qa = (du / A) ^ 2 + (dv / B) ^ 2
	local qb = 2 * (u0 * du / (A * A) + v0 * dv / (B * B))
	local qc = (u0 / A) ^ 2 + (v0 / B) ^ 2 - 1
	local disc = qb * qb - 4 * qa * qc
	if qa < 1e-12 or disc < 0 then return nil end
	local r = math.sqrt(disc)
	return (-qb - r) / (2 * qa), (-qb + r) / (2 * qa)
end

-- What each crossed piece did in the last analysis, for key 4:
-- { order = {guid...}, pieces = {[guid] = {obj, kind, cover, coverDenied, obscures, solid, opening}},
--   exposed = {[guid] = obj} }
local lastReport = { order = {}, pieces = {}, exposed = {} }

-- Sets coverState / obscuredState for the current shooter (objModel, sight
-- lines from the cone at `sp`) and target.
function analyseTerrain(target, sp)
	coverState, obscuredState, vantageState, tooCloseState = nil, false, false, false
	lastReport = { order = {}, pieces = {}, exposed = {} }
	local shooterBottom, targetBottom = baseBottom(objModel), baseBottom(ObjMiniTarget)
	if onVantage() then
		vantageState = true
		return
	end
	local shooter = baseEllipse(objModel)
	local fullTarget = baseEllipse(ObjMiniTarget)
	local coverAllowed = ovalGap(shooter, fullTarget) > COVER_DENIED_WITHIN
	tooCloseState = not coverAllowed
	local a = { x = sp.x, y = shooterBottom + RAY_LIFT, z = sp.z }
	local ty = targetBottom + RAY_LIFT
	local skip = {}
	-- The shooter's own terrain never intervenes. The target's does when it is
	-- shot at from below (Vantage: the platform is between them), else not.
	supportsOf(objModel, skip)
	if targetBottom <= shooterBottom + SHOOTING_UP then supportsOf(ObjMiniTarget, skip) end
	local light, heavy = false, false
	local function entryFor(obj)
		local key = guidOf(obj)
		local entry = lastReport.pieces[key]
		if not entry then
			entry = { obj = obj, kind = terrainKind(obj) }
			lastReport.pieces[key] = entry
			lastReport.order[#lastReport.order + 1] = key
		end
		return entry
	end
	for _, p in ipairs(facingPoints(target, sp.x, sp.z)) do
		local pieces, len, d = rayStretches(a, { x = p[1], y = ty, z = p[2] }, skip, lastReport.exposed)
		if next(pieces) then
			local dx, dz = d.x / len, d.z / len
			-- Within 1" of the target from nearTarget on; more than 1" from the
			-- shooter from leaveShooter on.
			local tIn = rayThroughZone(fullTarget, a.x, a.z, dx, dz, CONTROL_RANGE)
			local _, sOut = rayThroughZone(shooter, a.x, a.z, dx, dz, CONTROL_RANGE)
			local nearTarget = tIn and math.max(0, tIn) or len
			local leaveShooter = sOut and math.max(0, sOut) or 0
			for _, piece in pairs(pieces) do
				local entry = entryFor(piece.obj)
				local mid = (piece.sIn + piece.sOut) * 0.5
				if throughOpening(piece.obj, a.x + dx * mid, a.z + dz * mid) then
					entry.opening = true
				else
					entry.solid = true
					local kind = entry.kind
					if piece.sOut >= nearTarget then
						if not coverAllowed then
							entry.coverDenied = true
						elseif kind == "heavy" then
							heavy, entry.cover = true, "heavy"
						else
							light = true
							if entry.cover ~= "heavy" then entry.cover = "light" end
						end
					end
					if kind == "heavy" and math.max(piece.sIn, leaveShooter) < math.min(piece.sOut, nearTarget) then
						obscuredState, entry.obscures = true, true
					end
				end
			end
		end
	end
	coverState = heavy and "heavy" or (light and "light" or nil)
end

-- Cover/obscured readout in the shared top-centre HUD the move tools use
-- (ktmove_hud in the Global UI), shown to the player using the cone.
local HUD_COLORS = { "White", "Brown", "Red", "Orange", "Yellow",
                     "Green", "Teal", "Blue", "Purple", "Pink" }
local hudColor, hudText = nil, nil

local function ensureHud()
	local cur = ""
	pcall(function() cur = Global.UI.getXml() or "" end)
	if type(cur) ~= "string" then cur = "" end
	if cur:find("ktmove_hud", 1, true) then return end
	local rows = ""
	for _, c in ipairs(HUD_COLORS) do
		local col = Color.fromString(c):lerp(Color.White, 0.25)
		rows = rows .. string.format(
			'<Text id="ktmove_txt_%s" active="false" color="#%s" fontSize="26" '
			.. 'fontStyle="Bold" alignment="Center" preferredHeight="32" '
			.. 'outline="#000000" outlineSize="2 -2" raycastTarget="false"> </Text>', c, col:toHex(false))
	end
	pcall(function() Global.UI.setXml(cur
		.. '<Panel id="ktmove_hud" active="true" rectAlignment="UpperCenter" '
		.. 'width="600" height="120" offsetXY="0 -80" color="#00000000" raycastTarget="false">'
		.. '<VerticalLayout childAlignment="UpperCenter" childForceExpandWidth="true" '
		.. 'childForceExpandHeight="false" spacing="2" raycastTarget="false">'
		.. rows .. '</VerticalLayout></Panel>') end)
end

local function hudSet(color, text)
	if hudColor and (color ~= hudColor or not text) then
		local old = hudColor
		pcall(function()
			Global.UI.setAttribute("ktmove_txt_" .. old, "active", "false")
			Global.UI.setValue("ktmove_txt_" .. old, " ")
		end)
		hudColor, hudText = nil, nil
	end
	if not color or not text or text == hudText then return end
	if not hudColor then ensureHud() end
	hudColor, hudText = color, text
	pcall(function()
		Global.UI.setAttribute("ktmove_txt_" .. color, "active", "true")
		Global.UI.setValue("ktmove_txt_" .. color, text)
	end)
end

local function stateText()
	if vantageState then return "Cover check doesn't currently work with Vantage" end
	local text = coverState == "heavy" and "Heavy cover" or (coverState == "light" and "Light cover" or "No cover")
	if tooCloseState then text = "Target within 2\" - all cover is ignored" end
	if obscuredState then text = text .. "  +  Obscured" end
	return text
end

-- Key 4: the result plus what each terrain piece on the sight lines does.
local REPORT_COLORS = { heavy = COL_HEAVY, light = COL_LIGHT, obscures = COL_OBSCURED, none = { 0.8, 0.8, 0.8 } }

local function pieceText(entry)
	local parts = {}
	if entry.cover then parts[#parts + 1] = entry.cover .. " cover" end
	if entry.obscures then parts[#parts + 1] = "obscures the target" end
	if #parts > 0 then return table.concat(parts, ", "), entry.cover or "obscures" end
	if entry.coverDenied then return "no cover, the target is within 2\"", "none" end
	if entry.solid then
		return entry.kind .. " terrain, no effect (not within 1\" of the target"
			.. (entry.kind == "heavy" and " and within 1\" of the shooter)" or ")"), "none"
	end
	return "no cover, the line goes through the open doorway", "none"
end

function explainTerrain(pc)
	if estado_cono ~= 2 or ObjMiniTarget == nil or objModel == nil then
		printToColor("Targeting: select a target first (key 1).", pc, { 1, 1, 1 })
		return
	end
	analyseTerrain(shrink(baseEllipse(ObjMiniTarget), 0.02), self.getPosition())
	printToColor("Targeting: " .. stateText(), pc, { 1, 1, 1 })
	if vantageState then
		printToColor("  A model is on Vantage: check cover manually.", pc, REPORT_COLORS.none)
		return
	end
	local function name(obj)
		local n = tostring(obj.getName() or "")
		return n:find("%S") and n or "Unnamed terrain"
	end
	for _, key in ipairs(lastReport.order) do
		local entry = lastReport.pieces[key]
		local text, tone = pieceText(entry)
		printToColor("  " .. name(entry.obj) .. ": " .. text, pc, REPORT_COLORS[tone])
	end
	for key, obj in pairs(lastReport.exposed) do
		if not lastReport.pieces[key] then
			printToColor("  " .. name(obj) .. ": no cover (exposed terrain)", pc, REPORT_COLORS.none)
		end
	end
	if #lastReport.order == 0 and next(lastReport.exposed) == nil then
		printToColor("  No terrain on the sight lines.", pc, REPORT_COLORS.none)
	end
end

function onPickUp(cp)
	activeColor = cp
	pickedUp = true
	startLuaCoroutine(self, "movModel")
end

function movModel()
	while (pickedUp == true) do
		posicionLock()
		coroutine.yield(0)
	end
	return 1
end

function posicionLock(forceAnalysis)
	objModel = getObjectFromGUID(GUIDModel)
	posY = objModel.getPosition().y + 0.5
	local mouse = self.getPosition()
	newX, newZ = mouse.x, mouse.z

	if lockEnabled then
		newX, newZ = edgeToward(baseEllipse(objModel), mouse.x, mouse.z)
		self.setPosition({x=newX, y=posY, z=newZ})
	else
		self.setPosition({x=newX, y=mouse.y, z=newZ})
	end

	self.setVelocity({0,0,0})
	self.setAngularVelocity({0,0,0})
	self.setRotation({0,0,0})
	refrescaVectores(forceAnalysis)
end

function onDropped(cp)
	if pickedUp == true then
		pickedUp = false

		if lockEnabled then
			self.setPosition({x=newX, y=posY, z=newZ})
		else
			local mouseY = self.getPosition().y
			self.setPosition({x=newX, y=mouseY, z=newZ})
		end

		self.setVelocity({0,0,0})
		self.setAngularVelocity({0,0,0})
		self.setRotation({0,0,0})
		refrescaVectores()
	end
end

function refrescaVectores(forceAnalysis)
	if estado_cono ~= 2 then return end
	local lambda = 1
	local ancho_linea = 0.04
	local sp = self.getPosition()
	local target = shrink(baseEllipse(ObjMiniTarget), ancho_linea * 0.5)
	local pY = ObjMiniTarget.getPosition().y - sp.y + 0.05
	local x1, z1, x2, z2 = tangentPoints(target, sp.x, sp.z)

	-- Line points are local to the cone (unrotated, unit scale); each line runs
	-- from the cone tip (0, -0.45, 0) past its tangent point by `lambda`.
	local function extended(wx, wz)
		local sX, sZ = wx - sp.x, wz - sp.z
		local Cy = pY + 0.45
		local mag = math.sqrt(sX * sX + Cy * Cy + sZ * sZ)
		return { x = sX + lambda * sX / mag, y = pY + lambda * Cy / mag, z = sZ + lambda * sZ / mag }
	end

	dragFrames = pickedUp and dragFrames + 1 or 0
	if forceAnalysis or dragFrames % ANALYSE_EVERY == 0 then
		analyseTerrain(target, sp)
		hudSet(activeColor, stateText())
		refrescaTextoRango()
	end
	local lineColor = colorLinea
	if coverState == "heavy" then lineColor = COL_HEAVY elseif coverState == "light" then lineColor = COL_LIGHT end
	local vectorLines = {{
		points = { extended(x1, z1), { x = 0, y = -0.45, z = 0 }, extended(x2, z2) },
		color = lineColor,
		thickness = ancho_linea,
		rotation = {0, 0, 0},
	}}
	if obscuredState then
		local arc = {}
		for _, p in ipairs(facingPoints(target, sp.x, sp.z)) do
			arc[#arc + 1] = { x = p[1] - sp.x, y = pY + 0.05, z = p[2] - sp.z }
		end
		vectorLines[2] = { points = arc, color = COL_OBSCURED, thickness = 0.12, rotation = {0, 0, 0} }
	end
	self.setVectorLines(vectorLines)
end

function onNumberTyped( pc, n )
	if n == 1 then
		estado_cono = 1
		broadcastToColor("Select Target", pc, {r=1, g=1, b=1})
	elseif n == 2 then
		lockEnabled = not lockEnabled
		if lockEnabled then
			broadcastToColor("Targeting Tool locked to base", pc, {1,1,1})
		else
			broadcastToColor("Targeting Tool unlocked", pc, {1,1,1})
		end
	elseif n == 3 then
		hudSet(nil)
		self.destruct()
	elseif n == 4 then
		explainTerrain(pc)
	end
	return true
end

function onDestroy()
	hudSet(nil)
end

function onLoad(ls)
	self.setName(
	"Hover over and press these buttons:\n" ..
	"- 1 to select a target\n" ..
	"- 2 to unlock or lock to base\n" ..
	"- 3 to finish\n" ..
	"- 4 to explain terrain"
	)
	self.max_typed_number=9
	self.clearButtons()
	local rango = {['function_owner'] = self, ['click_function'] = 'gg', ['label'] = "0''", ['position'] = {0, 0.5, 0}, ['rotation'] =  {0,0,0}, ['width'] = 5, ['height'] = 5, ['font_size'] = 150, ['font_color'] = {1,1,1}}
	self.createButton(rango)
	self.setVectorLines(nil)
	self.setTags({"KTUI_ToolActive"})
	posicionLock()
end

function refrescaTextoRango()
	local target = baseEllipse(ObjMiniTarget)
	local lhip, cat3
	if lockEnabled then
		lhip = ovalGap(baseEllipse(objModel), target)
		cat3 = objModel.getPosition().y - objModel.getBounds().offset.y
			- ObjMiniTarget.getPosition().y - ObjMiniTarget.getBounds().offset.y
	else
		local sp = self.getPosition()
		lhip = pointGap(sp.x, sp.z, target)
		cat3 = ObjMiniTarget.getPosition().y - ObjMiniTarget.getBounds().offset.y
			- sp.y - self.getBounds().offset.y
	end
	local hip = math.ceil(math.sqrt((lhip * lhip) + (cat3 * cat3)))
	self.editButton({index=0, label=hip.."''"})
end

function onObjectPickUp(selfpc, targetObj)
	if estado_cono == 1 then
		ObjMiniTarget = targetObj
		activeColor = selfpc
		estado_cono = 2
		markerCache = nil
		posicionLock(true)
	end
end
