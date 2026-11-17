-- KTUI targeting cone ("Targeting lines" context item on KTUI minis).
-- Derived from "KTMT Target Cone" (KT24 Table / KTMT by xSpaghettyx & Ixidior),
-- which treated every base as a circle of diameter base.x. This version models
-- each base as the oval KTUI draws: base.x wide, base.z long along the model's
-- facing (transform forward, plus kt_front on command-node models). The lines
-- run to the two outermost points of the target base as seen from the origin
-- (the tangents), the cone stays on the origin's base edge, and the range is
-- measured base edge to base edge. Line colour shows the target's cover (orange
-- light, red heavy) and a purple arc + label marks it obscured.

pickedUp = false
clickPlayerColor = ""
newX = 0
newZ = 0
posY = 0
colorLinea = Color(1,1,1)
state = nil
baseModel = nil
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

-- Parameter of the point on the oval closest to (px, pz): coarse scan, then a
-- shrinking pattern search so the ceil()'d range isn't nudged up by sampling.
local function closestT(e, px, pz, t0, span)
	local function dist2(t)
		local x, z = pointAt(e, t)
		return (x - px) ^ 2 + (z - pz) ^ 2
	end
	local best, bestD
	if t0 then
		best, bestD = t0, dist2(t0)
	else
		for i = 0, SAMPLES - 1 do
			local t = i * 2 * math.pi / SAMPLES
			local dd = dist2(t)
			if not bestD or dd < bestD then best, bestD = t, dd end
		end
		span = 2 * math.pi / SAMPLES
	end
	for _ = 1, 30 do
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
	for _ = 1, 12 do
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
-- only reports where it enters a collider). Operatives, tokens and tools are
-- ignored. Per stretch (so one piece can do both):
--   light/heavy within 1" of the target  -> light/heavy cover (heavy wins),
--                                            none if the bases are within 2"
--   heavy more than 1" from BOTH bases    -> obscured
-- Terrain type comes from the name or description ("Light Rubble",
-- "Capillary Tower (Heavy)"); untyped terrain is treated as heavy.
local FAN_RAYS = 9
local RAY_LIFT = 0.25
local STRETCH_SAMPLES = 8
local CONTROL_RANGE = 1
local COVER_DENIED_WITHIN = 2
local COL_LIGHT = { 1, 0.55, 0 }
local COL_HEAVY = { 0.95, 0.1, 0.1 }
local COL_OBSCURED = { 0.7, 0.3, 1 }
local IGNORE_TYPES = { Scripting = true, Surface = true, Hand = true, Card = true, Deck = true, Dice = true }
local IGNORE_TAGS = { "KTUIMini", "KTUI_ToolActive", "KT24Token", "KT_Objective" }

coverState = nil      -- nil | "light" | "heavy"
obscuredState = false

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

local function isIgnored(obj)
	if obj == nil or obj == self or obj == objModel or obj == ObjMiniTarget then return true end
	if IGNORE_TYPES[obj.type] then return true end
	for _, tag in ipairs(IGNORE_TAGS) do
		if obj.hasTag(tag) then return true end
	end
	for _, tag in ipairs(obj.getTags() or {}) do
		if tostring(tag):find("KTUIToken", 1, true) == 1 then return true end
	end
	return false
end

local function terrainKind(obj)
	local text = (tostring(obj.getName() or "") .. " " .. tostring(obj.getDescription() or "")):lower()
	if text:find("heavy", 1, true) then return "heavy" end
	if text:find("light", 1, true) then return "light" end
	return "heavy"
end

local function baseBottom(obj)
	local b = obj.getBounds()
	return b.center.y - b.size.y * 0.5
end

-- Stretches of one ray inside each terrain piece: { [guid] = {obj=, sIn=, sOut=} }
-- with s measured along the ray from `a` (0..len).
local function rayStretches(a, b)
	local d = { x = b.x - a.x, y = b.y - a.y, z = b.z - a.z }
	local len = math.sqrt(d.x * d.x + d.y * d.y + d.z * d.z)
	local pieces = {}
	if len < 1e-6 then return pieces, len, d end
	local u = { x = d.x / len, y = d.y / len, z = d.z / len }
	local function record(hits)
		for _, hit in ipairs(hits or {}) do
			local obj = hit.hit_object
			if not isIgnored(obj) and hit.point then
				local p = hit.point
				local s = (p.x - a.x) * u.x + (p.y - a.y) * u.y + (p.z - a.z) * u.z
				s = math.max(0, math.min(len, s))
				local key = obj.getGUID and obj.getGUID() or tostring(obj)
				local piece = pieces[key]
				if piece then
					piece.sIn, piece.sOut = math.min(piece.sIn, s), math.max(piece.sOut, s)
				else
					pieces[key] = { obj = obj, sIn = s, sOut = s }
				end
			end
		end
	end
	record(Physics.cast({ origin = a, direction = d, type = 1, max_distance = len }))
	record(Physics.cast({ origin = b, direction = { x = -d.x, y = -d.y, z = -d.z }, type = 1, max_distance = len }))
	return pieces, len, d
