state = {}

self.max_typed_number = 99

ranges = {
	triangle = {
		color = Color(0.10, 0.10, 0.09),
		range = 1,
	},
	circle = {
		color = Color(1, 1, 1),
		range = 2,
	},
	square = {
		color = Color(0, 0.36, 0.62),
		range = 3,
	},
	pentagon = {
		color = Color(0.80, 0.08, 0.09),
		range = 6,
	},
}

triangle = '(1")'
circle = '(2")'
square = '(3")'
pentagon = '(6")'

function textColorXml(color, text)
	return string.format('<textcolor color="#%s">%s</textcolor>', color, text)
end

function textColorMd(color, text)
	return string.format("[%s]%s[-]", color, text)
end

secrets = {
	"ktcnid-status-hiddenRole",
}

text_subs = {
	["1&&"] = textColorXml("000000", triangle),
	["2&&"] = textColorXml("ffffff", circle),
	["3&&"] = textColorXml("1E87FF", square),
	["6&&"] = textColorXml("DA1A18", pentagon),
	["%(R%)"] = textColorXml("1E87FF", "R"),
	["%(M%)"] = textColorXml("F4641D", "M"),
}

md_subs = {
	["1&&"] = textColorMd("000000", triangle),
	["2&&"] = textColorMd("ffffff", circle),
	["3&&"] = textColorMd("1E87FF", square),
	["6&&"] = textColorMd("DA1A18", pentagon),
	["%(R%)"] = textColorMd("1E87FF", "R"),
	["%(M%)"] = textColorMd("F4641D", "M"),
}

function subsymbol(s, tbl)
	local st = s
	for o, sub in pairs(tbl) do
		st = string.gsub(st, o, sub)
	end
	return st
end

function xt(tag, attributes, children, value)
	return {
		tag = tag,
		attributes = attributes,
		children = children,
		value = value,
	}
end

function secretVisibility()
	local p = getOwningPlayer()
	if p == nil then
		return ""
	end
	return table.concat({ "Jokers", p.color }, "|")
end

function hideSecrets()
	local sv = secretVisibility()
	for i, v in ipairs(secrets) do
		self.UI.setAttribute(v, "visibility", sv)
	end
end

modelMeasureLineRadius = 0.05
base = {}
baseLineRadius = 0.0125
baseLineHeight = 0.2

rangeShown = false
measureColor = nil
measureRange = 0

function onNumberTyped(pc, n)
	rangeShown = n > 0
	measureColor = Color.fromString(pc)
	measureRange = n
	refreshVectors()
	Player[pc].broadcast(string.format('%d"', measureRange))
end

function saveState()
	self.script_state = JSON.encode(state)
end

function loadState()
	state = JSON.decode(self.script_state)
end

function savePosition(p, r)
	local savePos = {
		position = p or self.getPosition(),
		rotation = r or self.getRotation(),
	}
	state.savePos = savePos
	saveState()
	self.highlightOn(Color(0.19, 0.63, 0.87), 0.5)
end

function loadPosition()
	local sp = state.savePos
	if sp then
		self.setPositionSmooth(sp.position, false, true)
		self.setRotationSmooth(sp.rotation, false, true)
		self.highlightOn(Color(0.87, 0.43, 0.19), 0.5)
	end
end

function refreshWounds()
	local w = state.wounds
	local m = state.stats.Wounds

	local uiwstring = function()
		if w == 0 then
			return textColorXml("DA1A18", "DEAD")
		end
		return string.format("%d/%d", w, m)
	end

	local namewstring = function()
		if w == 0 then
			return "{[DA1A18]DEAD[-]}"
		elseif w < m / 2 then
			return string.format("{[9A1111]*[-]%d/%d[9A1111]*[-]}", w, m)
		end
		return string.format("{%d/%d}", w, m)
	end

	self.UI.setValue("ktcnid-status-wounds", uiwstring())

	local nname = self.getName()
	if string.find(nname, "%b{}") == nil then
		nname = "{} " .. nname
	end

	self.setName(string.gsub(nname, "%b{}", namewstring()))
end

function callback_role(player, value, id)
	player.broadcast(table.concat(state.roles, ", "))
end

function callback_hiddenRole(player, value, id)
	player.broadcast(table.concat(state.hiddenRoles, ", "))
end

function callback_item(player, value, id)
	player.broadcast(table.concat(state.items, ", "))
end

