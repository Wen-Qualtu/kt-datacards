-- KT model-side extension (appended AFTER the healed KTUI extender script).
-- This is OUR code that rides on top of the real extender model script, composed
-- into the single KTUI_MODELSCRIPT our cards stamp onto a model.
--
-- Append-safety relies on the composer healing getWoundPanelWidth first.
-- Slot for future model-side hooks (move/sprint/callout). When adding code, chain
-- onLoad: `local prev = onLoad; function onLoad(...) if prev then pcall(prev, ...) end ... end`.

-- START KT_EXTENSION_V1 --
local extenderGetUIPosition = getUIPosition

function getUIPosition()
	local position = extenderGetUIPosition()
	if not state.kt_node_ui or not position then return position end
	local horizontal, vertical, depth = position:match("^(%S+)%s+(%S+)%s+(%S+)$")
	horizontal, vertical = tonumber(horizontal), tonumber(vertical)
	local scale = self.getScale()
	local angle = math.rad(state.uiAngle or 0)
	local worldHorizontal = horizontal * scale.x
	local worldVertical = vertical * scale.z
	return string.format("%.6f %.6f %s",
		(worldHorizontal * math.cos(angle) - worldVertical * math.sin(angle)) / scale.x,
		(worldHorizontal * math.sin(angle) + worldVertical * math.cos(angle)) / scale.z,
		depth)
end
-- END KT_EXTENSION_V1 --