end

-- Sets coverState / obscuredState for the current shooter (objModel, sight
-- lines from the cone at `sp`) and target.
function analyseTerrain(target, sp)
	coverState, obscuredState = nil, false
	local shooter = baseEllipse(objModel)
	local fullTarget = baseEllipse(ObjMiniTarget)
	local coverAllowed = ovalGap(shooter, fullTarget) > COVER_DENIED_WITHIN
	local a = { x = sp.x, y = baseBottom(objModel) + RAY_LIFT, z = sp.z }
	local ty = baseBottom(ObjMiniTarget) + RAY_LIFT
	local light, heavy = false, false
	for _, p in ipairs(facingPoints(target, sp.x, sp.z)) do
		local pieces, len, d = rayStretches(a, { x = p[1], y = ty, z = p[2] })
		for _, piece in pairs(pieces) do
			local kind = terrainKind(piece.obj)
			local nearTarget, farFromBoth = false, false
			for i = 0, STRETCH_SAMPLES do
				local s = piece.sIn + (piece.sOut - piece.sIn) * i / STRETCH_SAMPLES
				local x, z = a.x + d.x * s / len, a.z + d.z * s / len
				local toTarget = pointGap(x, z, fullTarget)
				if toTarget <= CONTROL_RANGE then nearTarget = true end
				if toTarget > CONTROL_RANGE and pointGap(x, z, shooter) > CONTROL_RANGE then farFromBoth = true end
			end
			if nearTarget and coverAllowed then
				if kind == "heavy" then heavy = true else light = true end
			end
			if farFromBoth and kind == "heavy" then obscuredState = true end
		end
	end
	coverState = heavy and "heavy" or (light and "light" or nil)
end

function onPickUp(cp)
	clickPlayerColor = cp
	pickedUp = true
	startLuaCoroutine(self, "movModel")
end

function movModel()
	objModel = getObjectFromGUID(GUIDModel)
	posY = objModel.getPosition().y + 0.5
	state = objModel.getTable("state")
	baseModel = state.base.x
	while (pickedUp == true) do
		posicionLock()
		coroutine.yield(0)
	end
	return 1
end

function posicionLock()
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
	refrescaVectores()
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

function refrescaVectores()
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

	analyseTerrain(target, sp)
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
	refrescaTextoRango()
end

function onNumberTyped( pc, n )
	if n == 9 then
		lockEnabled = not lockEnabled
		if lockEnabled then
			broadcastToColor("Targeting Tool locked to base", pc, {1,1,1})
		else
			broadcastToColor("Targeting Tool unlocked", pc, {1,1,1})
		end
	elseif n == 0 then
		self.destruct()
	end
end

function onLoad(ls)
	self.setName(
	"Hover over and press these buttons:\n" ..
	"- R to select a target\n" ..
	"- 9 to unlock or lock to base\n" ..
	"- 0 to finish"
	)
	self.max_typed_number=9
	self.clearButtons()
	local rango = {['function_owner'] = self, ['click_function'] = 'gg', ['label'] = "0''", ['position'] = {0, 0.5, 0}, ['rotation'] =  {0,0,0}, ['width'] = 5, ['height'] = 5, ['font_size'] = 150, ['font_color'] = {1,1,1}}
	self.createButton(rango)
	pickedUp = true
	startLuaCoroutine(self, "movModel")
	pickedUp = false
	self.setVectorLines(nil)
	self.setTags({"KTUI_ToolActive"})
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
	local status = ""
	if coverState == "heavy" then status = "\nHeavy cover" elseif coverState == "light" then status = "\nLight cover" end
	if obscuredState then status = status .. "\nObscured" end
	self.editButton({index=0, label=hip.."''"..status})
end

function tryRandomize(pc)
	estado_cono = 1
	broadcastToColor("Select Target", pc, {r=1, g=1, b=1})
	return false
end

function onObjectPickUp(selfpc, targetObj)
	if estado_cono == 1 then
		ObjMiniTarget = targetObj
		estado_cono = 2
		refrescaVectores()
	end
end