function refreshUI()
	local sc = self.getScale()
	local scaleFactorX = 1 / sc.x
	local scaleFactorY = 1 / sc.y
	local scaleFactorZ = 1 / sc.z

	local circOffset = function(d, a)
		local ra = math.rad(a)
		return string.format("%d %d", math.cos(ra) * d, math.sin(ra) * d)
	end

	local uid = 50

	local sv = secretVisibility()

	self.UI.setXmlTable({
		xt("Defaults", {}, {
			xt("Image", {
				class = "statusDisplay",
				hideAnimation = "Shrink",
				showAnimation = "Grow",
			}),
		}),
		xt("Panel", {
			position = "0 0 -" .. tostring((state.uiHeight or 2) * 100 * scaleFactorZ),
			width = 100,
			height = 100,
			rotation = "0 0 " .. (state.uiAngle or 0),
			scale = string.format("%f %f %f", scaleFactorX, scaleFactorY, scaleFactorZ),
		}, {
			xt("Panel", {
				id = "ktcnid-status-display-ring",
			}, {
				xt("Image", {
					class = "statusDisplay",
					image = "role",
					color = "#F3961C",
					width = 30,
					height = 30,
					offsetXY = circOffset(uid, 90),
					id = "ktcnid-status-role",
					onClick = "callback_role",
					active = next(state.roles) ~= nil,
				}),
				xt("Image", {
					class = "statusDisplay",
					image = "role",
					color = "#2C20CA",
					width = 30,
					height = 30,
					offsetXY = circOffset(uid, 45),
					id = "ktcnid-status-hiddenRole",
					onClick = "callback_hiddenRole",
					active = next(state.hiddenRoles) ~= nil,
					visibility = sv,
				}),
				xt("Image", {
					class = "statusDisplay",
					image = "item",
					color = "#F3961C",
					width = 30,
					height = 30,
					offsetXY = circOffset(uid, 135),
					id = "ktcnid-status-holding",
					active = state.holding,
				}),
			}),
			xt("Image", {
				class = "statusDisplay",
				image = "engage",
				width = 75,
				height = 75,
				color = "#FF5500",
				active = false,
				id = "ktcnid-status-order",
			}),
			xt("Panel", {
				color = "#808080",
				outline = "#FF5500",
				outlineSize = "2 2",
				width = 50,
				height = 25,
				offsetXY = circOffset(40, 270),
			}, {
				xt("Image", {
					image = "wound",
					class = "statusDisplay",
					color = "#921110",
					width = 30,
					height = 30,
					rectAlignment = "MiddleLeft",
					offsetXY = "-35 0",
					id = "ktcnid-status-injured",
					active = state.stats.Wounds and state.wounds < state.stats.Wounds / 2 or false,
				}),
				xt("Image", {
					image = "item",
					class = "statusDisplay",
					color = "#713B17",
					width = 30,
					height = 30,
					rectAlignment = "MiddleRight",
					offsetXY = "35 0",
					id = "ktcnid-status-item",
					active = next(state.items) ~= nil,
					onClick = "callback_item",
				}),
				xt("Text", {
					text = string.format("%d/%d", state.wounds or 0, state.stats.Wounds or 0),
					resizeTextForBestFit = true,
					color = "#ffffff",
					id = "ktcnid-status-wounds",
				}),
			}),
		}),
	})
end

