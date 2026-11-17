-- Movement for this model, picked when its script loads: Sprint/Turn/Leap for
-- MOUNTED operatives (keywords in the saved state.info.categories), Move/Dash
-- for everyone else. Both tools are wrapped in functions (ktMoveTool /
-- ktSprintTool, added by the composer) and only the chosen one is called, so
-- the other never registers menu items or keys. (TTS can't compile text at
-- runtime, so the tools can't be kept as strings and compiled on demand.)
local function ktIsMounted()
	local ok, saved = pcall(function() return JSON.decode(self.script_state or "") end)
	local categories = ok and type(saved) == "table" and type(saved.info) == "table" and saved.info.categories
	for _, keyword in ipairs(type(categories) == "table" and categories or {}) do
		if tostring(keyword):upper() == "MOUNTED" then return true end
	end
	return false
end

if ktIsMounted() then ktSprintTool() else ktMoveTool() end
