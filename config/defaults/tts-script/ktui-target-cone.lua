-- KTUI targeting cone ("Targeting lines" context item on KTUI minis).
-- Derived from "KTMT Target Cone" (KT24 Table / KTMT by xSpaghettyx & Ixidior),
-- which treated every base as a circle of diameter base.x. This version models
-- each base as the oval KTUI draws: base.x wide, base.z long along the model's
-- facing (transform forward, plus kt_front on command-node models). The lines
-- run to the two outermost points of the target base as seen from the origin
-- (the tangents), the cone stays on the origin's base edge, and the range is
-- measured base edge to base edge. Line colour shows the target's cover (orange
-- light, red heavy), a purple arc marks it obscured, and the state is shown in
-- the top-centre HUD.

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
-- only reports where it enters a collider). Operatives, tokens and tools are
-- ignored. Per stretch (so one piece can do both):
--   light/heavy within 1" of the target  -> light/heavy cover (heavy wins),
--                                            none if the bases are within 2"
--   heavy more than 1" from BOTH bases    -> obscured
-- Terrain type comes from the name or description ("Light Rubble",
-- "Capillary Tower (Heavy)"); untyped terrain is treated as heavy.
local FAN_RAYS = 9
local RAY_LIFT = 0.25
local CONTROL_RANGE = 1
local COVER_DENIED_WITHIN = 2
local ANALYSE_EVERY = 6          -- frames between terrain checks while dragging
local COL_LIGHT = { 1, 0.55, 0 }
local COL_HEAVY = { 0.95, 0.1, 0.1 }
local COL_OBSCURED = { 0.7, 0.3, 1 }
local IGNORE_TYPES = { Scripting = true, Surface = true, Hand = true, Card = true, Deck = true, Dice = true }
local IGNORE_TAGS = { "KTUIMini", "KTUI_ToolActive", "KT24Token", "KT_Objective" }
-- Light terrain whose name doesn't say so (e.g. the Portable Barricade equipment).
local LIGHT_WORDS = { "light", "barricade" }

coverState = nil      -- nil | "light" | "heavy"
obscuredState = false
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
	for _, word in ipairs(LIGHT_WORDS) do
		if text:find(word, 1, true) then return "light" end
	end
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
		if next(pieces) then
			local dx, dz = d.x / len, d.z / len
			-- Within 1" of the target from nearTarget on; more than 1" from the
			-- shooter from leaveShooter on.
			local tIn = rayThroughZone(fullTarget, a.x, a.z, dx, dz, CONTROL_RANGE)
			local _, sOut = rayThroughZone(shooter, a.x, a.z, dx, dz, CONTROL_RANGE)
			local nearTarget = tIn and math.max(0, tIn) or len
			local leaveShooter = sOut and math.max(0, sOut) or 0
			for _, piece in pairs(pieces) do
				local kind = terrainKind(piece.obj)
				if coverAllowed and piece.sOut >= nearTarget then
					if kind == "heavy" then heavy = true else light = true end
				end
				if kind == "heavy" and math.max(piece.sIn, leaveShooter) < math.min(piece.sOut, nearTarget) then
					obscuredState = true
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
	local text = coverState == "heavy" and "Heavy cover" or (coverState == "light" and "Light cover" or "No cover")
	if obscuredState then text = text .. "  +  Obscured" end
	return text
end

function onPickUp(cp)
	activeColor = cp
	pickedUp = true
	startLuaCoroutine(self, "movModel")
end

function movModel()
	objModel = getObjectFromGUID(GUIDModel)
	posY = objModel.getPosition().y + 0.5
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

	dragFrames = pickedUp and dragFrames + 1 or 0
	if dragFrames % ANALYSE_EVERY == 0 then
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
	"- 3 to finish"
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
	self.editButton({index=0, label=hip.."''"})
end

function onObjectPickUp(selfpc, targetObj)
	if estado_cono == 1 then
		ObjMiniTarget = targetObj
		activeColor = selfpc
		estado_cono = 2
		refrescaVectores()
	end
end