function createUI()
	self.UI.setCustomAssets({
		-- {name="conceal", url=[=[https://steamusercontent-a.akamaihd.net/ugc/1613967569139373439/322556886BB52F6618257B7670C16DFCF234491C/]=]},
		-- {name="engage",  url=[=[https://steamusercontent-a.akamaihd.net/ugc/1613967569139373385/10EBAC6E2A9A0226C23790B4D6C3FAF0222CFBD2/]=]},
		-- {name="item",    url=[=[https://steamusercontent-a.akamaihd.net/ugc/1613967569139373338/32A408D41A6CF96B31F8E41032664CAD756665A4/]=]},
		-- {name="role",    url=[=[https://steamusercontent-a.akamaihd.net/ugc/1613967569139373274/67450F5CD734514E71F9A6B0C61E52D0A0D48358/]=]},
		{
			name = "wound",
			url = [=[https://steamusercontent-a.akamaihd.net/ugc/1613967569139373232/CA1024D61CAE8AA810E3D70D58BE0823D6F63FCF/]=],
		},
		-- {name="dead",    url=[=[https://steamusercontent-a.akamaihd.net/ugc/1613967569139373167/775C3F30A3EB854CB0FC7B5454EAFDA59A701E9F/]=]},
		-- {name="roster",  url=[=[https://steamusercontent-a.akamaihd.net/ugc/1613967569139450440/D4CAF07C20088B4611666FAEFD5C3E22DEB9FF78/]=]}
	})

	refreshUI()
end

function isInjured()
	return state.stats.Wounds and (state.wounds < state.stats.Wounds / 2) or false
end

function notify(pc, message)
	local owner = getOwningPlayer()
	if pc == owner.color then
		owner.broadcast(message)
	else
		owner.broadcast(string.format("%s: %s", Player[pc].name, message))
		Player[pc].broadcast(message)
	end
end

function damage(pc)
	local si = isInjured()
	state.wounds = math.max(0, (state.wounds or 0) - 1)
	if not si and isInjured() then
		self.UI.show("ktcnid-status-injured")
	end
	saveState()
	refreshWounds()
	notify(pc, string.format("%s took damage", self.getName()))
end

function heal(pc)
	local si = isInjured()
	state.wounds = math.min((state.stats.Wounds or 0), (state.wounds or 0) + 1)
	if si and not isInjured() then
		self.UI.hide("ktcnid-status-injured")
	end
	saveState()
	refreshWounds()
	notify(pc, string.format("%s recovered", self.getName()))
end

function kill(pc)
	state.wounds = 0
	saveState()
	refreshWounds()
	notify(pc, string.format("%s KO", self.getName()))
end

function updateStats(pc)
	local op = getOwningPlayer()
	if op and op.color ~= pc then
		notify(pc, "Only the model's owner can update stats")
		return
	end
	notify(pc, "Updating stats from values in description")
	local statsub = {}
	local prevW = state.stats.Wounds or 0
	local wounds = state.wounds or 0
	local desc = self.getDescription() or ""
	local innerUpdate = function(stat)
		local statNames = {
			["WOUNDS"] = "Wounds",
			["APL"] = "APL",
			["MOVE"] = "Move",
			["SAVE"] = "Save",
		}
		local innerStat = statNames[stat]
		local sstring = "%[84E680%]" .. stat .. "%[%-%]%s*%[ffffff%]%s*(%d+).*%[%-%]"
		for match in string.gmatch(desc, "%b[]") do
			local s = match:match(sstring)
			if s then
				local ss = state.stats[innerStat]
				table.insert(statsub, string.format("%s = %s", stat, s))
				if ss and ss == tonumber(s) then
					return false
				end
				state.stats[innerStat] = tonumber(s)

				-- notify(pc, string.format("%s set to %s", stat, s))
				return true
			end
		end
		table.insert(statsub, string.format("%s = [ff0000]X[-]", stat))
		return false
	end
	innerUpdate("APL")
	innerUpdate("MOVE")
	innerUpdate("SAVE")
	if innerUpdate("WOUNDS") then
		if wounds == prevW then
			state.wounds = state.stats.Wounds or 0
		else
			state.wounds = min(state.stats.Wounds or 0)
		end
		refreshWounds()
	end
	saveState()
	notify(pc, table.concat(statsub, ", "))
end

function onLoad(ls)
	loadState()

	self.addContextMenuItem("Take damage", damage, true)
	self.addContextMenuItem("Restore wounds", heal, true)
	self.addContextMenuItem("Kill", kill)
	self.addContextMenuItem("Save place", function(pc)
		savePosition()
	end)
	self.addContextMenuItem("Load place", function(pc)
		loadPosition()
	end)
	self.addContextMenuItem("Update stats", updateStats)

	local taglist = { state.modelid, "Operative" }
	for _, category in pairs(state.info.categories) do
		table.insert(taglist, category)
	end
	self.setTags(taglist)
	createUI()

	refreshVectors()
end

function onPickUp(pc)
	if rangeShown then
		refreshVectors(true)
	end
end

function tryRandomize(pc)
	rangeShown = not rangeShown
	measureColor = nil
	measureRange = 0
	refreshVectors()

	return false
end

function getOwningPlayer()
	for _, player in ipairs(Player.getPlayers()) do
		if player.steam_id == state.owner then
			return player
		end
	end
	return nil
end

function onPlayerChangeColor(color)
	if color ~= "Grey" then
		local p = Player[color]
		if p.steam_id == state.owner then
			refreshVectors()
			hideSecrets()
		end
	end
end

function refreshVectors(norotate)
	local op = getOwningPlayer()
	local circ = {}
	local scaleFactor = 1 / self.getScale().x

	local rotation = self.getRotation()

	local newLines = {
		{
			points = getCircleVectorPoints(0 - baseLineRadius, baseLineHeight),
			color = op and Color.fromString(op.color) or { 0.5, 0.5, 0.5 },
			thickness = baseLineRadius * 2 * scaleFactor,
		},
	}

	if rangeShown then
		if measureRange > 0 then
			table.insert(newLines, {
				points = getCircleVectorPoints(measureRange - modelMeasureLineRadius + 0.05, 0.125),
				color = measureColor,
				thickness = modelMeasureLineRadius * 2 * scaleFactor,
				rotation = (norotate and { 0, 0, 0 } or { -rotation.x, 0, -rotation.z }),
			})
		else
			for _, r in pairs(ranges) do
				local range = r.range
				table.insert(newLines, {
					points = getCircleVectorPoints(range - modelMeasureLineRadius + 0.05, 0.125),
					color = r.color,
					thickness = modelMeasureLineRadius * 2 * scaleFactor,
					rotation = (norotate and { 0, 0, 0 } or { -rotation.x, 0, -rotation.z }),
				})
			end
		end
	end

	self.setVectorLines(newLines)
end

function getCircleVectorPoints(radius, height, segments)
	local bounds = self.getBoundsNormalized()
	local result = {}
	local scaleFactorX = 1 / self.getScale().x
	local scaleFactorY = 1 / self.getScale().y
	local scaleFactorZ = 1 / self.getScale().z
	local steps = segments or 64
	local degrees, sin, cos, toRads = 360 / steps, math.sin, math.cos, math.rad
	local modelBase = state.base or { x = 25, z = 25 }

	local mtoi = 0.0393701
	local baseX = (tonumber(modelBase.x) or 25) * 0.5 * mtoi
	local baseZ = (tonumber(modelBase.z) or 25) * 0.5 * mtoi

	for i = 0, steps do
		table.insert(result, {
			x = cos(toRads(degrees * i)) * (radius + baseX) * scaleFactorX,
			z = sin(toRads(degrees * i)) * (radius + baseZ) * scaleFactorZ,
			y = height * scaleFactorY,
		})
	end

	return result
end

function doAutoSize()
	local nx = state.base.x
	local nz = state.base.z
	local bounds = self.getBoundsNormalized()
	if bounds.size.x == 0 or bounds.size.y == 0 then
		local r = self.getRotation()
		self.setRotation(Vector(0, 0, 0))
		bounds = self.getBounds()
		self.setRotation(r)
	end
	local scale = self.getScale()
	local xi = nx / 25.4
	local zi = nz / 25.4
	local xs = (xi / bounds.size.x) * scale.x
	local zs = (zi / bounds.size.z) * scale.z

	self.setScale(Vector(xs, (xs + zs) / 2, zs))
	refreshVectors()
end

function setBaseSize(x, z)
	state.base = { x = x, z = z }
	-- state.uiHeight=((x + z)/25)
	saveState()
	refreshVectors()
	refreshUI()
end

function addRole(role, hidden)
	local rg = hidden and state.hiddenRoles or state.roles
	local empty = next(rg) == nil
	table.insert(rg, role)
	if empty then
		self.UI.show(hidden and "ktcnid-status-hiddenRole" or "ktcnid-status-role")
	end
	saveState()
end

function removeRole(role)
	local rri = function(rg, id)
		local nr = {}
		for i, v in ipairs(rg) do
			if v ~= role then
				table.insert(nr, v)
			end
		end
		rg = nr
		if next(rg) == nil then
			self.UI.hide(id)
		end
	end
	rri(state.roles, "ktcnid-status-role")
	rri(state.hiddenRoles, "ktcnid-status-hiddenRole")
end

function revealRole(role)
	removeRole(role)
	addRole(role, false)
end

function comCheckOwner(t)
	return t[1] == state.owner
end

function comBaseSize()
	return state.base
end

function comSetBase(t)
	setBaseSize(t.x, t.z)
end

function comAutoSize()
	doAutoSize()
	refreshUI()
end

function comSavePosition(t)
	savePosition(t.position, t.rotation)
end

function comLoadPosition()
	loadPosition()
end

function comAddRole(t)
	addRole(t.role, t.hidden)
end

function comRemoveRole(t)
	removeRole(t.role)
end

function comRevealRole(t)
	revealRole(t.role)
end

function comSetUIAngle(t)
	state.uiAngle = t.uiAngle
	saveState()
	refreshUI()
end
